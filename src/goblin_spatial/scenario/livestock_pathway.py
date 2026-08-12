"""Compose sequential adult reductions into complete 31-cohort ED pathways.

Two pathway contracts are retained:

``build_full_livestock_pathway``
    Compatibility route for studies that supply an exact national target for
    every cattle cohort at every milestone.

``build_adult_driven_livestock_pathway``
    Principal GOBLIN-Spatial route. Dairy cows, suckler cows and total sheep are
    the only externally controlled livestock populations. Young/follower cattle
    respond endogenously to the realised incremental adult reductions, while
    sheep reductions are distributed through the ten existing sheep cohorts.

Both routes are cumulative: milestone t starts from the solved ED state at
milestone t-1. Animals are never rebuilt from scratch at each milestone.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.allocation import _bounded_integer_allocate
from goblin_spatial.scenario.cattle_pathway import build_cattle_cohort_pathway
from goblin_spatial.scenario.cohort_response import (
    FOLLOWER_COHORTS,
    _cohort_origin,
    _integer_array,
    _reduction_signal,
)
from goblin_spatial.scenario.sheep_pathway import build_sheep_cohort_pathway
from goblin_spatial.standard_output import add_pathway_standard_output


ADULT_COHORT_MAP = {
    "dairy_cows": "DAIRY_COW",
    "suckler_cows": "OTHER_COW",
}


def _adult_driven_cattle_pathway(adult_pathway: pd.DataFrame) -> pd.DataFrame:
    """Propagate sequential adult reductions through all 21 cattle cohorts.

    For each follower cohort and milestone, the incremental reduction signal is
    inherited from the corresponding *previous-state* adult population:

    ``incremental follower reduction ~= previous follower * adult cut rate``.

    The local ED signal is used first, same-county breeding signal second, and
    national fallback only for true orphan follower locations. No independent
    national follower targets are required.
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
        raise ValueError(
            f"adult-driven cattle pathway missing required columns: {missing}"
        )

    years = sorted(
        pd.to_numeric(
            adult_pathway["MILESTONE_YEAR"], errors="raise"
        ).astype(int).unique()
    )
    first = adult_pathway.loc[
        adult_pathway["MILESTONE_YEAR"] == years[0]
    ].copy()
    first = first.sort_values("CSOED", kind="stable").reset_index(drop=True)
    ed_order = first["CSOED"].astype(str).tolist()

    base_cohorts = {
        cohort: _integer_array(first, cohort) for cohort in FINAL_21_COHORTS
    }
    current = {cohort: values.copy() for cohort, values in base_cohorts.items()}

    rows: list[pd.DataFrame] = []
    for year in years:
        out = adult_pathway.loc[
            adult_pathway["MILESTONE_YEAR"] == year
        ].copy()
        out = out.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if out["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between milestones")

        # Adult cohorts are already solved by the sequential adult pathway.
        for cohort, adult_column in ADULT_COHORT_MAP.items():
            base = base_cohorts[cohort]
            previous = _integer_array(out, f"PREVIOUS_{adult_column}")
            incremental = _integer_array(
                out, f"INCREMENTAL_REDUCTION_{adult_column}"
            )
            scenario = _integer_array(out, f"SCENARIO_{adult_column}")
            cumulative = base - scenario

            if not np.array_equal(previous - incremental, scenario):
                raise AssertionError(
                    f"adult pathway identity failed for {cohort}"
                )
            out[f"BASE_COHORT_{cohort}"] = base
            out[f"PREVIOUS_COHORT_{cohort}"] = previous
            out[f"INCREMENTAL_REDUCTION_COHORT_{cohort}"] = incremental
            out[f"CUMULATIVE_REDUCTION_COHORT_{cohort}"] = cumulative
            out[f"SCENARIO_COHORT_{cohort}"] = scenario
            current[cohort] = scenario.copy()

        prev_dairy = _integer_array(out, "PREVIOUS_DAIRY_COW")
        prev_suckler = _integer_array(out, "PREVIOUS_OTHER_COW")
        prev_adults = prev_dairy + prev_suckler
        inc_dairy = _integer_array(
            out, "INCREMENTAL_REDUCTION_DAIRY_COW"
        )
        inc_suckler = _integer_array(
            out, "INCREMENTAL_REDUCTION_OTHER_COW"
        )
        inc_adults = inc_dairy + inc_suckler
        counties = out["County"].astype(str).to_numpy(dtype=object)

        for cohort in FOLLOWER_COHORTS:
            base = base_cohorts[cohort]
            previous = current[cohort]
            origin = _cohort_origin(cohort)

            if origin == "DAIRY":
                signal, source = _reduction_signal(
                    prev_dairy, inc_dairy, previous, counties
                )
            elif origin == "SUCKLER":
                signal, source = _reduction_signal(
                    prev_suckler, inc_suckler, previous, counties
                )
            else:
                signal, source = _reduction_signal(
                    prev_adults, inc_adults, previous, counties
                )

            implied = previous.astype(float) * signal
            incremental_total = int(round(float(implied.sum())))
            incremental = _bounded_integer_allocate(
                implied, previous, incremental_total
            )
            scenario = previous - incremental
            cumulative = base - scenario

            if not np.array_equal(previous - incremental, scenario):
                raise AssertionError(
                    f"incremental follower identity failed for {cohort}"
                )
            if (scenario < 0).any() or (scenario > previous).any():
                raise AssertionError(
                    f"non-monotonic follower pathway for {cohort}"
                )

            out[f"BASE_COHORT_{cohort}"] = base
            out[f"PREVIOUS_COHORT_{cohort}"] = previous
            out[f"INCREMENTAL_REDUCTION_COHORT_{cohort}"] = incremental
            out[f"CUMULATIVE_REDUCTION_COHORT_{cohort}"] = cumulative
            out[f"SCENARIO_COHORT_{cohort}"] = scenario
            out[f"REDUCTION_SIGNAL_{cohort}"] = signal
            out[f"REDUCTION_SIGNAL_SOURCE_{cohort}"] = source
            current[cohort] = scenario.copy()

        base_cols = [f"BASE_COHORT_{c}" for c in FINAL_21_COHORTS]
        prev_cols = [f"PREVIOUS_COHORT_{c}" for c in FINAL_21_COHORTS]
        inc_cols = [
            f"INCREMENTAL_REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS
        ]
        cum_cols = [
            f"CUMULATIVE_REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS
        ]
        scenario_cols = [
            f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS
        ]
        out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_cols].sum(axis=1)
        out["PREVIOUS_GOBLIN_21_CATTLE_TOTAL"] = out[prev_cols].sum(axis=1)
        out["INCREMENTAL_REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[
            inc_cols
        ].sum(axis=1)
        out["CUMULATIVE_REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[
            cum_cols
        ].sum(axis=1)
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_cols].sum(
            axis=1
        )
        rows.append(out)

    result = pd.concat(rows, ignore_index=True)
    ordered = result.sort_values(
        ["CSOED", "MILESTONE_YEAR"], kind="stable"
    )
    for cohort in FINAL_21_COHORTS:
        diff = ordered.groupby("CSOED", sort=False)[
            f"SCENARIO_COHORT_{cohort}"
        ].diff()
        if (diff.dropna() > 0).any():
            raise AssertionError(
                f"ED cattle cohort increases between milestones: {cohort}"
            )
    return result


def build_adult_driven_livestock_pathway(
    adult_pathway: pd.DataFrame,
    *,
    include_standard_output: bool = False,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Return the principal cumulative 31-cohort ED livestock pathway.

    Dairy cows, suckler cows and total sheep are the externally controlled
    populations. Young cattle and the ten sheep cohorts are derived
    sequentially from the previous solved ED state. Standard Output, when
    requested, is appended only after the physical livestock state is complete.
    """

    cattle = _adult_driven_cattle_pathway(adult_pathway)
    sheep = build_sheep_cohort_pathway(adult_pathway)

    keys = ["CSOED", "MILESTONE_YEAR"]
    sheep_columns = keys + [
        column
        for column in sheep.columns
        if column.startswith("BASE_SHEEP_COHORT_")
        or column.startswith("PREVIOUS_SHEEP_COHORT_")
        or column.startswith("INCREMENTAL_REDUCTION_SHEEP_COHORT_")
        or column.startswith("CUMULATIVE_REDUCTION_SHEEP_COHORT_")
        or column.startswith("SCENARIO_SHEEP_COHORT_")
        or column
        in {
            "BASE_GOBLIN_10_SHEEP_TOTAL",
            "PREVIOUS_GOBLIN_10_SHEEP_TOTAL",
            "INCREMENTAL_REDUCTION_GOBLIN_10_SHEEP_TOTAL",
            "CUMULATIVE_REDUCTION_GOBLIN_10_SHEEP_TOTAL",
            "SCENARIO_GOBLIN_10_SHEEP_TOTAL",
        }
    ]
    out = cattle.merge(
        sheep[sheep_columns],
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if out.filter(regex=r"^SCENARIO_SHEEP_COHORT_").isna().any().any():
        raise AssertionError(
            "sheep cohort pathway failed merge into cattle pathway"
        )

    out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_21_CATTLE_TOTAL"]
        + out["BASE_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["PREVIOUS_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["PREVIOUS_GOBLIN_21_CATTLE_TOTAL"]
        + out["PREVIOUS_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["INCREMENTAL_REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["INCREMENTAL_REDUCTION_GOBLIN_21_CATTLE_TOTAL"]
        + out["INCREMENTAL_REDUCTION_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"]
        + out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["CUMULATIVE_REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"]
        - out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"]
    )

    if include_standard_output:
        out = add_pathway_standard_output(
            out,
            mapping_path=mapping_path,
            coefficient_path=coefficient_path,
        )
        ordered = out.sort_values(
            ["CSOED", "MILESTONE_YEAR"], kind="stable"
        )
        previous_exposure = ordered.groupby("CSOED", sort=False)[
            "SO_LIVESTOCK_EXPOSURE_2020_EUR"
        ].shift(fill_value=0.0)
        ordered["INCREMENTAL_SO_LIVESTOCK_EXPOSURE_2020_EUR"] = (
            ordered["SO_LIVESTOCK_EXPOSURE_2020_EUR"]
            - previous_exposure
        )
        out = ordered.sort_index()

    return out


def build_full_livestock_pathway(
    adult_pathway: pd.DataFrame,
    cattle_targets_by_year: Mapping[int, Mapping[str, int]],
    *,
    include_standard_output: bool = False,
) -> pd.DataFrame:
    """Compatibility route using exact national 21-cohort cattle targets."""

    cattle = build_cattle_cohort_pathway(
        adult_pathway, cattle_targets_by_year
    )
    sheep = build_sheep_cohort_pathway(adult_pathway)

    keys = ["CSOED", "MILESTONE_YEAR"]
    sheep_columns = keys + [
        c
        for c in sheep.columns
        if c.startswith("BASE_SHEEP_COHORT_")
        or c.startswith("PREVIOUS_SHEEP_COHORT_")
        or c.startswith("INCREMENTAL_REDUCTION_SHEEP_COHORT_")
        or c.startswith("CUMULATIVE_REDUCTION_SHEEP_COHORT_")
        or c.startswith("SCENARIO_SHEEP_COHORT_")
        or c
        in {
            "BASE_GOBLIN_10_SHEEP_TOTAL",
            "PREVIOUS_GOBLIN_10_SHEEP_TOTAL",
            "INCREMENTAL_REDUCTION_GOBLIN_10_SHEEP_TOTAL",
            "CUMULATIVE_REDUCTION_GOBLIN_10_SHEEP_TOTAL",
            "SCENARIO_GOBLIN_10_SHEEP_TOTAL",
        }
    ]

    out = cattle.merge(
        sheep[sheep_columns],
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if out.filter(regex=r"^SCENARIO_SHEEP_COHORT_").isna().any().any():
        raise AssertionError(
            "sheep cohort pathway failed merge into cattle pathway"
        )

    out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_21_CATTLE_TOTAL"]
        + out["BASE_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"]
        + out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["CUMULATIVE_REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"]
        - out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"]
    )

    if include_standard_output:
        out = add_pathway_standard_output(out)
    return out
