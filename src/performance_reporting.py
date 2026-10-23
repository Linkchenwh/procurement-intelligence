"""Audited practice-data outputs; descriptive findings and scoring hypotheses stay distinct."""
import hashlib
import json
import math
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from src.data_cleaning import clean_performance
from src.export_utils import csv_bytes
from src.scoring_model import sensitivity
from src.spend_analysis import spend_summary, sql_summary, spend_breakdown, monthly_spend
from src.supplier_analysis import supplier_metrics

SCENARIOS = {"均衡": {"delivery_days": .5, "compliance_rate": .5},
             "周期优先": {"delivery_days": .8, "compliance_rate": .2},
             "合规优先": {"delivery_days": .2, "compliance_rate": .8}}
ASSUMPTION = "同品类服务条件可比的假设，未经SKU/规格/合同验证；不作为正式供应商优劣排名"


def source_check(path, raw, root):
    content = path.read_bytes()
    expected_preview = [("PO-00001", "Alpha_Inc", "1176", "17.81"),
                        ("PO-00002", "Delta_Logistics", "1509", "37.34"),
                        ("PO-00003", "Gamma_Co", "910", "92.26")]
    observed = list(raw[["PO_ID", "Supplier", "Quantity", "Negotiated_Price"]].head(3).itertuples(index=False, name=None))
    checks = []
    for archive in sorted((root / "data/raw/kaggle").glob("*.zip")):
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.namelist():
                if member.lower().endswith(".csv"):
                    checks.append({"archive": str(archive.relative_to(root)), "member": member,
                                   "identical_to_input": zipped.read(member) == content,
                                   "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
    return {"source_url": "https://www.kaggle.com/datasets/shahriarkabir/procurement-kpi-analysis-dataset",
            "publisher": "Shahriar Kabir", "filename": str(path.relative_to(root)).replace("\\", "/"),
            "bytes": len(content), "rows": len(raw), "columns": list(raw),
            "sha256": hashlib.sha256(content).hexdigest(),
            "verified_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "acquisition": "user supplied Kaggle download; exact download timestamp not independently recorded",
            "matches_previous_page_preview": observed == expected_preview,
            "matches_previous_preview_shape": raw.shape == (777, 11),
            "zip_member_checks": checks, "license": "CC0 displayed on original page, verified earlier in this conversation",
            "authenticity": "public procurement practice data; author's anonymized-enterprise claim not independently verified",
            "boundary": "Local ZIP equality and preview agreement are not an independent remote cryptographic attestation."}


def analyze_performance(path, root):
    raw = pd.read_csv(path, dtype="string")
    data, audit = clean_performance(raw)
    summary = spend_summary(data)
    sql = sql_summary(data)
    for key in sql:
        if not math.isclose(summary[key], sql[key], rel_tol=1e-12, abs_tol=.01):
            raise AssertionError(f"Performance SQL/Python mismatch: {key}")
    metrics = pd.concat([supplier_metrics(data, c) for c in sorted(data.Item_Category.unique())], ignore_index=True)
    overall = supplier_metrics(data)
    with duckdb.connect() as con:
        con.register("orders", data)
        assert con.execute((root / "sql/01_data_audit.sql").read_text()).fetchdf().empty
        assert con.execute((root / "sql/04_data_validation.sql").read_text()).fetchdf().empty
        sql_metrics = con.execute((root / "sql/03_supplier_analysis.sql").read_text()).fetchdf()
    columns = list(sql_metrics)
    keys = ["Item_Category", "Supplier"]
    expected = metrics[columns].sort_values(keys).reset_index(drop=True)
    observed = sql_metrics.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(observed, expected, check_dtype=False, rtol=1e-10, atol=1e-10)
    assert metrics.orders.sum() == summary["valid_order_count"]
    assert math.isclose(metrics.amount.sum(), summary["valid_amount"], abs_tol=.01)
    assert metrics.defect_rate_proxy.isna().all()
    parsed_defect = pd.to_numeric(raw.Defective_Units, errors="coerce")
    flags = {
        "delivered_missing_date": data.Order_Status.eq("Delivered") & data.Delivery_Date.isna(),
        "delivery_before_order": data.Delivery_Date.lt(data.Order_Date),
        "non_delivered_with_date": ~data.Order_Status.eq("Delivered") & data.Delivery_Date.notna(),
        "non_delivered_with_defect_record": ~data.Order_Status.eq("Delivered") & parsed_defect.notna(),
    }
    issues = raw.copy()
    issues.insert(0, "source_record", range(2, len(raw) + 2))
    issues["issue_codes"] = [";".join(name for name, mask in flags.items() if mask.iloc[i]) for i in range(len(raw))]
    issues = issues.loc[issues.issue_codes.ne("")]
    audit.update({"exact_duplicate_rows": int(raw.duplicated().sum()), "duplicate_po_ids": int(raw.PO_ID.duplicated().sum()),
                  "missing_by_column": raw.isna().sum().astype(int).to_dict(),
                  "status_counts": raw.Order_Status.value_counts().to_dict(),
                  "order_date_min": str(data.Order_Date.min().date()), "order_date_max": str(data.Order_Date.max().date()),
                  "delivery_date_min": str(data.Delivery_Date.min().date()), "delivery_date_max": str(data.Delivery_Date.max().date()),
                  "delivered_orders": int(data.delivered_order.sum()), "valid_delivery_samples": int(data.delivery_days.notna().sum()),
                  "delivered_quality_samples": int(data.observed_defective_units.notna().sum()),
                  "non_delivered_with_defect_record": int(flags["non_delivered_with_defect_record"].sum()),
                  "flagged_records": len(issues), "currency": "unknown", "dataset_snapshot_cutoff": "unknown",
                  "note": "原始行不删除；未交付日期不用于周期。缺陷数量观测仅限Delivered，不确认收货分母。"})
    hypotheses = pd.concat([sensitivity(g, SCENARIOS, min_samples=5).assign(
        comparability_assumption=ASSUMPTION, minimum_samples=5, quality_weight=0, cost_weight=0)
        for _, g in metrics.groupby("Item_Category")], ignore_index=True)
    hypotheses["delivery_weight"] = hypotheses.scenario.map(lambda name: SCENARIOS[name]["delivery_days"])
    hypotheses["compliance_weight"] = hypotheses.scenario.map(lambda name: SCENARIOS[name]["compliance_rate"])
    stability_rows = []
    for category, group in hypotheses.groupby("Item_Category"):
        winners = {name: ", ".join(sorted(g.loc[g["rank"].eq(1), "Supplier"])) for name, g in group.groupby("scenario")}
        stability_rows.append({"Item_Category": category, **winners,
                               "winner_changes": len(set(winners.values())) > 1, "comparability_assumption": ASSUMPTION})
    stability = pd.DataFrame(stability_rows)
    source = source_check(path, raw, root)
    folder = root / "outputs/tables"
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in [("performance_summary", summary), ("performance_audit", audit), ("performance_source_check", source)]:
        (folder / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tables = {"performance_supplier": spend_breakdown(data, "Supplier"), "performance_category": spend_breakdown(data, "Item_Category"),
              "performance_monthly": monthly_spend(data), "performance_supplier_metrics": metrics,
              "performance_supplier_overall": overall, "performance_record_issues": issues,
              "performance_scoring_hypotheses": hypotheses, "performance_rank_sensitivity": stability,
              "performance_field_audit": pd.DataFrame([{"field": c, "missing": int(raw[c].isna().sum()),
                  "distinct_nonnull": int(raw[c].nunique()), "raw_dtype": str(raw[c].dtype)} for c in raw])}
    for name, table in tables.items():
        table = table.copy()
        table["source_domain"] = "performance_practice"
        (folder / (name + ".csv")).write_bytes(csv_bytes(table))
    (root / "data/processed").mkdir(parents=True, exist_ok=True)
    data.to_parquet(root / "data/processed/performance.parquet", index=False)
    delivery_count = audit["valid_delivery_samples"]
    delivered_count = audit["delivered_orders"]
    supplier_lines = []
    for _, row in overall.iterrows():
        supplier_lines.append(f"| {row.Supplier} | {row.orders} | {row.delivered_orders} | {row.delivery_samples} | {row.delivery_days:.2f} | {row.delivery_coverage:.1%} | {row.compliance_rate:.1%} ({row.compliance_samples}) | {row.quality_samples} |")
    stability_lines = [f"| {row.Item_Category} | {row['均衡']} | {row['周期优先']} | {row['合规优先']} |" for _, row in stability.iterrows()]
    preview_description = "内容与之前核查的指定Kaggle页面预览吻合" if source["matches_previous_page_preview"] and source["matches_previous_preview_shape"] else "尚未确认与指定页面预览一致，需重新核对来源"
    archive_description = "ZIP内CSV与解压文件完全相同" if source["zip_member_checks"] and all(x["identical_to_input"] for x in source["zip_member_checks"]) else "没有完成ZIP成员完全一致确认"
    report = f"""# 供应商绩效分析：Kaggle公开练习数据

## 文件核对

用户下载的`{source['filename']}`为{len(raw)}行、{len(raw.columns)}列，{data.Supplier.nunique()}个供应商标签、{data.Item_Category.nunique()}个品类；PO_ID无重复，{preview_description}，{archive_description}。SHA256：`{source['sha256']}`。文件匹配判断见来源检查JSON，不代表企业来源已独立证实。页面CC0许可已在2026-10-22核查。

订单日期{audit['order_date_min']}至{audit['order_date_max']}，交付日期至{audit['delivery_date_max']}。作者介绍700条和2022–2023，与实际777条及2024-01-01订单不完全一致；以原文件为准。币种、承诺交期、实际收货量、SKU规格与数据快照截止日均未知。

## 金额与记录口径

原始订单额{summary['raw_amount']:,.2f}；排除{int((~data.valid_order).sum())}条取消订单后，{summary['valid_order_count']}条非取消订单额{summary['valid_amount']:,.2f}；取消额{summary['cancelled_amount']:,.2f}；已交付订单额{summary['delivered_amount']:,.2f}。均为未知币种数值，不是付款。名义议价差额{summary['nominal_price_difference']:,.2f}，没有合同基准，不能称为实际节约。

原始状态：{audit['status_counts']}。有{audit['delivered_missing_date']}条Delivered缺交付日期、{audit['negative_delivery_days']}条日期先后异常；{audit['non_delivered_with_date']}条非Delivered却有日期；{audit['non_delivered_with_defect_record']}条非Delivered却有缺陷记录。原始行完整保留，异常明细见`performance_record_issues.csv`，同一记录可有多个问题标记。

## 已观测绩效

交付周期仅用Delivered且日期有效的{delivery_count}/{delivered_count}条（覆盖{delivery_count/delivered_count:.1%}），全体均值{data.delivery_days.mean():.2f}天。质量仅有{audit['delivered_quality_samples']}/{delivered_count}条已交付缺陷数量观测；没有实际收货分母，不发布正式缺陷率、合格率或合格数量。无承诺日期，不发布准时率。

以下跨品类表仅用于描述，不能据此排整体优劣；合规率分母是非取消订单中的已知标签数，非全面法律/合同合规。

| 供应商标签 | 非取消订单 | 已交付订单 | 周期有效样本 | 平均周期/天 | 周期记录覆盖 | 合规标记Yes率（有效样本） | 缺陷数量记录样本 |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(supplier_lines)}

业务建议是优先核实合规No标记的具体定义、缺失交付记录和异常状态；观察周期与合规存在差异，不能证明供应商原因或据此直接淘汰。缺陷数量总和受订单数量、规格和记录覆盖影响，不能用于品牌或供应商质量高低排名。

## 评分敏感性：明确假设案例

仅在“同品类服务条件可比”的假设下演示周期与合规加权，SKU/合同条件并未验证。成本和质量权重均为0，最少有效样本为5，权重分别为50/50、80/20、20/80，三种情景覆盖{len(metrics)}个供应商×品类组，共{len(hypotheses)}行。结果文件每行携带假设，不是正式采购排名。正式工具仍需用户明确确认比较条件。

| 品类 | 均衡权重首位 | 周期优先首位 | 合规优先首位 |
|---|---|---|---|
{chr(10).join(stability_lines)}

{int(stability.winner_changes.sum())}/{len(stability)}个品类在上述权重之间出现首位变化，说明结论依赖业务偏好。min-max只在当前候选集内成立，换候选集会改变分数。下一步需补齐实际SKU、规格、承诺交期、收货数量及合规定义，才能验证可比性。

## 验证路径

`src/performance_reporting.py:analyze_performance`调用独立SQL与pandas计算，核对金额、订单数以及{len(metrics)}个供应商×品类组的周期均值/样本和合规均值/样本；对账不是仅检查输出行数。指标/异常/假设分别导出，原文件不改，三个数据域不关联。
"""
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reports/supplier_performance_report.md").write_text(report, encoding="utf-8")
    return {"raw_rows": len(raw), **summary, "raw_sha256": source["sha256"],
            "supplier_category_groups": len(metrics), "scoring_hypothesis_rows": len(hypotheses),
            "valid_delivery_samples": delivery_count, "delivered_orders": delivered_count,
            "checks": f"SQL/pandas all spend totals and {len(metrics)} supplier-category metrics matched; unknown defect rates remain NULL"}
