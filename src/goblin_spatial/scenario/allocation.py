"""Spatialise fixed national livestock reductions across EDs.

The selected 2020 or 2025 ED baseline is always the authority. GOBLIN supplies
(or implies) the national endpoint. GOBLIN-Spatial converts that endpoint into
a number of animals to remove, allocates only that reduction across animals
already present in EDs, and subtracts the allocated reduction from each ED.

    national reduction = baseline national total - scenario national target
    scenario ED count = baseline ED count - ED allocated reduction

The allocation rule changes *where the reduction lands*. It never changes the
national reduction itself and never seeds livestock into a new ED footprint.
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
    """Min-max normalise a pre-scenario indicator to [0, 1]."""

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


def _rank_score(series: pd.Series) -> np.ndarray:
    """Return a monotonic 0-1 score without allowing a single outlier to dominate."""

    x = pd.to_numeric(series, errors="raise").astype(float)
    if (x < 0).any() or (~np.isfinite(x)).any():
        raise ValueError("rank score requires finite non-negative values")
    if len(x) == 0:
        return np.array([], dtype=float)
    if float(x.max()) <= 0:
        return np.zeros(len(x), dtype=float)

    positive = x > 0
    score = pd.Series(0.0, index=x.index, dtype=float)
    if positive.any():
        ranks = x.loc[positive].rank(method="average", pct=True)
        if len(ranks) == 1:
            score.loc[positive] = 1.0
        else:
            lo = float(ranks.min())
            hi = float(ranks.max())
            score.loc[positive] = (ranks - lo) / (hi - lo)
    return score.to_numpy(dtype=float)


def _protection_multiplier(score: np.ndarray, strength: float) -> np.ndarray:
    """Convert higher protection score into lower cut weight."""

    score = np.clip(np.asarray(score, dtype=float), 0.0, 1.0)
    return 1.0 - float(strength) * score


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


def _rule_cut_weights(
    baseline: pd.DataFrame,
    base: np.ndarray,
    scenario: ScenarioDefinition,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Return ED cut weights and an optional protection-score diagnostic.

    High protection score means a smaller proportional cut. DairyProtection is
    defined from the selected baseline itself: EDs with larger dairy-cow herds
    receive higher protection scores and therefore less reduction pressure.
    """

    base = np.asarray(base, dtype=np.int64)
    raw = base.astype(float)
    rule = scenario.allocation_rule
    strength = float(scenario.protection_strength)

    if rule == AllocationRule.PRORATA:
        return raw, None

    if rule == AllocationRule.DAIRY_PROTECTION:
        score = _rank_score(baseline["DAIRY_COW"])
        return raw * _protection_multiplier(score, strength), score

    if rule == AllocationRule.SCORE_WEIGHTED:
        if scenario.score_column not in baseline.columns:
            raise ValueError(
                f"score column not found in selected baseline: {scenario.score_column}"
            )
        score = _normalise_score(baseline[scenario.score_column])
        return raw * _protection_multiplier(score, strength), score

    if rule == AllocationRule.PRODUCTIVITY_PROTECTION:
        column = scenario.productivity_score_column
        if column not in baseline.columns:
            raise ValueError(f"productivity score column not found: {column}")
        score = _normalise_score(baseline[column])
        return raw * _protection_multiplier(score, strength), score

    if rule == AllocationRule.VULNERABILITY_PROTECTION:
        column = scenario.vulnerability_score_column
        if column not in baseline.columns:
            raise ValueError(f"vulnerability score column not found: {column}")
        score = _normalise_score(baseline[column])
        return raw * _protection_multiplier(score, strength), score

    if rule == AllocationRule.HYBRID_BALANCED:
        p_col = scenario.productivity_score_column
        v_col = scenario.vulnerability_score_column
        if p_col not in baseline.columns:
            raise ValueError(f"productivity score column not found: {p_col}")
        if v_col not in baseline.columns:
            raise ValueError(f"vulnerability score column not found: {v_col}")

        p_score = _normalise_score(baseline[p_col])
        d_score = _rank_score(baseline["DAIRY_COW"])
        v_score = _normalise_score(baseline[v_col])
        w_prorata, w_productivity, w_dairy, w_vulnerability = scenario.hybrid_weights

        p_cut = raw * _protection_multiplier(p_score, strength)
        d_cut = raw * _protection_multiplier(d_score, strength)
        v_cut = raw * _protection_multiplier(v_score, strength)
        cut_weights = (
            float(w_prorata) * raw
            + float(w_productivity) * p_cut
            + float(w_dairy) * d_cut
            + float(w_vulnerability) * v_cut
        )
        combined_score = (
            float(w_productivity) * p_score
            + float(w_dairy) * d_score
            + float(w_vulnerability) * v_score
        ) / max(float(w_productivity + w_dairy + w_vulnerability), 1e-12)
        return cut_weights, np.clip(combined_score, 0.0, 1.0)

    raise ValueError(f"unsupported allocation rule: {rule}")


def _allocate_reduction(
    base: np.ndarray,
    reduction_fraction: float,
    cut_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Allocate the number to remove, then subtract it from the baseline."""

    base = np.asarray(base, dtype=np.int64)
    if (base < 0).any():
        raise ValueError("baseline livestock counts must be non-negative")

    base_total = int(base.sum())
    target_total = int(round(base_total * (1.0 - float(reduction_fraction))))
    target_total = max(0, min(base_total, target_total))
    reduction_total = base_total - target_total

    if reduction_total == 0:
        reductions = np.zeros(len(base), dtype=np.int64)
        return base.copy(), reductions, target_total
    if target_total == 0:
        reductions = base.copy()
        return np.zeros(len(base), dtype=np.int64), reductions, target_total

    reductions = _bounded_integer_allocate(cut_weights, base, reduction_total)
    scenario = base - reductions

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
    return scenario.astype(np.int64), reductions.astype(np.int64), target_total


def allocate_adult_livestock_scenario(
    panel: pd.DataFrame,
    scenario: ScenarioDefinition,
    *,
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Allocate national adult-cattle/sheep reductions from an ED baseline.

    The selected 2020 or 2025 ED state is the authority. For each livestock
    category the function reads the baseline counts, calculates the national
    number to remove, allocates only that reduction under the selected rule,
    and subtracts the ED reduction from the ED baseline.

    The returned table is therefore a spatial incidence table of destocking.
    Young cattle are handled by the separate biological cohort-response layer.
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

    national_targets: dict[str, int] = {}
    for column, reduction_attr in CATEGORY_COLUMNS.items():
        values = pd.to_numeric(baseline[column], errors="raise").to_numpy(dtype=float)
        rounded = np.rint(values).astype(np.int64)
        if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
            raise AssertionError(f"{column} must contain non-negative integer counts")

        cut_weights, protection_score = _rule_cut_weights(baseline, rounded, scenario)
        scenario_values, reductions, target_total = _allocate_reduction(
            rounded,
            float(getattr(scenario, reduction_attr)),
            cut_weights,
        )
        national_targets[column] = target_total

        out[f"BASE_{column}"] = rounded
        out[f"SCENARIO_{column}"] = scenario_values
        out[f"REDUCTION_{column}"] = reductions
        out[f"REDUCTION_PCT_{column}"] = np.where(
            rounded > 0,
            100.0 * reductions / rounded,
            0.0,
        )
        out[f"CUT_WEIGHT_{column}"] = cut_weights
        if protection_score is not None:
            out[f"PROTECTION_SCORE_{column}"] = protection_score

        national_reduction = int(rounded.sum()) - target_total
        if int(reductions.sum()) != national_reduction:
            raise AssertionError(f"national reduction failed for {column}")
        if not np.array_equal(rounded - reductions, scenario_values):
            raise AssertionError(f"baseline-minus-reduction identity failed for {column}")

    out["BASE_ADULT_COWS"] = out["BASE_DAIRY_COW"] + out["BASE_OTHER_COW"]
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
