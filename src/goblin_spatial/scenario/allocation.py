"""Spatialise fixed national adult-livestock reductions across EDs.

This is the first scenario layer. It does not yet rebuild young cattle cohorts.
It answers one transparent question: given a selected 2020 or 2025 ED starting
state and a national reduction, where does that adult-livestock reduction land
under the chosen allocation rule?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.reconciliation import hamilton_allocate
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


def _bounded_integer_allocate(weights: np.ndarray, capacities: np.ndarray, target: int) -> np.ndarray:
    """Allocate an integer target without exceeding per-ED capacities."""

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
        scenario = hamilton_allocate(base.astype(float), target_total).astype(np.int64)
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

    if int(scenario.sum()) != target_total:
        raise AssertionError("national scenario target failed exact closure")
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
    """Allocate a national adult-cattle/sheep reduction to EDs exactly.

    The returned table is the spatial incidence layer for future destocking
    studies. It preserves the selected baseline, reports the reduction assigned
    to every ED, and closes exactly to the national reduction implied by the
    scenario definition.

    Young cattle are deliberately not changed here. A subsequent biological
    response step will translate adult changes into national GOBLIN/COHORTS
    follower targets and then spatialise those followers across breeding and
    receiver/rearing EDs.
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
