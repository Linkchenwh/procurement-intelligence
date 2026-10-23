"""Spend metrics over normalized order rows, with an independent DuckDB check."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


def spend_summary(data):
    valid = data.loc[data.valid_order]
    supplier = valid.groupby("Supplier", dropna=False).amount.sum().sort_values(ascending=False)
    total = float(valid.amount.sum())
    shares = supplier / total if total > 0 else supplier * np.nan
    return {
        "raw_amount": float(data.amount.sum()), "valid_amount": total,
        "cancelled_amount": float(data.loc[~data.valid_order, "amount"].sum()),
        "delivered_amount": float(data.loc[data.delivered_order, "amount"].sum()),
        "order_count": int(data.PO_ID.nunique()), "valid_order_count": int(valid.PO_ID.nunique()),
        "supplier_count": int(valid.Supplier.nunique()),
        "nominal_price_difference": float((valid.baseline_amount - valid.amount).sum()),
        "top1_share": float(shares.iloc[0]) if len(shares) else None,
        "top5_share": float(shares.head(5).sum()) if total > 0 else None,
        "hhi": float((shares ** 2).sum() * 10000) if total > 0 else None,
    }


def spend_breakdown(data, column):
    valid = data.loc[data.valid_order]
    out = valid.groupby(column, dropna=False).agg(amount=("amount", "sum"), orders=("PO_ID", "nunique")).reset_index()
    out = out.sort_values(["amount", column], ascending=[False, True], kind="stable").reset_index(drop=True)
    total = out.amount.sum()
    out["share"] = out.amount / total if total > 0 else np.nan
    out["cumulative_share"] = out.share.cumsum()
    # Boundary-crossing supplier stays in the earlier class, including first large supplier.
    prior = out.cumulative_share - out.share
    out["abc"] = np.select([prior.lt(.8), prior.lt(.95)], ["A", "B"], default="C")
    out.loc[out.share.isna(), "abc"] = "Unclassified"
    return out


def monthly_spend(data):
    valid = data.loc[data.valid_order].copy()
    valid["month"] = valid.Order_Date.dt.to_period("M").astype(str)
    return valid.groupby("month", as_index=False).agg(amount=("amount", "sum"), orders=("PO_ID", "nunique"))


def sql_summary(data):
    with duckdb.connect() as connection:
        connection.register("orders", data)
        sql = (Path(__file__).resolve().parents[1] / "sql/02_spend_analysis.sql").read_text(encoding="utf-8")
        return connection.execute(sql).fetchdf().iloc[0].to_dict()
