from __future__ import annotations

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import GoblinNationalMilestone, GoblinPathwayControls
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _row(ed: str, dairy: int, suckler: int) -> dict:
    row = {
        "YEAR": 2020,
        "CSOED": ed,
        "County": "Test",
        "DAIRY_COW": dairy,
        "OTHER_COW": suckler,
        "TOTAL_SHEEP": 10,
        "ALL_GRASSLAND": 100.0,
        "dairy_cows": dairy,
        "suckler_cows": suckler,
        "bulls": 4,
    }
    for cohort in FINAL_21_COHORTS:
        row.setdefault(cohort, 10)
    row["dairy_cows"] = dairy
    row["suckler_cows"] = suckler
    row["bulls"] = 4
    for cohort in GOBLIN_SHEEP_10:
        row[cohort] = 1
    return row


def _panel() -> pd.DataFrame:
    return pd.DataFrame([
        _row("A", dairy=100, suckler=50),
        _row("B", dairy=60, suckler=30),
    ])


def _controls() -> GoblinPathwayControls:
    return GoblinPathwayControls(
        scenario_id="SI_SG",
        baseline_year=2020,
        milestones=(
            GoblinNationalMilestone(
                year=2050,
                dairy_cows=120,
                suckler_cows=60,
            ),
        ),
    )


def test_principal_endpoint_hits_adult_targets_and_solves_full_cattle_state():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(),
        expected_eds=2,
        include_standard_output=False,
    )

    assert set(out["MILESTONE_YEAR"]) == {2050}
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 120
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 60
    assert int(out["SCENARIO_TOTAL_SHEEP"].sum()) == 20

    assert (out.loc[out["BASE_DAIRY_COW"] > 0, "CUMULATIVE_REDUCTION_DAIRY_COW"] > 0).all()
    assert (out.loc[out["BASE_OTHER_COW"] > 0, "CUMULATIVE_REDUCTION_OTHER_COW"] > 0).all()

    cattle_cols = [f"SCENARIO_COHORT_{cohort}" for cohort in FINAL_21_COHORTS]
    assert (out[cattle_cols].sum(axis=1) == out["SCENARIO_TOTAL_CATTLE"]).all()
    assert (out["SCENARIO_TOTAL_CATTLE"] <= out["BASE_TOTAL_CATTLE"]).all()

    sheep_cols = [f"SCENARIO_SHEEP_COHORT_{cohort}" for cohort in GOBLIN_SHEEP_10]
    assert (out[sheep_cols].sum(axis=1) == 10).all()


def test_dairy_protection_changes_intensity_without_exempting_an_ed():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(),
        allocation_rule=AllocationRule.DAIRY_PROTECTION,
        expected_eds=2,
        include_standard_output=False,
    )

    a = out.loc[out["CSOED"] == "A"].iloc[0]
    b = out.loc[out["CSOED"] == "B"].iloc[0]
    assert a["CUMULATIVE_REDUCTION_DAIRY_COW"] > 0
    assert b["CUMULATIVE_REDUCTION_DAIRY_COW"] > 0
    assert a["CUMULATIVE_REDUCTION_PCT_DAIRY_COW"] < b["CUMULATIVE_REDUCTION_PCT_DAIRY_COW"]
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 120
