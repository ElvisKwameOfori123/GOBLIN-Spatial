"""Tests for the principal sequential livestock-to-land scenario engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.land import LandUseAllocationDefinition
from goblin_spatial.scenario import (
    AllocationRule,
    SequentialScenarioDefinition,
    run_sequential_scenario,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _row(ed: str, county: str, dairy: int, suckler: int, sheep: int) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": 2020,
        "CSOED": ed,
        "County": county,
        "DAIRY_COW": dairy,
        "OTHER_COW": suckler,
        "TOTAL_SHEEP": sheep,
        "ALL_GRASSLAND": 1000.0,
        "GOBLIN_SOIL_G1_SHARE": 0.40,
        "GOBLIN_SOIL_G2_SHARE": 0.40,
        "GOBLIN_SOIL_G3_SHARE": 0.20,
        "FOREST_YC_WEIGHTED_MEAN": 20.0,
        "IFS_SOIL_DOMINANT": "AminDW",
        "IFS_SOIL_DOMINANT_SHARE": 0.80,
    }
    row.update({cohort: 0 for cohort in FINAL_21_COHORTS})
    row.update({cohort: 0 for cohort in GOBLIN_SHEEP_10})
    row["dairy_cows"] = dairy
    row["suckler_cows"] = suckler
    row["DxD_calves_m"] = dairy // 2
    row["BxB_calves_m"] = suckler // 2
    row["Lowland ewes"] = int(round(sheep * 0.6))
    row["Lowland lamb_less_1_yr"] = sheep - row["Lowland ewes"]
    return row


def _panel() -> pd.DataFrame:
    rows = [
        _row("A", "Mayo", 100, 80, 100),
        _row("B", "Mayo", 100, 80, 100),
        _row("C", "Cork", 100, 80, 100),
        _row("D", "Cork", 100, 80, 100),
    ]
    # Only one ED has conservative peat/cutover evidence for rewetting.
    rows[0]["IFS_SOIL_DOMINANT"] = "BktPt"
    rows[0]["IFS_SOIL_DOMINANT_SHARE"] = 0.75
    return pd.DataFrame(rows)


def _pasture_profiles() -> dict[int, dict[str, float]]:
    profile = {
        cohort: 1.0 for cohort in [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
    }
    return {2020: profile, 2030: profile, 2040: profile, 2050: profile}


def test_linear_30_percent_pathway_so_spared_land_and_allocation() -> None:
    definition = SequentialScenarioDefinition(
        name="ALL_30",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.30,
        sheep_reduction=0.30,
    )
    land_use = LandUseAllocationDefinition(
        forest=0.25,
        rewetting=0.20,
        ad_grass=0.20,
        nature=0.10,
    )
    result = run_sequential_scenario(
        _panel(),
        definition,
        expected_eds=4,
        pasture_dm_t_per_head_by_year=_pasture_profiles(),
        land_use=land_use,
    )

    assert result.schedule["MILESTONE_YEAR"].tolist() == [2030, 2040, 2050]
    assert np.allclose(
        result.schedule["dairy_reduction"].to_numpy(dtype=float),
        [0.10, 0.20, 0.30],
    )

    national = result.national.set_index("MILESTONE_YEAR")
    assert int(national.loc[2050, "SCENARIO_DAIRY_COW"]) == 280
    assert int(national.loc[2050, "SCENARIO_OTHER_COW"]) == 224
    assert int(national.loc[2050, "SCENARIO_TOTAL_SHEEP"]) == 280
    assert national.loc[2050, "SO_LIVESTOCK_EXPOSURE_2020_EUR"] > 0
    assert (
        national["SO_LIVESTOCK_EXPOSURE_2020_EUR"].diff().dropna() >= -1e-8
    ).all()
    assert (
        national["POTENTIAL_SPARED_GRASSLAND_HA"].diff().dropna() >= -1e-8
    ).all()

    ed = result.ed
    cumulative_columns = [
        "CUMULATIVE_FOREST_HA",
        "CUMULATIVE_REWETTING_HA",
        "CUMULATIVE_AD_GRASS_HA",
        "CUMULATIVE_WILLOW_HA",
        "CUMULATIVE_ENERGY_GRASS_HA",
        "CUMULATIVE_NATURE_HA",
        "CUMULATIVE_RETAINED_GRASSLAND_HA",
    ]
    assert np.allclose(
        ed[cumulative_columns].sum(axis=1),
        ed["POTENTIAL_SPARED_GRASSLAND_HA"],
        atol=1e-7,
    )

    # Rewetting is screened to the ED with peat/cutover evidence.
    non_peat = ed["CSOED"].ne("A")
    assert np.isclose(ed.loc[non_peat, "CUMULATIVE_REWETTING_HA"].sum(), 0.0)


def test_randomised_allocation_is_reproducible_and_preserves_national_target() -> None:
    common = dict(
        name="ALL_30_RANDOMISED",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.30,
        sheep_reduction=0.30,
        allocation_rule=AllocationRule.RANDOMISED,
        random_seed=77,
    )
    definition = SequentialScenarioDefinition(**common)

    first = run_sequential_scenario(
        _panel(), definition, expected_eds=4, include_standard_output=False
    )
    second = run_sequential_scenario(
        _panel(), definition, expected_eds=4, include_standard_output=False
    )
    prorata = run_sequential_scenario(
        _panel(),
        SequentialScenarioDefinition(
            name="ALL_30",
            baseline_year=2020,
            target_year=2050,
            dairy_reduction=0.30,
            suckler_reduction=0.30,
            sheep_reduction=0.30,
        ),
        expected_eds=4,
        include_standard_output=False,
    )

    a = first.ed.sort_values(["MILESTONE_YEAR", "CSOED"])
    b = second.ed.sort_values(["MILESTONE_YEAR", "CSOED"])
    assert np.array_equal(
        a["CUMULATIVE_REDUCTION_DAIRY_COW"].to_numpy(),
        b["CUMULATIVE_REDUCTION_DAIRY_COW"].to_numpy(),
    )

    random_2050 = a.loc[a["MILESTONE_YEAR"].eq(2050)]
    prorata_2050 = prorata.ed.loc[
        prorata.ed["MILESTONE_YEAR"].eq(2050)
    ].sort_values("CSOED")
    assert int(random_2050["SCENARIO_DAIRY_COW"].sum()) == int(
        prorata_2050["SCENARIO_DAIRY_COW"].sum()
    )
    assert not np.array_equal(
        random_2050.sort_values("CSOED")[
            "CUMULATIVE_REDUCTION_DAIRY_COW"
        ].to_numpy(),
        prorata_2050["CUMULATIVE_REDUCTION_DAIRY_COW"].to_numpy(),
    )
