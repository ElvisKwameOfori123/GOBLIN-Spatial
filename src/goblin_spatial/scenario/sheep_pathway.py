"""Cumulative sheep-cohort pathway built from the ED total-sheep trajectory.

The adult pathway already fixes the exact TOTAL_SHEEP population in every ED at
each milestone.  This module subtracts each ED's incremental sheep reduction
from its existing ten GOBLIN sheep cohorts, preserving local lowland/upland and
age structure as closely as integer accounting allows.

If future GOBLIN runs provide independent national ten-cohort sheep controls,
those can be added as a reconciliation constraint.  The present implementation
does not invent a national cohort structure that GOBLIN has not supplied.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.scenario.allocation import _bounded_integer_allocate
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _integer_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def build_sheep_cohort_pathway(adult_pathway: pd.DataFrame) -> pd.DataFrame:
    """Disaggregate the cumulative ED sheep pathway into ten GOBLIN cohorts."""

    required = {
        "CSOED",
        "MILESTONE_YEAR",
        "BASE_TOTAL_SHEEP",
        "PREVIOUS_TOTAL_SHEEP",
        "INCREMENTAL_REDUCTION_TOTAL_SHEEP",
        "SCENARIO_TOTAL_SHEEP",
        *GOBLIN_SHEEP_10,
    }
    missing = sorted(required - set(adult_pathway.columns))
    if missing:
        raise ValueError(f"sheep pathway missing required columns: {missing}")

    years = sorted(pd.to_numeric(adult_pathway["MILESTONE_YEAR"], errors="raise").astype(int).unique())
    first = adult_pathway.loc[adult_pathway["MILESTONE_YEAR"] == years[0]].copy()
    first = first.sort_values("CSOED", kind="stable").reset_index(drop=True)
    ed_order = first["CSOED"].astype(str).tolist()

    base_cohorts = {cohort: _integer_array(first, cohort) for cohort in GOBLIN_SHEEP_10}
    current = {cohort: values.copy() for cohort, values in base_cohorts.items()}

    # The validated baseline ten-cohort representation must close to TOTAL_SHEEP.
    base_total_from_cohorts = np.sum(np.vstack(list(base_cohorts.values())), axis=0)
    if not np.array_equal(base_total_from_cohorts, _integer_array(first, "BASE_TOTAL_SHEEP")):
        raise AssertionError("baseline ten sheep cohorts do not close to BASE_TOTAL_SHEEP")

    rows: list[pd.DataFrame] = []
    for year in years:
        out = adult_pathway.loc[adult_pathway["MILESTONE_YEAR"] == year].copy()
        out = out.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if out["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between sheep milestones")

        previous_total = _integer_array(out, "PREVIOUS_TOTAL_SHEEP")
        scenario_total = _integer_array(out, "SCENARIO_TOTAL_SHEEP")
        incremental_total = _integer_array(out, "INCREMENTAL_REDUCTION_TOTAL_SHEEP")
        if not np.array_equal(previous_total - incremental_total, scenario_total):
            raise AssertionError("ED total-sheep pathway identity failed")

        scenario_arrays = {cohort: np.zeros(len(out), dtype=np.int64) for cohort in GOBLIN_SHEEP_10}
        incremental_arrays = {cohort: np.zeros(len(out), dtype=np.int64) for cohort in GOBLIN_SHEEP_10}

        # Allocate each ED's own total-sheep reduction across the cohorts that
        # are currently present in that ED.  No sheep are seeded into a new ED
        # or into a cohort that was absent from the previous state.
        for i in range(len(out)):
            prev = np.array([current[c][i] for c in GOBLIN_SHEEP_10], dtype=np.int64)
            if int(prev.sum()) != int(previous_total[i]):
                raise AssertionError("previous ten-cohort sheep total differs from ED pathway")
            cut = _bounded_integer_allocate(prev.astype(float), prev, int(incremental_total[i]))
            sc = prev - cut
            if int(sc.sum()) != int(scenario_total[i]):
                raise AssertionError("scenario ten-cohort sheep total differs from ED pathway")
            for j, cohort in enumerate(GOBLIN_SHEEP_10):
                incremental_arrays[cohort][i] = cut[j]
                scenario_arrays[cohort][i] = sc[j]

        for cohort in GOBLIN_SHEEP_10:
            base = base_cohorts[cohort]
            previous = current[cohort]
            incremental = incremental_arrays[cohort]
            scenario = scenario_arrays[cohort]
            cumulative = base - scenario

            out[f"BASE_SHEEP_COHORT_{cohort}"] = base
            out[f"PREVIOUS_SHEEP_COHORT_{cohort}"] = previous
            out[f"INCREMENTAL_REDUCTION_SHEEP_COHORT_{cohort}"] = incremental
            out[f"CUMULATIVE_REDUCTION_SHEEP_COHORT_{cohort}"] = cumulative
            out[f"SCENARIO_SHEEP_COHORT_{cohort}"] = scenario
            current[cohort] = scenario.copy()

        base_cols = [f"BASE_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
        prev_cols = [f"PREVIOUS_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
        inc_cols = [f"INCREMENTAL_REDUCTION_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
        cum_cols = [f"CUMULATIVE_REDUCTION_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
        sc_cols = [f"SCENARIO_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]

        out["BASE_GOBLIN_10_SHEEP_TOTAL"] = out[base_cols].sum(axis=1)
        out["PREVIOUS_GOBLIN_10_SHEEP_TOTAL"] = out[prev_cols].sum(axis=1)
        out["INCREMENTAL_REDUCTION_GOBLIN_10_SHEEP_TOTAL"] = out[inc_cols].sum(axis=1)
        out["CUMULATIVE_REDUCTION_GOBLIN_10_SHEEP_TOTAL"] = out[cum_cols].sum(axis=1)
        out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"] = out[sc_cols].sum(axis=1)

        if not np.array_equal(
            out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"].to_numpy(dtype=np.int64),
            scenario_total,
        ):
            raise AssertionError("ten-cohort sheep scenario failed ED closure")

        rows.append(out)

    result = pd.concat(rows, ignore_index=True)
    ordered = result.sort_values(["CSOED", "MILESTONE_YEAR"], kind="stable")
    for cohort in GOBLIN_SHEEP_10:
        diff = ordered.groupby("CSOED", sort=False)[f"SCENARIO_SHEEP_COHORT_{cohort}"].diff()
        if (diff.dropna() > 0).any():
            raise AssertionError(f"ED sheep cohort increases between milestones: {cohort}")

    return result
