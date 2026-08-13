"""Allocate an absolute adult-cattle endpoint across the existing ED footprint."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.scenario.allocation import _allocate_reduction_total, _rule_cut_weights
from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.endpoint_composition import reconcile_endpoint_composition
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls


def _integer(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def allocate_adult_endpoint(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule = AllocationRule.PRORATA,
    random_seed: int = 42,
    score_column: str | None = None,
    productivity_score_column: str | None = None,
    vulnerability_score_column: str | None = None,
    protection_strength: float = 0.8,
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15),
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Allocate total adult contraction, then impose exact pathway composition."""

    baseline = select_baseline_year(panel, controls.baseline_year, expected_eds=expected_eds)
    for column in ("DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"):
        if column not in baseline.columns:
            raise ValueError(f"adult endpoint allocation requires {column}")

    base_dairy = _integer(baseline, "DAIRY_COW")
    base_suckler = _integer(baseline, "OTHER_COW")
    base_adults = base_dairy + base_suckler
    milestone = controls.milestone(controls.target_year)
    target_dairy = int(milestone.dairy_cows)
    target_suckler = int(milestone.suckler_cows)
    target_adults = target_dairy + target_suckler
    baseline_adults = int(base_adults.sum())
    if target_adults > baseline_adults:
        raise ValueError("principal pathway requires an overall adult-cow contraction")

    rule = ScenarioDefinition(
        name=controls.scenario_id,
        baseline_year=controls.baseline_year,
        target_year=controls.target_year,
        allocation_rule=allocation_rule,
        random_seed=int(random_seed),
        score_column=score_column,
        productivity_score_column=productivity_score_column,
        vulnerability_score_column=vulnerability_score_column,
        protection_strength=float(protection_strength),
        hybrid_weights=hybrid_weights,
    )
    cut_weights, protection_score = _rule_cut_weights(baseline, base_adults, rule)
    preferred_retained, _ = _allocate_reduction_total(
        base_adults, baseline_adults - target_adults, cut_weights
    )
    scenario_dairy, scenario_suckler = reconcile_endpoint_composition(
        base_dairy,
        base_suckler,
        preferred_retained,
        target_dairy=target_dairy,
        target_suckler=target_suckler,
    )
    scenario_adults = scenario_dairy + scenario_suckler
    adult_reductions = base_adults - scenario_adults

    out = baseline.copy()
    out.insert(0, "SCENARIO_NAME", controls.scenario_id)
    out.insert(1, "SCENARIO_BASELINE_YEAR", int(controls.baseline_year))
    out.insert(2, "SCENARIO_TARGET_YEAR", int(controls.target_year))
    out.insert(3, "SCENARIO_ALLOCATION_RULE", allocation_rule.value)
    out["BASE_DAIRY_COW"] = base_dairy
    out["BASE_OTHER_COW"] = base_suckler
    out["BASE_ADULT_COWS"] = base_adults
    out["SCENARIO_DAIRY_COW"] = scenario_dairy
    out["SCENARIO_OTHER_COW"] = scenario_suckler
    out["SCENARIO_ADULT_COWS"] = scenario_adults
    out["CHANGE_DAIRY_COW"] = scenario_dairy - base_dairy
    out["CHANGE_OTHER_COW"] = scenario_suckler - base_suckler
    out["REDUCTION_ADULT_COWS"] = adult_reductions
    out["REDUCTION_PCT_ADULT_COWS"] = np.divide(
        100.0 * adult_reductions.astype(float), base_adults.astype(float),
        out=np.zeros(len(base_adults)), where=base_adults > 0,
    )
    out["PREFERRED_SCENARIO_ADULT_COWS"] = preferred_retained
    out["CUT_WEIGHT_ADULT_COWS"] = cut_weights
    if protection_score is not None:
        out["PROTECTION_SCORE_ADULT_COWS"] = protection_score
    sheep = _integer(baseline, "TOTAL_SHEEP")
    out["BASE_TOTAL_SHEEP"] = sheep
    out["SCENARIO_TOTAL_SHEEP"] = sheep

    active = base_adults > 0
    if ((adult_reductions[active] <= 0)).any():
        raise AssertionError("an adult-cattle ED was exempted from the pathway contraction")
    if int(scenario_dairy.sum()) != target_dairy or int(scenario_suckler.sum()) != target_suckler:
        raise AssertionError("national adult endpoint failed exact closure")
    return out
