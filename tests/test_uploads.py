from io import BytesIO

import pandas as pd
import pytest
from src.data_loader import read_table
from src.export_utils import csv_bytes


def test_csv_ids_preserved():
    data = read_table(BytesIO(b"PO_ID,Quantity\n0001,10\n"), "input.csv")
    assert data.iloc[0].PO_ID == "0001"


@pytest.mark.parametrize("filename,content", [("x.txt", b"a"), ("x.csv", b""), ("x.xlsx", b"bad"), ("x.csv", b"a,a\n1,2\n")])
def test_invalid_upload_has_clear_error(filename, content):
    with pytest.raises(ValueError):
        read_table(BytesIO(content), filename)


def test_formula_injection_escaped_only_on_export():
    data = pd.DataFrame({"Supplier": ["=HYPERLINK(1)", "+cmd", "@x", "-s"], "amount": [-3, 2, 1, 0]})
    result = csv_bytes(data).decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in result
    assert data.iloc[0].Supplier == "=HYPERLINK(1)"
    assert ",-3" in result
