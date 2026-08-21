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
            "SCENARIO_DAIRY_COW": [80, 70, 30, 15],
            "BASE_OTHER_COW": [50, 40, 30, 20],
            "SCENARIO_OTHER_COW": [30, 30, 20, 15],
            "REDUCTION_ADULT_COWS": [40, 20, 20, 10],
            "BASE_TOTAL_CATTLE": [400, 300, 200, 100],
            "SCENARIO_TOTAL_CATTLE": [300, 260, 150, 90],
            "CUMULATIVE_REDUCTION_TOTAL_CATTLE": [100, 40, 50, 10],
            "BASE_SO_LIVESTOCK_2020_EUR": [4000.0, 3000.0, 2000.0, 1000.0],
            "SCENARIO_SO_LIVESTOCK_2020_EUR": [3000.0, 3100.0, 1500.0, 900.0],
            "SO_LIVESTOCK_EXPOSURE_2020_EUR": [1000.0, -100.0, 500.0, 100.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 40.0, 50.0, 10.0],
            "ALL_GRASSLAND": [500.0, 400.0, 300.0, 200.0],
            "AGRICULTURAL_HOLDINGS": [10, 20, 10, 5],
        }
    )


def test_gini_basic_cases() -> None:
    assert gini(np.zeros(4)) == 0.0
    assert gini(np.ones(4)) == 0.0
    assert 0.0 < gini(np.array([0.0, 0.0, 0.0, 4.0])) <= 1.0


def test_sc1_ed_metrics_split_losses_and_gains() -> None:
    out = add_sc1_ed_metrics(_frame())
    assert out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].tolist() == [1000.0, 0.0, 500.0, 100.0]
    assert out["SO_LIVESTOCK_GAIN_2020_EUR"].tolist() == [0.0, 100.0, 0.0, 0.0]
    assert out["TOTAL_CATTLE_REDUCTION_HEAD"].sum() == 200.0
    assert np.isclose(out["GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE"].iloc[0], 20.0)
    assert np.isclose(out["SO_GROSS_LOSS_SHARE_NATIONAL"].sum(), 1.0)


def test_sc1_national_metrics_report_distribution_and_net_exposure() -> None:
    metrics = build_sc1_national_metrics(_frame()).iloc[0]
    assert metrics["ED_COUNT"] == 4
    assert metrics["NET_SO_LIVESTOCK_EXPOSURE_2020_EUR"] == 1500.0
    assert metrics["GROSS_SO_LIVESTOCK_LOSS_2020_EUR"] == 1600.0
    assert metrics["GROSS_SO_LIVESTOCK_GAIN_2020_EUR"] == 100.0
    assert metrics["EDS_WITH_SO_LOSS"] == 3
    assert metrics["EDS_WITH_SO_GAIN"] == 1
    assert 0.0 <= metrics["GINI_SO_LOSS"] <= 1.0
    assert 0.0 <= metrics["TOP_10PCT_ED_SHARE_SO_LOSS"] <= 1.0


def test_sc1_county_summary_closes_to_national_values() -> None:
    county = build_sc1_county_summary(_frame())
    assert county["TOTAL_CATTLE_REDUCTION_HEAD"].sum() == 200.0
    assert county["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].sum() == 1600.0
    assert np.isclose(county["COUNTY_SHARE_NATIONAL_SO_GROSS_LOSS"].sum(), 1.0)
