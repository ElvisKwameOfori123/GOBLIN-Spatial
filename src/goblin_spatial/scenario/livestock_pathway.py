"""Compose cattle and sheep milestone pathways into one ED livestock state."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from goblin_spatial.scenario.cattle_pathway import build_cattle_cohort_pathway
from goblin_spatial.scenario.sheep_pathway import build_sheep_cohort_pathway
from goblin_spatial.standard_output import add_pathway_standard_output


def build_full_livestock_pathway(
    adult_pathway: pd.DataFrame,
    cattle_targets_by_year: Mapping[int, Mapping[str, int]],
) -> pd.DataFrame:
    """Return one cumulative 31-cohort ED pathway with fixed-2020 SO exposure."""

    cattle = build_cattle_cohort_pathway(adult_pathway, cattle_targets_by_year)
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
        or c in {
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
        raise AssertionError("sheep cohort pathway failed merge into cattle pathway")

    out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_21_CATTLE_TOTAL"] + out["BASE_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] + out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["CUMULATIVE_REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"]
        - out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"]
    )

    # Standard Output is deliberately downstream of the physical herd pathway.
    # The same Irish 2020 coefficients value baseline and scenario cohorts, so
    # SO change measures structural production exposure rather than price drift.
    return add_pathway_standard_output(out)
