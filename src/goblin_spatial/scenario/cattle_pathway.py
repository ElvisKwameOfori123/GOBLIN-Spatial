"""Cumulative 21-cohort cattle pathways driven by GOBLIN/COHORTS controls.

Adult and follower changes are solved as one herd state at each milestone.  The
adult pathway supplies the incremental dairy/suckler reductions.  GOBLIN/COHORTS
supplies the exact national target for every one of the 21 cattle cohorts.  ED
relationships determine the first spatial response, receiver/rearing/finishing
EDs inherit the same-county breeding signal, and national fallback is reserved
for true orphan county cases.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.allocation import _bounded_integer_allocate
from goblin_spatial.scenario.cohort_response import (
    _cohort_origin,
    _integer_array,
    _reduction_signal,
)


ADULT_COHORT_MAP = {
    "dairy_cows": "DAIRY_COW",
    "suckler_cows": "OTHER_COW",
}
FOLLOWER_COHORTS = tuple(
    c for c in FINAL_21_COHORTS if c not in ADULT_COHORT_MAP
)


def build_cattle_cohort_pathway(
    adult_pathway: pd.DataFrame,
    national_targets_by_year: Mapping[int, Mapping[str, int]],
) -> pd.DataFrame:
    """Propagate an ED adult pathway through all 21 cattle cohorts cumulatively.

    ``adult_pathway`` is the stacked output of ``build_transition_pathway``.
    ``national_targets_by_year`` must contain an exact GOBLIN/COHORTS national
    endpoint for each of the 21 cohorts at every milestone year.

    The returned rows retain the adult-pathway columns and add, for each cohort,
    ``BASE_COHORT_*``, ``PREVIOUS_COHORT_*``,
    ``INCREMENTAL_REDUCTION_COHORT_*``, ``CUMULATIVE_REDUCTION_COHORT_*`` and
    ``SCENARIO_COHORT_*`` fields.
    """

    required = {
        "CSOED",
        "County",
        "MILESTONE_YEAR",
        "BASE_DAIRY_COW",
        "BASE_OTHER_COW",
        "PREVIOUS_DAIRY_COW",
        "PREVIOUS_OTHER_COW",
        "INCREMENTAL_REDUCTION_DAIRY_COW",
        "INCREMENTAL_REDUCTION_OTHER_COW",
        "SCENARIO_DAIRY_COW",
        "SCENARIO_OTHER_COW",
        *FINAL_21_COHORTS,
    }
    missing = sorted(required - set(adult_pathway.columns))
    if missing:
        raise ValueError(f"cattle pathway missing required columns: {missing}")

    years = sorted(pd.to_numeric(adult_pathway["MILESTONE_YEAR"], errors="raise").astype(int).unique())
    if set(years) != {int(y) for y in national_targets_by_year}:
        raise ValueError("national cattle cohort target years must match adult pathway milestones")

    first = adult_pathway.loc[adult_pathway["MILESTONE_YEAR"] == years[0]].copy()
    if first["CSOED"].duplicated().any():
        raise AssertionError("adult pathway must contain one row per ED and milestone")
    ed_order = first.sort_values("CSOED", kind="stable")["CSOED"].astype(str).tolist()

    base_cohorts = {
        cohort: _integer_array(first.sort_values("CSOED", kind="stable"), cohort)
        for cohort in FINAL_21_COHORTS
    }
    current_cohorts = {cohort: values.copy() for cohort, values in base_cohorts.items()}

    output_rows: list[pd.DataFrame] = []

    for year in years:
        out = adult_pathway.loc[adult_pathway["MILESTONE_YEAR"] == year].copy()
        out = out.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if out["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between milestones")

        targets = {k: int(v) for k, v in national_targets_by_year[year].items()}
        if set(targets) != set(FINAL_21_COHORTS):
            missing_targets = sorted(set(FINAL_21_COHORTS) - set(targets))
            extra_targets = sorted(set(targets) - set(FINAL_21_COHORTS))
            raise ValueError(
                f"invalid {year} cattle targets; missing={missing_targets}, extra={extra_targets}"
            )
        if any(v < 0 for v in targets.values()):
            raise ValueError("national cattle cohort targets cannot be negative")

        counties = out["County"].to_numpy(dtype=object)

        # Adults are already spatially allocated by the pathway engine.
        for cohort, adult_column in ADULT_COHORT_MAP.items():
            base = base_cohorts[cohort]
            previous = _integer_array(out, f"PREVIOUS_{adult_column}")
            incremental = _integer_array(out, f"INCREMENTAL_REDUCTION_{adult_column}")
            scenario = _integer_array(out, f"SCENARIO_{adult_column}")
            cumulative = base - scenario

            if int(scenario.sum()) != targets[cohort]:
                raise AssertionError(
                    f"{year} GOBLIN target for {cohort} does not match adult pathway"
                )
            if not np.array_equal(previous - incremental, scenario):
                raise AssertionError(f"adult pathway identity failed for {cohort}")

            out[f"BASE_COHORT_{cohort}"] = base
            out[f"PREVIOUS_COHORT_{cohort}"] = previous
            out[f"INCREMENTAL_REDUCTION_COHORT_{cohort}"] = incremental
            out[f"CUMULATIVE_REDUCTION_COHORT_{cohort}"] = cumulative
            out[f"SCENARIO_COHORT_{cohort}"] = scenario
            current_cohorts[cohort] = scenario.copy()

        prev_dairy = _integer_array(out, "PREVIOUS_DAIRY_COW")
        prev_suckler = _integer_array(out, "PREVIOUS_OTHER_COW")
        prev_adults = prev_dairy + prev_suckler
        inc_dairy = _integer_array(out, "INCREMENTAL_REDUCTION_DAIRY_COW")
        inc_suckler = _integer_array(out, "INCREMENTAL_REDUCTION_OTHER_COW")
        inc_adults = inc_dairy + inc_suckler

        for cohort in FOLLOWER_COHORTS:
            base = base_cohorts[cohort]
            previous = current_cohorts[cohort]
            previous_total = int(previous.sum())
            target_total = targets[cohort]
            if target_total > previous_total:
                raise ValueError(
                    f"reduction-only cattle pathway cannot expand {cohort} at {year}: "
                    f"previous={previous_total:,}, target={target_total:,}"
                )
            incremental_total = previous_total - target_total

            origin = _cohort_origin(cohort)
            if origin == "DAIRY":
                signal, source = _reduction_signal(prev_dairy, inc_dairy, previous, counties)
            elif origin == "SUCKLER":
                signal, source = _reduction_signal(prev_suckler, inc_suckler, previous, counties)
            else:
                signal, source = _reduction_signal(prev_adults, inc_adults, previous, counties)

            # The signal is equivalent to the direct local adult/cohort marginal
            # relationship.  The tiny floor leaves existing cohort locations
            # available for exact GOBLIN closure when national biology changes
            # more than the adult signal alone would imply.
            cut_weights = previous.astype(float) * (signal + 1e-9)
            incremental = _bounded_integer_allocate(
                cut_weights, previous, incremental_total
            )
            scenario = previous - incremental
            cumulative = base - scenario

            if int(scenario.sum()) != target_total:
                raise AssertionError(f"{year} national target failed for {cohort}")
            if not np.array_equal(previous - incremental, scenario):
                raise AssertionError(f"incremental identity failed for {cohort}")
            if (scenario < 0).any() or (scenario > previous).any():
                raise AssertionError(f"non-monotonic cohort pathway for {cohort}")

            out[f"BASE_COHORT_{cohort}"] = base
            out[f"PREVIOUS_COHORT_{cohort}"] = previous
            out[f"INCREMENTAL_REDUCTION_COHORT_{cohort}"] = incremental
            out[f"CUMULATIVE_REDUCTION_COHORT_{cohort}"] = cumulative
            out[f"SCENARIO_COHORT_{cohort}"] = scenario
            out[f"REDUCTION_SIGNAL_{cohort}"] = signal
            out[f"REDUCTION_SIGNAL_SOURCE_{cohort}"] = source
            current_cohorts[cohort] = scenario.copy()

        base_cols = [f"BASE_COHORT_{c}" for c in FINAL_21_COHORTS]
        prev_cols = [f"PREVIOUS_COHORT_{c}" for c in FINAL_21_COHORTS]
        inc_cols = [f"INCREMENTAL_REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS]
        cum_cols = [f"CUMULATIVE_REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS]
        sc_cols = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]

        out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_cols].sum(axis=1)
        out["PREVIOUS_GOBLIN_21_CATTLE_TOTAL"] = out[prev_cols].sum(axis=1)
        out["INCREMENTAL_REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[inc_cols].sum(axis=1)
        out["CUMULATIVE_REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[cum_cols].sum(axis=1)
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[sc_cols].sum(axis=1)

        if int(out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].sum()) != sum(targets.values()):
            raise AssertionError(f"{year} 21-cohort national closure failed")

        output_rows.append(out)

    result = pd.concat(output_rows, ignore_index=True)
    ordered = result.sort_values(["CSOED", "MILESTONE_YEAR"], kind="stable")
    for cohort in FINAL_21_COHORTS:
        diff = ordered.groupby("CSOED", sort=False)[f"SCENARIO_COHORT_{cohort}"].diff()
        if (diff.dropna() > 0).any():
            raise AssertionError(f"ED cattle cohort increases between milestones: {cohort}")

    return result
