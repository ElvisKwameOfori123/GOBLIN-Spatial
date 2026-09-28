import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import from_wkt

from goblin_spatial.land.lpis import build_ed_lpis_profile


def test_lpis_area_is_split_across_two_model_eds():
    baseline = pd.DataFrame({
        "CSOED": ["01003", "08045/08046"],
        "EDNAME": ["Clonmore", "Brisha / Capard"],
        "COUNTYNAME": ["CARLOW", "LAOIS"],
        "County": ["Carlow", "Laois"],
    })
    ed = gpd.GeoDataFrame(
        {"CSOED": ["01003", "08045/08046"]},
        geometry=from_wkt([
            "POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))",
            "POLYGON ((100 0, 200 0, 200 100, 100 100, 100 0))",
        ]),
        crs="EPSG:2157",
        index=[10, 20],
    )
    lpis = gpd.GeoDataFrame(
        {
            "PARCEL_ID": ["P1"],
            "CLAIMED_AREA_HA": [2.0],
            "PARCEL_AREA_HA": [2.0],
            "ELIGIBLE_AREA_HA": [2.0],
            "SHARE_DIGITISED_HA": [2.0],
            "SHARE_ELIGIBLE_HA": [2.0],
            "CROP_DESCRIPTION": ["Permanent Pasture"],
            "IS_GRASSLAND": [True],
            "IS_COMMONAGE": [False],
            "COMMONAGE_FRACTION": [1.0],
        },
        geometry=from_wkt(["POLYGON ((50 0, 150 0, 150 100, 50 100, 50 0))"]),
        crs="EPSG:2157",
    )
    result = build_ed_lpis_profile(lpis, ed, baseline, year=2025).set_index("CSOED_CANONICAL")
    assert np.isclose(result.loc["1003", "LPIS_CLAIMED_GRASS_HA"], 1.0)
    assert np.isclose(result.loc["8045/8046", "LPIS_CLAIMED_GRASS_HA"], 1.0)
    assert np.isclose(result["LPIS_CLAIMED_GRASS_HA"].sum(), 2.0)
