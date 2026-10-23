"""Demand is hypothetical. Unknown procurement conditions never silently become zero."""
import math

import numpy as np
import pandas as pd

from src.market_benchmark import normalize_quotes


def sourcing_scenario(quotes, demand_reams, *, budget=None, currency="CNY", region="深圳", max_lead_days=None,
                      include_shipping=True, only_tax_included=False, as_of=None):
    if not np.isfinite(demand_reams) or demand_reams <= 0 or int(demand_reams) != demand_reams:
        raise ValueError("需求包数必须为有限正整数（每包500张）")
    if budget is not None and (not np.isfinite(budget) or budget < 0):
        raise ValueError("预算必须为有限非负数")
    if max_lead_days is not None and (not np.isfinite(max_lead_days) or max_lead_days < 0):
        raise ValueError("交付天数上限必须为有限非负数")
    data = normalize_quotes(quotes, as_of=as_of)
    rows = []
    for _, row in data.iterrows():
        notes = []
        spec = bool(row.spec_comparable)
        units = math.ceil(demand_reams / row.reams_per_unit) if spec else np.nan
        if spec and pd.notna(row.min_order_units):
            units = max(units, int(row.min_order_units))
        if pd.isna(row.min_order_units):
            notes.append("起订量未知")
        if pd.isna(row.max_order_units):
            notes.append("该标价适用数量上限未知")
        elif spec and units > row.max_order_units:
            notes.append("超过已核实价格数量区间")
        if not spec:
            notes.append("规格/单位不可比")
        same_currency = str(row.currency) == currency
        if not same_currency:
            notes.append("币种不同")
        if str(row.region).strip() != region.strip():
            notes.append("目标地区适用性未核实")
        if not row.fresh_observation:
            notes.append("报价过期或日期无效")
        if not row.source_link_present or row.data_status != "observed_public_page":
            notes.append("来源未核实")
        if row.tax_status != "included":
            notes.append("当前标价含税未核实")
        if include_shipping and pd.isna(row.shipping_cost):
            notes.append("本情景运费未知")
        if not include_shipping:
            notes.append("未计运费，非到货总成本")
        if max_lead_days is not None and (pd.isna(row.lead_time_days) or row.lead_time_days > max_lead_days):
            notes.append("目标交付条件未满足或未知")
        goods = float(units * row.price) if spec else np.nan
        total = goods + row.shipping_cost if not notes else np.nan
        out = row.to_dict()
        out.update({"requested_reams": demand_reams, "purchase_units": units,
                    "supplied_reams": units * row.reams_per_unit if spec else np.nan,
                    "goods_reference_cost": goods, "total_cost": total,
                    "budget_difference": budget - total if budget is not None and pd.notna(total) else np.nan,
                    "scenario_comparable": not notes,
                    "limitations": ";".join(notes) or "在录入报价条件下测算；下单前仍需确认",
                    "calculation_basis": "数量×观察标价的线性假设；未知阶梯价不视为已验证采购成本"})
        rows.append(out)
    result = pd.DataFrame(rows)
    if not result.empty:
        if only_tax_included:
            result = result.loc[result.tax_status.eq("included")].copy()
        result["rank"] = result.total_cost.rank(method="min")
        result = result.sort_values(["rank", "quote_id"], na_position="last")
    return result
