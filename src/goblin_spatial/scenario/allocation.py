"""Spatialise fixed national livestock reductions across EDs.

This is the first scenario layer. It does not construct a new ED population from
scratch. It always starts from the selected 2020 or 2025 ED baseline, calculates
the national number of animals to remove, allocates that reduction across the
animals already present in EDs, and subtracts the allocated reduction from the
baseline.

In other words::

    national reduction = baseline national total - scenario national target
    scenario ED count = baseline ED count - ED allocated reduction

Young cattle are not yet rebuilt here. A subsequent biological response step
will translate adult changes into national GOBLIN/COHORTS follower targets and
spatialise those cohort changes across breeding and receiver/rearing EDs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition


CATEGORY_COLUMNS = {
    "DAIRY_COW": "dairy_reduction",
    "OTHER_COW": "suckler_reduction",
    "TOTAL_SHEEP": "sheep_reduction",
}


def _normalise_score(series: pd.Series) -> np.ndarray:
    x = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(x)
    if not finite.any():
        return np.full(len(x), 0.5, dtype=float)
    lo = float(np.nanmin(x[finite]))
    hi = float(np.nanmax(x[finite]))
    if hi <= lo:
        return np.full(len(x), 0.5, dtype=float)
    out = np.full(len(x), 0.5, dtype=float)
    out[finite] = (x[finite] - lo) / (hi - lo)
    return np.clip(out, 0.0, 1.0)


def _bounded_integer_allocate(
    weights: np.ndarray, capacities: np.ndarray, target: int
) -> np.ndarray:
    """Allocate an integer reduction without exceeding per-ED baseline counts."""

    weights = np.asarray(weights, dtype=float)
    capacities = np.asarray(capacities, dtype=np.int64)
    target = int(target)
    if target < 0 or target > int(capacities.sum()):
        raise ValueError("allocation target exceeds available capacity")
    if target == 0:
        return np.zeros(len(capacities), dtype=np.int64)
    if (capacities < 0).any() or (~np.isfinite(weights)).any() or (weights < 0).any():
        raise ValueError("invalid weights or capacities")

    remaining_capacity = capacities.astype(float).copy()
    fractional = np.zeros(len(capacities), dtype=float)
    remaining = float(target)

    for _ in range(len(capacities) + 2):
        if remaining <= 1e-10:
            break
        active = remaining_capacity > 1e-12
        if not active.any():
            break
        w = np.where(active, weights, 0.0)
        if float(w.sum()) <= 0:
            w = np.where(active, remaining_capacity, 0.0)
        proposal = remaining * w / w.sum()
        take = np.minimum(proposal, remaining_capacity)
        fractional += take
        remaining_capacity -= take
        remaining = float(target - fractional.sum())

    if abs(remaining) > 1e-7:
        raise AssertionError("bounded allocation failed to close in fractional space")

    floors = np.floor(fractional + 1e-12).astype(np.int64)
    left = target - int(floors.sum())
    if left:
        remainder = fractional - floors
        eligible = floors < capacities
        order = np.argsort(-np.where(eligible, remainder, -1.0), kind="stable")
        for idx in order:
            if left == 0:
                break
            if floors[idx] < capacities[idx]:
                floors[idx] += 1
                left -= 1

    if left != 0 or int(floors.sum()) != target:
        raise AssertionError("bounded integer allocation failed exact closure")
    if (floors < 0).any() or (floors > capacities).any():
        raise AssertionError("bounded integer allocation violated ED capacity")
    return floors


def _allocate_reduction(
    base: np.ndarray,
    reduction_fraction: float,
    rule: AllocationRule,
    score: np.ndarray | None,
) -> tuple[np.ndarray, int]:
    """Subtract an allocated national reduction from an existing ED baseline.

    The scenario endpoint is used only to determine the national reduction that
    must be removed. The ED scenario population is never rebuilt independently
    from the target total.
    """

    base = np.asarray(base, dtype=np.int64)
    if (base < 0).any():
        raise ValueError("baseline livestock counts must be non-negative")

    base_total = int(base.sum())
    target_total = int(round(base_total * (1.0 - float(reduction_fraction))))
    target_total = max(0, min(base_total, target_total))
    reduction_total = base_total - target_total

    if reduction_total == 0:
        return base.copy(), target_total
    if target_total == 0:
        return np.zeros(len(base), dtype=np.int64), target_total

    if rule == AllocationRule.PRORATA:
        # Allocate the number to REMOVE, proportional to the animals already
        # present in each ED, then subtract. This makes the baseline the
        # explicit authority rather than reconstructing a target distribution.
        cut_weights = base.astype(float)
        reductions = _bounded_integer_allocate(cut_weights, base, reduction_total)
        scenario = base - reductions
    elif rule == AllocationRule.SCORE_WEIGHTED:
        if score is None:
            raise ValueError("SCORE_WEIGHTED allocation requires an ED score")
        score = np.asarray(score, dtype=float)
        if len(score) != len(base):
            raise ValueError("score length differs from ED baseline")
        # High score = more protected. The 0.05 floor prevents an ED becoming
        # mathematically untouchable while retaining a strong protection signal.
        cut_weights = base.astype(float) * (0.05 + (1.0 - np.clip(score, 0.0, 1.0)))
        reductions = _bounded_integer_allocate(cut_weights, base, reduction_total)
        scenario = base - reductions
    else:
        raise ValueError(f"unsupported allocation rule: {rule}")

    if int(reductions.sum()) != reduction_total:
        raise AssertionError("national reduction failed exact closure")
    if int(scenario.sum()) != target_total:
        raise AssertionError("national scenario target failed exact closure")
    if not np.array_equal(base - reductions, scenario):
        raise AssertionError("scenario is not baseline minus allocated reduction")
    if (scenario < 0).any() or (scenario > base).any():
        raise AssertionError("ED scenario count is outside baseline reduction bounds")
    if ((base == 0) & (scenario > 0)).any():
        raise AssertionError("scenario seeded livestock into a zero-footprint ED")
    return scenario.astype(np.int64), target_total


def allocate_adult_livestock_scenario(
    panel: pd.DataFrame,
    scenario: ScenarioDefinition,
    *,
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Allocate national adult-cattle/sheep reductions from an ED baseline.

    The selected 2020 or 2025 ED state is the authority. For each livestock
    category the function:

    1. reads the baseline ED counts;
    2. calculates the national number to remove;
    3. allocates only that reduction across EDs under the selected rule; and
    4. subtracts each ED reduction from its own baseline count.

    The returned table therefore makes the geography of destocking directly
    observable. Young cattle are deliberately not changed here. A subsequent
    biological response step will translate adult changes into national
    GOBLIN/COHORTS follower targets and then spatialise those cohort changes
    across breeding and receiver/rearing EDs.
    """

    baseline = select_baseline_year(
        panel, scenario.baseline_year, expected_eds=expected_eds
    )
    missing = [c for c in CATEGORY_COLUMNS if c not in baseline.columns]
    if missing:
        raise ValueError(f"scenario allocation missing required columns: {missing}")

    out = baseline.copy()
    out.insert(0, "SCENARIO_NAME", scenario.name)
    out.insert(1, "SCENARIO_BASELINE_YEAR", scenario.baseline_year)
    out.insert(2, "SCENARIO_TARGET_YEAR", scenario.target_year)
    out.insert(3, "SCENARIO_ALLOCATION_RULE", scenario.allocation_rule.value)

    score = None
    if scenario.allocation_rule == AllocationRule.SCORE_WEIGHTED:
        if scenario.score_column not in baseline.columns:
            raise ValueError(
                f"score column not found in selected baseline: {scenario.score_column}"
            )
        score = _normalise_score(baseline[scenario.score_column])
        out["SCENARIO_ALLOCATION_SCORE"] = score

    national_targets: dict[str, int] = {}
    for column, reduction_attr in CATEGORY_COLUMNS.items():
        values = pd.to_numeric(baseline[column], errors="raise").to_numpy(dtype=float)
        rounded = np.rint(values).astype(np.int64)
        if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
            raise AssertionError(f"{column} must contain non-negative integer counts")

        scenario_values, target_total = _allocate_reduction(
            rounded,
            float(getattr(scenario, reduction_attr)),
            scenario.allocation_rule,
            score,
        )
        national_targets[column] = target_total

        out[f"BASE_{column}"] = rounded
        out[f"SCENARIO_{column}"] = scenario_values
        out[f"REDUCTION_{column}"] = rounded - scenario_values
        out[f"REDUCTION_PCT_{column}"] = np.where(
            rounded > 0,
            100.0 * (rounded - scenario_values) / rounded,
            0.0,
        )

        national_reduction = int(rounded.sum()) - target_total
        if int(out[f"REDUCTION_{column}"].sum()) != national_reduction:
            raise AssertionError(f"national reduction failed for {column}")
        if not np.array_equal(
            out[f"BASE_{column}"].to_numpy(dtype=np.int64)
            - out[f"REDUCTION_{column}"].to_numpy(dtype=np.int64),
            out[f"SCENARIO_{column}"].to_numpy(dtype=np.int64),
        ):
            raise AssertionError(f"baseline-minus-reduction identity failed for {column}")

    out["REDUCTION_ADULT_COWS"] = (
        out["REDUCTION_DAIRY_COW"] + out["REDUCTION_OTHER_COW"]
    )
    out["SCENARIO_ADULT_COWS"] = (
        out["SCENARIO_DAIRY_COW"] + out["SCENARIO_OTHER_COW"]
    )

    for column, target_total in national_targets.items():
        if int(out[f"SCENARIO_{column}"].sum()) != target_total:
            raise AssertionError(f"national target failed for {column}")

    # Null-scenario guarantee: zero reductions reproduce the selected ED state.
    for column, reduction_attr in CATEGORY_COLUMNS.items():
        if float(getattr(scenario, reduction_attr)) == 0.0:
            if not np.array_equal(
                out[f"SCENARIO_{column}"].to_numpy(dtype=np.int64),
                out[f"BASE_{column}"].to_numpy(dtype=np.int64),
            ):
                raise AssertionError(f"null scenario changed {column}")

    return out
