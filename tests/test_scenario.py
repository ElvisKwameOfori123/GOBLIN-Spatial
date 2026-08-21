"""Compact tests for the ED scenario allocation foundation."""

from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.scenario import (
    AllocationRule,
    ScenarioDefinition,
    allocate_adult_livestock_scenario,
)


def _panel() -> pd.DataFrame:
    rows = []
    for year, scale in [(2020, 1), (2025, 2)]:
        rows.extend(
            [
                {
                    "YEAR": year,
                    "CSOED": "A",
                    "DAIRY_COW": 100 * scale,
                    "OTHER_COW": 20 * scale,
                    "TOTAL_SHEEP": 50 * scale,
                    "CORE_SCORE": 1.0,
                },
                {
                    "YEAR": year,
                    "CSOED": "B",
                    "DAIRY_COW": 60 * scale,
                    "OTHER_COW": 40 * scale,
                    "TOTAL_SHEEP": 30 * scale,
                    "CORE_SCORE": 0.5,
                },
                {
                    "YEAR": year,
                    "CSOED": "C",
                    "DAIRY_COW": 40 * scale,
                    "OTHER_COW": 40 * scale,
                    "TOTAL_SHEEP": 20 * scale,
                    "CORE_SCORE": 0.0,
                },
                {
                    "YEAR": year,
                    "CSOED": "D",
                    "DAIRY_COW": 0,
                    "OTHER_COW": 0,
                    "TOTAL_SHEEP": 0,
                    "CORE_SCORE": 0.2,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_prorata_reduction_closes_and_preserves_footprint():
    scenario = ScenarioDefinition(
        name="thirty_percent",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.25,
        sheep_reduction=0.10,
    )
    out = allocate_adult_livestock_scenario(_panel(), scenario, expected_eds=4)

    assert len(out) == 4
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 140
    assert int(out["SCENARIO_OTHER_COW"].sum()) == 75
    assert int(out["SCENARIO_TOTAL_SHEEP"].sum()) == 90
    assert (out["SCENARIO_DAIRY_COW"] <= out["BASE_DAIRY_COW"]).all()
    assert (out["SCENARIO_OTHER_COW"] <= out["BASE_OTHER_COW"]).all()
    assert (out["SCENARIO_TOTAL_SHEEP"] <= out["BASE_TOTAL_SHEEP"]).all()

    # Every ED that has the relevant baseline livestock participates.
    for column in ["DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"]:
        eligible = out[f"BASE_{column}"] > 0
        assert (out.loc[eligible, f"REDUCTION_{column}"] > 0).all()

    zero = out.loc[out["CSOED"] == "D"].iloc[0]
    assert zero["SCENARIO_DAIRY_COW"] == 0
    assert zero["SCENARIO_OTHER_COW"] == 0
    assert zero["SCENARIO_TOTAL_SHEEP"] == 0


def test_baseline_year_switch_uses_2025_state():
    scenario = ScenarioDefinition(
        name="2025_start",
        baseline_year=2025,
        target_year=2050,
        dairy_reduction=0.50,
    )
    out = allocate_adult_livestock_scenario(_panel(), scenario, expected_eds=4)

    assert int(out["BASE_DAIRY_COW"].sum()) == 400
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 200
    assert set(out["SCENARIO_BASELINE_YEAR"]) == {2025}


def test_null_scenario_reproduces_selected_baseline_exactly():
    scenario = ScenarioDefinition(
        name="null_2025",
        baseline_year=2025,
        target_year=2025,
    )
    out = allocate_adult_livestock_scenario(_panel(), scenario, expected_eds=4)

    for column in ["DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"]:
        assert out[f"SCENARIO_{column}"].tolist() == out[f"BASE_{column}"].tolist()
        assert int(out[f"REDUCTION_{column}"].sum()) == 0


def test_score_weighting_protects_higher_score_ed_without_exemption():
    scenario = ScenarioDefinition(
        name="protect_core",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.50,
        allocation_rule=AllocationRule.SCORE_WEIGHTED,
        score_column="CORE_SCORE",
    )
    out = allocate_adult_livestock_scenario(_panel(), scenario, expected_eds=4)
    a = out.loc[out["CSOED"] == "A"].iloc[0]
    c = out.loc[out["CSOED"] == "C"].iloc[0]

    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 100
    assert a["REDUCTION_PCT_DAIRY_COW"] < c["REDUCTION_PCT_DAIRY_COW"]
    assert (out.loc[out["BASE_DAIRY_COW"] > 0, "REDUCTION_DAIRY_COW"] > 0).all()


def test_dairy_protection_cuts_high_dairy_ed_less_but_never_exempts_it():
    scenario = ScenarioDefinition(
        name="dairy_protection",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.50,
        allocation_rule=AllocationRule.DAIRY_PROTECTION,
    )
    out = allocate_adult_livestock_scenario(_panel(), scenario, expected_eds=4)
    high_dairy = out.loc[out["CSOED"] == "A"].iloc[0]
    low_dairy = out.loc[out["CSOED"] == "C"].iloc[0]

    # The national reduction is unchanged: 200 -> 100 dairy cows.
    assert int(out["REDUCTION_DAIRY_COW"].sum()) == 100
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 100

    # Protection changes intensity, not participation.
    assert high_dairy["BASE_DAIRY_COW"] > low_dairy["BASE_DAIRY_COW"]
    assert high_dairy["REDUCTION_DAIRY_COW"] > 0
    assert low_dairy["REDUCTION_DAIRY_COW"] > 0
    assert (
        high_dairy["REDUCTION_PCT_DAIRY_COW"]
        < low_dairy["REDUCTION_PCT_DAIRY_COW"]
    )


def test_universal_participation_can_produce_complete_local_exit():
    panel = pd.DataFrame(
        [
            {"YEAR": 2020, "CSOED": "A", "DAIRY_COW": 1, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
            {"YEAR": 2020, "CSOED": "B", "DAIRY_COW": 9, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
        ]
    )
    scenario = ScenarioDefinition(
        name="shared_reduction_with_exit",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.20,  # remove 2 animals, one from each eligible ED
    )
    out = allocate_adult_livestock_scenario(panel, scenario, expected_eds=2)

    a = out.loc[out["CSOED"] == "A"].iloc[0]
    b = out.loc[out["CSOED"] == "B"].iloc[0]
    assert a["REDUCTION_DAIRY_COW"] == 1
    assert a["SCENARIO_DAIRY_COW"] == 0
    assert b["REDUCTION_DAIRY_COW"] == 1
    assert b["SCENARIO_DAIRY_COW"] == 8
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 8


def test_universal_participation_fails_if_integer_reduction_is_too_small():
    panel = pd.DataFrame(
        [
            {"YEAR": 2020, "CSOED": "A", "DAIRY_COW": 5, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
            {"YEAR": 2020, "CSOED": "B", "DAIRY_COW": 5, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
            {"YEAR": 2020, "CSOED": "C", "DAIRY_COW": 5, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
        ]
    )
    scenario = ScenarioDefinition(
        name="too_small_for_universal_participation",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.10,
    )
    with pytest.raises(ValueError, match="universal-participation"):
        allocate_adult_livestock_scenario(panel, scenario, expected_eds=3)


def test_baseline_minus_reduction_identity_with_five_plus_seven_example():
    panel = pd.DataFrame(
        [
            {"YEAR": 2020, "CSOED": "A", "DAIRY_COW": 5, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
            {"YEAR": 2020, "CSOED": "B", "DAIRY_COW": 7, "OTHER_COW": 0, "TOTAL_SHEEP": 0},
        ]
    )
    scenario = ScenarioDefinition(
        name="remove_three",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.25,  # 12 baseline -> 9 target -> remove exactly 3
    )
    out = allocate_adult_livestock_scenario(panel, scenario, expected_eds=2)

    assert int(out["BASE_DAIRY_COW"].sum()) == 12
    assert int(out["REDUCTION_DAIRY_COW"].sum()) == 3
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == 9
    assert (
        out["BASE_DAIRY_COW"] - out["REDUCTION_DAIRY_COW"]
        == out["SCENARIO_DAIRY_COW"]
    ).all()
