import pandas as pd

from scripts.prepare_powerbi import government_fact


def test_order_surrogate_preserves_case_sensitive_identity_and_repeated_lines():
    raw = pd.DataFrame({"source_row": [2, 3, 4], "order_key": ["Dept|2014|abc", "Dept|2014|ABC", "Dept|2014|abc"],
                        "supplier_key": ["01", "01", "02"], "purchase_date": [pd.NaT] * 3,
                        "Department Name": ["Dept"] * 3, "Fiscal Year": ["2014"] * 3,
                        "Acquisition Type": ["Goods"] * 3, "amount": [10., 20., 30.]})
    result = government_fact(raw)
    assert len(result) == 3 and result.amount.sum() == 60
    assert result.order_id.nunique() == 2
    assert result.order_key.str.casefold().nunique() == 1
    assert result.order_id.iloc[0] == result.order_id.iloc[2]
    assert result.order_id.iloc[0] != result.order_id.iloc[1]
    assert result.supplier_key.tolist() == ["01", "01", "02"]
