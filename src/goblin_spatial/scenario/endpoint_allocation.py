"""Allocate exact dairy and suckler endpoints across their existing ED footprints.

This is the principal SC1 allocation used by the mature v2.1 study. Dairy and
suckler categories are treated separately because a pathway can expand one
category while contracting the other. Protection policies redistribute only a
fixed national contraction. Expansion remains PRORATA and no new category
footprint is seeded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from goblin_spatial.scenario.principal_allocation import (
    PRINCIPAL_ALLOCATION_POLICIES,
    PRINCIPAL_PROTECTION_STRENGTH,
    allocate_category_endpoint,
    build_principal_baseline_scores,
    policy_score_array,
)


def _integer(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def _adult_columns(baseline: pd.DataFrame) -> tuple[str, str]:
    dairy = "dairy_cows" if "dairy_cows" in baseline.columns else "DAIRY_COW"
    suckler = "suckler_cows" if "suckler_cows" in baseline.columns else "OTHER_COW"
    for column in (dairy, suckler, "TOTAL_SHEEP"):
        if column not in baseline.columns:
            raise ValueError(f"adult endpoint allocation requires {column}")
    return dairy, suckler


def allocate_adult_endpoint(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule = AllocationRule.PRORATA,
    random_seed: int = 42,
    score_column: str | None = None,
    productivity_score_column: str | None = None,
    vulnerability_score_column: str | None = None,
    protection_strength: float = PRINCIPAL_PROTECTION_STRENGTH,
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15),
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Allocate exact national adult-category endpoints using principal SC1 rules.

    The unused generic-rule arguments are retained in the function signature for
    API compatibility. The principal endpoint deliberately accepts only the four
    validated policies in ``PRINCIPAL_ALLOCATION_POLICIES``.
    """

    del random_seed, score_column, productivity_score_column, vulnerability_score_column, hybrid_weights

    policy = allocation_rule.value
    if policy not in PRINCIPAL_ALLOCATION_POLICIES:
        raise ValueError(
            f"{policy} is not a validated principal SC1 policy; "
            f"choose one of {PRINCIPAL_ALLOCATION_POLICIES}"
        )

    baseline = select_baseline_year(
        panel,
        controls.baseline_year,
        expected_eds=expected_eds,
    )
    dairy_col, suckler_col = _adult_columns(baseline)

    # Protection scores are frozen from the selected baseline before any scenario
    # allocation. Stage-08 fixed-2020 SO is part of the economic-capacity score.
    scored = build_principal_baseline_scores(baseline)
    base_dairy = _integer(scored, dairy_col)
    base_suckler = _integer(scored, suckler_col)
    base_adults = base_dairy + base_suckler

    # The aggregate adult fields, when present, must reproduce the cohort adults.
    if "DAIRY_COW" in scored.columns:
        if not np.array_equal(_integer(scored, "DAIRY_COW"), base_dairy):
            raise AssertionError("DAIRY_COW disagrees with dairy_cows in selected baseline")
    if "OTHER_COW" in scored.columns:
        if not np.array_equal(_integer(scored, "OTHER_COW"), base_suckler):
            raise AssertionError("OTHER_COW disagrees with suckler_cows in selected baseline")

    milestone = controls.milestone(controls.target_year)
    target_dairy = int(milestone.dairy_cows)
    target_suckler = int(milestone.suckler_cows)
    score = policy_score_array(scored, policy)

    scenario_dairy, dairy_reduction_signed, dairy_burden, dairy_mode = allocate_category_endpoint(
        base_dairy,
        target_dairy,
        score,
        policy,
        "DAIRY",
        protection_strength=float(protection_strength),
    )
    scenario_suckler, suckler_reduction_signed, suckler_burden, suckler_mode = allocate_category_endpoint(
        base_suckler,
        target_suckler,
        score,
        policy,
        "SUCKLER",
        protection_strength=float(protection_strength),
    )
    scenario_adults = scenario_dairy + scenario_suckler

    if int(scenario_dairy.sum()) != target_dairy:
        raise AssertionError("national dairy endpoint failed exact closure")
    if int(scenario_suckler.sum()) != target_suckler:
        raise AssertionError("national suckler endpoint failed exact closure")
    if ((base_dairy == 0) & (scenario_dairy > 0)).any():
        raise AssertionError("principal allocation seeded a new dairy footprint")
    if ((base_suckler == 0) & (scenario_suckler > 0)).any():
        raise AssertionError("principal allocation seeded a new suckler footprint")

    out = scored.copy()
    out.insert(0, "SCENARIO_NAME", controls.scenario_id)
    out.insert(1, "SCENARIO_BASELINE_YEAR", int(controls.baseline_year))
    out.insert(2, "SCENARIO_TARGET_YEAR", int(controls.target_year))
    out.insert(3, "SCENARIO_ALLOCATION_RULE", policy)
    out["ALLOCATION_POLICY"] = policy
    out["PROTECTION_STRENGTH_LAMBDA"] = float(protection_strength)
    out["POLICY_PROTECTION_SCORE"] = score
    out["DAIRY_BURDEN_FACTOR"] = dairy_burden
    out["SUCKLER_BURDEN_FACTOR"] = suckler_burden
    out["DAIRY_ALLOCATION_MODE"] = dairy_mode
    out["SUCKLER_ALLOCATION_MODE"] = suckler_mode

    out["BASE_DAIRY_COW"] = base_dairy
    out["BASE_OTHER_COW"] = base_suckler
    out["BASE_ADULT_COWS"] = base_adults
    out["SCENARIO_DAIRY_COW"] = scenario_dairy
    out["SCENARIO_OTHER_COW"] = scenario_suckler
    out["SCENARIO_ADULT_COWS"] = scenario_adults
    out["CHANGE_DAIRY_COW"] = scenario_dairy - base_dairy
    out["CHANGE_OTHER_COW"] = scenario_suckler - base_suckler
    out["CHANGE_ADULT_COWS"] = scenario_adults - base_adults

    out["DAIRY_REDUCTION_HEAD"] = np.maximum(0, base_dairy - scenario_dairy)
    out["SUCKLER_REDUCTION_HEAD"] = np.maximum(0, base_suckler - scenario_suckler)
    out["DAIRY_EXPANSION_HEAD"] = np.maximum(0, scenario_dairy - base_dairy)
    out["SUCKLER_EXPANSION_HEAD"] = np.maximum(0, scenario_suckler - base_suckler)
    out["ADULT_REDUCTION_HEAD"] = base_adults - scenario_adults
    out["REDUCTION_ADULT_COWS"] = np.maximum(0, base_adults - scenario_adults)
    out["ADULT_EXPANSION_HEAD"] = np.maximum(0, scenario_adults - base_adults)
    out["ADULT_REDUCTION_PCT_SIGNED"] = np.divide(
        100.0 * (base_adults - scenario_adults).astype(float),
        base_adults.astype(float),
        out=np.zeros(len(base_adults), dtype=float),
        where=base_adults > 0,
    )
    out["REDUCTION_PCT_ADULT_COWS"] = np.maximum(
        out["ADULT_REDUCTION_PCT_SIGNED"].to_numpy(dtype=float),
        0.0,
    )
    out["ADULT_BURDEN_RATE"] = np.maximum(
        out["ADULT_REDUCTION_PCT_SIGNED"].to_numpy(dtype=float) / 100.0,
        0.0,
    )

    sheep = _integer(out, "TOTAL_SHEEP")
    out["BASE_TOTAL_SHEEP"] = sheep
    out["SCENARIO_TOTAL_SHEEP"] = sheep
    return out
