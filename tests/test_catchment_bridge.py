"""Tests for the downstream ED-to-catchment aggregation bridge."""

import pandas as pd
import pytest

from goblin_spatial.aggregation import (
    aggregate_to_wfd_catchments,
    aggregate_wfd_to_colm,
    build_ed_catchment_crosswalk,
    canonical_wfd_catchment_name,
    to_colm_catchment_name,
    validate_aggregation_closure,
)


def test_wfd_names_are_preserved_and_colm_mapping_is_secondary():
    assert canonical_wfd_catchment_name("  Upper Shannon 26G  ") == "Upper Shannon 26G"
    assert to_colm_catchment_name("Blackwater") == "Blackwater (Munster)"
    assert to_colm_catchment_name("Lower Shannon 25A") == "Lower Shannon"
    assert to_colm_catchment_name("Upper Shannon 26G") == "Upper Shannon"
    assert to_colm_catchment_name("Liffey & Dublin Bay") == "Liffey and Dublin Bay"
    assert to_colm_catchment_name("Sligo Bay & Drowse 35") == "Sligo Bay"


def test_crosswalk_preserves_wfd_units_and_aggregation_closes():
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
        {
            "CATCHMENTI": ["001", "026A", "026B"],
            "NAME": ["Blackwater (Munster)", "Upper Shannon 26A", "Upper Shannon 26B"],
        },
        geometry=[
            box(0, 0, 10, 10),
            box(10, 0, 15, 10),
            box(15, 0, 20, 10),
        ],
        crs="EPSG:2157",
    )

    crosswalk = build_ed_catchment_crosswalk(
        master,
        eds,
        catchments,
        expected_wfd_catchments=None,
    )
    weights = crosswalk.groupby("CSOED")["ED_CATCHMENT_WEIGHT"].sum()
    assert weights.to_dict() == pytest.approx({"001": 1.0, "002": 1.0})
    assert set(crosswalk["WFD_CATCHMENT"]) == {
        "Blackwater (Munster)", "Upper Shannon 26A", "Upper Shannon 26B"
    }

    wfd = aggregate_to_wfd_catchments(
        master,
        crosswalk,
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    wfd_diagnostics = validate_aggregation_closure(
        master,
        wfd,
        geography_col="WFD catchment",
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    assert wfd_diagnostics["DIFF"].abs().max() < 1e-9

    y2020 = wfd.loc[wfd["YEAR"] == 2020].set_index("WFD_CATCHMENT")
    assert y2020.loc["Blackwater (Munster)", "TOTAL_CATTLE"] == pytest.approx(100.0)
    assert y2020.loc["Upper Shannon 26A", "TOTAL_CATTLE"] == pytest.approx(100.0)
    assert y2020.loc["Upper Shannon 26B", "TOTAL_CATTLE"] == pytest.approx(100.0)

    colm = aggregate_wfd_to_colm(
        wfd,
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    colm_diagnostics = validate_aggregation_closure(
        master,
        colm,
        geography_col="Colm catchment",
        additive_columns=["TOTAL_CATTLE", "SO_LIVESTOCK_2020_EUR"],
    )
    assert colm_diagnostics["DIFF"].abs().max() < 1e-9

    c2020 = colm.loc[colm["YEAR"] == 2020].set_index("COLM_CATCHMENT")
    assert c2020.loc["Blackwater (Munster)", "TOTAL_CATTLE"] == pytest.approx(100.0)
    assert c2020.loc["Upper Shannon", "TOTAL_CATTLE"] == pytest.approx(200.0)
