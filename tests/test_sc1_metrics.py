from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.scenario.metrics import (
    add_sc1_ed_metrics,
    build_sc1_county_summary,
    build_sc1_national_metrics,
    gini,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["1", "2", "3", "4"],
            "County": ["A", "A", "B", "B"],
            "PATHWAY_NAME": ["TEST"] * 4,
            "PATHWAY_BASELINE_YEAR": [2020] * 4,
            "MILESTONE_YEAR": [2050] * 4,
            "BASE_DAIRY_COW": [100, 80, 40, 20],
            "SCENARIO_DAIRY_COW": [80, 90, 30, 15],
            "BASE_OTHER_COW": [50, 40, 30, 20],
            "SCENARIO_OTHER_COW": [30, 30, 20, 15],
            "REDUCTION_ADULT_COWS": [40, 0, 20, 10],
            "BASE_TOTAL_CATTLE": [400, 300, 200, 100],
            "SCENARIO_TOTAL_CATTLE": [300, 320, 150, 90],
            "CUMULATIVE_REDUCTION_TOTAL_CATTLE": [100, -20, 50, 10],
            "BASE_SO_LIVESTOCK_2020_EUR": [4000.0, 3000.0, 2000.0, 1000.0],
            "SCENARIO_SO_LIVESTOCK_2020_EUR": [3000.0, 3100.0, 1500.0, 900.0],
            "SO_LIVESTOCK_EXPOSURE_2020_EUR": [1000.0, -100.0, 500.0, 100.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 40.0, 50.0, 10.0],
            "SIGNED_GRASSLAND_BALANCE_HA": [100.0, -20.0, 50.0, 10.0],
            "POTENTIAL_SPARED_GRASSLAND_HA": [100.0, 0.0, 50.0, 10.0],
            "ADDITIONAL_GRASSLAND_REQUIRED_HA": [0.0, 20.0, 0.0, 0.0],
            "ALL_GRASSLAND": [500.0, 400.0, 300.0, 200.0],
            "AGRICULTURAL_HOLDINGS": [10, 20, 10, 5],
        }
    )


def test_gini_basic_cases() -> None:
    assert gini(np.zeros(4)) == 0.0
    assert gini(np.ones(4)) == 0.0
    assert 0.0 < gini(np.array([0.0, 0.0, 0.0, 4.0])) <= 1.0


def test_sc1_ed_metrics_split_losses_gains_and_dm_land_pressure() -> None:
    out = add_sc1_ed_metrics(_frame())
    assert out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].tolist() == [1000.0, 0.0, 500.0, 100.0]
    assert out["SO_LIVESTOCK_GAIN_2020_EUR"].tolist() == [0.0, 100.0, 0.0, 0.0]
    assert out["TOTAL_CATTLE_REDUCTION_HEAD"].sum() == 160.0
    assert out["TOTAL_CATTLE_EXPANSION_HEAD"].sum() == 20.0
    assert np.isclose(out["GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE"].iloc[0], 20.0)
    assert np.isclose(out["SO_GROSS_LOSS_SHARE_NATIONAL"].sum(), 1.0)
    assert out["DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA"].tolist() == [100.0, 20.0, 50.0, 10.0]
    assert np.isclose(out["DM_POTENTIAL_RELEASE_SHARE_NATIONAL"].sum(), 1.0)
    assert np.isclose(out["DM_ADDITIONAL_REQUIRED_SHARE_NATIONAL"].sum(), 1.0)


def test_sc1_metrics_allow_local_cattle_expansion_under_national_contraction() -> None:
    frame = _frame()
    out = add_sc1_ed_metrics(frame)
    assert out["TOTAL_CATTLE_REDUCTION_HEAD"].tolist() == [100.0, 0.0, 50.0, 10.0]
    assert out["TOTAL_CATTLE_EXPANSION_HEAD"].tolist() == [0.0, 20.0, 0.0, 0.0]

    metrics = build_sc1_national_metrics(frame).iloc[0]
    assert metrics["TOTAL_CATTLE_REDUCTION_HEAD"] == 140.0
    assert metrics["NET_TOTAL_CATTLE_REDUCTION_HEAD"] == 140.0
    assert metrics["GROSS_TOTAL_CATTLE_REDUCTION_HEAD"] == 160.0
    assert metrics["GROSS_TOTAL_CATTLE_EXPANSION_HEAD"] == 20.0
    assert metrics["EDS_WITH_POSITIVE_TOTAL_CATTLE_REDUCTION"] == 3
    assert metrics["EDS_WITH_POSITIVE_TOTAL_CATTLE_EXPANSION"] == 1


def test_sc1_national_metrics_report_distribution_net_exposure_and_dm_reorganisation() -> None:
    metrics = build_sc1_national_metrics(_frame()).iloc[0]
    assert metrics["ED_COUNT"] == 4
    assert metrics["NET_SO_LIVESTOCK_EXPOSURE_2020_EUR"] == 1500.0
    assert metrics["GROSS_SO_LIVESTOCK_LOSS_2020_EUR"] == 1600.0
    assert metrics["GROSS_SO_LIVESTOCK_GAIN_2020_EUR"] == 100.0
    assert metrics["EDS_WITH_SO_LOSS"] == 3
    assert metrics["EDS_WITH_SO_GAIN"] == 1
    assert 0.0 <= metrics["GINI_SO_LOSS"] <= 1.0
    assert 0.0 <= metrics["TOP_10PCT_ED_SHARE_SO_LOSS"] <= 1.0

    assert metrics["GOBLIN_RELEASED_GRASSLAND_HA"] == 200.0
    assert metrics["DM_DIAGNOSTIC_NET_LAND_RELEASE_HA"] == 140.0
    assert metrics["DM_DIAGNOSTIC_GROSS_POTENTIAL_RELEASE_HA"] == 160.0
    assert metrics["DM_DIAGNOSTIC_GROSS_ADDITIONAL_REQUIRED_HA"] == 20.0
    assert metrics["DM_DIAGNOSTIC_GROSS_SPATIAL_MOVEMENT_HA"] == 180.0
    assert metrics["GOBLIN_MINUS_DM_DIAGNOSTIC_NET_RELEASE_HA"] == 60.0
    assert metrics["EDS_WITH_ADDITIONAL_GRASSLAND_REQUIREMENT"] == 1
    assert metrics["EDS_WITH_BOTH_ADDITIONAL_GRASSLAND_AND_CATTLE_EXPANSION"] == 1
    assert metrics["EDS_WITH_BOTH_ADDITIONAL_GRASSLAND_AND_DAIRY_EXPANSION"] == 1


def test_sc1_county_summary_closes_to_national_values() -> None:
    county = build_sc1_county_summary(_frame())
    assert county["TOTAL_CATTLE_REDUCTION_HEAD"].sum() == 160.0
    assert county["TOTAL_CATTLE_EXPANSION_HEAD"].sum() == 20.0
    assert county["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].sum() == 1600.0
    assert county["SIGNED_GRASSLAND_BALANCE_HA"].sum() == 140.0
    assert county["POTENTIAL_SPARED_GRASSLAND_HA"].sum() == 160.0
    assert county["ADDITIONAL_GRASSLAND_REQUIRED_HA"].sum() == 20.0
    assert np.isclose(county["COUNTY_SHARE_NATIONAL_SO_GROSS_LOSS"].sum(), 1.0)
    assert np.isclose(county["COUNTY_SHARE_NATIONAL_DM_POTENTIAL_RELEASE"].sum(), 1.0)
