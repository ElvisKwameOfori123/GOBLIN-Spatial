"""Allocate an absolute adult-cattle endpoint across the existing ED footprint.

The principal Styles/GOBLIN pathway is not necessarily a reduction in every
adult category. SI_SG, for example, has fewer adult cows overall but a slightly
higher dairy-cow total than the validated 2020/2025 ED baseline. The spatial
problem is therefore split into two exact steps:

1. allocate the *total adult-cow contraction* across every ED with adult cows;
2. reconcile the retained adult stock to the pathway's exact national dairy and
   suckler endpoint within the categories already present in each ED.

Protection changes the intensity of the total adult-cow reduction. It does not
exempt an adult-cattle ED. Category composition may shift within mixed EDs, but
the model never seeds dairy into a zero-dairy ED or sucklers into a zero-suckler
ED. Complete local adult-cattle exit is allowed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.scenario.allocation import (
    _allocate_reduction_total,
    _bounded_integer_allocate,
    _rule_cut_weights,
)
from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls


def _integer(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def _composition_reconcile(
    base_dairy: np.ndarray,
    base_suckler: np.ndarray,
    retained_adults: np.ndarray,
    *,
    target_dairy: int,
    target_suckler: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Split retained adult capacity into exact national dairy/suckler totals.

    Dairy-only and suckler-only EDs retain their original category identity.
    Mixed EDs absorb the national composition shift. Their dairy allocation is
    weighted by the baseline dairy share of retained adult capacity and bounded
    by each ED's retained adult total.
    """

    base_dairy = np.asarray(base_dairy, dtype=np.int64)
    base_suckler = np.asarray(base_suckler, dtype=np.int64)
    retained_adults = np.asarray(retained_adults, dtype=np.int64)
    target_dairy = int(target_dairy)
    target_suckler = int(target_suckler)

    if any(len(x) != len(retained_adults) for x in (base_dairy, base_suckler)):
        raise ValueError("adult arrays must have equal length")
    if (base_dairy < 0).any() or (base_suckler < 0).any() or (retained_adults < 0).any():
        raise ValueError("adult counts must be non-negative")
    if target_dairy < 0 or target_suckler < 0:
        raise ValueError("adult endpoint counts must be non-negative")
    if target_dairy + target_suckler != int(retained_adults.sum()):
        raise AssertionError(
            "adult endpoint composition does not equal retained national adult total"
        )

    had_dairy = base_dairy > 0
    had_suckler = base_suckler > 0
    dairy_only = had_dairy & ~had_suckler
    suckler_only = ~had_dairy & had_suckler
    mixed = had_dairy & had_suckler
    zero = ~had_dairy & ~had_suckler

    if (retained_adults[zero] != 0).any():
        raise AssertionError("adult allocation seeded a zero-adult ED")

    dairy = np.zeros(len(retained_adults), dtype=np.int64)
    suckler = np.zeros(len(retained_adults), dtype=np.int64)
    dairy[dairy_only] = retained_adults[dairy_only]
    suckler[suckler_only] = retained_adults[suckler_only]

    fixed_dairy = int(dairy.sum())
    fixed_suckler = int(suckler.sum())
    mixed_capacity = int(retained_adults[mixed].sum())
    dairy_needed = target_dairy - fixed_dairy
    suckler_needed = target_suckler - fixed_suckler

    if dairy_needed < 0 or suckler_needed < 0:
        raise ValueError(
            "endpoint composition is infeasible after preserving single-category ED footprints"
        )
    if dairy_needed + suckler_needed != mixed_capacity:
        raise AssertionError("mixed adult capacity does not match residual endpoint composition")
    if dairy_needed > mixed_capacity or suckler_needed > mixed_capacity:
        raise ValueError("endpoint composition exceeds mixed-ED retained capacity")

    if mixed.any():
        base_adults = base_dairy + base_suckler
        baseline_dairy_share = np.divide(
            base_dairy.astype(float),
            base_adults.astype(float),
            out=np.zeros(len(base_dairy), dtype=float),
            where=base_adults > 0,
        )
        weights = retained_adults.astype(float) * baseline_dairy_share
        mixed_dairy = _bounded_integer_allocate(
            weights[mixed],
            retained_adults[mixed],
            dairy_needed,
        )
        dairy[mixed] = mixed_dairy
        suckler[mixed] = retained_adults[mixed] - mixed_dairy

    if int(dairy.sum()) != target_dairy:
        raise AssertionError("national dairy endpoint failed exact closure")
    if int(suckler.sum()) != target_suckler:
        raise AssertionError("national suckler endpoint failed exact closure")
    if not np.array_equal(dairy + suckler, retained_adults):
        raise AssertionError("adult composition does not close to retained adult stock")
    if ((base_dairy == 0) & (dairy > 0)).any():
        raise AssertionError("dairy was seeded into a zero-dairy ED")
    if ((base_suckler == 0) & (suckler > 0)).any():
        raise AssertionError("sucklers were seeded into a zero-suckler ED")
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
    protection_strength: float = 0.8,
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15),
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Allocate one absolute GOBLIN adult endpoint across the selected baseline."""

    baseline = select_baseline_year(
        panel,
        controls.baseline_year,
        expected_eds=expected_eds,
    )
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
        raise ValueError(
            "principal endpoint requires an overall adult-cow contraction; "
            f"baseline={baseline_adults}, endpoint={target_adults}"
        )
    adult_reduction_total = baseline_adults - target_adults

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
    retained_adults, adult_reductions = _allocate_reduction_total(
        base_adults,
        adult_reduction_total,
        cut_weights,
    )
    scenario_dairy, scenario_suckler = _composition_reconcile(
        base_dairy,
        base_suckler,
        retained_adults,
        target_dairy=target_dairy,
        target_suckler=target_suckler,
    )

    out = baseline.copy()
    out.insert(0, "SCENARIO_NAME", controls.scenario_id)
    out.insert(1, "SCENARIO_BASELINE_YEAR", int(controls.baseline_year))
    out.insert(2, "SCENARIO_TARGET_YEAR", int(controls.target_year))
    out.insert(3, "SCENARIO_ALLOCATION_RULE", allocation_rule.value)

    out["BASE_DAIRY_COW"] = base_dairy
    out["BASE_OTHER_COW"] = base_suckler
    out["BASE_ADULT_COWS"] = base_adults
    out["REDUCTION_ADULT_COWS"] = adult_reductions
    out["SCENARIO_ADULT_COWS"] = retained_adults
    out["SCENARIO_DAIRY_COW"] = scenario_dairy
    out["SCENARIO_OTHER_COW"] = scenario_suckler
    out["CHANGE_DAIRY_COW"] = scenario_dairy - base_dairy
    out["CHANGE_OTHER_COW"] = scenario_suckler - base_suckler
    out["NET_REDUCTION_DAIRY_COW"] = base_dairy - scenario_dairy
    out["NET_REDUCTION_OTHER_COW"] = base_suckler - scenario_suckler
    out["REDUCTION_PCT_ADULT_COWS"] = np.divide(
        100.0 * adult_reductions.astype(float),
        base_adults.astype(float),
        out=np.zeros(len(base_adults), dtype=float),
        where=base_adults > 0,
    )
    out["CUT_WEIGHT_ADULT_COWS"] = cut_weights
    if protection_score is not None:
        out["PROTECTION_SCORE_ADULT_COWS"] = protection_score

    base_sheep = _integer(baseline, "TOTAL_SHEEP")
    out["BASE_TOTAL_SHEEP"] = base_sheep
    out["SCENARIO_TOTAL_SHEEP"] = base_sheep

    if adult_reduction_total > 0:
        eligible = base_adults > 0
        if (adult_reductions[eligible] <= 0).any():
            raise AssertionError("an adult-cattle ED was exempted from the pathway contraction")
    if int(retained_adults.sum()) != target_adults:
        raise AssertionError("national adult endpoint failed exact closure")
    if int(scenario_dairy.sum()) != target_dairy or int(scenario_suckler.sum()) != target_suckler:
        raise AssertionError("national adult composition failed exact closure")
    return out
