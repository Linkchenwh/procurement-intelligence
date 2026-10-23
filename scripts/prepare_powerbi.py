"""Export three independent Power BI input domains, without inventing missing facts."""
import json

import pandas as pd

from src.data_loader import ROOT
from src.export_utils import csv_bytes


def government_fact(data):
    """Keep case-sensitive order identity independent of VertiPaq text collation."""
    facts = data[["source_row", "order_key", "supplier_key", "purchase_date", "Department Name", "Fiscal Year", "Acquisition Type", "amount"]].copy()
    facts.columns = ["row_id", "order_key", "supplier_key", "purchase_date", "department", "fiscal_year", "acquisition_type", "amount"]
    if facts.order_key.isna().any():
        raise ValueError("A case-sensitive order_key is required before creating the BI order identifier")
    facts.insert(2, "order_id", pd.factorize(facts.order_key, sort=True)[0] + 1)
    return facts


def write_project_root(base, project_root):
    definition = base / "ProcurementIntelligence.SemanticModel/definition"
    if definition.exists():
        value = str(project_root).replace('"', '""')
        source = 'expression ProjectRoot = "' + value + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\tannotation PBI_ResultType = Text\n'
        (definition / "expressions.tmdl").write_text(source, encoding="utf-8")


def main():
    target = ROOT / "dashboard/powerbi/input"
    target.mkdir(parents=True, exist_ok=True)
    exported = []
    write_project_root(target.parent, ROOT)

    def save(name, frame):
        (target / (name + ".csv")).write_bytes(csv_bytes(frame))
        exported.append({"name": name, "rows": len(frame), "columns": list(frame.columns)})

    path = ROOT / "data/processed/government.parquet"
    if path.exists():
        data = pd.read_parquet(path)
        facts = government_fact(data)
        save("GovFact", facts)
        suppliers = data.groupby("supplier_key", as_index=False).agg(supplier_label=("supplier_label", "first"), name_variants=("supplier_label", "nunique"))
        save("GovSupplier", suppliers)
        save("GovDepartment", facts[["department"]].drop_duplicates())
        save("GovType", facts[["acquisition_type"]].drop_duplicates())
        valid_dates = facts.purchase_date.dropna()
        dates = pd.DataFrame({"date": pd.date_range(valid_dates.min(), valid_dates.max(), freq="D")})
        dates["month"] = dates.date.dt.to_period("M").astype(str)
        dates["year"] = dates.date.dt.year
        save("GovDate", dates)
    path = ROOT / "data/processed/performance.parquet"
    if path.exists():
        data = pd.read_parquet(path)
        save("PerfFact", data)
        save("PerfSupplier", data[["Supplier"]].drop_duplicates())
        save("PerfCategory", data[["Item_Category"]].drop_duplicates())
    path = ROOT / "data/processed/market.parquet"
    if path.exists():
        data = pd.read_parquet(path)
        save("MarketQuotes", data)
        scenario = pd.read_csv(ROOT / "outputs/tables/market_scenario_100_reams.csv")
        save("MarketScenario", scenario)
    manifest = {"generated_inputs": exported,
                "desktop_validation": "Input export only; consult desktop_validation.json for actual engine and visual verification",
                "native_project": "PBIP exists; existence is not verification" if (ROOT / "dashboard/powerbi/ProcurementIntelligence.pbip").exists() else "NOT CREATED",
                "performance_domain": "available" if (target / "PerfFact.csv").exists() else "awaiting official Kaggle file"}
    (ROOT / "dashboard/powerbi/preparation_status.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
