"""Tests for ED agricultural-soil aggregation."""

import numpy as np
import pandas as pd

from goblin_spatial.soil import (
    add_ed_agricultural_soil,
    build_ed_agricultural_soil_profile,
)


def test_area_weighted_use_range_mapping() -> None:
    source = pd.DataFrame(
        {
            "cso_ed": [1001, 1001, 1001, 1002],
            "fsizuaa": [10.0, 30.0, 60.0, 20.0],
            "soil_code_nfs": [1, 4, 6, 2],
            "yc": [24, 20, 14, 18],
            "ifs_soil": ["AminDW", "BminSW", "BktPt", "AminPD"],
        }
    )

    profile = build_ed_agricultural_soil_profile(source).set_index("CSOED")
    assert np.isclose(profile.loc[1001, "SOIL_SOURCE_UAA_HA"], 100.0)
    assert np.isclose(profile.loc[1001, "GOBLIN_SOIL_G1_SHARE"], 0.10)
    assert np.isclose(profile.loc[1001, "GOBLIN_SOIL_G2_SHARE"], 0.30)
    assert np.isclose(profile.loc[1001, "GOBLIN_SOIL_G3_SHARE"], 0.60)
    assert np.isclose(profile.loc[1001, "FOREST_YC_WEIGHTED_MEAN"], 16.8)
    assert profile.loc[1001, "IFS_SOIL_DOMINANT"] == "BktPt"


def test_attach_preserves_grassland_and_fallback() -> None:
    profile = pd.DataFrame(
        {
            "CSOED": [1001, 1002],
            "SOIL_SOURCE_HOLDINGS": [2, 3],
            "SOIL_SOURCE_UAA_HA": [100.0, 300.0],
            "GOBLIN_SOIL_G1_SHARE": [0.5, 0.2],
            "GOBLIN_SOIL_G2_SHARE": [0.3, 0.5],
            "GOBLIN_SOIL_G3_SHARE": [0.2, 0.3],
            "FOREST_YC_WEIGHTED_MEAN": [20.0, 18.0],
        }
    )
    master = pd.DataFrame(
        {
            "YEAR": [2020, 2020, 2020, 2020],
            "CSOED": [1001, 1002, 1003, 9999],
            "County": ["A", "A", "A", "Z"],
            "ALL_GRASSLAND": [1000.0, 500.0, 200.0, 100.0],
        }
    )

    result = add_ed_agricultural_soil(master, profile)
    grass_columns = [f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in (1, 2, 3)]
    assert np.allclose(result[grass_columns].sum(axis=1), result["ALL_GRASSLAND"])
    assert result.loc[result["CSOED"].eq(1001), "SOIL_PROFILE_SOURCE"].item() == "ED"
    assert result.loc[result["CSOED"].eq(1003), "SOIL_PROFILE_SOURCE"].item() == "COUNTY_FALLBACK"
    assert result.loc[result["CSOED"].eq(9999), "SOIL_PROFILE_SOURCE"].item() == "NATIONAL_FALLBACK"
    assert np.isclose(
        result.loc[result["CSOED"].eq(1003), "GOBLIN_SOIL_G1_SHARE"].item(),
        0.275,
    )
