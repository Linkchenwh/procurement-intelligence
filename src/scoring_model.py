"""Transparent exploratory ranking within an explicitly confirmed comparison cohort."""
import numpy as np
import pandas as pd

DIRECTIONS = {"delivery_days": "lower", "compliance_rate": "higher", "defect_rate_proxy": "lower"}
SAMPLES = {"delivery_days": "delivery_samples", "compliance_rate": "compliance_samples", "defect_rate_proxy": "quality_samples"}


def score_suppliers(metrics, weights, *, comparable=False, min_samples=5, min_compliance=0.):
    if not comparable or metrics.empty or metrics.Item_Category.nunique() != 1 or metrics.Item_Category.eq("ALL_CATEGORIES_DESCRIPTIVE_ONLY").any():
        raise ValueError("仅允许明确确认可比的单一品类队列进行探索性评分")
    if min_samples < 1 or not np.isfinite(min_compliance) or not 0 <= min_compliance <= 1:
        raise ValueError("样本数必须 >=1，合规门槛必须介于0和1")
    if not weights or set(weights) - DIRECTIONS.keys():
        raise ValueError("仅支持已定义且有依据的维度；当前不支持跨商品成本评分")
    if any(not np.isfinite(v) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("权重必须非负、有限，且至少一个大于0")
    weights = {k: v / sum(weights.values()) for k, v in weights.items() if v > 0}
    result = metrics.copy()
    eligible = result.orders.ge(min_samples)
    for metric in weights:
        if metric not in result or SAMPLES[metric] not in result:
            raise ValueError(f"缺少评分维度或样本数: {metric}")
        eligible &= np.isfinite(result[metric]) & result[SAMPLES[metric]].ge(min_samples)
    if min_compliance > 0:
        eligible &= result.compliance_rate.ge(min_compliance) & result.compliance_samples.ge(min_samples)
    result["eligible"] = eligible
    result["eligibility_note"] = np.where(eligible, "通过分析准入", "样本不足、维度缺失或未达合规门槛")
    result["score"] = np.nan
    if eligible.sum() >= 2:
        result.loc[eligible, "score"] = 0.
        for metric, weight in weights.items():
            values = result.loc[eligible, metric].astype(float)
            span = values.max() - values.min()
            normalized = pd.Series(50., index=values.index) if span == 0 else (values - values.min()) / span * 100
            if DIRECTIONS[metric] == "lower" and span != 0:
                normalized = 100 - normalized
            result.loc[eligible, metric + "_score"] = normalized
            result.loc[eligible, "score"] += weight * normalized
    else:
        result.loc[eligible, "eligibility_note"] = "可评分供应商不足2家，不生成排名"
    result["rank"] = result.score.rank(method="min", ascending=False)
    return result.sort_values(["rank", "Supplier"], na_position="last").reset_index(drop=True)


def sensitivity(metrics, scenarios, **kwargs):
    outputs = []
    for name, weights in scenarios.items():
        result = score_suppliers(metrics, weights, comparable=True, **kwargs)
        result["scenario"] = name
        outputs.append(result)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
