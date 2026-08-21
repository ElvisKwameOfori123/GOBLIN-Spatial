from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.scenario.livestock_pathway import (
    _add_total_cattle_accounting,
    _validate_national_total_cattle_targets,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["A", "B", "A", "B"],
            "MILESTONE_YEAR": [2030, 2030, 2050, 2050],
            "TOTAL_CATTLE": [100, 50, 100, 50],
            "BASE_GOBLIN_21_CATTLE_TOTAL": [100, 50, 100, 50],
            "PREVIOUS_GOBLIN_21_CATTLE_TOTAL": [100, 50, 90, 45],
            "INCREMENTAL_REDUCTION_GOBLIN_21_CATTLE_TOTAL": [10, 5, 10, 5],
            "SCENARIO_GOBLIN_21_CATTLE_TOTAL": [90, 45, 80, 40],
        }
    )


def test_total_cattle_is_exactly_the_solved_21_cohort_total() -> None:
    result = _add_total_cattle_accounting(_frame())

    assert result["BASE_TOTAL_CATTLE"].tolist() == [100, 50, 100, 50]
    assert result["SCENARIO_TOTAL_CATTLE"].tolist() == [90, 45, 80, 40]
    assert result["CUMULATIVE_REDUCTION_TOTAL_CATTLE"].tolist() == [10, 5, 20, 10]
    assert result["PREVIOUS_TOTAL_CATTLE"].tolist() == [100, 50, 90, 45]
    assert result["INCREMENTAL_REDUCTION_TOTAL_CATTLE"].tolist() == [10, 5, 10, 5]


def test_historical_total_cattle_must_close_to_baseline_cohorts() -> None:
    frame = _frame()
    frame.loc[0, "TOTAL_CATTLE"] = 99

    with pytest.raises(AssertionError, match="do not close"):
        _add_total_cattle_accounting(frame)


def test_external_national_total_cattle_target_is_a_hard_validation() -> None:
    result = _add_total_cattle_accounting(_frame())
    result = _validate_national_total_cattle_targets(
        result,
        {2030: 135, 2050: 120},
    )

    for year, target in ((2030, 135), (2050, 120)):
        block = result.loc[result["MILESTONE_YEAR"] == year]
        assert block["NATIONAL_TARGET_TOTAL_CATTLE"].nunique() == 1
        assert int(block["NATIONAL_TARGET_TOTAL_CATTLE"].iloc[0]) == target
        assert int(block["NATIONAL_ACTUAL_TOTAL_CATTLE"].iloc[0]) == target
        assert int(block["NATIONAL_TOTAL_CATTLE_DIFFERENCE"].iloc[0]) == 0


def test_external_total_cattle_mismatch_is_not_silently_rebalanced() -> None:
    result = _add_total_cattle_accounting(_frame())

    with pytest.raises(AssertionError, match="national total-cattle target failed"):
        _validate_national_total_cattle_targets(result, {2050: 119})
