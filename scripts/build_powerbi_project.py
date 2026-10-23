"""Extend a Desktop-created PBIP with auditable tables, measures and plain report pages.

Run only with this project closed in Desktop. The seed is backed up once under
outputs/logs. Opening and refreshing the result in Desktop is a separate check.
"""
import csv
import json
import shutil
import uuid

from src.data_loader import ROOT
from scripts.prepare_powerbi import write_project_root

BASE = ROOT / "dashboard/powerbi"
MODEL = BASE / "ProcurementIntelligence.SemanticModel/definition"
REPORT = BASE / "ProcurementIntelligence.Report/definition"
TOP10_TEMPLATE = BASE / "templates/supplier_top10.json"

SCHEMAS = {
    "GovFact": {"row_id": "int", "order_key": "text", "order_id": "int", "supplier_key": "text", "purchase_date": "date", "department": "text", "fiscal_year": "text", "acquisition_type": "text", "amount": "money"},
    "GovSupplier": {"supplier_key": "text", "supplier_label": "text", "name_variants": "int"},
    "GovDepartment": {"department": "text"}, "GovType": {"acquisition_type": "text"},
    "GovDate": {"date": "date", "month": "text", "year": "int"},
    "PerfFact": {"PO_ID": "text", "Supplier": "text", "Order_Date": "date", "Delivery_Date": "date", "Item_Category": "text", "Order_Status": "text", "Quantity": "int", "Unit_Price": "money", "Negotiated_Price": "money", "Defective_Units": "int", "Compliance": "text", "delivery_days": "number", "observed_defective_units": "int", "compliant": "int", "amount": "money", "baseline_amount": "money", "valid_order": "bool", "delivered_order": "bool", "source_domain": "text"},
    "PerfSupplier": {"Supplier": "text"}, "PerfCategory": {"Item_Category": "text"},
}
MARKET_TYPES = {"gsm": "number", "sheets_per_ream": "int", "reams_per_box": "int", "price": "money", "min_order_units": "int", "max_order_units": "int", "shipping_cost": "money", "lead_time_days": "number", "collected_at": "text", "packaging_conflict": "bool", "reams_per_unit": "number", "price_per_500": "money", "spec_comparable": "bool", "quote_age_days": "int", "fresh_observation": "bool", "source_link_present": "bool", "requested_reams": "int", "purchase_units": "int", "supplied_reams": "number", "goods_reference_cost": "money", "total_cost": "money", "budget_difference": "money", "scenario_comparable": "bool", "rank": "number"}
TYPE = {"text": ("type text", "string"), "int": ("Int64.Type", "int64"), "number": ("type number", "double"), "money": ("Currency.Type", "decimal"), "date": ("type date", "dateTime"), "bool": ("type logical", "boolean")}

# All measures refer only to one independent case domain.
MEASURES = {
    "GovFact": {
        "Gov Observed Amount": ("SUM(GovFact[amount])", "#,0.00"),
        "Gov Observed Orders": ("DISTINCTCOUNT(GovFact[order_id])", "#,0"),
        "Gov Observation Rows": ("COUNTROWS(GovFact)", "#,0"),
        "Gov Known Suppliers": ('CALCULATE(DISTINCTCOUNT(GovFact[supplier_key]), GovFact[supplier_key] <> "UNKNOWN")', "#,0"),
        "Gov Top5 Share": ('VAR S = ALLSELECTED(GovSupplier) VAR A = ADDCOLUMNS(S, "SupplierAmount", CALCULATE([Gov Observed Amount])) RETURN DIVIDE(SUMX(TOPN(5,A,[SupplierAmount],DESC,GovSupplier[supplier_key],ASC),[SupplierAmount]),CALCULATE([Gov Observed Amount],S))', "0.0%"),
        "Gov HHI": ('VAR S = ALLSELECTED(GovSupplier) VAR A = CALCULATE([Gov Observed Amount],S) RETURN IF(A>0,SUMX(S,POWER(DIVIDE(CALCULATE([Gov Observed Amount]),A),2))*10000)', "0.00"),
        "Gov Dated Coverage": ("DIVIDE(CALCULATE([Gov Observed Amount],NOT ISBLANK(GovFact[purchase_date])),[Gov Observed Amount])", "0.0%"),
    },
    "PerfFact": {
        "Perf Noncancelled Orders": ("CALCULATE(COUNTROWS(PerfFact),PerfFact[valid_order]=TRUE())", "#,0"),
        "Perf Noncancelled Amount": ("CALCULATE(SUM(PerfFact[amount]),PerfFact[valid_order]=TRUE())", "#,0.00"),
        "Perf Cancelled Amount": ("CALCULATE(SUM(PerfFact[amount]),PerfFact[valid_order]=FALSE())", "#,0.00"),
        "Perf Delivered Amount": ("CALCULATE(SUM(PerfFact[amount]),PerfFact[delivered_order]=TRUE())", "#,0.00"),
        "Perf Nominal Price Difference": ("CALCULATE(SUM(PerfFact[baseline_amount])-SUM(PerfFact[amount]),PerfFact[valid_order]=TRUE())", "#,0.00"),
        "Perf Delivered Orders": ("CALCULATE(COUNTROWS(PerfFact),PerfFact[delivered_order]=TRUE())", "#,0"),
        "Perf Delivery Days": ("CALCULATE(AVERAGE(PerfFact[delivery_days]),PerfFact[valid_order]=TRUE())", "0.00"),
        "Perf Delivery Samples": ("CALCULATE(COUNT(PerfFact[delivery_days]),PerfFact[valid_order]=TRUE())", "#,0"),
        "Perf Delivery Coverage": ("DIVIDE([Perf Delivery Samples],[Perf Delivered Orders])", "0.0%"),
        "Perf Recorded Compliance Rate": ("CALCULATE(AVERAGE(PerfFact[compliant]),PerfFact[valid_order]=TRUE())", "0.0%"),
        "Perf Compliance Samples": ("CALCULATE(COUNT(PerfFact[compliant]),PerfFact[valid_order]=TRUE())", "#,0"),
        "Perf Quality Samples": ("CALCULATE(COUNT(PerfFact[observed_defective_units]),PerfFact[valid_order]=TRUE())", "#,0"),
        "Perf Quality Record Coverage": ("DIVIDE([Perf Quality Samples],[Perf Delivered Orders])", "0.0%"),
        "Perf Observed Defects": ("CALCULATE(SUM(PerfFact[observed_defective_units]),PerfFact[valid_order]=TRUE())", "#,0"),
    },
    "MarketQuotes": {
        "Market Comparable Observations": ("CALCULATE(COUNTROWS(MarketQuotes),MarketQuotes[spec_comparable]=TRUE())", "#,0"),
        "Market Minimum Listed Price SameCurrency": ("IF(HASONEVALUE(MarketQuotes[currency]),CALCULATE(MIN(MarketQuotes[price_per_500]),MarketQuotes[spec_comparable]=TRUE()))", "0.00"),
        "Market Maximum Listed Price SameCurrency": ("IF(HASONEVALUE(MarketQuotes[currency]),CALCULATE(MAX(MarketQuotes[price_per_500]),MarketQuotes[spec_comparable]=TRUE()))", "0.00"),
        "Market Comparable Listed Price": ("IF(HASONEVALUE(MarketQuotes[currency]) && SELECTEDVALUE(MarketQuotes[spec_comparable])=TRUE(),MAX(MarketQuotes[price_per_500]))", "0.00"),
    },
    "MarketScenario": {
        "Market Scenario Known Total": ("IF(COUNT(MarketScenario[total_cost])>0,MIN(MarketScenario[total_cost]))", "#,0.00"),
    },
}


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def m_query(name, columns):
    path = "\\dashboard\\powerbi\\input\\" + name + ".csv"
    types = ", ".join('{"' + c + '", ' + TYPE[t][0] + "}" for c, t in columns.items())
    return (f'let\n    Source = Csv.Document(File.Contents(ProjectRoot & "{path}"), [Delimiter=",", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
            '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n'
            '    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),\n'
            f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")\nin\n    Typed')


def model_table(name, columns):
    lines = [f"table {name}", f"\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, 'procurement/' + name)}", ""]
    for measure, (formula, fmt) in MEASURES.get(name, {}).items():
        lines += [f"\tmeasure '{measure}' = {formula}", f"\t\tformatString: {fmt}", "\t\tdisplayFolder: Audited metrics", ""]
    for column, kind in columns.items():
        lines += [f"\tcolumn {column}", f"\t\tdataType: {TYPE[kind][1]}", f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, 'procurement/' + name + '/' + column)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {column}"]
        if kind in {"money", "number"}:
            lines.append("\t\tformatString: #,0.00")
        elif kind == "int":
            lines.append("\t\tformatString: #,0")
        elif kind == "date":
            lines += ["\t\tformatString: yyyy-MM-dd", "\t\tannotation UnderlyingDateTimeDataType = Date"]
        if column in {"url"}:
            lines.append("\t\tdataCategory: WebUrl")
        if column == "order_id":
            lines.append("\t\tisHidden")
        lines.append("")
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource ="]
    lines += ["\t\t\t\t" + line for line in m_query(name, columns).splitlines()]
    lines += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(lines)


def col(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def measure(table, name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def visual(page, name, kind, box, roles=None, title=None, objects=None):
    config = {"visualType": kind, "drillFilterOtherVisuals": True}
    if roles:
        state = {}
        for role, fields in roles.items():
            projections = []
            for field in fields:
                expression = next(iter(field.values()))
                entity = expression["Expression"]["SourceRef"]["Entity"]
                property_name = expression["Property"]
                projections.append({"field": field, "queryRef": entity + "." + property_name, "nativeQueryRef": property_name})
            state[role] = {"projections": projections}
        config["query"] = {"queryState": state}
    config["visualContainerObjects"] = {"border": [{"properties": {"show": literal("false")}}], "background": [{"properties": {"show": literal("false")}}]}
    if title:
        config["visualContainerObjects"]["title"] = [{"properties": {"show": literal("true"), "text": literal("'" + title.replace("'", "''") + "'"), "fontFamily": literal("'SimSun'"), "fontSize": literal("12D")}}]
    if objects:
        config["objects"] = objects
    x, y, w, h = box
    dump(REPORT / "pages" / page / "visuals" / name / "visual.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "width": w, "height": h, "z": y + x, "tabOrder": y + x}, "visual": config})


def text(page, name, message, y, height=48, size=13):
    visual(page, name, "textbox", (24, y, 1232, height), objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": message, "textStyle": {"fontFamily": "SimSun", "fontSize": f"{size}pt"}}]}]}}]})


def card(page, name, table, metric, title, x, y=105, width=290):
    visual(page, name, "card", (x, y, width, 105), {"Values": [measure(table, metric)]}, title,
           {"labels": [{"properties": {"fontFamily": literal("'Arial'"), "fontSize": literal("24D"), "labelDisplayUnits": literal("0D")}}], "categoryLabels": [{"properties": {"show": literal("false")}}]})


def build():
    if not (BASE / "ProcurementIntelligence.pbip").exists():
        raise FileNotFoundError("Save the Desktop-created seed PBIP first")
    seed = ROOT / "outputs/logs/powerbi_desktop_seed"
    if not seed.exists():
        seed.mkdir(parents=True)
        for name in ["ProcurementIntelligence.pbip", "ProcurementIntelligence.Report", "ProcurementIntelligence.SemanticModel"]:
            source = BASE / name
            if source.is_dir():
                shutil.copytree(source, seed / name, ignore=shutil.ignore_patterns(".pbi"))
            else:
                shutil.copy2(source, seed / name)
    # Archive only Desktop-generated automatic date definitions; keep the seed intact.
    for old in (MODEL / "tables").glob("*DateTable*.tmdl"):
        target = seed / "archived_auto_dates" / old.name
        target.parent.mkdir(exist_ok=True)
        if not old.resolve().is_relative_to(ROOT.resolve()) or not target.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Archive path outside the workspace")
        if target.exists():
            raise FileExistsError(target)
        shutil.move(str(old), str(target))
    for name in ["MarketQuotes", "MarketScenario"]:
        with (BASE / "input" / (name + ".csv")).open(encoding="utf-8-sig", newline="") as f:
            SCHEMAS[name] = {c: MARKET_TYPES.get(c, "text") for c in next(csv.reader(f))}
    for name, columns in SCHEMAS.items():
        with (BASE / "input" / (name + ".csv")).open(encoding="utf-8-sig", newline="") as f:
            assert next(csv.reader(f)) == list(columns), f"Unexpected columns: {name}"
        (MODEL / "tables" / (name + ".tmdl")).write_text(model_table(name, columns), encoding="utf-8")
        q = BASE / "queries" / (name + ".pq")
        q.parent.mkdir(exist_ok=True)
        q.write_text(m_query(name, columns) + "\n", encoding="utf-8")
    write_project_root(BASE, ROOT)
    refs = "\n".join("ref table " + n for n in SCHEMAS)
    (MODEL / "model.tmdl").write_text('model Model\n\tculture: zh-CN\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\tvalueFilterBehavior: independent\n\tdataAccessOptions\n\t\tlegacyRedirects\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\nannotation PBI_QueryOrder = ' + json.dumps(list(SCHEMAS)) + '\n\nannotation PBI_ProTooling = ["DevMode"]\n\n' + refs + '\n\nref expression ProjectRoot\n\nref cultureInfo zh-CN\n', encoding="utf-8")
    relationships = [("GovFact", "supplier_key", "GovSupplier", "supplier_key"), ("GovFact", "department", "GovDepartment", "department"), ("GovFact", "acquisition_type", "GovType", "acquisition_type"), ("GovFact", "purchase_date", "GovDate", "date"), ("PerfFact", "Supplier", "PerfSupplier", "Supplier"), ("PerfFact", "Item_Category", "PerfCategory", "Item_Category")]
    relation_text = []
    for fact, fk, dim, pk in relationships:
        relation_text += [f"relationship {uuid.uuid5(uuid.NAMESPACE_URL, fact + fk + dim + pk)}", "\tcrossFilteringBehavior: oneDirection", f"\tfromColumn: {fact}.{fk}", f"\ttoColumn: {dim}.{pk}", ""]
    (MODEL / "relationships.tmdl").write_text("\n".join(relation_text), encoding="utf-8")
    # Existing Desktop-created automatic date files stay backed up and unreferenced.
    page_names = ["spend_overview", "supplier_performance", "market_sourcing"]
    for old in (REPORT / "pages").iterdir():
        if not old.is_dir() or old.name in page_names:
            continue
        target = seed / "archived_seed_pages" / old.name
        target.parent.mkdir(exist_ok=True)
        if not old.resolve().is_relative_to(ROOT.resolve()) or not target.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Archive path outside the workspace")
        if target.exists():
            raise FileExistsError(target)
        shutil.move(str(old), str(target))
    for page, label in zip(page_names, ["采购支出总览", "供应商绩效", "市场对标与寻源"]):
        dump(REPORT / "pages" / page / "page.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json", "name": page, "displayName": label, "displayOption": "FitToPage", "height": 900, "width": 1280})
    dump(REPORT / "pages/pages.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json", "pageOrder": page_names, "activePageName": page_names[0]})
    p = page_names[0]
    text(p, "spend_heading", "加州历史采购：通过审计的观测子集", 12, 40, 20)
    text(p, "spend_scope", "2012–2015财年；不是全州完整支出或付款。异常与疑似重复已隔离，三个案例之间不建业务关联。", 56)
    for i, (metric, title) in enumerate([("Gov Observed Amount", "保留观测金额（源文件金额）"), ("Gov Observed Orders", "涉及订单组合"), ("Gov Known Suppliers", "已知供应商编码"), ("Gov Top5 Share", "Top5金额占比")]):
        card(p, "spend_card_" + str(i), "GovFact", metric, title, 24 + i * 310)
    visual(p, "spend_type", "barChart", (24, 225, 600, 275), {"Category": [col("GovType", "acquisition_type")], "Y": [measure("GovFact", "Gov Observed Amount")]}, "采购类型金额")
    visual(p, "spend_trend", "lineChart", (646, 225, 610, 275), {"Category": [col("GovDate", "month")], "Y": [measure("GovFact", "Gov Observed Amount")]}, "有有效日期的月度金额（仅覆盖总额约29.6%）")
    # Preserve the visual-only exclusion verified and saved in Desktop by the user.
    trend_path = REPORT / "pages" / p / "visuals/spend_trend/visual.json"
    trend = json.loads(trend_path.read_text(encoding="utf-8"))
    trend["filterConfig"] = {"filters": [{"name": "valid_month_only", "field": col("GovDate", "month"),
        "type": "Categorical", "filter": {"Version": 2, "From": [{"Name": "g", "Entity": "GovDate", "Type": 0}],
        "Where": [{"Condition": {"Not": {"Expression": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "g"}}, "Property": "month"}}],
            "Values": [[{"Literal": {"Value": "null"}}]]}}}}}]}}]}
    dump(trend_path, trend)
    visual(p, "spend_supplier", "tableEx", (24, 515, 910, 315), {"Values": [col("GovSupplier", "supplier_key"), col("GovSupplier", "supplier_label"), measure("GovFact", "Gov Observed Amount")]}, "供应商编码明细（按表头排序；UNKNOWN不是一家真实供应商）")
    supplier_path = REPORT / "pages" / p / "visuals/spend_supplier/visual.json"
    supplier = json.loads(supplier_path.read_text(encoding="utf-8"))
    top10 = json.loads(TOP10_TEMPLATE.read_text(encoding="utf-8"))
    supplier["filterConfig"] = top10["filterConfig"]
    supplier["visual"]["query"]["sortDefinition"] = top10["sortDefinition"]
    dump(supplier_path, supplier)
    visual(p, "spend_year", "slicer", (956, 525, 300, 150), {"Values": [col("GovFact", "fiscal_year")]}, "财年筛选")
    visual(p, "spend_department", "slicer", (956, 685, 300, 145), {"Values": [col("GovDepartment", "department")]}, "部门筛选")
    text(p, "spend_footer", "来源：California DGS历史开放数据。金额范围与数据覆盖说明见采购分析报告；集中度只描述当前观测组合。", 845)
    p = page_names[1]
    text(p, "perf_heading", "供应商绩效：Kaggle公开练习数据", 12, 40, 20)
    text(p, "perf_scope", "777条订单、5供应商、5品类；企业来源未独立验证，币种未知。跨品类仅描述，无承诺交期和实际收货分母。", 56)
    for i, (metric, title) in enumerate([("Perf Noncancelled Orders", "非取消订单"), ("Perf Delivery Days", "平均交付周期（天）"), ("Perf Delivery Coverage", "有效周期记录覆盖"), ("Perf Recorded Compliance Rate", "合规标记Yes率")]):
        card(p, "perf_card_" + str(i), "PerfFact", metric, title, 24 + i * 310)
    visual(p, "perf_category", "slicer", (24, 220, 600, 100), {"Values": [col("PerfCategory", "Item_Category")]}, "品类筛选（同品类仍不自动证明业务条件可比）")
    visual(p, "perf_supplier_filter", "slicer", (646, 220, 610, 100), {"Values": [col("PerfSupplier", "Supplier")]}, "供应商筛选")
    fields = [col("PerfSupplier", "Supplier")] + [measure("PerfFact", m) for m in ["Perf Noncancelled Orders", "Perf Delivered Orders", "Perf Delivery Samples", "Perf Delivery Days", "Perf Delivery Coverage", "Perf Recorded Compliance Rate", "Perf Compliance Samples", "Perf Quality Samples", "Perf Quality Record Coverage"]]
    visual(p, "perf_table", "tableEx", (24, 335, 1232, 240), {"Values": fields}, "观测指标与有效分母（不是整体优劣排名）")
    visual(p, "perf_cycle", "barChart", (24, 590, 600, 225), {"Category": [col("PerfSupplier", "Supplier")], "Y": [measure("PerfFact", "Perf Delivery Days")]}, "已交付且日期有效的周期均值")
    visual(p, "perf_compliance", "barChart", (646, 590, 610, 225), {"Category": [col("PerfSupplier", "Supplier")], "Y": [measure("PerfFact", "Perf Recorded Compliance Rate")]}, "非取消订单的已知合规标签Yes占比")
    text(p, "perf_footer", "全量数据基线：有效周期491/560；68条已交付缺日期、1条先后异常。记录覆盖不是准时率或合格率；不发布正式缺陷率或已实现节约。", 835)
    p = page_names[2]
    text(p, "market_heading", "市场对标与寻源：A4 / 80g / 500张", 12, 40, 20)
    text(p, "market_scope", "2026-10-22单一销售渠道公开标价快照，非有效询价或成交价。税运费、MOQ和数量适用范围仍待核实。", 56)
    for i, (table, metric, title) in enumerate([("MarketQuotes", "Market Comparable Observations", "基础规格可比记录"), ("MarketQuotes", "Market Minimum Listed Price SameCurrency", "最低标价（同币种/500张）"), ("MarketQuotes", "Market Maximum Listed Price SameCurrency", "最高标价（同币种/500张）"), ("MarketScenario", "Market Scenario Known Total", "条件齐备总成本（当前空白）")]):
        card(p, "market_card_" + str(i), table, metric, title, 24 + i * 310)
    visual(p, "market_brand", "slicer", (24, 220, 600, 90), {"Values": [col("MarketQuotes", "brand")]}, "品牌筛选（不等于生产商或合同主体）")
    visual(p, "market_currency", "slicer", (646, 220, 610, 90), {"Values": [col("MarketQuotes", "currency")]}, "币种（不同币种不能直接比较）")
    visual(p, "market_price", "barChart", (24, 325, 600, 270), {"Category": [col("MarketQuotes", "product_name")], "Y": [measure("MarketQuotes", "Market Comparable Listed Price")]}, "基础同规格标价（单渠道、条件仍待核实）")
    visual(p, "market_evidence", "tableEx", (646, 325, 610, 270), {"Values": [col("MarketQuotes", c) for c in ["brand", "price_per_500", "currency", "spec_comparable", "collected_at", "url"]]}, "来源、时间与可比性（链接可核对）")
    visual(p, "market_scenario", "tableEx", (24, 610, 1232, 215), {"Values": [col("MarketScenario", c) for c in ["product_name", "requested_reams", "purchase_units", "goods_reference_cost", "total_cost", "budget_difference", "limitations"]]}, "100包假设需求；参考货品金额不等于到货总成本")
    text(p, "market_footer", "情景表为独立的固定100包计算，不随品牌/币种筛选联动；数量/地区等参数在Streamlit调整后导出再刷新。未知成本保持空白。", 840)
    dump(ROOT / "outputs/tables/powerbi_build.json", {"tables": len(SCHEMAS), "relationships": len(relationships), "measures": sum(map(len, MEASURES.values())), "pages": 3, "status": "authored; awaiting actual Desktop refresh and DAX checks", "seed": "Desktop-created project backed up under outputs/logs/powerbi_desktop_seed"})
    print("Authored 10 tables, 6 relationships, 26 measures and 3 pages; Desktop verification required.")


if __name__ == "__main__":
    build()
