"""Tests for manuscript-facing historical synthesis."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.synthesis.historical import (
    SO_COMPONENTS,
    add_signature_metrics,
    aggregate_state,
    build_matched_pairs,
    build_so_decomposition,
    information_geography,
    stable_ed_sensitivity,
)


def _row(year: int, ed: str, county: str, dairy: int, suckler: int, followers: int) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": year,
        "CSOED": ed,
        "EDNAME": f"ED {ed}",
        "County": county,
        "DAIRY_COW": dairy,
        "OTHER_COW": suckler,
        "BULLS": 10,
        "TOTAL_CATTLE": dairy + suckler + followers + 10,
        "TOTAL_SHEEP": 100,
        "AREA_FARMED": 1000.0,
        "ALL_GRASSLAND": 900.0,
        "TOTAL_CEREALS": 50.0,
        "OTHER_CROPS_HA": 50.0,
        "AGRICULTURAL_HOLDINGS": 20,
    }
    for c in FINAL_21_COHORTS:
        row[c] = 0
    row["dairy_cows"] = dairy
    row["suckler_cows"] = suckler
    row["bulls"] = 10

    # Put one third of followers in each origin family, concentrated in first cohort.
    row["DxD_calves_m"] = followers // 3
    row["DxB_calves_m"] = followers // 3
    row["BxB_calves_m"] = followers - 2 * (followers // 3)

    for c in GOBLIN_SHEEP_10:
        row[c] = 10

    so = {
        "SO_DAIRY_COWS_2020_EUR": dairy * 2000.0,
        "SO_SUCKLER_COWS_2020_EUR": suckler * 800.0,
        "SO_BULLS_2020_EUR": 10 * 1000.0,
        "SO_FOLLOWERS_2020_EUR": followers * 700.0,
        "SO_SHEEP_2020_EUR": 100 * 100.0,
        "SO_CEREALS_2020_EUR": 50 * 1500.0,
        "SO_OTHER_CROPS_2020_EUR": 50 * 1000.0,
    }
    row.update(so)
    row["SO_LIVESTOCK_2020_EUR"] = sum(
        so[k] for k in (
            "SO_DAIRY_COWS_2020_EUR",
            "SO_SUCKLER_COWS_2020_EUR",
            "SO_BULLS_2020_EUR",
            "SO_FOLLOWERS_2020_EUR",
            "SO_SHEEP_2020_EUR",
        )
    )
    row["SO_COVERED_TOTAL_2020_EUR"] = sum(so.values())
    row["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"] = row["SO_COVERED_TOTAL_2020_EUR"]
    return row


def _frame() -> pd.DataFrame:
    rows = []
    for year, scale in ((2015, 1.0), (2025, 1.1)):
        rows.extend(
            [
                _row(year, "1", "A", int(300 * scale), 50, 650),
                _row(year, "2", "A", 0, int(350 * scale), 650),
                _row(year, "3", "B", int(250 * scale), 100, 650),
                _row(year, "4", "B", 50, int(300 * scale), 650),
            ]
        )
    return pd.DataFrame(rows)


def test_signature_metrics_and_information_geography_are_finite():
    out = add_signature_metrics(_frame())
    assert np.isfinite(out["FOLLOWER_TO_ADULT_RATIO"]).all()
    assert np.isfinite(out["CATTLE_PER_FARMED_HA"]).all()
    info = information_geography(out.loc[out["YEAR"] == 2015])
    assert set(info["METRIC"]).issuperset(
        {"DAIRY_SHARE_ADULT_PCT", "FOLLOWER_TO_ADULT_RATIO"}
    )


def test_so_decomposition_closes_exactly():
    result = build_so_decomposition(_frame())
    parts = result.loc[result["COMPONENT"].isin(SO_COMPONENTS), "CHANGE_EUR"].sum()
    total = result.loc[
        result["COMPONENT"] == "SO_COVERED_TOTAL_2020_EUR", "CHANGE_EUR"
    ].iloc[0]
    assert np.isclose(parts, total)


def test_stable_ed_sensitivity_reports_all_three_bands():
    out = add_signature_metrics(_frame())
    result = stable_ed_sensitivity(out)
    assert result["STABILITY_BAND_PCT"].tolist() == [2.5, 5.0, 10.0]
    assert (result["N_ED"] >= 0).all()


def test_matched_pairs_uses_common_farmed_area_denominator():
    out = add_signature_metrics(_frame())
    result = build_matched_pairs(out, year=2015)
    assert not result.empty
    assert "CATTLE_PER_FARMED_HA_A" in result.columns
    assert "SO_PER_FARMED_HA_A" in result.columns



def test_aggregate_state_recomputes_structure_metrics():
    frame = _frame()
    frame["AVERAGE_SIZE_OF_HOLDINGS"] = 999.0
    frame["MEDIAN_AGE_OF_HOLDER"] = 60.0
    frame["AVERAGE_AGE_OF_HOLDER"] = 60.0

    mask_a1 = frame["CSOED"].eq("1")
    mask_a2 = frame["CSOED"].eq("2")
    frame.loc[mask_a1, "AGRICULTURAL_HOLDINGS"] = 10.0
    frame.loc[mask_a2, "AGRICULTURAL_HOLDINGS"] = 30.0
    frame.loc[mask_a1, "AREA_FARMED"] = 100.0
    frame.loc[mask_a2, "AREA_FARMED"] = 600.0
    frame.loc[mask_a1, "AVERAGE_AGE_OF_HOLDER"] = 50.0
    frame.loc[mask_a2, "AVERAGE_AGE_OF_HOLDER"] = 70.0

    county = aggregate_state(frame, ["YEAR", "County"])
    a2015 = county.loc[
        (county["YEAR"] == 2015) & (county["County"] == "A")
    ].iloc[0]

    assert a2015["AVERAGE_SIZE_OF_HOLDINGS"] == np.float64(17.5)
    assert np.isclose(a2015["AVERAGE_AGE_OF_HOLDER"], 65.0)
    assert "MEDIAN_AGE_OF_HOLDER" not in county.columns
