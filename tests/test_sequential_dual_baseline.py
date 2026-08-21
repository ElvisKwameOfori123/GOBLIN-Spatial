"""Dual-baseline contract for the principal sequential scenario engine.

The same scenario code must be able to start from either the validated 2020 or
2025 ED livestock state.  Changing ``baseline_year`` changes only the selected
starting state and the elapsed-time interpolation; it must not require a second
scenario implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario import (
    SequentialScenarioDefinition,
    run_sequential_scenario,
    standard_reduction_suite,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _ed_row(
    *,
    year: int,
    ed: str,
    county: str,
    dairy: int,
    suckler: int,
    sheep: int,
) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": year,
        "CSOED": ed,
        "County": county,
        "DAIRY_COW": dairy,
        "OTHER_COW": suckler,
        "TOTAL_SHEEP": sheep,
        "ALL_GRASSLAND": 1000.0,
    }
    row.update({cohort: 0 for cohort in FINAL_21_COHORTS})
    row.update({cohort: 0 for cohort in GOBLIN_SHEEP_10})

    # Adult cohort controls must reproduce the selected ED adult state.
    row["dairy_cows"] = dairy
    row["suckler_cows"] = suckler

    # Keep this fixture deliberately simple: all sheep sit in one valid GOBLIN
    # cohort so the ten-cohort representation closes exactly to TOTAL_SHEEP.
    row["Lowland ewes"] = sheep
    return row


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # 2020 starting state.
            _ed_row(
                year=2020,
                ed="A",
                county="Mayo",
                dairy=120,
                suckler=60,
                sheep=240,
            ),
            _ed_row(
                year=2020,
                ed="B",
                county="Cork",
                dairy=80,
                suckler=40,
                sheep=160,
            ),
            # 2025 starting state is intentionally different.
            _ed_row(
                year=2025,
                ed="A",
                county="Mayo",
                dairy=100,
                suckler=50,
                sheep=180,
            ),
            _ed_row(
                year=2025,
                ed="B",
                county="Cork",
                dairy=60,
                suckler=30,
                sheep=120,
            ),
        ]
    )


def _all_30(baseline_year: int) -> SequentialScenarioDefinition:
    return SequentialScenarioDefinition(
        name=f"ALL_30_FROM_{baseline_year}",
        baseline_year=baseline_year,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.30,
        sheep_reduction=0.30,
    )


def test_2020_and_2025_are_both_valid_starting_states() -> None:
    panel = _panel()

    from_2020 = run_sequential_scenario(
        panel,
        _all_30(2020),
        expected_eds=2,
        include_standard_output=False,
    )
    from_2025 = run_sequential_scenario(
        panel,
        _all_30(2025),
        expected_eds=2,
        include_standard_output=False,
    )

    # The selected baseline state is immutable and visible in every output row.
    assert set(from_2020.ed["YEAR"]) == {2020}
    assert set(from_2025.ed["YEAR"]) == {2025}
    assert set(from_2020.ed["PATHWAY_BASELINE_YEAR"]) == {2020}
    assert set(from_2025.ed["PATHWAY_BASELINE_YEAR"]) == {2025}

    # Same endpoint percentage, different observed starting totals.
    n20 = from_2020.national.set_index("MILESTONE_YEAR")
    n25 = from_2025.national.set_index("MILESTONE_YEAR")

    assert int(n20.loc[2050, "BASE_DAIRY_COW"]) == 200
    assert int(n20.loc[2050, "SCENARIO_DAIRY_COW"]) == 140
    assert int(n20.loc[2050, "BASE_OTHER_COW"]) == 100
    assert int(n20.loc[2050, "SCENARIO_OTHER_COW"]) == 70
    assert int(n20.loc[2050, "BASE_TOTAL_SHEEP"]) == 400
    assert int(n20.loc[2050, "SCENARIO_TOTAL_SHEEP"]) == 280

    assert int(n25.loc[2050, "BASE_DAIRY_COW"]) == 160
    assert int(n25.loc[2050, "SCENARIO_DAIRY_COW"]) == 112
    assert int(n25.loc[2050, "BASE_OTHER_COW"]) == 80
    assert int(n25.loc[2050, "SCENARIO_OTHER_COW"]) == 56
    assert int(n25.loc[2050, "BASE_TOTAL_SHEEP"]) == 300
    assert int(n25.loc[2050, "SCENARIO_TOTAL_SHEEP"]) == 210


def test_linear_schedule_respects_elapsed_time_from_selected_baseline() -> None:
    from_2020 = run_sequential_scenario(
        _panel(),
        _all_30(2020),
        expected_eds=2,
        include_standard_output=False,
    )
    from_2025 = run_sequential_scenario(
        _panel(),
        _all_30(2025),
        expected_eds=2,
        include_standard_output=False,
    )

    assert from_2020.schedule["MILESTONE_YEAR"].tolist() == [2030, 2040, 2050]
    assert from_2025.schedule["MILESTONE_YEAR"].tolist() == [2030, 2040, 2050]

    # 2020 -> 2050 is 30 years: 10/20/30% along a 30% endpoint.
    assert np.allclose(
        from_2020.schedule["dairy_reduction"].to_numpy(dtype=float),
        [0.10, 0.20, 0.30],
    )

    # 2025 -> 2050 is 25 years: 5/15/25 years of progress gives 6/18/30%.
    assert np.allclose(
        from_2025.schedule["dairy_reduction"].to_numpy(dtype=float),
        [0.06, 0.18, 0.30],
    )


def test_standard_suite_can_be_built_from_either_baseline() -> None:
    suite_2020 = standard_reduction_suite(
        reduction=0.30,
        baseline_year=2020,
        target_year=2050,
    )
    suite_2025 = standard_reduction_suite(
        reduction=0.30,
        baseline_year=2025,
        target_year=2050,
    )

    assert all(defn.baseline_year == 2020 for defn in suite_2020.values())
    assert all(defn.baseline_year == 2025 for defn in suite_2025.values())
    assert set(suite_2020) == set(suite_2025)
