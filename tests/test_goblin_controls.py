from __future__ import annotations

import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
)


def _cohort_targets(total_each: int = 1) -> dict[str, int]:
    return {cohort: total_each for cohort in FINAL_21_COHORTS}


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


def test_complete_cohort_controls_must_close_to_total_cattle() -> None:
    cohorts = _cohort_targets(10)
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
