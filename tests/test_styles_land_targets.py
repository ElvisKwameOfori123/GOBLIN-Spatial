from pathlib import Path

import pandas as pd

from goblin_spatial.land.styles_targets import (
    allocate_styles_released_land_targets,
    summarise_styles_released_land_targets,
)
from goblin_spatial.scenario.styles_pathway_controls import (
    load_styles_split_gas_pathway_controls,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "configs/styles_split_gas_pathway_controls.csv"


def _frame(total_release: float, *, willow_score: float = 1.0) -> pd.DataFrame:
    first = 1_000_000.0
    second = total_release - first
    return pd.DataFrame(
        {
            "CSOED": ["A", "B"],
            "MILESTONE_YEAR": [2050, 2050],
            "GOBLIN_RELEASED_GRASSLAND_HA": [first, second],
            "FORESTRY_OPPORTUNITY_SCORE": [1.0, 1.0],
            "AD_GRASS_OPPORTUNITY_SCORE": [1.0, 1.0],
            "WILLOW_OPPORTUNITY_SCORE": [willow_score, willow_score],
            "GOBLIN_SOIL_PRODUCTIVITY_SCORE": [1.0, 1.0],
        }
    )


def test_si_styles_targets_close_to_1089k_available_residual():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="SI_SG", baseline_year=2020
    )
    allocated = allocate_styles_released_land_targets(
        _frame(1_593_000.0), controls, attach_scores=False
    )
    summary = summarise_styles_released_land_targets(allocated).iloc[0]
    assert summary["GOBLIN_RELEASED_GRASSLAND_HA"] == 1_593_000.0
    assert summary["ALLOCATED_AD_GRASS_HA"] == 130_000.0
    assert summary["ALLOCATED_FOREST_HA"] == 374_000.0
    assert summary["STYLES_AVAILABLE_RESIDUAL_HA"] == 1_089_000.0
    assert summary["STYLES_TOTAL_UNMET_LAND_TARGET_HA"] == 0.0


def test_be_styles_targets_close_to_403k_available_residual():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="BE_SG", baseline_year=2020
    )
    allocated = allocate_styles_released_land_targets(
        _frame(1_587_000.0), controls, attach_scores=False
    )
    summary = summarise_styles_released_land_targets(allocated).iloc[0]
    assert summary["ALLOCATED_AD_GRASS_HA"] == 130_000.0
    assert summary["ALLOCATED_BIOREFINERY_GRASS_HA"] == 180_000.0
    assert summary["ALLOCATED_WILLOW_HA"] == 400_000.0
    assert summary["ALLOCATED_ADDITIONAL_TILLAGE_HA"] == 100_000.0
    assert summary["ALLOCATED_FOREST_HA"] == 374_000.0
    assert summary["STYLES_AVAILABLE_RESIDUAL_HA"] == 403_000.0
    assert summary["STYLES_TOTAL_UNMET_LAND_TARGET_HA"] == 0.0


def test_unmet_styles_target_is_not_forced_into_ineligible_eds():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="BE_SG", baseline_year=2020
    )
    allocated = allocate_styles_released_land_targets(
        _frame(1_587_000.0, willow_score=0.0), controls, attach_scores=False
    )
    summary = summarise_styles_released_land_targets(allocated).iloc[0]
    assert summary["ALLOCATED_WILLOW_HA"] == 0.0
    assert summary["UNMET_WILLOW_HA"] == 400_000.0
    assert summary["STYLES_TOTAL_UNMET_LAND_TARGET_HA"] == 400_000.0
    assert summary["STYLES_AVAILABLE_RESIDUAL_HA"] == 803_000.0
