"""Strict order-level validation; preserve anomalies for review."""
import numpy as np
import pandas as pd

PERFORMANCE_COLUMNS = ["PO_ID", "Supplier", "Order_Date", "Delivery_Date", "Item_Category",
                       "Order_Status", "Quantity", "Unit_Price", "Negotiated_Price",
                       "Defective_Units", "Compliance"]
STATUSES = {"delivered": "Delivered", "pending": "Pending", "cancelled": "Cancelled",
            "partially delivered": "Partially Delivered"}


def clean_performance(frame):
    missing = sorted(set(PERFORMANCE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError("缺少字段: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("采购表没有数据行")
    data = frame.copy().reset_index(drop=True)
    audit = {"input_rows": len(data), "output_rows": len(data), "grain": "one PO_ID per row"}
    for column in ["PO_ID", "Supplier", "Item_Category", "Order_Status"]:
        data[column] = data[column].astype("string").str.strip()
        if (data[column].isna() | data[column].eq("")).any():
            raise ValueError(f"{column} 含空值")
    if data.PO_ID.duplicated().any():
        raise ValueError("PO_ID 重复；模板要求每订单一行，请先核实粒度，不自动删除")
    data["Order_Status"] = data.Order_Status.str.lower().map(STATUSES)
    if data.Order_Status.isna().any():
        raise ValueError("Order_Status 仅支持 Delivered/Pending/Cancelled/Partially Delivered")
    for column in ["Quantity", "Unit_Price", "Negotiated_Price"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").astype(float)
        if (~np.isfinite(data[column]) | data[column].lt(0)).any():
            raise ValueError(f"{column} 必须是有限的非负数")
    if data.Quantity.le(0).any() or data.Quantity.mod(1).ne(0).any():
        raise ValueError("Quantity 必须为正整数；这是订单练习模板的单位约定")
    data["Order_Date"] = pd.to_datetime(data.Order_Date, errors="coerce", format="mixed")
    if data.Order_Date.isna().any():
        raise ValueError("Order_Date 含缺失或无法解析的日期")
    original_delivery = data.Delivery_Date.replace(r"^\s*$", pd.NA, regex=True)
    data["Delivery_Date"] = pd.to_datetime(original_delivery, errors="coerce", format="mixed")
    audit["invalid_delivery_date"] = int((original_delivery.notna() & data.Delivery_Date.isna()).sum())
    days = (data.Delivery_Date - data.Order_Date).dt.total_seconds() / 86400
    audit["negative_delivery_days"] = int(days.lt(0).sum())
    audit["delivered_missing_date"] = int((data.Order_Status.eq("Delivered") & data.Delivery_Date.isna()).sum())
    audit["non_delivered_with_date"] = int((~data.Order_Status.eq("Delivered") & data.Delivery_Date.notna()).sum())
    data["delivery_days"] = days.where(days.ge(0) & data.Order_Status.eq("Delivered"))
    defects = pd.to_numeric(data.Defective_Units, errors="coerce").astype(float)
    valid_defect = np.isfinite(defects) & defects.ge(0) & defects.le(data.Quantity) & defects.mod(1).eq(0)
    audit["invalid_defect_records"] = int((data.Defective_Units.notna() & ~valid_defect).sum())
    data["observed_defective_units"] = defects.where(valid_defect & data.Order_Status.eq("Delivered"))
    compliance = data.Compliance.astype("string").str.strip().str.lower()
    data["compliant"] = compliance.map({"yes": 1., "no": 0., "compliant": 1., "non-compliant": 0.,
                                         "true": 1., "false": 0.})
    audit["unknown_compliance"] = int(data.compliant.isna().sum())
    data["amount"] = data.Quantity * data.Negotiated_Price
    data["baseline_amount"] = data.Quantity * data.Unit_Price
    if (~np.isfinite(data.amount) | ~np.isfinite(data.baseline_amount)).any():
        raise ValueError("数量乘单价超出有效数值范围")
    data["valid_order"] = ~data.Order_Status.eq("Cancelled")
    data["delivered_order"] = data.Order_Status.eq("Delivered")
    data["source_domain"] = "performance_practice"
    return data, audit
