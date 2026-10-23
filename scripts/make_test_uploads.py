"""Create clearly labeled synthetic fixtures solely for local UI verification."""
import pandas as pd
from src.data_loader import ROOT

target = ROOT / "tests/fixtures"
target.mkdir(parents=True, exist_ok=True)
rows = []
for i in range(12):
    a = i < 6
    rows.append({"PO_ID": f"SYNTHETIC_TEST_{i:03d}", "Supplier": "SYNTHETIC_TEST_A" if a else "SYNTHETIC_TEST_B",
                 "Order_Date": "2026-01-01", "Delivery_Date": "2026-01-03" if a else "2026-01-09",
                 "Item_Category": "SYNTHETIC_TEST_ONLY", "Order_Status": "Delivered", "Quantity": 100,
                 "Unit_Price": 12, "Negotiated_Price": 10, "Defective_Units": 1 if a else 2,
                 "Compliance": "Yes" if (not a or i < 5) else "No"})
pd.DataFrame(rows).to_csv(target / "synthetic_ui_orders.csv", index=False, encoding="utf-8-sig")
pd.DataFrame({"wrong_header": ["SYNTHETIC_INVALID_TEST"]}).to_csv(target / "invalid_ui_orders.csv", index=False, encoding="utf-8-sig")
print("Created 12 clearly marked test orders and one invalid upload; never used as app defaults.")
