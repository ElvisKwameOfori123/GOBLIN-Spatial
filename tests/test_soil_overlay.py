from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.soil import canonical_csoed


def test_canonical_csoed_handles_leading_zeros_and_compounds():
    assert canonical_csoed("01001") == "1001"
    assert canonical_csoed("08045/08046") == "8045/8046"
    assert canonical_csoed("8045/8046") == "8045/8046"
    assert canonical_csoed(1003.0) == "1003"


def test_soil_overlay_uses_baseline_ed_universe_only():
    gpd = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")
    box = shapely_geometry.box

    from goblin_spatial.soil import overlay_soil_associations

    baseline = pd.DataFrame(
        {
            "CSOED": ["01001", "01002"],
            "GRASSLAND_HA": [50.0, 60.0],
        }
    )

    # The geometry contains a third ED that is deliberately absent from the
    # baseline.  The baseline must remain the authority for scenario scope.
    ed = gpd.GeoDataFrame(
        {
            "CSOED": ["01001", "01002", "01003"],
            "EDNAME": ["A", "B", "C"],
            "COUNTYNAME": ["Test", "Test", "Test"],
            "geometry": [
                box(0, 0, 1000, 1000),
                box(1000, 0, 2000, 1000),
                box(2000, 0, 3000, 1000),
            ],
        },
        crs="EPSG:2157",
    )

    soil = gpd.GeoDataFrame(
        {
            "Associatio": ["1000a", "0700b"],
            "geometry": [
                box(0, 0, 1500, 1000),
                box(1500, 0, 3000, 1000),
            ],
        },
        crs="EPSG:2157",
    )

    profile, diagnostics = overlay_soil_associations(
        baseline,
        ed,
        soil,
        target_crs="EPSG:2157",
        min_intersection_ha=0.0,
    )

    assert set(profile["CSOED_CANONICAL"]) == {"1001", "1002"}
    assert "1003" not in set(profile["CSOED_CANONICAL"])
    assert diagnostics.baseline_rows == 2
    assert diagnostics.ed_rows_available == 3
    assert diagnostics.ed_rows_selected == 2
    assert diagnostics.eds_with_soil == 2

    shares = profile.groupby("CSOED_CANONICAL")[
        "ASSOCIATION_SHARE_WITHIN_MAPPED_SOIL"
    ].sum()
    assert shares.loc["1001"] == pytest.approx(1.0)
    assert shares.loc["1002"] == pytest.approx(1.0)

    ed2 = profile.loc[profile["CSOED_CANONICAL"].eq("1002")]
    areas = dict(zip(ed2["SIS_ASSOCIATION"], ed2["INTERSECTION_HA"]))
    assert areas["1000a"] == pytest.approx(50.0)
    assert areas["0700b"] == pytest.approx(50.0)


def test_soil_overlay_fails_if_baseline_ed_is_missing_from_geometry():
    gpd = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")
    box = shapely_geometry.box

    from goblin_spatial.soil import select_baseline_ed_geometries

    baseline = pd.DataFrame({"CSOED": ["01001", "01002"]})
    ed = gpd.GeoDataFrame(
        {
            "CSOED": ["01001"],
            "geometry": [box(0, 0, 1000, 1000)],
        },
        crs="EPSG:2157",
    )

    with pytest.raises(ValueError, match="missing 1 baseline CSOED"):
        select_baseline_ed_geometries(baseline, ed)
