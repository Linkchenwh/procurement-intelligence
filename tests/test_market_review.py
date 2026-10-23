import pandas as pd
from src.market_benchmark import normalize_quotes
from tests.test_market_benchmark import quotes


def test_packaging_conflict_excluded_even_when_price_is_per_ream():
    raw = quotes().assign(packaging_conflict=True, quote_unit="ream")
    result = normalize_quotes(raw, as_of="2026-10-22")
    assert not result.iloc[0].spec_comparable
    assert pd.isna(result.iloc[0].price_per_500)
