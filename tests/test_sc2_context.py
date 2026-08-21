"""Tests for mature SC2 using the single frozen 2020 land-context contract."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.context import LAND_CONTEXT_COLUMNS, LAND_CONTEXT_EXPECTED_EDS
from goblin_spatial.land.sc2_context import prepare_sc2_context


CLASS_SHARE_COLUMNS = [f"SOIL_USE_CLASS_{i}_SHARE" for i in range(1, 7)]


def _sc1() -> pd.DataFrame:
    grass = np.array([1000.0, 500.0])
    classes = np.array(
        [
            [0.30, 0.20, 0.20, 0.10, 0.10, 0.10],
            [0.10, 0.10, 0.20, 0.30, 0.20, 0.10],
        ]
    )
    frame = pd.DataFrame(
        {
            "CSOED": ["1001", "1002"],
            "County": ["A", "B"],
            "ALL_GRASSLAND": grass,
            "GOBLIN_RELEASED_GRASSLAND_HA": [300.0, 100.0],
            "GOBLIN_RELEASED_G1_HA": [150.0, 20.0],
            "GOBLIN_RELEASED_G2_HA": [90.0, 50.0],
            "GOBLIN_RELEASED_G3_HA": [60.0, 30.0],
            "GOBLIN_SOIL_G1_SHARE": [0.50, 0.20],
            "GOBLIN_SOIL_G2_SHARE": [0.30, 0.50],
            "GOBLIN_SOIL_G3_SHARE": [0.20, 0.30],
            "IFS_PEAT_CUTOVER_UAA_SHARE": [0.10, 0.40],
            "FOREST_YC_WEIGHTED_MEAN": [20.0, 18.0],
            "SCENARIO_BASELINE_YEAR": [2020, 2020],
        }
    )
    for idx, column in enumerate(CLASS_SHARE_COLUMNS):
        frame[column] = classes[:, idx]
        frame[f"SOIL_USE_CLASS_{idx + 1}_GRASSLAND_HA"] = classes[:, idx] * grass
    return frame


def _land_context() -> pd.DataFrame:
    """Return a contract-valid neutral context; only the first two EDs are used."""

    rows: list[dict[str, object]] = []
    for index in range(LAND_CONTEXT_EXPECTED_EDS):
        ed = str(1001 + index)
        classes = (
            (0.30, 0.20, 0.20, 0.10, 0.10, 0.10)
            if index == 0
            else (0.10, 0.10, 0.20, 0.30, 0.20, 0.10)
            if index == 1
            else (0.20, 0.20, 0.20, 0.20, 0.10, 0.10)
        )
        groups = (
            classes[0] + classes[1],
            classes[2] + classes[3],
            classes[4] + classes[5],
        )
        row: dict[str, object] = {
            "CSOED": ed,
            "SOIL_PROFILE_SOURCE": "ED" if index < 2820 else "COUNTY_FALLBACK",
            "SOIL_SOURCE_HOLDINGS": 10.0,
            "SOIL_SOURCE_UAA_HA": 100.0,
            "FOREST_YC_WEIGHTED_MEAN": 20.0 if index == 0 else 18.0,
            "IFS_PEAT_CUTOVER_UAA_SHARE": 0.10 if index == 0 else 0.40 if index == 1 else 0.10,
            "IFS_MAP_DEEP_WELL_DRAINED_HA": 35.0,
            "IFS_MAP_SHALLOW_WELL_DRAINED_HA": 20.0,
            "IFS_MAP_POORLY_DRAINED_HA": 15.0,
            "IFS_MAP_POORLY_DRAINED_PEATY_HA": 10.0,
            "IFS_MAP_ALLUVIUM_HA": 5.0,
            "IFS_MAP_PEAT_HA": 10.0,
            "IFS_MAP_MISCELLANEOUS_HA": 5.0,
            "LPIS_YEAR": 2020,
            "LPIS_CLAIMED_AG_HA": 100.0,
            "LPIS_ELIGIBLE_AG_HA": 90.0,
            "LPIS_SPATIAL_FOOTPRINT_HA": 120.0,
            "LPIS_CLAIMED_GRASS_HA": 90.0,
            "LPIS_ELIGIBLE_GRASS_HA": 80.0,
            "LPIS_PERMANENT_PASTURE_HA": 60.0,
            "LPIS_LOW_INPUT_GRASS_HA": 10.0,
            "LPIS_TEMPORARY_GRASS_HA": 10.0,
            "LPIS_HAY_MEADOW_HA": 5.0,
            "LPIS_OTHER_GRASS_HA": 5.0,
            "LPIS_COMMONAGE_GRASS_HA": 0.0,
            "LPIS_ANC_GRASS_HA": 50.0,
            "LPIS_ENV_SCHEME_GRASS_HA": 20.0,
            "LPIS_ORGANIC_GRASS_HA": 5.0,
            "LPIS_BOG_PEAT_CONTEXT_HA": 2.0,
            "LPIS_HABITAT_CONTEXT_HA": 3.0,
            "LPIS_FORESTRY_CONTEXT_HA": 4.0,
        }
        for number, value in enumerate(classes, start=1):
            row[f"SOIL_USE_CLASS_{number}_SHARE"] = value
        for number, value in enumerate(groups, start=1):
            row[f"GOBLIN_SOIL_G{number}_SHARE"] = value
        rows.append(row)

    frame = pd.DataFrame(rows)
    return frame.loc[:, list(LAND_CONTEXT_COLUMNS)]


def test_sc2_v31_preserves_sc1_release_and_class_group_closure() -> None:
    sc1 = _sc1()
    original_release = sc1["GOBLIN_RELEASED_GRASSLAND_HA"].copy()
    out = prepare_sc2_context(
        sc1,
        land_context=_land_context(),
        baseline_year=2020,
    )

    assert np.array_equal(out["GOBLIN_RELEASED_GRASSLAND_HA"], original_release)
    assert np.allclose(
        out[["SC2_RELEASED_G1_HA", "SC2_RELEASED_G2_HA", "SC2_RELEASED_G3_HA"]].sum(axis=1),
        original_release,
    )
    assert np.allclose(
        out[[f"RELEASED_CLASS_{i}_HA" for i in range(1, 7)]].sum(axis=1),
        original_release,
    )
    assert np.allclose(
        out["RELEASED_CLASS_1_HA"] + out["RELEASED_CLASS_2_HA"],
        out["GOBLIN_RELEASED_G1_HA"],
    )
    assert np.allclose(
        out["RELEASED_CLASS_3_HA"] + out["RELEASED_CLASS_4_HA"],
        out["GOBLIN_RELEASED_G2_HA"],
    )
    assert np.allclose(
        out["RELEASED_CLASS_5_HA"] + out["RELEASED_CLASS_6_HA"],
        out["GOBLIN_RELEASED_G3_HA"],
    )
    assert out["SC2_OPPORTUNITY_SCIENCE_APPLIED"].all()
    assert set(out["SC2_OPPORTUNITY_VERSION"]) == {"3.1.0"}
    assert set(out["SC2_CONTEXT_VERSION"]) == {"3.1"}
    assert set(out["SC2_LAND_CONTEXT_ROLE"]) == {"FROZEN_REPOSITORY_CONTROL"}


def test_sc2_retains_08b_productivity_and_keeps_08c_independent() -> None:
    out = prepare_sc2_context(
        _sc1(),
        land_context=_land_context(),
        baseline_year=2020,
    )

    expected = (
        0.85 * out["GOBLIN_SOIL_G1_SHARE"]
        + 0.80 * out["GOBLIN_SOIL_G2_SHARE"]
        + 0.70 * out["GOBLIN_SOIL_G3_SHARE"]
    )
    assert np.allclose(out["GOBLIN_SOIL_PRODUCTIVITY_INDEX"], expected)
    assert out["SC2_DUAL_SOIL_PRINCIPAL_SCORES_CHANGED"].eq(False).all()
    assert out["SC2_DUAL_SOIL_METHOD"].eq(
        "CATHAL_NFS_CAPABILITY_PLUS_INDEPENDENT_COLM_IFS_PHYSICAL_CONTEXT_NO_BLEND"
    ).all()
    assert out["LPIS_PROFILE_YEAR"].eq(2020).all()
    assert out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"].all()

    for column in (
        "RELEASED_TILLAGE_ELIGIBLE_HA",
        "RELEASED_FOREST_ELIGIBLE_HA",
        "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
        "RELEASED_WILLOW_ELIGIBLE_HA",
        "RELEASED_REWETTING_ELIGIBLE_WEIGHT_HA",
    ):
        assert (out[column] >= -1e-12).all()
        assert (out[column] <= out["GOBLIN_RELEASED_GRASSLAND_HA"] + 1e-9).all()


def test_sc2_rejects_2025_until_separate_frozen_context_exists() -> None:
    with pytest.raises(ValueError, match="baseline_year=2020"):
        prepare_sc2_context(
            _sc1(),
            land_context=_land_context(),
            baseline_year=2025,
        )
