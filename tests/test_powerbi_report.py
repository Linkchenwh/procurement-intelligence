import copy
import csv
import json
import shutil

from scripts import build_powerbi_project as builder
from src.data_loader import ROOT


def test_report_rebuild_preserves_valid_date_scope_and_baseline_label(tmp_path, monkeypatch):
    """A fresh definition build must retain the two fixes verified in Desktop."""
    base = tmp_path / "dashboard/powerbi"
    model = base / "ProcurementIntelligence.SemanticModel/definition"
    report = base / "ProcurementIntelligence.Report/definition"
    (model / "tables").mkdir(parents=True)
    (report / "pages").mkdir(parents=True)
    (base / "input").mkdir()
    (tmp_path / "outputs/logs/powerbi_desktop_seed").mkdir(parents=True)
    shutil.copy2(ROOT / "dashboard/powerbi/ProcurementIntelligence.pbip", base)
    manifest = json.loads((ROOT / "dashboard/powerbi/preparation_status.json").read_text(encoding="utf-8"))
    # Header-only inputs test definition generation; they are not business data.
    for table in manifest["generated_inputs"]:
        with (base / "input" / (table["name"] + ".csv")).open("w", encoding="utf-8", newline="") as out:
            csv.writer(out).writerow(table["columns"])
    for name, value in [("ROOT", tmp_path), ("BASE", base), ("MODEL", model), ("REPORT", report),
                        ("SCHEMAS", copy.deepcopy(builder.SCHEMAS))]:
        monkeypatch.setattr(builder, name, value)
    builder.build()
    trend = json.loads((report / "pages/spend_overview/visuals/spend_trend/visual.json").read_text(encoding="utf-8"))
    filters = trend["filterConfig"]["filters"]
    assert len(filters) == 1 and filters[0]["field"]["Column"]["Property"] == "month"
    assert filters[0]["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "GovDate"
    condition = filters[0]["filter"]["Where"][0]["Condition"]["Not"]["Expression"]["In"]
    assert condition["Values"] == [[{"Literal": {"Value": "null"}}]]
    metric = trend["visual"]["query"]["queryState"]["Y"]["projections"][0]["field"]["Measure"]
    assert metric["Property"] == "Gov Observed Amount"
    footer = (report / "pages/supplier_performance/visuals/perf_footer/visual.json").read_text(encoding="utf-8")
    assert "全量数据基线" in footer
    supplier = json.loads((report / "pages/spend_overview/visuals/spend_supplier/visual.json").read_text(encoding="utf-8"))
    top_filter = supplier["filterConfig"]["filters"][0]
    assert top_filter["type"] == "TopN"
    query = top_filter["filter"]["From"][0]["Expression"]["Subquery"]["Query"]
    assert query["Top"] == 10
    assert query["OrderBy"][0]["Expression"]["Measure"]["Property"] == "Gov Observed Amount"
    sort = supplier["visual"]["query"]["sortDefinition"]["sort"][0]
    assert sort["direction"] == "Descending" and sort["field"]["Measure"]["Property"] == "Gov Observed Amount"
