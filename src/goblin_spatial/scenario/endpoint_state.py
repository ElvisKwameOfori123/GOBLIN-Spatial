"""Build the complete cattle state from an allocated adult endpoint."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.reconciliation import hamilton_allocate
from goblin_spatial.scenario.allocation import _bounded_integer_allocate
from goblin_spatial.scenario.cohort_response import FOLLOWER_COHORTS, _cohort_origin, _integer_array
from goblin_spatial.scenario.endpoint_multipliers import parent_endpoint_multiplier, round_implied_counts
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _reconcile_ed_decline(
    scenario: dict[str, np.ndarray], baseline: dict[str, np.ndarray]
) -> np.ndarray:
    """Keep each cattle-bearing ED below its baseline total when no hard cohort margins exist."""

    base_total = sum(baseline[c] for c in FINAL_21_COHORTS)
    scenario_total = sum(scenario[c] for c in FINAL_21_COHORTS)
    adjusted = np.zeros(len(base_total), dtype=np.int64)
    follower_order = list(FOLLOWER_COHORTS)
    for idx in np.where(base_total > 0)[0]:
        excess = int(scenario_total[idx]) - (int(base_total[idx]) - 1)
        if excess <= 0:
            continue
        capacity = np.array([int(scenario[c][idx]) for c in follower_order], dtype=np.int64)
        if int(capacity.sum()) < excess:
            raise AssertionError("ED cattle decline cannot be reconciled without changing adults")
        cuts = _bounded_integer_allocate(capacity.astype(float), capacity, excess)
        for cohort, cut in zip(follower_order, cuts, strict=True):
            scenario[cohort][idx] -= int(cut)
        adjusted[idx] = excess
        scenario_total[idx] -= excess
    if ((base_total > 0) & (scenario_total >= base_total)).any():
        raise AssertionError("not every cattle-bearing ED declined")
    return adjusted


def _allocate_target_by_signature(
    implied: np.ndarray,
    baseline: np.ndarray,
    target: int,
) -> np.ndarray:
    """Allocate one exact national cohort target across its existing ED footprint."""

    implied = np.maximum(np.asarray(implied, dtype=float), 0.0)
    baseline = np.asarray(baseline, dtype=np.int64)
    target = int(target)
    if target < 0:
        raise ValueError("national cohort target cannot be negative")
    if len(implied) != len(baseline):
        raise ValueError("implied and baseline cohort arrays must have equal length")
    if (baseline < 0).any() or (~np.isfinite(implied)).any():
        raise ValueError("invalid cohort signature arrays")
    if target == 0:
        return np.zeros(len(baseline), dtype=np.int64)

    eligible = baseline > 0
    if not eligible.any():
        raise ValueError("positive national cohort target has no baseline ED footprint")
    weights = np.where(eligible, implied, 0.0)
    if float(weights.sum()) <= 0.0:
        weights = np.where(eligible, baseline.astype(float), 0.0)
    out = hamilton_allocate(weights, target)
    if (out[~eligible] != 0).any():
        raise AssertionError("national cohort closure seeded a new ED cohort footprint")
    return out


def _reconcile_exact_targets_to_ed_decline(
    scenario: dict[str, np.ndarray], baseline: dict[str, np.ndarray]
) -> np.ndarray:
    """Preserve exact cohort margins while keeping every cattle-bearing ED contracting."""

    base_total = sum(baseline[c] for c in FINAL_21_COHORTS)
    scenario_adults = scenario["dairy_cows"] + scenario["suckler_cows"]
    max_total = np.where(base_total > 0, base_total - 1, 0).astype(np.int64)
    follower_capacity = max_total - scenario_adults
    if (follower_capacity < 0).any():
        raise AssertionError("adult endpoint alone violates an ED total-cattle decline bound")

    follower_order = list(FOLLOWER_COHORTS)
    follower_total = sum(scenario[c] for c in follower_order)
    spare = follower_capacity - follower_total
    if int(follower_capacity.sum()) < int(follower_total.sum()):
        raise AssertionError("national follower targets are incompatible with universal ED contraction")

    moved_out = np.zeros(len(base_total), dtype=np.int64)
    max_passes = max(1, len(base_total) * 2)
    for _ in range(max_passes):
        overloaded = np.where(spare < 0)[0]
        if len(overloaded) == 0:
            break
        progress = False
        for donor in overloaded:
            excess = int(-spare[donor])
            cohorts = sorted(
                follower_order,
                key=lambda c: int(scenario[c][donor]),
                reverse=True,
            )
            for cohort in cohorts:
                if excess <= 0:
                    break
                donor_available = int(scenario[cohort][donor])
                if donor_available <= 0:
                    continue
                candidates = (spare > 0) & (baseline[cohort] > 0)
                if not candidates.any():
                    continue
                capacities = spare[candidates].astype(np.int64)
                move = min(excess, donor_available, int(capacities.sum()))
                if move <= 0:
                    continue
                weights = (
                    baseline[cohort][candidates].astype(float)
                    + scenario[cohort][candidates].astype(float)
                )
                additions = _bounded_integer_allocate(weights, capacities, move)
                scenario[cohort][donor] -= move
                scenario[cohort][candidates] += additions
                spare[donor] += move
                spare[candidates] -= additions
                moved_out[donor] += move
                excess -= move
                progress = True
        if not progress:
            raise AssertionError(
                "exact national cohort targets cannot be spatially reconciled while preserving ED decline"
            )
    else:
        raise AssertionError("ED total-cattle reconciliation did not converge")

    scenario_total = sum(scenario[c] for c in FINAL_21_COHORTS)
    if ((base_total > 0) & (scenario_total >= base_total)).any():
        raise AssertionError("not every cattle-bearing ED declined after exact cohort reconciliation")
    for cohort in FOLLOWER_COHORTS:
        if (scenario[cohort][baseline[cohort] == 0] != 0).any():
            raise AssertionError(f"reconciliation seeded a new ED footprint for {cohort}")
    return moved_out


def _validated_national_targets(
    targets: Mapping[str, int],
    *,
    scenario_dairy: int,
    scenario_suckler: int,
    total_cattle_target: int | None,
) -> dict[str, int]:
    supplied = dict(targets)
    expected = set(FINAL_21_COHORTS)
    actual = set(supplied)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            "national_cohort_targets must contain the complete 21-cohort set; "
            f"missing={missing}, extra={extra}"
        )
    out = {cohort: int(supplied[cohort]) for cohort in FINAL_21_COHORTS}
    if any(value < 0 for value in out.values()):
        raise ValueError("national cohort targets cannot be negative")
    if out["dairy_cows"] != int(scenario_dairy):
        raise AssertionError("national dairy cohort target does not match adult endpoint")
    if out["suckler_cows"] != int(scenario_suckler):
        raise AssertionError("national suckler cohort target does not match adult endpoint")
    if total_cattle_target is not None and sum(out.values()) != int(total_cattle_target):
        raise AssertionError("national cohort targets do not close to total_cattle_target")
    return out


def build_endpoint_cattle_state(
    adult_endpoint: pd.DataFrame,
    *,
    total_cattle_target: int | None = None,
    national_cohort_targets: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """Propagate signed adult composition change through all 21 cattle cohorts.

    ED-specific adult-to-cohort relationships determine the first spatial state.
    When complete national cohort targets are supplied, those GOBLIN/COHORTS
    margins are imposed exactly without replacing heterogeneous ED signatures or
    seeding cohorts into new ED footprints.
    """

    out = adult_endpoint.copy().sort_values("CSOED", kind="stable").reset_index(drop=True)
    required = {"County", "BASE_DAIRY_COW", "BASE_OTHER_COW", "SCENARIO_DAIRY_COW", "SCENARIO_OTHER_COW", *FINAL_21_COHORTS}
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"endpoint cattle state missing columns: {missing}")

    counties = out["County"].astype(str).to_numpy(dtype=object)
    bd = _integer_array(out, "BASE_DAIRY_COW")
    bs = _integer_array(out, "BASE_OTHER_COW")
    sd = _integer_array(out, "SCENARIO_DAIRY_COW")
    ss = _integer_array(out, "SCENARIO_OTHER_COW")
    ba, sa = bd + bs, sd + ss
    base = {cohort: _integer_array(out, cohort) for cohort in FINAL_21_COHORTS}
    if not np.array_equal(base["dairy_cows"], bd) or not np.array_equal(base["suckler_cows"], bs):
        raise AssertionError("baseline adult cohorts do not close to aggregate adults")

    targets = None
    if national_cohort_targets is not None:
        targets = _validated_national_targets(
            national_cohort_targets,
            scenario_dairy=int(sd.sum()),
            scenario_suckler=int(ss.sum()),
            total_cattle_target=total_cattle_target,
        )

    scenario: dict[str, np.ndarray] = {
        "dairy_cows": sd.copy(),
        "suckler_cows": ss.copy(),
    }
    multipliers: dict[str, np.ndarray] = {}
    sources: dict[str, np.ndarray] = {}
    for cohort in FOLLOWER_COHORTS:
        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            multiplier, source = parent_endpoint_multiplier(bd, sd, base[cohort], counties)
        elif origin == "SUCKLER":
            multiplier, source = parent_endpoint_multiplier(bs, ss, base[cohort], counties)
        else:
            multiplier, source = parent_endpoint_multiplier(ba, sa, base[cohort], counties)
        implied = base[cohort].astype(float) * multiplier
        if targets is None:
            scenario[cohort] = round_implied_counts(implied)
        else:
            scenario[cohort] = _allocate_target_by_signature(
                implied,
                base[cohort],
                targets[cohort],
            )
        multipliers[cohort], sources[cohort] = multiplier, source

    if targets is None:
        adjustment = _reconcile_ed_decline(scenario, base)
    else:
        adjustment = _reconcile_exact_targets_to_ed_decline(scenario, base)
        for cohort in FINAL_21_COHORTS:
            if int(scenario[cohort].sum()) != int(targets[cohort]):
                raise AssertionError(f"exact national cohort closure failed for {cohort}")

    base_columns, scenario_columns = [], []
    for cohort in FINAL_21_COHORTS:
        bcol = f"BASE_COHORT_{cohort}"
        scol = f"SCENARIO_COHORT_{cohort}"
        base_columns.append(bcol)
        scenario_columns.append(scol)
        out[bcol] = base[cohort]
        out[scol] = scenario[cohort]
        out[f"CHANGE_COHORT_{cohort}"] = scenario[cohort] - base[cohort]
        if cohort in multipliers:
            out[f"ENDPOINT_MULTIPLIER_{cohort}"] = multipliers[cohort]
            out[f"ENDPOINT_MULTIPLIER_SOURCE_{cohort}"] = sources[cohort]

    out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_columns].sum(axis=1).astype(np.int64)
    out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_columns].sum(axis=1).astype(np.int64)
    out["BASE_TOTAL_CATTLE"] = out["BASE_GOBLIN_21_CATTLE_TOTAL"]
    out["SCENARIO_TOTAL_CATTLE"] = out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"]
    out["CUMULATIVE_REDUCTION_TOTAL_CATTLE"] = out["BASE_TOTAL_CATTLE"] - out["SCENARIO_TOTAL_CATTLE"]
    out["ED_CATTLE_DECLINE_RECONCILIATION"] = adjustment
    out["NATIONAL_COHORT_TARGETS_APPLIED"] = bool(targets is not None)
    if "TOTAL_CATTLE" in out.columns:
        if not np.array_equal(_integer_array(out, "TOTAL_CATTLE"), out["BASE_TOTAL_CATTLE"].to_numpy(dtype=np.int64)):
            raise AssertionError("baseline cohorts do not close to historical TOTAL_CATTLE")
    if total_cattle_target is not None and int(out["SCENARIO_TOTAL_CATTLE"].sum()) != int(total_cattle_target):
        raise AssertionError("external national total-cattle endpoint failed")
    if targets is not None and int(out["SCENARIO_TOTAL_CATTLE"].sum()) != sum(targets.values()):
        raise AssertionError("national 21-cohort endpoint total failed")
    return out


def add_fixed_sheep_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach unchanged ten sheep cohorts and explicit sheep totals."""

    out = frame.copy()
    base_columns = []
    scenario_columns = []
    for cohort in GOBLIN_SHEEP_10:
        values = _integer_array(out, cohort)
        bcol = f"BASE_SHEEP_COHORT_{cohort}"
        scol = f"SCENARIO_SHEEP_COHORT_{cohort}"
        base_columns.append(bcol)
        scenario_columns.append(scol)
        out[bcol] = values
        out[scol] = values
    out["BASE_GOBLIN_10_SHEEP_TOTAL"] = out[base_columns].sum(axis=1).astype(np.int64)
    out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"] = out[scenario_columns].sum(axis=1).astype(np.int64)
    return out
