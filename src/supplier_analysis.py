"""Observed practice-data metrics; no invented SLA or received quantities."""
import numpy as np
import pandas as pd


def supplier_metrics(data, category=None, *, ordered_equals_received=False):
    subset = data.loc[data.valid_order]
    if category is not None:
        subset = subset.loc[subset.Item_Category.eq(category)]
    rows = []
    for supplier, group in subset.groupby("Supplier", dropna=False):
        observed = group.observed_defective_units.notna()
        denominator = group.loc[observed, "Quantity"].sum()
        defects = group.observed_defective_units.sum(min_count=1)
        rate = defects / denominator if ordered_equals_received and denominator > 0 else np.nan
        delivered = group.Order_Status.eq("Delivered")
        delivered_orders = int(delivered.sum())
        delivery_samples = int(group.delivery_days.notna().sum())
        compliance_samples = int(group.compliant.notna().sum())
        noncompliant = int(group.compliant.eq(0).sum())
        missing_dates = int((delivered & group.Delivery_Date.isna()).sum())
        invalid_chronology = int((delivered & group.Delivery_Date.notna() & group.delivery_days.isna()).sum())
        notes = []
        if missing_dates:
            notes.append(f"已交付缺少日期{missing_dates}条")
        if invalid_chronology:
            notes.append(f"已交付日期先后异常{invalid_chronology}条")
        if delivery_samples < 5:
            notes.append("周期有效样本少于5")
        if noncompliant:
            notes.append(f"合规标记No共{noncompliant}条，需核实定义")
        if int(observed.sum()) < delivered_orders:
            notes.append("已交付缺陷记录不完整")
        rows.append({"Supplier": supplier, "Item_Category": category if category is not None else "ALL_CATEGORIES_DESCRIPTIVE_ONLY", "orders": len(group),
                     "amount": group.amount.sum(), "delivery_samples": int(group.delivery_days.notna().sum()),
                     "delivery_days": group.delivery_days.mean(), "delivery_days_std": group.delivery_days.std(),
                     "delivered_orders": delivered_orders,
                     "delivery_coverage": delivery_samples / delivered_orders if delivered_orders else np.nan,
                     "missing_delivered_dates": missing_dates, "invalid_delivered_chronology": invalid_chronology,
                     "compliance_samples": compliance_samples, "noncompliant_records": noncompliant,
                     "compliance_rate": group.compliant.mean(),
                     "quality_samples": int(observed.sum()), "observed_defective_units": defects,
                     "quality_record_coverage": int(observed.sum()) / delivered_orders if delivered_orders else np.nan,
                     "defect_rate_proxy": rate,
                     "quality_denominator_if_assumed": denominator if ordered_equals_received else np.nan,
                     "quality_basis": "ordered_equals_received assumption" if ordered_equals_received else "denominator unverified",
                     "watch_notes": ";".join(notes) or "当前规则未发现需关注的记录缺口"})
    return pd.DataFrame(rows)
