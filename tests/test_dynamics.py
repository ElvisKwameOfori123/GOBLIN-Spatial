import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.dynamics import (
    build_cattle_dynamics,
    build_sheep_dynamics,
    select_baseline_year,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def test_select_baseline_year_supports_2020_and_2025():
    panel = pd.DataFrame(
        {
            "YEAR": [2020, 2020, 2025, 2025],
            "CSOED": [2, 1, 2, 1],
            "VALUE": [20, 10, 25, 15],
        }
    )

    base_2020 = select_baseline_year(panel, 2020, expected_eds=2)
    base_2025 = select_baseline_year(panel, 2025, expected_eds=2)

    assert base_2020["CSOED"].tolist() == [1, 2]
    assert base_2020["VALUE"].tolist() == [10, 20]
    assert base_2025["VALUE"].tolist() == [15, 25]

    with pytest.raises(ValueError):
        select_baseline_year(panel, 2024)


def _cattle_row(csoed, dairy, suckler, other, allocations):
    row = {c: 0 for c in FINAL_21_COHORTS}
    row.update(allocations)
    row.update(
        {
            "CSOED": csoed,
            "DAIRY_COW": dairy,
            "OTHER_COW": suckler,
            "OTHER_CATTLE": other,
            "TOTAL_CATTLE": dairy + suckler + other,
            "dairy_cows": dairy,
            "suckler_cows": suckler,
        }
    )
    return row


def test_cattle_dynamics_identifies_breeding_and_receiver_structure():
    baseline = pd.DataFrame(
        [
            _cattle_row(
                1,
                10,
                0,
                20,
                {
                    "DxD_calves_m": 5,
                    "DxB_calves_m": 5,
                    "DxD_heifers_less_2_yr": 4,
                    "DxB_steers_less_2_yr": 4,
                    "bulls": 2,
                },
            ),
            _cattle_row(
                2,
                0,
                0,
                6,
                {
                    "DxD_calves_m": 3,
                    "DxB_calves_m": 1,
                    "BxB_calves_m": 2,
                },
            ),
            _cattle_row(
                3,
                0,
                5,
                10,
                {"BxB_calves_m": 6, "BxB_steers_less_2_yr": 4},
            ),
        ]
    )

    original = baseline.copy(deep=True)
    out = build_cattle_dynamics(baseline)

    pd.testing.assert_frame_equal(out[original.columns], original)

    dairy_ed = out.loc[out["CSOED"] == 1].iloc[0]
    receiver_ed = out.loc[out["CSOED"] == 2].iloc[0]
    suckler_ed = out.loc[out["CSOED"] == 3].iloc[0]

    assert dairy_ed["DYN_ED_CATTLE_ROLE"] == "DAIRY_BREEDING"
    assert dairy_ed["DYN_DAIRY_ORIGIN_FOLLOWERS"] == 18
    assert np.isclose(dairy_ed["DYN_DAIRY_FOLLOWERS_PER_DAIRY_COW"], 1.8)

    assert receiver_ed["DYN_ED_CATTLE_ROLE"] == "RECEIVER_REARING"
    assert bool(receiver_ed["DYN_RECEIVER_REARING_CANDIDATE"])
    assert bool(receiver_ed["DYN_DAIRY_ORIGIN_WITHOUT_DAIRY_COW"])
    assert np.isnan(receiver_ed["DYN_DXD_PER_DAIRY_COW"])

    assert suckler_ed["DYN_ED_CATTLE_ROLE"] == "SUCKLER_BREEDING"
    assert np.isclose(suckler_ed["DYN_BXB_PER_SUCKLER_COW"], 2.0)


def test_sheep_dynamics_preserves_baseline_and_reports_follower_rate():
    row = {c: 0 for c in GOBLIN_SHEEP_10}
    row.update(
        {
            "CSOED": 1,
            "Lowland ewes": 10,
            "Lowland lamb_less_1_yr": 8,
            "Lowland male_less_1_yr": 2,
            "Lowland lamb_more_1_yr": 1,
            "Lowland ram": 1,
            "TOTAL_SHEEP": 22,
        }
    )
    baseline = pd.DataFrame([row])
    original = baseline.copy(deep=True)

    out = build_sheep_dynamics(baseline)

    pd.testing.assert_frame_equal(out[original.columns], original)
    assert out.loc[0, "DYN_ED_SHEEP_ROLE"] == "LOWLAND_ONLY"
    assert out.loc[0, "DYN_EWES"] == 10
    assert out.loc[0, "DYN_RAMS"] == 1
    assert out.loc[0, "DYN_SHEEP_FOLLOWERS"] == 11
    assert np.isclose(out.loc[0, "DYN_SHEEP_FOLLOWERS_PER_EWE"], 1.1)
