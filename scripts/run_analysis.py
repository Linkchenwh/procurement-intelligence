"""Rebuild audited outputs; source data are never modified."""
import argparse
import hashlib
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.data_cleaning import PERFORMANCE_COLUMNS
from src.data_loader import ROOT, performance_path
from src.export_utils import csv_bytes
from src.government import clean_government, government_summary, government_sql_summary, government_breakdown
from src.market_benchmark import normalize_quotes, QUOTE_COLUMNS
from src.scenario_analysis import sourcing_scenario


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_table(name, frame, domain):
    data = frame.copy()
    data["source_domain"] = domain
    if domain == "california_history":
        data["amount_scope"] = "accepted_observation_subset_not_statewide_total"
    (ROOT / "outputs/tables" / (name + ".csv")).write_bytes(csv_bytes(data))


def main(as_of="2026-10-22"):
    for folder in ["outputs/tables", "outputs/logs", "reports", "data/processed", "data/templates", "docs"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    pd.Timestamp(as_of)  # Reject invalid reporting dates before modifying generated outputs.
    run = {"executed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "as_of": as_of, "domains": {}, "checks": []}
    pd.DataFrame(columns=PERFORMANCE_COLUMNS).to_csv(ROOT / "data/templates/performance_input.csv", index=False, encoding="utf-8-sig")
    extra = ["manufacturer", "contract_supplier", "tax_terms", "attributes", "notes"]
    pd.DataFrame(columns=QUOTE_COLUMNS + extra).to_csv(ROOT / "data/templates/market_quotes_input.csv", index=False, encoding="utf-8-sig")
    path = ROOT / "data/raw/california/purchase_orders.csv"
    if path.exists():
        raw = pd.read_csv(path, dtype="string")
        accepted, quarantine, audit = clean_government(raw)
        summary = government_summary(accepted)
        sql = government_sql_summary(accepted)
        for metric in ["amount", "orders", "rows", "supplier_codes"]:
            assert math.isclose(summary[metric], sql[metric], rel_tol=1e-12, abs_tol=.01), metric
        assert len(accepted) + len(quarantine) == len(raw)
        assert math.isclose(audit["source_row_amount_sum_unverified"], audit["accepted_amount"] + audit["quarantined_parsed_amount"], rel_tol=1e-12, abs_tol=.01)
        run["checks"].extend(["government SQL/Python amount/orders/rows/suppliers", "raw=accepted+quarantine row and parsed amount reconciliation"])
        keep = ["source_row", "order_key", "supplier_key", "supplier_label", "purchase_date", "Department Name", "Fiscal Year", "Acquisition Type", "amount", "source_domain"]
        accepted[keep].to_parquet(ROOT / "data/processed/government.parquet", index=False)
        quarantine.to_parquet(ROOT / "data/processed/government_quarantine.parquet", index=False)
        write_json(ROOT / "outputs/tables/government_audit.json", audit)
        write_json(ROOT / "outputs/tables/government_summary.json", summary)
        for label, column in [("supplier", "supplier_key"), ("category", "Acquisition Type"), ("department", "Department Name"), ("fiscal_year", "Fiscal Year")]:
            table = government_breakdown(accepted, column)
            if label == "supplier":
                # Name map is informational, never an additional fact-table join.
                names = accepted.groupby("supplier_key").supplier_label.agg(lambda s: " / ".join(sorted(s.dropna().unique()))[:500])
                table["supplier_label"] = table.supplier_key.map(names)
            write_table("government_" + label, table, "california_history")
        dated = accepted.loc[accepted.purchase_date.notna()].copy()
        dated["month"] = dated.purchase_date.dt.to_period("M").astype(str)
        trend = dated.groupby("month", as_index=False).agg(amount=("amount", "sum"), observed_orders=("order_key", "nunique"))
        write_table("government_monthly", trend, "california_history")
        dict_rows = [{"field": c, "observed_type": "raw string", "missing_count": int(raw[c].isna().sum()),
                      "distinct_nonnull": int(raw[c].nunique())} for c in raw]
        write_table("government_field_audit", pd.DataFrame(dict_rows), "california_history")
        run["domains"]["california_history"] = {"raw_rows": len(raw), **summary, "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        outliers = accepted.nlargest(5, "amount")[["source_row", "supplier_label", "Department Name", "amount"]]
        write_table("government_largest_observations", outliers, "california_history")
        date_amount_coverage = accepted.loc[accepted.purchase_date.notna(), "amount"].sum() / summary["amount"] if summary["amount"] > 0 else 0
        report = f"""# 加州历史采购观测子集分析\n\n本报告来自官方 2012–2015 财年数据，不代表当前采购。源文件有 $ 标记，USD 为美国州政府语境推断。订单行金额不等于付款。\n\n## 审计与口径\n\n- 原始 {len(raw):,} 行、{len(raw.columns)} 列。完全重复超额 {audit['exact_duplicate_excess']:,} 行。\n- 缺少官方行号；对除分类字段以外完全一致的所有候选组整体隔离，共 {audit['ambiguous_rows']:,} 行，不任意保留第一条。\n- 数值异常、负值、数量×单价与行总额差异超过0.02的行另行隔离。总共隔离 {len(quarantine):,} 行，主分析保留 {len(accepted):,} 行，行覆盖率 {audit['accepted_row_coverage']:.2%}。\n- 主分析观测金额 {summary['amount']:,.2f}，涉及 {summary['orders']:,} 个部门+财年+订单号组合和 {summary['supplier_codes']:,} 个已知供应商编码。只代表保留的观测行；部分订单仍可能不完整，不能称为全州实际采购总支出或严格下界。\n- 原始可解析行总额 {audit['source_row_amount_sum_unverified']:,.2f} 未去重，不用于经营结论。\n- 官方 PDF 字典的 Fi$Cal 字段与本 CSV 旧版字段不完全一致；实际字段审计表优先。\n\n## 发现与决策\n\n在该子集内，Top1 供应商编码金额占比 {summary['top1_share']:.2%}，Top5 占比 {summary['top5_share']:.2%}，HHI={summary['hhi']:.2f}。集中度按供应商编码计算，不能用来判定整个市场竞争或信用风险。优先复核金额较大的供应商及异常候选组，再讨论采购策略。不同财年覆盖和异常排除并不相同，不把趋势直接解释为效率提升。\n\n保留记录中 {audit['accepted_missing_purchase_date']:,} 行无有效采购日期，仅从月度趋势排除；不以创建日期冒充采购日期。不同物品数量/单位不汇总为可比采购总量。\n\n复核路径：`scripts/run_analysis.py` → `src/government.py` / `sql/05_government_spend.sql` → `outputs/tables/government_*.csv`。异常完整明细保留在 `data/processed/government_quarantine.parquet`，未删除原始数据。\n\n来源：[California DGS](https://data.ca.gov/dataset/purchase-order-data)。许可：官网 Rights 为 No Restrictions on Public Use。\n"""
        report += f"\n## 日期与未识别供应商补充复核\n\n有效且与所报财年一致的采购日期覆盖保留金额约{date_amount_coverage:.1%}；月度趋势不代表全部保留金额的时间分布。来源有{audit['purchase_date_outside_fiscal_year']:,}条可解析采购日期与财年不一致，不自动修正原文。\n\n来源编码0且名称Unknown的占位记录与空编码共同归入未识别桶，主分析该桶金额{summary['unknown_supplier_amount']:,.2f}，不是一家真实供应商。\n"
        (ROOT / "reports/procurement_report.md").write_text(report, encoding="utf-8")
    path = performance_path()
    if path:
        from src.performance_reporting import analyze_performance
        run["domains"]["performance_practice"] = analyze_performance(path, ROOT)
        run["checks"].append("performance SQL/Python all totals and supplier-category metrics; audit and scoring hypotheses")
    else:
        run["domains"]["performance_practice"] = {"status": "awaiting Kaggle login download; no business results generated"}
    path = ROOT / "data/market/quotes_reviewed.csv"
    if not path.exists():
        path = ROOT / "data/market/quotes.csv"
    if path.exists():
        quotes = normalize_quotes(pd.read_csv(path), as_of=as_of)
        quotes.to_parquet(ROOT / "data/processed/market.parquet", index=False)
        write_table("market_normalized", quotes, "market_quotes")
        scenario = sourcing_scenario(quotes, 100, budget=3000, currency="CNY", region="深圳", as_of=as_of)
        write_table("market_scenario_100_reams", scenario, "market_quotes")
        for _, row in quotes.iterrows():
            evidence_file = ROOT / row.evidence_file
            assert hashlib.sha256(evidence_file.read_bytes()).hexdigest() == row.evidence_sha256
        run["checks"].append("market evidence SHA256 verification for every quotation")
        comparable = quotes.loc[quotes.spec_comparable]
        run["domains"]["market_quotes"] = {"observations": len(quotes), "spec_comparable": len(comparable), "channels": int(quotes.channel.nunique()), "verified_all_in_scenarios": int(scenario.scenario_comparable.sum())}
        report = f"""# A4复印纸公开标价对标\n\n2026-10-22 采集，当前仅一个销售渠道，{len(quotes)} 个商品观察。不是全市场抽样、厂商报价或成交价格。商品链接、时间及证据哈希见 `data/market/quotes.csv`。销售主体来自页面公司介绍；制造商与未来合同供应商保持未知。\n\n基础规格 A4/80g/m²/500张且计价单位明确的观察 {len(comparable)} 条。其公开标价标准化范围 {comparable.price_per_500.min():.2f}–{comparable.price_per_500.max():.2f} CNY/500张。只比较公开标价；不同品牌不代表可替代性或质量已经验证。缺规格商品不填造500张。\n\n税费、MOQ、适用数量区间和目标地区运费尚不完整，100包/预算3000元属于假设需求；货品参考金额是数量×当前观察标价的线性情景，不是有效大宗报价。最终总成本和正式排名保持空缺。商家有数量阶梯价格和地区运费说明，应以目标数量、送达地区、发票和书面报价重新确认。\n\n先进行纸张样品/设备适配测试和供应商资质核查，再索取统一含税到货报价，确认库存、交期、付款、报价有效期与合同主体。最低标价不足以决定采购。缺少第二渠道，不生成渠道差异结论，也不虚构市场份额或品牌质量分。\n\n采集脚本 `scripts/collect_market.py`，标准化 `src/market_benchmark.py`，情景 `src/scenario_analysis.py`。原网页仅本地保存，不默认重新分发。\n"""
        dates = quotes.collected_at.astype(str).str[:10].unique().tolist()
        report = report.replace("2026-10-22 采集", f"报告基准日{as_of}；采集日期{', '.join(dates)}")
        (ROOT / "reports/market_benchmark_report.md").write_text(report, encoding="utf-8")
    write_json(ROOT / "outputs/tables/run_manifest.json", run)
    print(json.dumps(run, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-10-22", help="Reporting date; fixed original snapshot default for reproducibility")
    main(parser.parse_args().as_of)
