import pandas as pd
import pytest
from src.market_benchmark import normalize_quotes
from src.scenario_analysis import sourcing_scenario


def quotes():
    # Synthetic prices. Never imported by the production application.
    return pd.DataFrame({"quote_id": ["T"], "brand": ["Test"], "product_name": ["test paper"],
        "sku": ["TEST"], "seller": ["Test seller"], "channel": ["Test"],
        "paper_size": ["A4"], "gsm": [80], "sheets_per_ream": [500], "reams_per_box": [5],
        "price": [100.], "currency": ["CNY"], "quote_unit": ["box"], "min_order_units": [1],
        "max_order_units": [10], "shipping_cost": [None], "shipping_terms": ["unknown"],
        "tax_status": ["unknown"], "region": ["Shenzhen"], "lead_time_days": [2],
        "collected_at": ["2026-10-22"], "url": ["https://example.com/test"],
        "data_status": ["observed_public_page"]})


def test_box_price_and_unknown_total():
    data = normalize_quotes(quotes(), as_of="2026-10-22")
    assert data.iloc[0].price_per_500 == 20
    result = sourcing_scenario(data, 6, budget=200, currency="CNY", region="Shenzhen", as_of="2026-10-22")
    assert result.iloc[0].purchase_units == 2
    assert result.iloc[0].supplied_reams == 10
    assert result.iloc[0].goods_reference_cost == 200
    assert pd.isna(result.iloc[0].total_cost)
    assert pd.isna(result.iloc[0]["rank"])


def test_known_all_in_total_and_budget():
    raw = quotes()
    raw["tax_status"] = "included"
    raw["shipping_cost"] = 5
    data = normalize_quotes(raw, as_of="2026-10-22")
    result = sourcing_scenario(data, 6, budget=200, currency="CNY", region="Shenzhen", as_of="2026-10-22")
    assert result.iloc[0].total_cost == 205
    assert result.iloc[0].budget_difference == -5
    assert result.iloc[0]["rank"] == 1


def test_currency_and_spec_never_forced_comparable():
    raw = pd.concat([quotes(), quotes().assign(quote_id="T2", currency="GBP"), quotes().assign(quote_id="T3", gsm=70)])
    data = normalize_quotes(raw, as_of="2026-10-22")
    result = sourcing_scenario(data, 1, currency="CNY", region="Shenzhen", as_of="2026-10-22")
    assert not result.loc[result.quote_id.eq("T2"), "scenario_comparable"].iloc[0]
    assert not result.loc[result.quote_id.eq("T3"), "scenario_comparable"].iloc[0]


def test_stale_future_and_unknown_moq_not_ranked():
    for date in ["2020-01-01", "2027-01-01"]:
        raw = quotes().assign(collected_at=date, tax_status="included", shipping_cost=0)
        result = sourcing_scenario(normalize_quotes(raw, as_of="2026-10-22"), 1, currency="CNY", region="Shenzhen", as_of="2026-10-22")
        assert pd.isna(result.iloc[0]["rank"])
    raw = quotes().assign(min_order_units=None, tax_status="included", shipping_cost=0)
    result = sourcing_scenario(normalize_quotes(raw, as_of="2026-10-22"), 1, currency="CNY", region="Shenzhen", as_of="2026-10-22")
    assert pd.isna(result.iloc[0].total_cost)


@pytest.mark.parametrize("demand", [0, -1, 1.5, float('inf')])
def test_invalid_demand(demand):
    with pytest.raises(ValueError):
        sourcing_scenario(normalize_quotes(quotes(), as_of="2026-10-22"), demand)
