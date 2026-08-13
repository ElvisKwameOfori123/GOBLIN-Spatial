"""Tests for explicit cumulative alternative-land target allocation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land import (
    allocate_spared_land_to_cumulative_targets,
    read_land_use_targets,
    summarise_land_target_allocation,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["A", "B", "A", "B"],
            "MILESTONE_YEAR": [2030, 2030, 2050, 2050],
            "POTENTIAL_SPARED_GRASSLAND_HA": [20.0, 30.0, 50.0, 50.0],
            "GOBLIN_SOIL_G1_SHARE": [1.0, 0.5, 1.0, 0.5],
            "GOBLIN_SOIL_G2_SHARE": [0.0, 0.5, 0.0, 0.5],
            "GOBLIN_SOIL_G3_SHARE": [0.0, 0.0, 0.0, 0.0],
            "FOREST_YC_WEIGHTED_MEAN": [24.0, 20.0, 24.0, 20.0],
            "IFS_SOIL_DOMINANT": ["CUT", "AminDW", "CUT", "AminDW"],
            "IFS_SOIL_DOMINANT_SHARE": [1.0, 1.0, 1.0, 1.0],
        }
    )


def _targets() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "MILESTONE_YEAR": [2030, 2050],
            "FOREST_HA": [20.0, 50.0],
            "REWETTING_HA": [10.0, 40.0],
            "AD_GRASS_HA": [0.0, 0.0],
            "WILLOW_HA": [0.0, 0.0],
            "ENERGY_GRASS_HA": [0.0, 0.0],
            "NATURE_HA": [0.0, 0.0],
        }
    )


def test_explicit_cumulative_targets_close_and_do_not_invent_extra_land() -> None:
    allocated = allocate_spared_land_to_cumulative_targets(_frame(), _targets())
    summary = summarise_land_target_allocation(allocated).set_index("MILESTONE_YEAR")

    assert np.isclose(summary.loc[2030, "CUMULATIVE_REWETTING_HA"], 10.0)
    assert np.isclose(summary.loc[2030, "CUMULATIVE_FOREST_HA"], 20.0)
    assert np.isclose(summary.loc[2050, "CUMULATIVE_REWETTING_HA"], 40.0)
    assert np.isclose(summary.loc[2050, "CUMULATIVE_FOREST_HA"], 50.0)
    assert np.isclose(summary.loc[2050, "RETAINED_SPARED_GRASSLAND_HA"], 10.0)

    for year in (2030, 2050):
        block = allocated.loc[allocated["MILESTONE_YEAR"].eq(year)]
        cumulative = sum(
            block[f"CUMULATIVE_{land_use}_HA"].to_numpy(dtype=float)
            for land_use in (
                "FOREST",
                "REWETTING",
                "AD_GRASS",
                "WILLOW",
                "ENERGY_GRASS",
                "NATURE",
            )
        )
        assert np.allclose(
            cumulative + block["RETAINED_SPARED_GRASSLAND_HA"].to_numpy(dtype=float),
            block["POTENTIAL_SPARED_GRASSLAND_HA"].to_numpy(dtype=float),
            atol=1e-7,
        )

    # Only the CUT ED is eligible for the conservative rewetting screen.
    assert np.isclose(
        allocated.loc[allocated["CSOED"].eq("B"), "CUMULATIVE_REWETTING_HA"].sum(),
        0.0,
    )


def test_unmet_cumulative_target_is_carried_forward_when_capacity_appears() -> None:
    frame = _frame()
    frame.loc[frame["MILESTONE_YEAR"].eq(2030) & frame["CSOED"].eq("A"), "POTENTIAL_SPARED_GRASSLAND_HA"] = 10.0
    frame.loc[frame["MILESTONE_YEAR"].eq(2030) & frame["CSOED"].eq("B"), "POTENTIAL_SPARED_GRASSLAND_HA"] = 40.0

    targets = _targets()
    targets[["FOREST_HA", "REWETTING_HA"]] = [[0.0, 40.0], [0.0, 40.0]]
    allocated = allocate_spared_land_to_cumulative_targets(frame, targets)
    summary = summarise_land_target_allocation(allocated).set_index("MILESTONE_YEAR")

    assert np.isclose(summary.loc[2030, "CUMULATIVE_REWETTING_HA"], 10.0)
    assert np.isclose(
        summary.loc[2030, "NATIONAL_CUMULATIVE_UNMET_REWETTING_TARGET_HA"],
        30.0,
    )
    assert np.isclose(summary.loc[2050, "CUMULATIVE_REWETTING_HA"], 40.0)
    assert np.isclose(
        summary.loc[2050, "NATIONAL_CUMULATIVE_UNMET_REWETTING_TARGET_HA"],
        0.0,
    )


def test_target_table_rejects_decreasing_cumulative_target() -> None:
    targets = _targets()
    targets.loc[1, "FOREST_HA"] = 5.0
    with pytest.raises(ValueError, match="cannot fall"):
        read_land_use_targets(targets)


def test_target_milestones_must_match_scenario_milestones() -> None:
    targets = _targets().iloc[[1]].copy()
    with pytest.raises(ValueError, match="must exactly match"):
        allocate_spared_land_to_cumulative_targets(_frame(), targets)
