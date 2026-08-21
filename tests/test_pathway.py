"""Compact tests for cumulative GOBLIN-to-ED transition pathways."""

from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.scenario import (
    AllocationRule,
    NationalMilestone,
    TransitionPathwayDefinition,
    build_transition_pathway,
    linear_milestones_from_endpoint,
)


def _panel() -> pd.DataFrame:
    rows = []
    for year in (2020, 2025):
        rows.extend(
            [
                {
                    "YEAR": year,
                    "CSOED": "A",
                    "DAIRY_COW": 100,
                    "OTHER_COW": 20,
                    "TOTAL_SHEEP": 50,
                    "PRODUCTIVITY": 1.0,
                    "VULNERABILITY": 0.2,
                },
                {
                    "YEAR": year,
                    "CSOED": "B",
                    "DAIRY_COW": 60,
                    "OTHER_COW": 40,
                    "TOTAL_SHEEP": 30,
                    "PRODUCTIVITY": 0.6,
                    "VULNERABILITY": 0.5,
                },
                {
                    "YEAR": year,
                    "CSOED": "C",
                    "DAIRY_COW": 40,
                    "OTHER_COW": 40,
                    "TOTAL_SHEEP": 20,
                    "PRODUCTIVITY": 0.3,
                    "VULNERABILITY": 0.9,
                },
                {
                    "YEAR": year,
                    "CSOED": "D",
                    "DAIRY_COW": 0,
                    "OTHER_COW": 0,
                    "TOTAL_SHEEP": 0,
                    "PRODUCTIVITY": 0.0,
                    "VULNERABILITY": 0.0,
                },
            ]
        )
    return pd.DataFrame(rows)


def _milestones() -> tuple[NationalMilestone, ...]:
    return (
        NationalMilestone(2030, dairy_cows=180, suckler_cows=90, sheep=95),
        NationalMilestone(2040, dairy_cows=140, suckler_cows=70, sheep=80),
        NationalMilestone(2050, dairy_cows=100, suckler_cows=50, sheep=60),
    )


def test_pathway_hits_each_goblin_milestone_exactly():
    pathway = TransitionPathwayDefinition(
        name="carbon_neutral",
        baseline_year=2025,
        milestones=_milestones(),
        allocation_rule=AllocationRule.PRORATA,
    )
    out = build_transition_pathway(_panel(), pathway, expected_eds=4)

    assert len(out) == 12
    expected = {
        2030: (180, 90, 95),
        2040: (140, 70, 80),
        2050: (100, 50, 60),
    }
    for year, totals in expected.items():
        subset = out.loc[out["MILESTONE_YEAR"] == year]
        assert int(subset["SCENARIO_DAIRY_COW"].sum()) == totals[0]
        assert int(subset["SCENARIO_OTHER_COW"].sum()) == totals[1]
        assert int(subset["SCENARIO_TOTAL_SHEEP"].sum()) == totals[2]


def test_pathway_allocates_only_incremental_reduction_from_previous_state():
    pathway = TransitionPathwayDefinition(
        name="incremental",
        baseline_year=2025,
        milestones=_milestones(),
    )
    out = build_transition_pathway(_panel(), pathway, expected_eds=4)

    expected_dairy_increment = {2030: 20, 2040: 40, 2050: 40}
    expected_suckler_increment = {2030: 10, 2040: 20, 2050: 20}
    expected_sheep_increment = {2030: 5, 2040: 15, 2050: 20}

    for year in (2030, 2040, 2050):
        subset = out.loc[out["MILESTONE_YEAR"] == year]
        assert int(subset["INCREMENTAL_REDUCTION_DAIRY_COW"].sum()) == expected_dairy_increment[year]
        assert int(subset["INCREMENTAL_REDUCTION_OTHER_COW"].sum()) == expected_suckler_increment[year]
        assert int(subset["INCREMENTAL_REDUCTION_TOTAL_SHEEP"].sum()) == expected_sheep_increment[year]

        for column in ("DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"):
            assert (
                subset[f"PREVIOUS_{column}"]
                - subset[f"INCREMENTAL_REDUCTION_{column}"]
                == subset[f"SCENARIO_{column}"]
            ).all()
            assert (
                subset[f"BASE_{column}"]
                - subset[f"CUMULATIVE_REDUCTION_{column}"]
                == subset[f"SCENARIO_{column}"]
            ).all()


def test_ed_states_are_monotonic_and_zero_footprints_stay_zero():
    pathway = TransitionPathwayDefinition(
        name="monotonic",
        baseline_year=2025,
        milestones=_milestones(),
    )
    out = build_transition_pathway(_panel(), pathway, expected_eds=4)

    for ed, group in out.groupby("CSOED"):
        group = group.sort_values("MILESTONE_YEAR")
        for column in ("DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"):
            values = group[f"SCENARIO_{column}"].tolist()
            assert values == sorted(values, reverse=True)
        if ed == "D":
            assert int(group["SCENARIO_DAIRY_COW"].sum()) == 0
            assert int(group["SCENARIO_OTHER_COW"].sum()) == 0
            assert int(group["SCENARIO_TOTAL_SHEEP"].sum()) == 0


def test_dairy_protection_reduces_high_dairy_ed_less_proportionally():
    pathway = TransitionPathwayDefinition(
        name="protect_dairy",
        baseline_year=2025,
        milestones=_milestones(),
        allocation_rule=AllocationRule.DAIRY_PROTECTION,
    )
    out = build_transition_pathway(_panel(), pathway, expected_eds=4)
    final = out.loc[out["MILESTONE_YEAR"] == 2050]

    a = final.loc[final["CSOED"] == "A"].iloc[0]
    c = final.loc[final["CSOED"] == "C"].iloc[0]

    assert int(final["SCENARIO_DAIRY_COW"].sum()) == 100
    assert a["CUMULATIVE_REDUCTION_PCT_DAIRY_COW"] < c["CUMULATIVE_REDUCTION_PCT_DAIRY_COW"]


def test_linear_fallback_from_2050_endpoint_for_2025_baseline():
    endpoint = NationalMilestone(
        2050,
        dairy_cows=100,
        suckler_cows=50,
        sheep=60,
    )
    milestones = linear_milestones_from_endpoint(
        {"dairy_cows": 200, "suckler_cows": 100, "sheep": 100},
        baseline_year=2025,
        endpoint=endpoint,
    )

    assert milestones[0] == NationalMilestone(2030, 180, 90, 92)
    assert milestones[1] == NationalMilestone(2040, 140, 70, 76)
    assert milestones[2] == endpoint


def test_pathway_rejects_national_reexpansion_between_milestones():
    pathway = TransitionPathwayDefinition(
        name="invalid_reexpansion",
        baseline_year=2025,
        milestones=(
            NationalMilestone(2030, dairy_cows=150, suckler_cows=80, sheep=90),
            NationalMilestone(2040, dairy_cows=160, suckler_cows=70, sheep=80),
        ),
    )

    with pytest.raises(ValueError, match="non-increasing"):
        build_transition_pathway(_panel(), pathway, expected_eds=4)
