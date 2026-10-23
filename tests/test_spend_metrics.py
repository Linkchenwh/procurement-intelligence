"""All records in this file are synthetic test fixtures, never business evidence."""
import pandas as pd
import pytest

from src.data_cleaning import clean_performance
from src.spend_analysis import spend_summary, spend_breakdown, sql_summary


def orders():
    return pd.DataFrame({
        "PO_ID": ["T1", "T2", "T3"], "Supplier": ["A", "B", "B"],
        "Order_Date": ["2023-01-01"] * 3, "Delivery_Date": ["2023-01-03", None, None],
        "Item_Category": ["Paper"] * 3, "Order_Status": ["Delivered", "Pending", "Cancelled"],
        "Quantity": [10, 20, 5], "Unit_Price": [12, 10, 10],
        "Negotiated_Price": [10, 8, 9], "Defective_Units": [1, None, None],
        "Compliance": ["Yes", "No", None],
    })


def test_cancelled_excluded_but_raw_preserved():
    data, audit = clean_performance(orders())
    result = spend_summary(data)
    assert result["raw_amount"] == 305
    assert result["valid_amount"] == 260
    assert result["cancelled_amount"] == 45
    assert result["nominal_price_difference"] == 60
    assert result["valid_order_count"] == 2
    assert audit["input_rows"] == audit["output_rows"] == 3


def test_concentration_and_sql_agree():
    data, _ = clean_performance(orders())
    summary = spend_summary(data)
    assert summary["top1_share"] == pytest.approx(160 / 260)
    sql = sql_summary(data)
    assert sql["valid_amount"] == summary["valid_amount"]
    assert sql["valid_order_count"] == summary["valid_order_count"]
    assert spend_breakdown(data, "Supplier")["amount"].sum() == 260


def test_duplicate_po_rejected_without_silent_deletion():
    with pytest.raises(ValueError, match="PO_ID"):
        clean_performance(pd.concat([orders(), orders().iloc[[0]]]))


@pytest.mark.parametrize("column,value", [("Quantity", -1), ("Negotiated_Price", "bad"), ("Quantity", float('inf'))])
def test_bad_amount_inputs_rejected(column, value):
    data = orders().astype(object)
    data.loc[0, column] = value
    with pytest.raises(ValueError):
        clean_performance(data)


def test_unknown_status_and_blank_key_rejected():
    data = orders()
    data.loc[0, "Order_Status"] = "Mystery"
    with pytest.raises(ValueError):
        clean_performance(data)
    data = orders()
    data.loc[0, "Supplier"] = " "
    with pytest.raises(ValueError):
        clean_performance(data)


def test_missing_delivery_kept_and_invalid_dates_flagged():
    data = orders()
    data.loc[0, "Delivery_Date"] = "2022-12-01"
    result, audit = clean_performance(data)
    assert pd.isna(result.loc[0, "delivery_days"])
    assert audit["negative_delivery_days"] == 1
    assert len(result) == 3


def test_nullable_string_upload_missing_quantity_rejected():
    raw = orders().astype("string")
    raw.loc[0, "Quantity"] = pd.NA
    with pytest.raises(ValueError):
        clean_performance(raw)
