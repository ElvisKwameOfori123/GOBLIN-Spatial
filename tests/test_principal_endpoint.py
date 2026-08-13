import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import GoblinNationalMilestone, GoblinPathwayControls
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _panel():
    rows = []
    for ed, dairy, suckler in [("A", 100, 50), ("B", 60, 30)]:
        row = {"YEAR": 2020, "CSOED": ed, "County": "Test", "DAIRY_COW": dairy,
               "OTHER_COW": suckler, "TOTAL_SHEEP": 10, "ALL_GRASSLAND": 100.0}
        for cohort in FINAL_21_COHORTS:
            row[cohort] = 10
        row["dairy_cows"], row["suckler_cows"] = dairy, suckler
        row["TOTAL_CATTLE"] = sum(row[c] for c in FINAL_21_COHORTS)
        for cohort in GOBLIN_SHEEP_10:
            row[cohort] = 1
        rows.append(row)
    return pd.DataFrame(rows)


def _controls(dairy, suckler):
    return GoblinPathwayControls("SI_SG", 2020, (
        GoblinNationalMilestone(year=2050, dairy_cows=dairy, suckler_cows=suckler),
    ))


def test_endpoint_closes_and_every_ed_contracts():
    out = run_principal_goblin_endpoint(
        _panel(), _controls(120, 60), expected_eds=2, include_standard_output=False
    )
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 120
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 60
    assert (out["REDUCTION_ADULT_COWS"] > 0).all()
    assert (out["SCENARIO_TOTAL_CATTLE"] < out["BASE_TOTAL_CATTLE"]).all()
    cols = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]
    assert (out[cols].sum(axis=1) == out["SCENARIO_TOTAL_CATTLE"]).all()


def test_si_like_composition_can_raise_dairy_inside_total_contraction():
    out = run_principal_goblin_endpoint(
        _panel(), _controls(165, 15), expected_eds=2, include_standard_output=False
    )
    assert int(out["BASE_DAIRY_COW"].sum()) == 160
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 165
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 15
    assert (out["REDUCTION_ADULT_COWS"] > 0).all()
    assert (out["SCENARIO_TOTAL_CATTLE"] < out["BASE_TOTAL_CATTLE"]).all()


def test_dairy_protection_changes_total_adult_reduction_intensity():
    out = run_principal_goblin_endpoint(
        _panel(), _controls(120, 60), allocation_rule=AllocationRule.DAIRY_PROTECTION,
        expected_eds=2, include_standard_output=False
    )
    a = out.loc[out["CSOED"].eq("A")].iloc[0]
    b = out.loc[out["CSOED"].eq("B")].iloc[0]
    assert a["REDUCTION_ADULT_COWS"] > 0 and b["REDUCTION_ADULT_COWS"] > 0
    assert a["REDUCTION_PCT_ADULT_COWS"] < b["REDUCTION_PCT_ADULT_COWS"]
