"""Compose cattle and sheep milestone pathways into one ED livestock state."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from goblin_spatial.scenario.cattle_pathway import build_cattle_cohort_pathway
from goblin_spatial.scenario.sheep_pathway import build_sheep_cohort_pathway


def build_full_livestock_pathway(
    adult_pathway: pd.DataFrame,
    cattle_targets_by_year: Mapping[int, Mapping[str, int]],
) -> pd.DataFrame:
    """Return one cumulative 31-cohort ED pathway for cattle and sheep."""

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
    return out
