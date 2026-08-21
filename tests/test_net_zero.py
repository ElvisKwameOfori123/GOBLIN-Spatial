"""Tests for the principal adult-driven net-zero scenario interface."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario import run_net_zero_scenario
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _row(year: int, ed: str, county: str) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": year,
        "CSOED": ed,
        "County": county,
        "DAIRY_COW": 0,
        "OTHER_COW": 0,
        "TOTAL_SHEEP": 0,
    }
    row.update({cohort: 0 for cohort in FINAL_21_COHORTS})
    row.update({cohort: 0 for cohort in GOBLIN_SHEEP_10})
    return row


def _panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    # 2020 Mayo breeding ED.
    breeding = _row(2020, "A", "Mayo")
    breeding.update(
        {
            "DAIRY_COW": 100,
            "OTHER_COW": 50,
            "TOTAL_SHEEP": 100,
            "dairy_cows": 100,
            "suckler_cows": 50,
            "DxD_calves_m": 40,
            "BxB_calves_m": 20,
            "Lowland ewes": 60,
            "Lowland lamb_less_1_yr": 40,
        }
    )
    rows.append(breeding)

    # Same-county receiver/finishing ED: followers but no matching breeding cows.
    receiver = _row(2020, "B", "Mayo")
    receiver.update(
        {
            "TOTAL_SHEEP": 50,
            "DxD_calves_m": 20,
            "BxB_calves_m": 10,
            "Lowland ewes": 30,
            "Lowland lamb_less_1_yr": 20,
        }
    )
    rows.append(receiver)

    # True orphan follower location: no corresponding breeding cows in Cork.
    orphan = _row(2020, "C", "Cork")
    orphan.update({"DxD_calves_m": 10, "BxB_calves_m": 5})
    rows.append(orphan)

    # A deliberately different 2025 state proves the baseline selector is live.
    breeding_2025 = _row(2025, "A", "Mayo")
    breeding_2025.update(
        {
            "DAIRY_COW": 80,
            "OTHER_COW": 40,
            "TOTAL_SHEEP": 90,
            "dairy_cows": 80,
            "suckler_cows": 40,
            "DxD_calves_m": 32,
            "BxB_calves_m": 16,
            "Lowland ewes": 54,
            "Lowland lamb_less_1_yr": 36,
        }
    )
    rows.append(breeding_2025)

    receiver_2025 = _row(2025, "B", "Mayo")
    receiver_2025.update(
        {
            "TOTAL_SHEEP": 45,
            "DxD_calves_m": 16,
            "BxB_calves_m": 8,
            "Lowland ewes": 27,
            "Lowland lamb_less_1_yr": 18,
        }
    )
    rows.append(receiver_2025)

    orphan_2025 = _row(2025, "C", "Cork")
    orphan_2025.update({"DxD_calves_m": 8, "BxB_calves_m": 4})
    rows.append(orphan_2025)

    return pd.DataFrame(rows)


def test_receiver_and_orphan_follow_adult_reduction_signal() -> None:
    out = run_net_zero_scenario(
        _panel(),
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.50,
        suckler_reduction=0.20,
        sheep_reduction=0.10,
        expected_eds=3,
        include_standard_output=False,
    ).set_index("CSOED")

    # Breeding ED uses its own dairy reduction rate.
    assert np.isclose(out.loc["A", "REDUCTION_SIGNAL_DxD_calves_m"], 0.50)
    assert out.loc["A", "REDUCTION_SIGNAL_SOURCE_DxD_calves_m"] == "LOCAL_ED"

    # Finishing/rearing ED inherits the same-county breeding signal.
    assert np.isclose(out.loc["B", "REDUCTION_SIGNAL_DxD_calves_m"], 0.50)
    assert out.loc["B", "REDUCTION_SIGNAL_SOURCE_DxD_calves_m"] == "COUNTY_RECEIVER"

    # Cork has followers but no dairy cows, so only the explicit orphan fallback applies.
    assert np.isclose(out.loc["C", "REDUCTION_SIGNAL_DxD_calves_m"], 0.50)
    assert out.loc["C", "REDUCTION_SIGNAL_SOURCE_DxD_calves_m"] == "NATIONAL_ORPHAN"

    # The young cohort is endogenous: nobody supplied a separate calf target.
    assert int(out["BASE_COHORT_DxD_calves_m"].sum()) == 70
    assert int(out["SCENARIO_COHORT_DxD_calves_m"].sum()) == 35


def test_baseline_year_switch_changes_only_the_starting_state() -> None:
    panel = _panel()
    kwargs = dict(
        target_year=2050,
        dairy_reduction=0.25,
        suckler_reduction=0.25,
        sheep_reduction=0.25,
        expected_eds=3,
        include_standard_output=False,
    )

    out_2020 = run_net_zero_scenario(panel, baseline_year=2020, **kwargs)
    out_2025 = run_net_zero_scenario(panel, baseline_year=2025, **kwargs)

    assert set(out_2020["YEAR"]) == {2020}
    assert set(out_2025["YEAR"]) == {2025}
    assert int(out_2020["BASE_DAIRY_COW"].sum()) == 100
    assert int(out_2025["BASE_DAIRY_COW"].sum()) == 80
    assert int(out_2020["SCENARIO_DAIRY_COW"].sum()) == 75
    assert int(out_2025["SCENARIO_DAIRY_COW"].sum()) == 60


def test_changing_one_adult_parameter_reacts_through_related_followers() -> None:
    panel = _panel()
    low = run_net_zero_scenario(
        panel,
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.10,
        suckler_reduction=0.0,
        sheep_reduction=0.0,
        expected_eds=3,
        include_standard_output=False,
    )
    high = run_net_zero_scenario(
        panel,
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.50,
        suckler_reduction=0.0,
        sheep_reduction=0.0,
        expected_eds=3,
        include_standard_output=False,
    )

    assert int(high["SCENARIO_DAIRY_COW"].sum()) < int(low["SCENARIO_DAIRY_COW"].sum())
    assert int(high["SCENARIO_COHORT_DxD_calves_m"].sum()) < int(
        low["SCENARIO_COHORT_DxD_calves_m"].sum()
    )

    # Beef-origin followers do not change when the suckler control stays at zero.
    assert int(high["SCENARIO_COHORT_BxB_calves_m"].sum()) == int(
        low["SCENARIO_COHORT_BxB_calves_m"].sum()
    )
