"""Tests for the downstream ED-to-catchment aggregation bridge."""

import pandas as pd
import pytest

from goblin_spatial.aggregation import (
    aggregate_to_catchments,
    build_ed_catchment_crosswalk,
    canonical_catchment_name,
    validate_aggregation_closure,
)


def test_canonical_catchment_name_matches_colm_system():
    assert canonical_catchment_name("Blackwater") == "Blackwater (Munster)"
    assert canonical_catchment_name("Lower Shannon 25A") == "Lower Shannon"
    assert canonical_catchment_name("Upper Shannon 26G") == "Upper Shannon"
    assert canonical_catchment_name("Liffey & Dublin Bay") == "Liffey and Dublin Bay"


def test_crosswalk_and_aggregation_close():
    gpd = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")
    box = shapely_geometry.box

    master = pd.DataFrame({
        "YEAR": [2020, 2020, 2021, 2021],
        "CSOED": ["001", "002", "001", "002"],
        "County": ["A", "A", "A", "A"],
        "TOTAL_CATTLE": [100.0, 200.0, 110.0, 190.0],
        "SO_LIVESTOCK_2020_EUR": [1000.0, 2000.0, 1100.0, 1900.0],
    })
    eds = gpd.GeoDataFrame(
        {"CSOED": ["001", "002"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)],
        crs="EPSG:2157",
    )
    catchments = gpd.GeoDataFrame(
        {"Catchment": ["Blackwater", "Barrow"]},
        geometry=[box(0, 0, 15, 10), box(15, 0, 20, 10)],
        crs="EPSG:2157",
    )

    crosswalk = build_ed_catchment_crosswalk(master, eds, catchments)
    weights = crosswalk.groupby("CSOED")["ED_CATCHMENT_WEIGHT"].sum()
    assert weights.to_dict() == pytest.approx({"001": 1.0, "002": 1.0})

    out = aggregate_to_catchments(
        master,
        crosswalk,
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    diagnostics = validate_aggregation_closure(
        master,
        out,
        geography_col="catchment",
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    assert diagnostics["DIFF"].abs().max() < 1e-9

    y2020 = out.loc[out["YEAR"] == 2020].set_index("CATCHMENT")
    assert y2020.loc["Blackwater (Munster)", "TOTAL_CATTLE"] == pytest.approx(200.0)
    assert y2020.loc["Barrow", "TOTAL_CATTLE"] == pytest.approx(100.0)
