"""Conservative analysis of historical California source rows without a line ID."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

CLASS_COLUMNS = ["Classification Codes", "Normalized UNSPSC", "Commodity Title", "Class", "Class Title",
                 "Family", "Family Title", "Segment", "Segment Title"]
REQUIRED = ["Department Name", "Fiscal Year", "Purchase Order Number", "Supplier Code", "Supplier Name",
            "Purchase Date", "Creation Date", "Acquisition Type", "Quantity", "Unit Price", "Total Price"]


def money(series):
    text = series.astype("string").str.strip().str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(text.str.replace(r"[$,]", "", regex=True), errors="coerce").astype(float)


def clean_government(raw):
    missing = set(REQUIRED) - set(raw)
    if missing:
        raise ValueError("政府数据缺少字段: " + ", ".join(sorted(missing)))
    data = raw.copy().reset_index(drop=True)
    # Fingerprint is not a proven line ID. Every repeated candidate group is quarantined.
    base = [c for c in data if c not in CLASS_COLUMNS]
    ambiguous = data.duplicated(base, keep=False)
    amount = money(data["Total Price"])
    quantity = pd.to_numeric(data.Quantity, errors="coerce").astype(float)
    price = money(data["Unit Price"])
    bad_numeric = ~np.isfinite(amount) | ~np.isfinite(quantity) | ~np.isfinite(price)
    negative = amount.lt(0) | quantity.lt(0) | price.lt(0)
    mismatch = (~bad_numeric & ~negative & ((amount - quantity * price).abs() > .02))
    bad_key = pd.Series(False, index=data.index)
    separator = "\u241f"
    for column in ["Department Name", "Fiscal Year", "Purchase Order Number"]:
        value = data[column].astype("string").str.strip()
        bad_key |= value.isna() | value.eq("") | value.str.contains(separator, regex=False).fillna(False)
    reasons = pd.Series("", index=data.index)
    for mask, label in [(ambiguous, "ambiguous_candidate_line;"), (bad_numeric, "invalid_numeric;"),
                        (negative, "negative_numeric;"), (mismatch, "amount_mismatch;"), (bad_key, "invalid_order_key;")]:
        reasons.loc[mask] += label
    data["source_row"] = np.arange(2, len(data) + 2)  # CSV record index, not physical newline count.
    data["amount"] = amount
    data["quantity_numeric"] = quantity
    data["unit_price_numeric"] = price
    parsed_date = pd.to_datetime(data["Purchase Date"], format="%m/%d/%Y", errors="coerce")
    fiscal_start_year = data["Fiscal Year"].astype("string").str.extract(r"^(\d{4})-\d{4}$", expand=False)
    fiscal_start = pd.to_datetime(fiscal_start_year + "-07-01", errors="coerce")
    fiscal_end = fiscal_start + pd.DateOffset(years=1)
    date_in_scope = parsed_date.ge(fiscal_start) & parsed_date.lt(fiscal_end)
    outside_fiscal = parsed_date.notna() & ~date_in_scope
    # Preserve original text. Inconsistent dates stay out of time-series and date dimensions.
    data["purchase_date"] = parsed_date.where(date_in_scope)
    data["order_key"] = data["Department Name"].astype("string").str.strip().str.cat(
        [data["Fiscal Year"].astype("string").str.strip(), data["Purchase Order Number"].astype("string").str.strip()], sep=separator)
    data["supplier_key"] = data["Supplier Code"].astype("string").str.strip().replace("", pd.NA).fillna("UNKNOWN")
    placeholder_supplier = data.supplier_key.eq("0") & data["Supplier Name"].astype("string").str.strip().str.lower().eq("unknown")
    data.loc[placeholder_supplier.fillna(False), "supplier_key"] = "UNKNOWN"
    data["supplier_label"] = data["Supplier Name"].fillna("Unknown supplier")
    data["source_domain"] = "california_history"
    data["exclusion_reason"] = reasons
    accepted = data.loc[reasons.eq("")].copy()
    quarantine = data.loc[reasons.ne("")].copy()
    audit = {
        "input_rows": len(raw), "columns": len(raw.columns), "accepted_rows": len(accepted),
        "quarantined_rows": len(quarantine), "exact_duplicate_excess": int(raw.duplicated().sum()),
        "ambiguous_rows": int(ambiguous.sum()), "candidate_duplicate_excess": int(raw.duplicated(base).sum()),
        "invalid_numeric_rows": int(bad_numeric.sum()), "negative_amount_rows": int(negative.sum()),
        "amount_mismatch_rows": int(mismatch.sum()), "invalid_order_key_rows": int(bad_key.sum()),
        "placeholder_supplier_rows": int(placeholder_supplier.sum()),
        "missing_or_invalid_purchase_date": int(data.purchase_date.isna().sum()),
        "purchase_date_outside_fiscal_year": int(outside_fiscal.sum()),
        "accepted_missing_purchase_date": int(accepted.purchase_date.isna().sum()),
        "source_row_amount_sum_unverified": float(amount.sum()),
        "quarantined_parsed_amount": float(quarantine.amount.sum()),
        "accepted_amount": float(accepted.amount.sum()),
        "accepted_row_coverage": len(accepted) / len(raw) if len(raw) else 0,
        "missing_by_column": raw.isna().sum().astype(int).to_dict(),
        "warning": "仅分析未发现重复候选行及数值异常的观测子集；缺少官方行号，不能认定为完整去重后的全州支出或严格上下界。",
    }
    return accepted, quarantine, audit


def government_summary(data):
    grouped = data.groupby("supplier_key", dropna=False).amount.sum().sort_values(ascending=False)
    total = float(data.amount.sum())
    shares = grouped / total if total > 0 else grouped * np.nan
    return {"rows": len(data), "amount": total, "orders": int(data.order_key.nunique()),
            "supplier_codes": int(data.loc[data.supplier_key.ne("UNKNOWN"), "supplier_key"].nunique()),
            "unknown_supplier_amount": float(data.loc[data.supplier_key.eq("UNKNOWN"), "amount"].sum()),
            "top1_share": float(shares.iloc[0]) if len(shares) else None,
            "top5_share": float(shares.head(5).sum()) if total > 0 else None,
            "hhi": float((shares ** 2).sum() * 10000) if total > 0 else None}


def government_breakdown(data, column):
    out = data.groupby(column, dropna=False).agg(amount=("amount", "sum"),
            observed_orders=("order_key", "nunique"), rows=("source_row", "size")).reset_index()
    out = out.sort_values(["amount", column], ascending=[False, True], na_position="last").reset_index(drop=True)
    total = out.amount.sum()
    out["share"] = out.amount / total if total > 0 else np.nan
    out["cumulative_share"] = out.share.cumsum()
    prior = out.cumulative_share - out.share
    out["abc"] = np.select([prior.lt(.8), prior.lt(.95)], ["A", "B"], default="C")
    out.loc[out.share.isna(), "abc"] = "Unclassified"
    return out


def government_sql_summary(data):
    with duckdb.connect() as connection:
        connection.register("government", data)
        query = (Path(__file__).resolve().parents[1] / "sql/05_government_spend.sql").read_text(encoding="utf-8")
        return connection.execute(query).fetchdf().iloc[0].to_dict()
