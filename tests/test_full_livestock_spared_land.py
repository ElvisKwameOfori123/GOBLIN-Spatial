"""Integration tests from GOBLIN national milestones to ED spared grassland."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure import calculate_spared_grassland
from goblin_spatial.scenario import (
    AllocationRule,
    NationalMilestone,
    TransitionPathwayDefinition,
    build_full_livestock_pathway,
    build_transition_pathway,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _baseline() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "YEAR": [2025, 2025, 2025],
            "CSOED": ["A", "B", "C"],
            "County": ["Alpha", "Alpha", "Alpha"],
            "DAIRY_COW": [10, 5, 0],
            "OTHER_COW": [3, 8, 0],
            "TOTAL_SHEEP": [10, 5, 5],
            "ALL_GRASSLAND": [100.0, 80.0, 60.0],
        }
    )

    frame["dairy_cows"] = frame["DAIRY_COW"]
    frame["suckler_cows"] = frame["OTHER_COW"]
    frame["bulls"] = [2, 2, 1]

    for cohort in FINAL_21_COHORTS:
        if cohort in {"dairy_cows", "suckler_cows", "bulls"}:
            continue
        if cohort.startswith("DxD_") or cohort.startswith("DxB_"):
            frame[cohort] = [4, 2, 2]  # C is a dairy-origin receiver/finisher ED.
        elif cohort.startswith("BxB_"):
            frame[cohort] = [1, 4, 2]
        else:
            raise AssertionError(cohort)

    sheep_matrix = [
        [2, 1, 1, 1, 1, 1, 1, 1, 1, 0],  # 10
        [1, 1, 1, 0, 1, 0, 1, 0, 0, 0],  # 5
        [0, 1, 0, 0, 0, 0, 1, 1, 1, 1],  # 5
    ]
    for j, cohort in enumerate(GOBLIN_SHEEP_10):
        frame[cohort] = [row[j] for row in sheep_matrix]

    return frame


def _cattle_targets(frame: pd.DataFrame, milestones: tuple[NationalMilestone, ...]):
    baseline_totals = {c: int(frame[c].sum()) for c in FINAL_21_COHORTS}
    drops = {2030: 1, 2040: 2, 2050: 3}
    targets = {}
    for milestone in milestones:
        values = {
            cohort: max(0, baseline_totals[cohort] - drops[milestone.year])
            for cohort in FINAL_21_COHORTS
        }
        values["dairy_cows"] = milestone.dairy_cows
        values["suckler_cows"] = milestone.suckler_cows
        targets[milestone.year] = values
    return targets


def _dm_profiles(years=(2025, 2030, 2040, 2050)):
    profiles = {}
    for year in years:
        profile = {cohort: 1.0 for cohort in FINAL_21_COHORTS}
        profile.update({cohort: 0.2 for cohort in GOBLIN_SHEEP_10})
        profiles[year] = profile
    return profiles


def test_full_pathway_reaches_spared_land_and_preserves_closure():
    baseline = _baseline()
    milestones = (
        NationalMilestone(2030, dairy_cows=13, suckler_cows=10, sheep=18),
        NationalMilestone(2040, dairy_cows=10, suckler_cows=8, sheep=15),
        NationalMilestone(2050, dairy_cows=8, suckler_cows=6, sheep=12),
    )
    pathway = TransitionPathwayDefinition(
        name="TEST_NZ",
        baseline_year=2025,
        milestones=milestones,
        allocation_rule=AllocationRule.PRORATA,
    )

    adults = build_transition_pathway(baseline, pathway, expected_eds=3)
    livestock = build_full_livestock_pathway(
        adults, _cattle_targets(baseline, milestones)
    )
    land = calculate_spared_grassland(
        livestock,
        _dm_profiles(),
        supply_multiplier_by_year={2030: 1.0, 2040: 1.0, 2050: 1.0},
    )

    for year, milestone in [(2030, milestones[0]), (2040, milestones[1]), (2050, milestones[2])]:
        part = land.loc[land["MILESTONE_YEAR"] == year]
        assert int(part["SCENARIO_COHORT_dairy_cows"].sum()) == milestone.dairy_cows
        assert int(part["SCENARIO_COHORT_suckler_cows"].sum()) == milestone.suckler_cows
        assert int(part["SCENARIO_GOBLIN_10_SHEEP_TOTAL"].sum()) == milestone.sheep
        assert (part["POTENTIAL_SPARED_GRASSLAND_HA"] >= 0).all()
        assert (
            part["POTENTIAL_SPARED_GRASSLAND_HA"] <= part["ALL_GRASSLAND"] + 1e-9
        ).all()

    national_release = land.groupby("MILESTONE_YEAR")["POTENTIAL_SPARED_GRASSLAND_HA"].sum()
    assert national_release.loc[2030] < national_release.loc[2040] < national_release.loc[2050]

    # C has no dairy cows but carries dairy-origin cohorts and therefore uses
    # the same-county receiver signal rather than being excluded.
    c2030 = land.loc[(land["CSOED"] == "C") & (land["MILESTONE_YEAR"] == 2030)].iloc[0]
    assert c2030["BASE_DAIRY_COW"] == 0
    assert c2030["REDUCTION_SIGNAL_SOURCE_DxB_calves_m"] == "COUNTY_RECEIVER"


def test_pasture_supply_improvement_releases_more_land_than_no_improvement():
    baseline = _baseline()
    milestones = (
        NationalMilestone(2030, dairy_cows=13, suckler_cows=10, sheep=18),
        NationalMilestone(2040, dairy_cows=10, suckler_cows=8, sheep=15),
        NationalMilestone(2050, dairy_cows=8, suckler_cows=6, sheep=12),
    )
    adults = build_transition_pathway(
        baseline,
        TransitionPathwayDefinition(
            name="TEST_INTENSIFICATION",
            baseline_year=2025,
            milestones=milestones,
        ),
        expected_eds=3,
    )
    livestock = build_full_livestock_pathway(
        adults, _cattle_targets(baseline, milestones)
    )

    no_change = calculate_spared_grassland(livestock, _dm_profiles())
    improved = calculate_spared_grassland(
        livestock,
        _dm_profiles(),
        supply_multiplier_by_year={2030: 1.05, 2040: 1.10, 2050: 1.20},
    )

    base_2050 = no_change.loc[no_change["MILESTONE_YEAR"] == 2050, "POTENTIAL_SPARED_GRASSLAND_HA"].sum()
    improved_2050 = improved.loc[improved["MILESTONE_YEAR"] == 2050, "POTENTIAL_SPARED_GRASSLAND_HA"].sum()
    assert improved_2050 > base_2050


def test_null_livestock_scenario_has_zero_spared_grassland():
    baseline = _baseline()
    milestone = NationalMilestone(
        2030,
        dairy_cows=int(baseline["DAIRY_COW"].sum()),
        suckler_cows=int(baseline["OTHER_COW"].sum()),
        sheep=int(baseline["TOTAL_SHEEP"].sum()),
    )
    adults = build_transition_pathway(
        baseline,
        TransitionPathwayDefinition(
            name="NULL",
            baseline_year=2025,
            milestones=(milestone,),
        ),
        expected_eds=3,
    )
    cattle_targets = {
        2030: {cohort: int(baseline[cohort].sum()) for cohort in FINAL_21_COHORTS}
    }
    livestock = build_full_livestock_pathway(adults, cattle_targets)
    land = calculate_spared_grassland(
        livestock,
        _dm_profiles(years=(2025, 2030)),
    )

    assert land["POTENTIAL_SPARED_GRASSLAND_HA"].sum() == pytest.approx(0.0)
    assert np.allclose(
        land["SCENARIO_REQUIRED_GRASSLAND_HA"].to_numpy(dtype=float),
        land["ALL_GRASSLAND"].to_numpy(dtype=float),
        atol=1e-9,
    )
