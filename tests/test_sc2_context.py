from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.sc2_context import prepare_sc2_context


CLASS_SHARE_COLUMNS = [f"SOIL_USE_CLASS_{i}_SHARE" for i in range(1, 7)]
PHYSICAL_AREA_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
)


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
            "CSOED": [1001, 1002],
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
        frame[f"SOIL_USE_CLASS_{idx + 1}_GRASSLAND_HA"] = (
            classes[:, idx] * grass
        )
    return frame


def _lpis() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LPIS_YEAR": [2020, 2020],
            "CSOED": [1001, 1002],
            "LPIS_CLAIMED_AG_HA": [900.0, 450.0],
            "LPIS_ELIGIBLE_AG_HA": [850.0, 420.0],
            "LPIS_CLAIMED_GRASS_HA": [800.0, 400.0],
            "LPIS_ELIGIBLE_GRASS_HA": [750.0, 380.0],
            "LPIS_PERMANENT_PASTURE_HA": [600.0, 250.0],
            "LPIS_LOW_INPUT_GRASS_HA": [80.0, 50.0],
            "LPIS_TEMPORARY_GRASS_HA": [60.0, 30.0],
            "LPIS_HAY_MEADOW_HA": [40.0, 10.0],
            "LPIS_PEAT_GRASS_HA": [80.0, 100.0],
            "LPIS_RIPARIAN_GRASS_HA": [20.0, 10.0],
            "LPIS_OTHER_GRASS_HA": [0.0, 0.0],
        }
    )


def _physical() -> pd.DataFrame:
    values = (
        (35.0, 20.0, 15.0, 10.0, 5.0, 10.0, 5.0),
        (15.0, 15.0, 20.0, 15.0, 5.0, 25.0, 5.0),
    )
    rows = []
    for ed, areas in zip((1001, 1002), values, strict=True):
        row = {"CSOED": ed}
        row.update(dict(zip(PHYSICAL_AREA_COLUMNS, areas, strict=True)))
        total = float(sum(areas))
        for column, area in zip(PHYSICAL_AREA_COLUMNS, areas, strict=True):
            row[column.replace("_HA", "_SHARE")] = area / total

        deep, shallow, poor, poor_peaty, alluvium, peat, misc = areas
        effective_peat = 0.10 * peat
        sg1 = deep + 0.5 * shallow
        sg2 = 0.5 * shallow + poor + 0.5 * poor_peaty + alluvium
        sg3 = 0.5 * poor_peaty + effective_peat + misc
        denom = sg1 + sg2 + sg3
        row["IFS_MAP_SG1_SHARE"] = sg1 / denom
        row["IFS_MAP_SG2_SHARE"] = sg2 / denom
        row["IFS_MAP_SG3_SHARE"] = sg3 / denom
        rows.append(row)
    return pd.DataFrame(rows)


def test_sc2_v31_preserves_sc1_release_and_class_group_closure() -> None:
    sc1 = _sc1()
    original_release = sc1["GOBLIN_RELEASED_GRASSLAND_HA"].copy()
    out = prepare_sc2_context(
        sc1,
        lpis_profile=_lpis(),
        baseline_year=2020,
        physical_soil_context=_physical(),
    )

    assert np.array_equal(
        out["GOBLIN_RELEASED_GRASSLAND_HA"],
        original_release,
    )
    assert np.allclose(
        out[
            [
                "SC2_RELEASED_G1_HA",
                "SC2_RELEASED_G2_HA",
                "SC2_RELEASED_G3_HA",
            ]
        ].sum(axis=1),
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


def test_sc2_v31_retains_mature_productivity_science_and_dual_soil_no_blend() -> None:
    out = prepare_sc2_context(
        _sc1(),
        lpis_profile=_lpis(),
        baseline_year=2020,
        physical_soil_context=_physical(),
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
        assert (
            out[column]
            <= out["GOBLIN_RELEASED_GRASSLAND_HA"] + 1e-9
        ).all()


def test_sc2_requires_baseline_matched_lpis_and_compact_08c() -> None:
    with pytest.raises(ValueError, match="no 2025 snapshot"):
        prepare_sc2_context(
            _sc1(),
            lpis_profile=_lpis(),
            baseline_year=2025,
            physical_soil_context=_physical(),
        )

    with pytest.raises(ValueError, match="compact 08C physical-soil profile"):
        prepare_sc2_context(
            _sc1(),
            lpis_profile=_lpis(),
            baseline_year=2020,
            physical_soil_context=None,
        )
