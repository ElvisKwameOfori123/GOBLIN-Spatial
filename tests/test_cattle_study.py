"""Tests for the cattle-only study-facing scenario helpers."""

from __future__ import annotations

import pytest

from goblin_spatial.scenario import cattle_reduction_suite, make_cattle_scenario


def test_cattle_suite_keeps_sheep_fixed_and_exposes_principal_runs() -> None:
    suite = cattle_reduction_suite(reduction=0.30, baseline_year=2020, target_year=2050)
    assert set(suite) == {
        "BASELINE",
        "DAIRY_30",
        "SUCKLER_30",
        "BOTH_30",
        "BOTH_30_RANDOMISED",
    }
    assert all(defn.sheep_reduction == 0.0 for defn in suite.values())
    assert suite["DAIRY_30"].dairy_reduction == pytest.approx(0.30)
    assert suite["DAIRY_30"].suckler_reduction == pytest.approx(0.0)
    assert suite["SUCKLER_30"].dairy_reduction == pytest.approx(0.0)
    assert suite["SUCKLER_30"].suckler_reduction == pytest.approx(0.30)
    assert suite["BOTH_30"].dairy_reduction == pytest.approx(0.30)
    assert suite["BOTH_30"].suckler_reduction == pytest.approx(0.30)


def test_cattle_scenario_accepts_2025_and_non_linear_cattle_milestones() -> None:
    definition = make_cattle_scenario(
        name="BOTH_NONLINEAR",
        baseline_year=2025,
        target_year=2050,
        dairy_reduction=0.40,
        suckler_reduction=0.60,
        milestone_reductions={
            2030: {"dairy_reduction": 0.10, "suckler_reduction": 0.15},
            2040: {"dairy_reduction": 0.25, "suckler_reduction": 0.40},
            2050: {"dairy_reduction": 0.40, "suckler_reduction": 0.60},
        },
    )
    assert definition.baseline_year == 2025
    assert definition.sheep_reduction == 0.0
    assert definition.milestone_reductions[2030]["sheep_reduction"] == 0.0


def test_cattle_scenario_rejects_nonzero_sheep_milestone() -> None:
    with pytest.raises(ValueError, match="keep sheep unchanged"):
        make_cattle_scenario(
            name="INVALID",
            baseline_year=2020,
            target_year=2050,
            dairy_reduction=0.30,
            suckler_reduction=0.30,
            milestone_reductions={
                2050: {
                    "dairy_reduction": 0.30,
                    "suckler_reduction": 0.30,
                    "sheep_reduction": 0.10,
                }
            },
        )
