"""Normalize only explicit packaging facts and separate specification from procurement comparability."""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

QUOTE_COLUMNS = ["quote_id", "brand", "product_name", "sku", "seller", "channel", "paper_size", "gsm",
                 "sheets_per_ream", "reams_per_box", "price", "currency", "quote_unit", "min_order_units",
                 "max_order_units", "shipping_cost", "shipping_terms", "tax_status", "region", "lead_time_days",
                 "collected_at", "url", "data_status"]


def normalize_quotes(frame, *, as_of=None, freshness_days=30):
    missing = set(QUOTE_COLUMNS) - set(frame)
    if missing:
        raise ValueError("报价表缺少字段: " + ", ".join(sorted(missing)))
    data = frame.copy().reset_index(drop=True)
    if data.quote_id.isna().any() or data.quote_id.astype(str).str.strip().eq("").any() or data.quote_id.duplicated().any():
        raise ValueError("quote_id 必须非空且唯一")
    for column in ["gsm", "sheets_per_ream", "reams_per_box", "price", "min_order_units", "max_order_units", "shipping_cost", "lead_time_days"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").astype(float)
        data.loc[~np.isfinite(data[column]) | data[column].lt(0), column] = np.nan
    for column in ["paper_size", "currency"]:
        data[column] = data[column].astype("string").str.strip().str.upper()
    for column in ["quote_unit", "tax_status", "data_status"]:
        data[column] = data[column].astype("string").str.strip().str.lower()
    for column in ["sheets_per_ream", "reams_per_box", "min_order_units", "max_order_units"]:
        data.loc[data[column].le(0) | data[column].mod(1).ne(0), column] = np.nan
    data["reams_per_unit"] = np.where(data.quote_unit.eq("ream"), 1.,
                                      np.where(data.quote_unit.eq("box"), data.reams_per_box, np.nan))
    data["price_per_500"] = data.price * 500 / (data.reams_per_unit * data.sheets_per_ream)
    data["spec_comparable"] = (data.paper_size.eq("A4") & data.gsm.eq(80) & data.sheets_per_ream.eq(500)
                               & data.price.gt(0) & np.isfinite(data.price_per_500)).fillna(False)
    if "packaging_conflict" in data:
        conflict = data.packaging_conflict.astype("string").str.lower().isin(["true", "1", "yes"])
        data.loc[conflict, "spec_comparable"] = False
    data.loc[~data.spec_comparable, "price_per_500"] = np.nan
    today = pd.Timestamp(as_of or datetime.now(ZoneInfo("Asia/Shanghai")).date()).tz_localize(None).normalize()
    collected = pd.to_datetime(data.collected_at, errors="coerce", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()
    data["quote_age_days"] = (today - collected).dt.days
    data["fresh_observation"] = data.quote_age_days.between(0, freshness_days).fillna(False)
    data["source_link_present"] = data.url.astype("string").str.match(r"^https?://[^/\s]+(?:/|$)").fillna(False)
    data["evidence_note"] = np.where(data.spec_comparable, "仅基础规格可比；税运费/MOQ/库存/数量阶梯价仍需核对", "规格或计价单位不足，不比较标准单价")
    return data
