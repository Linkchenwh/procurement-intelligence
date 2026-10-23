"""Synthetic behavior tests, not supplier evidence."""
import pandas as pd
import pytest
from src.data_cleaning import clean_performance
from src.supplier_analysis import supplier_metrics
from src.scoring_model import score_suppliers, sensitivity
from tests.test_spend_metrics import orders


def test_delivery_only_fulfilled_and_no_default_defect_denominator():
    data, _ = clean_performance(orders())
    result = supplier_metrics(data, "Paper").set_index("Supplier")
    assert result.loc["A", "delivery_days"] == 2
    assert pd.isna(result.loc["B", "delivery_days"])
    assert pd.isna(result.loc["A", "defect_rate_proxy"])
    assert result.loc["A", "observed_defective_units"] == 1


def metrics():
    return pd.DataFrame({"Supplier": ["A", "B", "C"], "Item_Category": ["Paper"]*3,
                         "orders": [10, 10, 2], "delivery_samples": [10, 10, 2],
                         "compliance_samples": [10, 10, 2],
                         "delivery_days": [2., 8., None], "compliance_rate": [.8, 1., .9]})


def test_weights_direction_and_missing_are_explicit():
    result = score_suppliers(metrics(), {"delivery_days": 1}, comparable=True, min_samples=3).set_index("Supplier")
    assert result.loc["A", "score"] == 100
    assert result.loc["B", "score"] == 0
    assert pd.isna(result.loc["C", "score"])
    assert not result.loc["C", "eligible"]


@pytest.mark.parametrize("weights", [{"delivery_days": 0}, {"delivery_days": -1}, {"cost": 1}, {"delivery_days": float('nan')}])
def test_invalid_weights_rejected(weights):
    with pytest.raises(ValueError):
        score_suppliers(metrics(), weights, comparable=True)


def test_requires_comparability_and_single_category():
    with pytest.raises(ValueError):
        score_suppliers(metrics(), {"delivery_days": 1})
    data = metrics()
    data.loc[0, "Item_Category"] = "Other"
    with pytest.raises(ValueError):
        score_suppliers(data, {"delivery_days": 1}, comparable=True)


def test_sensitivity_shows_real_tradeoff():
    result = sensitivity(metrics(), {"speed": {"delivery_days": 1}, "compliance": {"compliance_rate": 1}}, min_samples=3)
    winners = result.loc[result["rank"].eq(1)].set_index("scenario").Supplier
    assert winners["speed"] == "A"
    assert winners["compliance"] == "B"


def test_coverage_and_flags_keep_delivered_denominators_separate():
    raw = orders()
    raw.loc[1, "Order_Status"] = "Delivered"
    data, _ = clean_performance(raw)
    result = supplier_metrics(data, "Paper").set_index("Supplier")
    assert result.loc["B", "delivered_orders"] == 1
    assert result.loc["B", "delivery_samples"] == 0
    assert result.loc["B", "delivery_coverage"] == 0
    assert result.loc["B", "missing_delivered_dates"] == 1
    assert result.loc["B", "noncompliant_records"] == 1
    assert pd.isna(result.loc["B", "observed_defective_units"])
    assert "缺少" in result.loc["B", "watch_notes"]


def test_all_category_descriptive_summary_never_ranked():
    data = metrics().assign(Item_Category="ALL_CATEGORIES_DESCRIPTIVE_ONLY")
    with pytest.raises(ValueError):
        score_suppliers(data, {"delivery_days": 1}, comparable=True)
