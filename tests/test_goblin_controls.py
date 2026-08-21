from __future__ import annotations

from pathlib import Path

import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
    load_adult_endpoint_controls,
)


ROOT = Path(__file__).resolve().parents[1]
STYLES_ENDPOINTS = ROOT / "configs/styles_split_gas_adult_endpoints.csv"


def _cohort_targets(total_each: int = 1, *, dairy: int | None = None, suckler: int | None = None) -> dict[str, int]:
    out = {cohort: total_each for cohort in FINAL_21_COHORTS}
    if dairy is not None:
        out["dairy_cows"] = dairy
    if suckler is not None:
        out["suckler_cows"] = suckler
    return out


def test_pathway_controls_preserve_explicit_quantities() -> None:
    milestone = GoblinNationalMilestone(
        year=2050,
        dairy_cows=700_000,
        suckler_cows=300_000,
        total_cattle=3_000_000,
        livestock_land_release_ha=1_500_000.0,
        land_use_targets_ha={"FOREST": 300_000.0, "WILLOW": 100_000.0},
        available_land_residual_ha=400_000.0,
    )
    controls = GoblinPathwayControls(
        scenario_id="BE_SG",
        baseline_year=2020,
        milestones=(milestone,),
    )

    assert controls.target_year == 2050
    assert controls.total_cattle_targets_by_year() == {2050: 3_000_000}
    assert controls.livestock_land_release_by_year() == {2050: 1_500_000.0}
    assert controls.milestone(2050).land_use_targets_ha["WILLOW"] == 100_000.0
    assert controls.milestone(2050).available_land_residual_ha == 400_000.0


def test_complete_cohort_controls_must_close_to_adults_and_total_cattle() -> None:
    cohorts = _cohort_targets(10, dairy=20, suckler=20)
    total = sum(cohorts.values())
    milestone = GoblinNationalMilestone(
        year=2050,
        dairy_cows=20,
        suckler_cows=20,
        total_cattle=total,
        cattle_cohorts=cohorts,
    )
    controls = GoblinPathwayControls(
        scenario_id="SI_SG",
        baseline_year=2020,
        milestones=(milestone,),
    )

    assert controls.cattle_cohort_targets_by_year()[2050] == cohorts

    with pytest.raises(ValueError, match="sum\\(cattle_cohorts\\)"):
        GoblinNationalMilestone(
            year=2050,
            dairy_cows=20,
            suckler_cows=20,
            total_cattle=total + 1,
            cattle_cohorts=cohorts,
        )

    bad_adults = dict(cohorts)
    bad_adults["dairy_cows"] = 19
    with pytest.raises(ValueError, match="dairy_cows"):
        GoblinNationalMilestone(
            year=2050,
            dairy_cows=20,
            suckler_cows=20,
            cattle_cohorts=bad_adults,
        )


def test_partial_or_unknown_cohort_controls_are_rejected() -> None:
    partial = {FINAL_21_COHORTS[0]: 100}
    with pytest.raises(ValueError, match="complete 21-cohort set"):
        GoblinNationalMilestone(
            year=2050,
            dairy_cows=20,
            suckler_cows=20,
            cattle_cohorts=partial,
        )


def test_available_land_is_kept_separate_from_livestock_land_release() -> None:
    milestone = GoblinNationalMilestone(
        year=2050,
        dairy_cows=100,
        suckler_cows=100,
        livestock_land_release_ha=1_590_000.0,
        available_land_residual_ha=403_000.0,
    )

    assert milestone.livestock_land_release_ha == 1_590_000.0
    assert milestone.available_land_residual_ha == 403_000.0
    assert milestone.livestock_land_release_ha != milestone.available_land_residual_ha


def test_pathway_years_are_unique_ascending_and_after_baseline() -> None:
    m2030 = GoblinNationalMilestone(year=2030, dairy_cows=100, suckler_cows=100)
    m2050 = GoblinNationalMilestone(year=2050, dairy_cows=80, suckler_cows=80)

    with pytest.raises(ValueError, match="unique and ascending"):
        GoblinPathwayControls(
            scenario_id="SI_SG",
            baseline_year=2020,
            milestones=(m2050, m2030),
        )

    with pytest.raises(ValueError, match="follow baseline_year"):
        GoblinPathwayControls(
            scenario_id="SI_SG",
            baseline_year=2020,
            milestones=(GoblinNationalMilestone(year=2020, dairy_cows=100, suckler_cows=100),),
        )


def test_total_cattle_cannot_be_smaller_than_adult_cows() -> None:
    with pytest.raises(ValueError, match="cannot be smaller"):
        GoblinNationalMilestone(
            year=2050,
            dairy_cows=100,
            suckler_cows=100,
            total_cattle=199,
        )


def test_same_endpoint_has_different_remaining_reduction_from_2020_and_2025() -> None:
    milestone = GoblinNationalMilestone(
        year=2050,
        dairy_cows=1_600_000,
        suckler_cows=160_000,
    )
    earlier = milestone.adult_reductions_from_baseline(
        baseline_dairy_cows=1_800_000,
        baseline_suckler_cows=800_000,
    )
    later = milestone.adult_reductions_from_baseline(
        baseline_dairy_cows=1_700_000,
        baseline_suckler_cows=700_000,
    )

    assert earlier["target_dairy_cows"] == later["target_dairy_cows"] == 1_600_000
    assert earlier["target_suckler_cows"] == later["target_suckler_cows"] == 160_000
    assert earlier["dairy_reduction_n"] == 200_000
    assert later["dairy_reduction_n"] == 100_000
    assert earlier["suckler_reduction_n"] == 640_000
    assert later["suckler_reduction_n"] == 540_000
    assert earlier["adult_reduction_n"] == 840_000
    assert later["adult_reduction_n"] == 640_000


def test_category_expansion_is_allowed_inside_overall_adult_contraction() -> None:
    milestone = GoblinNationalMilestone(year=2050, dairy_cows=160, suckler_cows=16)
    result = milestone.adult_reductions_from_baseline(
        baseline_dairy_cows=150,
        baseline_suckler_cows=50,
    )
    assert result["change_dairy_cows"] == 10
    assert result["dairy_reduction_n"] == 0
    assert result["change_suckler_cows"] == -34
    assert result["suckler_reduction_n"] == 34
    assert result["adult_reduction_n"] == 24


def test_overall_adult_expansion_is_rejected() -> None:
    milestone = GoblinNationalMilestone(year=2050, dairy_cows=180, suckler_cows=30)
    with pytest.raises(ValueError, match="overall adult-cow contraction"):
        milestone.adult_reductions_from_baseline(
            baseline_dairy_cows=150,
            baseline_suckler_cows=50,
        )


def test_frozen_styles_split_gas_adult_endpoints_are_exact() -> None:
    si = load_adult_endpoint_controls(
        STYLES_ENDPOINTS,
        scenario_id="SI_SG",
        baseline_year=2020,
    )
    be = load_adult_endpoint_controls(
        STYLES_ENDPOINTS,
        scenario_id="BE_SG",
        baseline_year=2025,
    )

    assert si.milestone(2050).dairy_cows == 1_600_000
    assert si.milestone(2050).suckler_cows == 160_000
    assert be.milestone(2050).dairy_cows == 1_540_000
    assert be.milestone(2050).suckler_cows == 154_000
    assert si.milestone(2050).total_cattle is None
    assert be.milestone(2050).livestock_land_release_ha is None
