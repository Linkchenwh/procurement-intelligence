"""Compare actual local Power BI engine exports against independent Python controls."""
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.data_loader import ROOT

TABLES = ROOT / "outputs/tables"


def read(name):
    return json.loads((TABLES / (name + ".json")).read_text(encoding="utf-8-sig"))


def clean_keys(row):
    return {k.removeprefix("[").removesuffix("]"): v for k, v in row.items()}


def main():
    actual = clean_keys(read("powerbi_dax_totals")[0])
    gov = read("government_summary")
    perf = read("performance_summary")
    gdata = pd.read_parquet(ROOT / "data/processed/government.parquet")
    pdata = pd.read_parquet(ROOT / "data/processed/performance.parquet")
    quotes = pd.read_parquet(ROOT / "data/processed/market.parquet")
    delivered = int(pdata.delivered_order.sum())
    cycle_samples = int(pdata.delivery_days.notna().sum())
    valid = pdata.loc[pdata.valid_order]
    quality_samples = int(valid.observed_defective_units.notna().sum())
    controls = {"Gov Rows": gov["rows"], "Gov Amount": gov["amount"], "Gov Orders": gov["orders"],
                "Gov Known Suppliers": gov["supplier_codes"], "Gov Top5": gov["top5_share"], "Gov HHI": gov["hhi"],
                "Gov Dated Coverage": gdata.loc[gdata.purchase_date.notna(), "amount"].sum() / gov["amount"],
                "Perf Rows": len(pdata), "Perf Orders": perf["valid_order_count"], "Perf Amount": perf["valid_amount"],
                "Perf Cancelled": perf["cancelled_amount"], "Perf Delivered Amount": perf["delivered_amount"],
                "Perf Nominal Difference": perf["nominal_price_difference"], "Perf Delivered Orders": delivered,
                "Perf Cycle": pdata.delivery_days.mean(), "Perf Cycle Samples": cycle_samples,
                "Perf Cycle Coverage": cycle_samples / delivered, "Perf Compliance": valid.compliant.mean(),
                "Perf Compliance Samples": int(valid.compliant.notna().sum()), "Perf Quality Samples": quality_samples,
                "Perf Quality Coverage": quality_samples / delivered, "Perf Observed Defects": valid.observed_defective_units.sum(),
                "Market Rows": len(quotes), "Market Scenario Rows": len(pd.read_csv(TABLES / "market_scenario_100_reams.csv")),
                "Market Comparable": int(quotes.spec_comparable.sum()),
                "Market Min": quotes.loc[quotes.spec_comparable, "price_per_500"].min(),
                "Market Max": quotes.loc[quotes.spec_comparable, "price_per_500"].max()}
    for table, key in [("GovSupplier", "Gov Supplier Dimension"), ("GovDepartment", "Gov Department Dimension"),
                       ("GovType", "Gov Type Dimension"), ("GovDate", "Gov Date Dimension"),
                       ("PerfSupplier", "Perf Supplier Dimension"), ("PerfCategory", "Perf Category Dimension")]:
        controls[key] = len(pd.read_csv(ROOT / f"dashboard/powerbi/input/{table}.csv"))
    for name, expected in controls.items():
        tolerance = .01 if any(word in name for word in ["Amount", "Cancelled", "Difference"]) else 1e-9
        assert actual[name] is not None and math.isclose(actual[name], expected, rel_tol=0, abs_tol=tolerance), (name, actual[name], expected)
    assert actual["Market Known Total"] is None
    metric_controls = pd.read_csv(TABLES / "performance_supplier_metrics.csv")
    dax_groups = pd.DataFrame(read("powerbi_dax_supplier"))
    dax_groups = dax_groups.rename(columns={"PerfCategory[Item_Category]": "Item_Category", "PerfSupplier[Supplier]": "Supplier",
                                          **{c: c.strip("[]") for c in dax_groups if c.startswith("[")}})
    keys = ["Item_Category", "Supplier"]
    expected_groups = metric_controls[list(dax_groups)].sort_values(keys).reset_index(drop=True)
    observed_groups = dax_groups.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(observed_groups, expected_groups, check_dtype=False, rtol=1e-10, atol=1e-10)
    relations = [clean_keys(r) for r in read("powerbi_dax_relationships")]
    actual_relations = {(r["FromTable"], r["FromColumn"], r["ToTable"], r["ToColumn"]) for r in relations}
    assert actual_relations == {("GovFact", "supplier_key", "GovSupplier", "supplier_key"),
                                ("GovFact", "department", "GovDepartment", "department"),
                                ("GovFact", "acquisition_type", "GovType", "acquisition_type"),
                                ("GovFact", "purchase_date", "GovDate", "date"),
                                ("PerfFact", "Supplier", "PerfSupplier", "Supplier"),
                                ("PerfFact", "Item_Category", "PerfCategory", "Item_Category")}
    assert all(r["IsActive"] and r["CrossFilteringBehavior"] == "OneDirection" and r["FromCardinality"] == "Many"
               and r["ToCardinality"] == "One" and r["State"] == "Ready" for r in relations)
    model = clean_keys(read("powerbi_dax_model")[0])
    assert model == {"Tables": 10, "Measures": 26, "Relationships": 6}
    filters = clean_keys(read("powerbi_dax_filters")[0])
    electronic = valid.loc[valid.Item_Category.eq("Electronics")]
    assert filters["Electronics Orders"] == len(electronic)
    assert filters["Alpha Electronics Orders"] == len(electronic.loc[electronic.Supplier.eq("Alpha_Inc")])
    assert math.isclose(filters["Alpha Electronics Cycle"], electronic.loc[electronic.Supplier.eq("Alpha_Inc"), "delivery_days"].mean())
    assert filters["MRO Orders"] == len(valid.loc[valid.Item_Category.eq("MRO")])
    assert math.isclose(filters["Government Amount With Unrelated Perf Filter"], gov["amount"], rel_tol=0, abs_tol=.01)
    assert filters["Market Min With Unrelated Perf Filter"] == controls["Market Min"]
    assert filters["Market Scenario With Unrelated Brand Filter"] == actual["Market Scenario Rows"]
    parts = json.loads((ROOT / "outputs/logs/powerbi_partition_after_full_refresh.json").read_text(encoding="utf-8-sig"))
    assert len(parts) == 10 and all(r["State"] == 1 and not r["ErrorMessage"] for r in parts)
    status = {"verified_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "desktop_version": "2.159.883.0",
              "method": "Actual running local Desktop model queried using Microsoft ADOMD/TOM clients",
              "engine_validation": "passed", "scalar_controls_matched": len(controls), "supplier_category_groups_matched": len(dax_groups),
              "active_many_to_one_relationships_verified": len(relations), "model": model,
              "filter_and_domain_isolation_checks": "passed", "unknown_market_total": "BLANK preserved",
              "government_order_identity": "198343 case-sensitive source orders preserved with integer order_id; text collation had merged 24",
              "visual_pages_and_screenshots": "See docs/validation.md; exported engine checks do not inspect the UI",
              "save_reopen_refresh_check": "Desktop acceptance is documented in docs/validation.md",
              "overall_native_acceptance": "Engine controls passed; UI acceptance is documented separately"}
    (ROOT / "dashboard/powerbi/desktop_validation.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
