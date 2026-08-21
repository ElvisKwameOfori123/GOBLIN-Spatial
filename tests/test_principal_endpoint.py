from pathlib import Path

import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import GoblinNationalMilestone, GoblinPathwayControls
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)
from goblin_spatial.scenario.principal_allocation import PRINCIPAL_PROTECTION_STRENGTH
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/controls/cohort2012-2020.csv"


def _panel():
    rows = []
    specs = [
        ("A", 100, 50, 10, 100.0, 10, 50.0, 55.0, 150_000.0),
        ("B", 60, 30, 10, 80.0, 8, 40.0, 62.0, 72_000.0),
    ]
    for ed, dairy, suckler, sheep, grass, holdings, size, age, livestock_so in specs:
        row = {
            "YEAR": 2020,
            "CSOED": ed,
            "County": "Test",
            "DAIRY_COW": dairy,
            "OTHER_COW": suckler,
            "TOTAL_SHEEP": sheep,
            "ALL_GRASSLAND": grass,
            "AGRICULTURAL_HOLDINGS": holdings,
            "AVERAGE_SIZE_OF_HOLDINGS": size,
            "MEDIAN_AGE_OF_HOLDER": age,
            "SO_LIVESTOCK_2020_EUR": livestock_so,
        }
        for cohort in FINAL_21_COHORTS:
            row[cohort] = 10
        row["dairy_cows"], row["suckler_cows"] = dairy, suckler
        row["TOTAL_CATTLE"] = sum(row[c] for c in FINAL_21_COHORTS)
        for cohort in GOBLIN_SHEEP_10:
            row[cohort] = 1
        rows.append(row)
    return pd.DataFrame(rows)


def _controls(dairy, suckler):
    return GoblinPathwayControls(
        "SI_SG",
        2020,
        (GoblinNationalMilestone(year=2050, dairy_cows=dairy, suckler_cows=suckler),),
    )


def test_principal_category_endpoints_close_exactly():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(120, 60),
        expected_eds=2,
        include_standard_output=False,
    )
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 120
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 60
    assert set(out["ALLOCATION_POLICY"]) == {"PRORATA"}
    assert set(out["PROTECTION_STRENGTH_LAMBDA"]) == {PRINCIPAL_PROTECTION_STRENGTH}
    cols = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]
    assert (out[cols].sum(axis=1) == out["SCENARIO_TOTAL_CATTLE"]).all()


def test_si_like_dairy_expansion_is_prorata_within_existing_footprint():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(165, 15),
        allocation_rule=AllocationRule.DAIRY_PROTECTION,
        expected_eds=2,
        include_standard_output=False,
    )
    assert int(out["BASE_DAIRY_COW"].sum()) == 160
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 165
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 15
    assert set(out["DAIRY_ALLOCATION_MODE"]) == {
        "PRORATA_EXPANSION_UNDER_PROTECTION_POLICY"
    }
    assert (out.loc[out["BASE_DAIRY_COW"].eq(0), "SCENARIO_DAIRY_COW"] == 0).all()
    assert int(out["DAIRY_EXPANSION_HEAD"].sum()) == 5


def test_dairy_protection_redistributes_contraction_but_keeps_national_endpoint():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(120, 60),
        allocation_rule=AllocationRule.DAIRY_PROTECTION,
        expected_eds=2,
        include_standard_output=False,
    )
    a = out.loc[out["CSOED"].eq("A")].iloc[0]
    b = out.loc[out["CSOED"].eq("B")].iloc[0]
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 120
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 60
    assert a["DAIRY_STRENGTH_SCORE"] > b["DAIRY_STRENGTH_SCORE"]
    assert a["DAIRY_BURDEN_FACTOR"] < b["DAIRY_BURDEN_FACTOR"]
    assert a["SUCKLER_BURDEN_FACTOR"] < b["SUCKLER_BURDEN_FACTOR"]


def test_sheep_are_carried_unchanged_in_principal_sc1():
    out = run_principal_goblin_endpoint(
        _panel(),
        _controls(120, 60),
        expected_eds=2,
        include_standard_output=False,
    )
    assert (out["SCENARIO_TOTAL_SHEEP"] == out["BASE_TOTAL_SHEEP"]).all()
    for cohort in GOBLIN_SHEEP_10:
        assert (
            out[f"SCENARIO_SHEEP_COHORT_{cohort}"]
            == out[f"BASE_SHEEP_COHORT_{cohort}"]
        ).all()


def test_experimental_allocation_rule_is_rejected_by_principal_endpoint():
    with pytest.raises(ValueError, match="not a validated principal SC1 policy"):
        run_principal_goblin_endpoint(
            _panel(),
            _controls(120, 60),
            allocation_rule=AllocationRule.RANDOMISED,
            expected_eds=2,
            include_standard_output=False,
        )


def test_principal_endpoint_closes_to_goblin_derived_21_cohort_targets():
    controls = _controls(120, 60)
    out = run_principal_goblin_endpoint(
        _panel(),
        controls,
        expected_eds=2,
        include_standard_output=False,
        cohort_reference_path=str(REFERENCE),
    )
    reference = load_goblin_cohort_reference(REFERENCE, reference_year=2020)
    targets = derive_national_cohort_targets(
        dairy_cows=120,
        suckler_cows=60,
        reference_counts=reference,
    )
    for cohort in FINAL_21_COHORTS:
        assert int(out[f"SCENARIO_COHORT_{cohort}"].sum()) == targets[cohort]
    assert int(out["SCENARIO_TOTAL_CATTLE"].sum()) == sum(targets.values())
    assert out["NATIONAL_COHORT_TARGETS_APPLIED"].all()
    assert set(out["NATIONAL_COHORT_TARGET_SOURCE"]) == {
        "GOBLIN_COHORT_RELATIONSHIP_2020"
    }


def test_national_closure_does_not_flatten_ed_cohort_signature():
    panel = _panel()
    panel.loc[panel["CSOED"].eq("A"), "DxD_calves_m"] = 20
    panel.loc[panel["CSOED"].eq("B"), "DxD_calves_m"] = 5
    panel["TOTAL_CATTLE"] = panel[list(FINAL_21_COHORTS)].sum(axis=1)
    out = run_principal_goblin_endpoint(
        panel,
        _controls(120, 60),
        expected_eds=2,
        include_standard_output=False,
        cohort_reference_path=str(REFERENCE),
    )
    a = int(
        out.loc[out["CSOED"].eq("A"), "SCENARIO_COHORT_DxD_calves_m"].iloc[0]
    )
    b = int(
        out.loc[out["CSOED"].eq("B"), "SCENARIO_COHORT_DxD_calves_m"].iloc[0]
    )
    assert a > b
