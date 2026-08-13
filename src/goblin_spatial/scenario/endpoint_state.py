"""Build the complete cattle state from an allocated adult endpoint."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.allocation import _bounded_integer_allocate
from goblin_spatial.scenario.cohort_response import FOLLOWER_COHORTS, _cohort_origin, _integer_array
from goblin_spatial.scenario.endpoint_multipliers import parent_endpoint_multiplier, round_implied_counts
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _reconcile_ed_decline(
    scenario: dict[str, np.ndarray], baseline: dict[str, np.ndarray]
) -> np.ndarray:
    """Keep each cattle-bearing ED below its baseline total."""

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


def build_endpoint_cattle_state(
    adult_endpoint: pd.DataFrame,
    *,
    total_cattle_target: int | None = None,
) -> pd.DataFrame:
    """Propagate signed adult composition change through all 21 cattle cohorts."""

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
        scenario[cohort] = round_implied_counts(base[cohort].astype(float) * multiplier)
        multipliers[cohort], sources[cohort] = multiplier, source

    adjustment = _reconcile_ed_decline(scenario, base)
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
    if "TOTAL_CATTLE" in out.columns:
        if not np.array_equal(_integer_array(out, "TOTAL_CATTLE"), out["BASE_TOTAL_CATTLE"].to_numpy(dtype=np.int64)):
            raise AssertionError("baseline cohorts do not close to historical TOTAL_CATTLE")
    if total_cattle_target is not None and int(out["SCENARIO_TOTAL_CATTLE"].sum()) != int(total_cattle_target):
        raise AssertionError("external national total-cattle endpoint failed")
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
