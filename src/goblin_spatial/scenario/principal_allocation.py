"""Principal SC1 allocation policies from the validated v2.1 study script.

This module preserves the category-consistent incidence experiment used by the
mature SC1 workflow. Dairy and suckler endpoints are allocated independently.
Protection policies redistribute contraction only; category expansion remains
PRORATA. No policy can seed a new adult-category footprint.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.reconciliation import hamilton_allocate
from goblin_spatial.scenario.allocation import _bounded_integer_allocate

PRINCIPAL_PROTECTION_STRENGTH = 0.50
PRINCIPAL_ALLOCATION_POLICIES = (
    "PRORATA",
    "DAIRY_PROTECTION",
    "ECONOMIC_CAPACITY_PROTECTION",
    "SOCIAL_VULNERABILITY_PROTECTION",
)


def _series(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return pd.to_numeric(frame[name], errors="raise")
    raise ValueError(f"principal SC1 baseline missing one of: {names}")


def rank01(values: pd.Series, eligible: pd.Series) -> pd.Series:
    """Average-rank percentile scaled exactly to [0, 1] over eligible rows."""
    x = pd.to_numeric(values, errors="coerce")
    e = pd.Series(eligible, index=values.index).astype(bool)
    if x[e].isna().any():
        raise ValueError(f"score input has {int(x[e].isna().sum())} missing eligible values")
    out = pd.Series(0.0, index=values.index, dtype=float)
    n = int(e.sum())
    if n == 0:
        return out
    if n == 1:
        out.loc[e] = 0.5
        return out
    ranks = x.loc[e].rank(method="average", ascending=True)
    out.loc[e] = (ranks - 1.0) / float(n - 1)
    return out.clip(0.0, 1.0)


def build_principal_baseline_scores(baseline: pd.DataFrame) -> pd.DataFrame:
    """Freeze the three validated pre-scenario protection scores."""
    out = baseline.copy()
    base_d = _series(out, "dairy_cows", "DAIRY_COW")
    base_s = _series(out, "suckler_cows", "OTHER_COW")
    adults = base_d + base_s
    active = adults > 0

    out["BASE_ADULT_COWS"] = adults
    out["BASE_DAIRY_SHARE_OF_ADULT_COWS"] = np.divide(
        base_d,
        adults,
        out=np.zeros(len(out), dtype=float),
        where=adults.to_numpy(dtype=float) > 0,
    )

    dairy_positive = base_d > 0
    share_rank = rank01(out["BASE_DAIRY_SHARE_OF_ADULT_COWS"], dairy_positive)
    scale_rank = rank01(base_d, dairy_positive)
    dairy_strength = 0.5 * share_rank + 0.5 * scale_rank
    dairy_strength.loc[~dairy_positive] = 0.0
    out["DAIRY_ORIENTATION_SCORE"] = share_rank
    out["DAIRY_SCALE_SCORE"] = scale_rank
    out["DAIRY_STRENGTH_SCORE"] = dairy_strength.clip(0.0, 1.0)

    holdings = _series(out, "AGRICULTURAL_HOLDINGS")
    grass = _series(out, "ALL_GRASSLAND")
    base_so = _series(
        out,
        "SO_LIVESTOCK_2020_EUR",
        "BASE_LIVESTOCK_SO_EUR",
        "BASE_SO_LIVESTOCK_2020_EUR",
    )
    out["BASE_LIVESTOCK_SO_EUR"] = base_so
    out["BASE_LIVESTOCK_SO_PER_HOLDING_EUR"] = np.divide(
        base_so,
        holdings,
        out=np.full(len(out), np.nan, dtype=float),
        where=holdings.to_numpy(dtype=float) > 0,
    )
    out["BASE_LIVESTOCK_SO_PER_GRASSLAND_HA_EUR"] = np.divide(
        base_so,
        grass,
        out=np.full(len(out), np.nan, dtype=float),
        where=grass.to_numpy(dtype=float) > 0,
    )
    for column in (
        "BASE_LIVESTOCK_SO_PER_HOLDING_EUR",
        "BASE_LIVESTOCK_SO_PER_GRASSLAND_HA_EUR",
    ):
        if out.loc[active, column].isna().any():
            raise AssertionError(f"economic score undefined for active cattle ED: {column}")

    so_hold_rank = rank01(out["BASE_LIVESTOCK_SO_PER_HOLDING_EUR"], active)
    so_ha_rank = rank01(out["BASE_LIVESTOCK_SO_PER_GRASSLAND_HA_EUR"], active)
    economic_capacity = 0.5 * so_hold_rank + 0.5 * so_ha_rank
    economic_vulnerability = 1.0 - economic_capacity
    economic_capacity.loc[~active] = 0.0
    economic_vulnerability.loc[~active] = 0.0
    out["ECON_SO_PER_HOLDING_SCORE"] = so_hold_rank
    out["ECON_SO_PER_GRASSLAND_HA_SCORE"] = so_ha_rank
    out["ECONOMIC_CAPACITY_SCORE"] = economic_capacity.clip(0.0, 1.0)
    out["ECONOMIC_VULNERABILITY_SCORE"] = economic_vulnerability.clip(0.0, 1.0)

    age = _series(out, "MEDIAN_AGE_OF_HOLDER")
    size = _series(out, "AVERAGE_SIZE_OF_HOLDINGS")
    age_vulnerability = rank01(age, active)
    size_capacity = rank01(size, active)
    small_holding_vulnerability = 1.0 - size_capacity
    social_vulnerability = 0.5 * age_vulnerability + 0.5 * small_holding_vulnerability
    age_vulnerability.loc[~active] = 0.0
    small_holding_vulnerability.loc[~active] = 0.0
    social_vulnerability.loc[~active] = 0.0
    out["OLDER_HOLDER_VULNERABILITY_SCORE"] = age_vulnerability.clip(0.0, 1.0)
    out["SMALL_HOLDING_VULNERABILITY_SCORE"] = small_holding_vulnerability.clip(0.0, 1.0)
    out["SOCIAL_VULNERABILITY_SCORE"] = social_vulnerability.clip(0.0, 1.0)

    for column in (
        "DAIRY_STRENGTH_SCORE",
        "ECONOMIC_VULNERABILITY_SCORE",
        "SOCIAL_VULNERABILITY_SCORE",
    ):
        values = pd.to_numeric(out.loc[active, column], errors="raise")
        if values.isna().any() or (values < -1e-12).any() or (values > 1.0 + 1e-12).any():
            raise AssertionError(f"invalid principal protection score: {column}")
    return out


def policy_score_array(frame: pd.DataFrame, policy: str) -> np.ndarray:
    policy = str(policy).upper()
    if policy == "PRORATA":
        return np.zeros(len(frame), dtype=float)
    column = {
        "DAIRY_PROTECTION": "DAIRY_STRENGTH_SCORE",
        "ECONOMIC_CAPACITY_PROTECTION": "ECONOMIC_VULNERABILITY_SCORE",
        "SOCIAL_VULNERABILITY_PROTECTION": "SOCIAL_VULNERABILITY_SCORE",
    }.get(policy)
    if column is None:
        raise ValueError(f"not a principal SC1 allocation policy: {policy}")
    return pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)


def allocate_category_endpoint(
    base_counts: np.ndarray,
    target_total: int,
    protection_score: np.ndarray,
    policy: str,
    category: str,
    *,
    protection_strength: float = PRINCIPAL_PROTECTION_STRENGTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """Allocate one exact adult-category endpoint over its existing ED footprint."""
    base = np.asarray(base_counts, dtype=np.int64)
    score = np.asarray(protection_score, dtype=float)
    target_total = int(target_total)
    base_total = int(base.sum())
    policy = str(policy).upper()

    if policy not in PRINCIPAL_ALLOCATION_POLICIES:
        raise ValueError(f"unsupported principal allocation policy: {policy}")
    if target_total < 0:
        raise ValueError(f"{category}: target cannot be negative")
    if base_total == 0 and target_total > 0:
        raise ValueError(f"{category}: positive target has no baseline spatial footprint")
    if (~np.isfinite(score)).any() or (score < -1e-12).any() or (score > 1.0 + 1e-12).any():
        raise ValueError(f"{category}: invalid protection score")
    strength = float(protection_strength)
    if not 0.0 <= strength < 1.0:
        raise ValueError("protection_strength must lie in [0, 1)")

    eligible = base > 0
    burden_factor = np.ones(len(base), dtype=float)
    if target_total == base_total:
        return base.copy(), np.zeros(len(base), dtype=np.int64), burden_factor, "UNCHANGED"

    if policy == "PRORATA" or target_total > base_total:
        scenario = hamilton_allocate(base.astype(float), target_total)
        if (scenario[~eligible] != 0).any():
            raise AssertionError(f"{category}: PRORATA seeded a new footprint")
        reductions = base - scenario
        if target_total > base_total:
            mode = (
                "PRORATA_EXPANSION"
                if policy == "PRORATA"
                else "PRORATA_EXPANSION_UNDER_PROTECTION_POLICY"
            )
        else:
            mode = "PRORATA_CONTRACTION"
        return scenario.astype(np.int64), reductions.astype(np.int64), burden_factor, mode

    reduction_total = base_total - target_total
    burden_factor = np.clip(1.0 - strength * score, 1.0 - strength, 1.0)
    weights = base.astype(float) * burden_factor
    reductions = _bounded_integer_allocate(weights, base, reduction_total)
    scenario = base - reductions
    if int(scenario.sum()) != target_total:
        raise AssertionError(f"{category}: exact national endpoint failed")
    if (scenario < 0).any() or (scenario[~eligible] != 0).any():
        raise AssertionError(f"{category}: invalid protected-contraction allocation")
    return scenario.astype(np.int64), reductions.astype(np.int64), burden_factor, "PROTECTED_CONTRACTION"
