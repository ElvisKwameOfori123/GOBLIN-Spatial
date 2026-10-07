"""Livestock-signature algebra and multiscale catchment structure."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import parent_follower_multiplier
from goblin_spatial.synthesis.signatures import (
    build_signature_long,
    build_wfd_signature_spread,
)


def test_receiver_relationship_uses_county_support_when_local_parent_is_absent() -> None:
    base = np.array([100.0, 0.0, 50.0, 0.0])
    new = np.array([50.0, 0.0, 50.0, 0.0])
    cohort = np.array([10, 40, 5, 0])
    counties = np.array(["X", "X", "X", "X"], dtype=object)
    multiplier, roles = parent_follower_multiplier(base, new, cohort, counties)
    assert roles.tolist() == ["LOCAL_ED", "COUNTY_RECEIVER", "LOCAL_ED", "NONE"]
    assert multiplier[0] == 0.5
    assert multiplier[2] == 1.0
    assert np.isclose(multiplier[1], 100.0 / 150.0)


def _signature_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "GEOGRAPHY_TYPE": ["ED", "ED", "WFD_CATCHMENT"],
            "GEOGRAPHY_ID": ["1", "2", "W1"],
            "GEOGRAPHY_NAME": ["a", "b", "Catchment One"],
            "YEAR": [2020, 2020, 2020],
            "dairy_cows": [30.0, 10.0, 40.0],
            "ADULT_COWS": [60.0, 40.0, 100.0],
            "DXD_FOLLOWERS": [5.0, 5.0, 10.0],
            "DXB_FOLLOWERS": [5.0, 15.0, 20.0],
            "BXB_FOLLOWERS": [10.0, 20.0, 30.0],
            "FOLLOWER_TOTAL": [20.0, 40.0, 60.0],
            "TOTAL_CATTLE": [80.0, 80.0, 160.0],
            "TOTAL_SHEEP": [20.0, 80.0, 100.0],
            "AREA_FARMED": [40.0, 80.0, 120.0],
            "ALL_GRASSLAND": [30.0, 60.0, 90.0],
            "TOTAL_CEREALS": [5.0, 8.0, 13.0],
            "SO_COVERED_TOTAL_2020_EUR": [800.0, 1200.0, 2000.0],
            "UPLAND_SHEEP": [10.0, 20.0, 30.0],
            "DAIRY_SHARE_ADULT_PCT": [50.0, 25.0, 40.0],
            "DXD_SHARE_FOLLOWERS_PCT": [25.0, 12.5, 100.0 / 6.0],
            "DXB_SHARE_FOLLOWERS_PCT": [25.0, 37.5, 100.0 / 3.0],
            "BXB_SHARE_FOLLOWERS_PCT": [50.0, 50.0, 50.0],
            "FOLLOWER_TO_ADULT_RATIO": [1.0 / 3.0, 1.0, 0.6],
            "CATTLE_PER_FARMED_HA": [2.0, 1.0, 4.0 / 3.0],
            "SHEEP_PER_FARMED_HA": [0.5, 1.0, 5.0 / 6.0],
            "GRASSLAND_SHARE_FARMED_PCT": [75.0, 75.0, 75.0],
            "CEREAL_SHARE_FARMED_PCT": [12.5, 10.0, 100.0 * 13.0 / 120.0],
            "SO_PER_FARMED_HA": [20.0, 15.0, 2000.0 / 120.0],
            "UPLAND_SHARE_SHEEP_PCT": [50.0, 25.0, 30.0],
        }
    )


def test_signature_long_carries_exact_numerators_and_denominators() -> None:
    long = build_signature_long(_signature_frame())
    dairy = long.loc[
        (long["GEOGRAPHY_TYPE"] == "ED")
        & (long["GEOGRAPHY_ID"] == "1")
        & (long["SIGNATURE"] == "DAIRY_SHARE_ADULT_PCT")
    ].iloc[0]
    assert dairy["NUMERATOR"] == 30.0
    assert dairy["DENOMINATOR"] == 60.0
    assert dairy["VALUE"] == 50.0
    assert {
        "SHEEP_PER_FARMED_HA",
        "GRASSLAND_SHARE_FARMED_PCT",
        "CEREAL_SHARE_FARMED_PCT",
    }.issubset(set(long["SIGNATURE"]))


def test_wfd_signature_spread_pairs_accounting_value_with_ed_distribution() -> None:
    long = build_signature_long(_signature_frame())
    crosswalk = pd.DataFrame(
        {
            "CSOED": ["1", "2"],
            "WFD_CATCHMENT_ID": ["W1", "W1"],
            "WFD_CATCHMENT": ["Catchment One", "Catchment One"],
            "ED_CATCHMENT_WEIGHT": [1.0, 1.0],
        }
    )
    spread = build_wfd_signature_spread(long, crosswalk)
    row = spread.loc[spread["SIGNATURE"] == "DAIRY_SHARE_ADULT_PCT"].iloc[0]
    assert np.isclose(row["CATCHMENT_VALUE"], 40.0)
    assert row["INTERSECTING_EDS"] == 2
    assert row["DENOMINATOR_COLUMN"] == "ADULT_COWS"
    assert row["ED_WEIGHTED_P10"] <= row["ED_WEIGHTED_P50"] <= row["ED_WEIGHTED_P90"]
    assert np.isclose(
        row["ED_WEIGHTED_P90_P10"],
        row["ED_WEIGHTED_P90"] - row["ED_WEIGHTED_P10"],
    )
