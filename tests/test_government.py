import pandas as pd
import pytest
from src.government import clean_government, government_summary, government_sql_summary


def fixture():
    # Synthetic: two classifications describe the same candidate line; keep both in quarantine.
    return pd.DataFrame({"Department Name": ["D", "D", "D", "E"], "Fiscal Year": ["2013-2014"]*4,
        "Purchase Order Number": ["1", "1", "2", "2"], "Supplier Code": ["S"]*4,
        "Supplier Name": ["Test"]*4, "Purchase Date": ["1/2/2014"]*4,
        "Creation Date": ["1/3/2014"]*4, "Acquisition Type": ["Goods"]*4,
        "Item Name": ["Pen", "Pen", "Paper", "Paper"], "Quantity": [1,1,2,1],
        "Unit Price": ["$10", "$10", "$5", "$3"], "Total Price": ["$10", "$10", "$10", "$3"],
        "Classification Codes": ["A", "B", "C", "C"]})


def test_no_false_dedup_or_cross_department_order_merge():
    data, quarantine, audit = clean_government(fixture())
    assert len(data) == 2
    assert len(quarantine) == 2
    assert audit["ambiguous_rows"] == 2
    assert data.order_key.nunique() == 2
    summary = government_summary(data)
    assert summary["amount"] == 13
    assert government_sql_summary(data)["amount"] == summary["amount"]


def test_money_mismatch_and_negative_are_visible():
    raw = fixture().iloc[[2,3]].copy()
    raw.loc[2, "Total Price"] = "$11"
    raw.loc[3, "Total Price"] = "($3)"
    data, quarantine, audit = clean_government(raw)
    assert data.empty
    assert len(quarantine) == 2
    assert audit["amount_mismatch_rows"] == 1
    assert audit["negative_amount_rows"] == 1


def test_missing_date_is_not_creation_date_substitution():
    raw = fixture().iloc[[2]].copy()
    raw["Purchase Date"] = None
    data, _, _ = clean_government(raw)
    assert pd.isna(data.iloc[0].purchase_date)


def test_purchase_date_outside_reported_fiscal_year_not_used_in_trend():
    raw = fixture().iloc[[2]].copy()
    raw["Purchase Date"] = "1/2/1914"
    data, _, audit = clean_government(raw)
    assert len(data) == 1
    assert pd.isna(data.iloc[0].purchase_date)
    assert audit["purchase_date_outside_fiscal_year"] == 1


def test_zero_supplier_code_and_unknown_label_is_unidentified_bucket():
    raw = fixture().iloc[[2]].copy()
    raw["Supplier Code"] = "0"
    raw["Supplier Name"] = "Unknown"
    data, _, _ = clean_government(raw)
    assert data.iloc[0].supplier_key == "UNKNOWN"
    assert government_summary(data)["supplier_codes"] == 0


def test_nullable_missing_amount_is_quarantined():
    raw = fixture().iloc[[2]].astype("string")
    raw["Total Price"] = pd.NA
    data, quarantine, audit = clean_government(raw)
    assert data.empty
    assert len(quarantine) == 1
    assert audit["invalid_numeric_rows"] == 1
