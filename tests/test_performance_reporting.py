import shutil

import pandas as pd

from src.data_loader import ROOT
from src.performance_reporting import analyze_performance
from tests.test_spend_metrics import orders


def test_reporting_crosschecks_values_and_does_not_certify_wrong_source(tmp_path):
    (tmp_path / "sql").mkdir()
    for name in ["01_data_audit.sql", "03_supplier_analysis.sql", "04_data_validation.sql"]:
        shutil.copyfile(ROOT / "sql" / name, tmp_path / "sql" / name)
    folder = tmp_path / "data/raw/kaggle"
    folder.mkdir(parents=True)
    path = folder / "synthetic_test.csv"
    orders().to_csv(path, index=False)
    result = analyze_performance(path, tmp_path)
    assert result["valid_amount"] == 260
    assert result["valid_delivery_samples"] == 1
    source = pd.read_json(tmp_path / "outputs/tables/performance_source_check.json", typ="series")
    assert not source["matches_previous_page_preview"]
    report = (tmp_path / "reports/supplier_performance_report.md").read_text(encoding="utf-8")
    assert "尚未确认与指定页面预览一致" in report
    metrics = pd.read_csv(tmp_path / "outputs/tables/performance_supplier_metrics.csv")
    assert metrics.defect_rate_proxy.isna().all()
