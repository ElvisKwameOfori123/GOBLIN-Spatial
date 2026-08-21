from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.scenario.control_table import (
    active_scenario_ids,
    load_scenario_controls,
)


def _table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "SCENARIO_NO": 7,
                "SCENARIO_ID": "EDITABLE_CASE",
                "SCENARIO_NAME": "Editable case",
                "ACTIVE": True,
                "TARGET_YEAR": 2050,
                "TARGET_LIVESTOCK_LAND_HA": 2_000_000,
                "DAIRY_COWS": 1_000_000,
                "SUCKLER_COWS": 200_000,
                "AD_GRASS_HA": 100_000,
                "BIOREFINERY_GRASS_HA": 50_000,
                "WILLOW_HA": 75_000,
                "ADDITIONAL_TILLAGE_HA": 25_000,
                "ADDITIONAL_FOREST_HA": 150_000,
                "REWETTING_HA": 40_000,
            },
            {
                "SCENARIO_NO": 8,
                "SCENARIO_ID": "OFF",
                "SCENARIO_NAME": "Inactive",
                "ACTIVE": False,
                "TARGET_YEAR": 2050,
                "TARGET_LIVESTOCK_LAND_HA": 2_100_000,
                "DAIRY_COWS": 900_000,
                "SUCKLER_COWS": 150_000,
                "AD_GRASS_HA": 0,
                "BIOREFINERY_GRASS_HA": 0,
                "WILLOW_HA": 0,
                "ADDITIONAL_TILLAGE_HA": 0,
                "ADDITIONAL_FOREST_HA": 0,
                "REWETTING_HA": 0,
            },
        ]
    )


def test_editable_control_is_resolved_against_selected_baseline() -> None:
    table = _table()
    selected = load_scenario_controls(
        table,
        scenario_id="EDITABLE_CASE",
        baseline_year=2025,
        baseline_grassland_ha=4_100_000,
    )

    assert selected.scenario_no == 7
    assert selected.scenario_name == "Editable case"
    assert selected.baseline_year == 2025
    assert selected.gross_release_ha == 2_100_000
    assert selected.stage_a_target_ha == 400_000
    assert selected.stage_a_available_before_rewetting_ha == 1_700_000
    assert selected.rewetting_target_ha == 40_000

    milestone = selected.controls.milestone(2050)
    assert milestone.dairy_cows == 1_000_000
    assert milestone.suckler_cows == 200_000
    assert milestone.livestock_land_release_ha == 2_100_000
    assert milestone.land_use_targets_ha["REWETTING"] == 40_000


def test_active_scenario_ids_are_data_driven() -> None:
    assert active_scenario_ids(_table()) == ("EDITABLE_CASE",)


def test_inactive_scenario_cannot_run() -> None:
    with pytest.raises(ValueError, match="inactive"):
        load_scenario_controls(
            _table(),
            scenario_id="OFF",
            baseline_year=2020,
            baseline_grassland_ha=4_000_000,
        )


def test_target_land_cannot_exceed_selected_baseline() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        load_scenario_controls(
            _table(),
            scenario_id="EDITABLE_CASE",
            baseline_year=2020,
            baseline_grassland_ha=1_900_000,
        )
