from pathlib import Path

from goblin_spatial.scenario.styles_pathway_controls import (
    load_styles_split_gas_pathway_controls,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "configs/styles_split_gas_pathway_controls.csv"


def test_si_split_gas_land_accounting_closes_exactly():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="SI_SG", baseline_year=2020
    )
    milestone = controls.milestone(2050)
    assert milestone.dairy_cows == 1_600_000
    assert milestone.suckler_cows == 160_000
    assert milestone.livestock_land_release_ha == 1_593_000.0
    assert milestone.land_use_targets_ha["AD_GRASS"] == 130_000.0
    assert milestone.land_use_targets_ha["FOREST"] == 374_000.0
    assert milestone.available_land_residual_ha == 1_089_000.0
    assert sum(milestone.land_use_targets_ha.values()) + milestone.available_land_residual_ha == milestone.livestock_land_release_ha


def test_be_split_gas_land_accounting_closes_exactly():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="BE_SG", baseline_year=2020
    )
    milestone = controls.milestone(2050)
    assert milestone.dairy_cows == 1_540_000
    assert milestone.suckler_cows == 154_000
    assert milestone.livestock_land_release_ha == 1_587_000.0
    assert milestone.land_use_targets_ha["AD_GRASS"] == 130_000.0
    assert milestone.land_use_targets_ha["BIOREFINERY_GRASS"] == 180_000.0
    assert milestone.land_use_targets_ha["WILLOW"] == 400_000.0
    assert milestone.land_use_targets_ha["ADDITIONAL_TILLAGE"] == 100_000.0
    assert milestone.land_use_targets_ha["FOREST"] == 374_000.0
    assert milestone.available_land_residual_ha == 403_000.0
    assert sum(milestone.land_use_targets_ha.values()) + milestone.available_land_residual_ha == milestone.livestock_land_release_ha


def test_2025_run_keeps_livestock_endpoint_but_withholds_2020_land_release():
    controls = load_styles_split_gas_pathway_controls(
        CONTROLS, scenario_id="SI_SG", baseline_year=2025
    )
    milestone = controls.milestone(2050)
    assert milestone.dairy_cows == 1_600_000
    assert milestone.suckler_cows == 160_000
    assert milestone.livestock_land_release_ha is None
    assert dict(milestone.land_use_targets_ha) == {}
    assert milestone.available_land_residual_ha is None
