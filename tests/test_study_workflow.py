"""Tests for the end-to-end cattle-study wrapper and 18-cohort audit."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario import (
    PRE_ADULT_CATTLE_COHORTS,
    make_cattle_scenario,
    run_cattle_study,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _row(
    year: int,
    ed: str,
    county: str,
    dairy: int,
    suckler: int,
    *,
    dairy_receiver: bool = False,
) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": year,
        "CSOED": ed,
        "County": county,
        "DAIRY_COW": dairy,
        "OTHER_COW": suckler,
        "TOTAL_SHEEP": 20,
        "ALL_GRASSLAND": 100.0,
        "TOTAL_CEREALS": 10.0,
        "OTHER_CROPS_HA": 5.0,
        "AREA_FARMED": 115.0,
        "AGRICULTURAL_HOLDINGS": 10,
    }
    row.update({cohort: 0 for cohort in FINAL_21_COHORTS})
    row.update({cohort: 0 for cohort in GOBLIN_SHEEP_10})
    row["dairy_cows"] = dairy
    row["suckler_cows"] = suckler
    row["bulls"] = max(1, (dairy + suckler) // 50) if dairy + suckler else 0

    for cohort in PRE_ADULT_CATTLE_COHORTS:
        if cohort.startswith("DxD_") or cohort.startswith("DxB_"):
            if dairy > 0:
                row[cohort] = max(1, dairy // 20)
            elif dairy_receiver:
                row[cohort] = 4
        elif cohort.startswith("BxB_") and suckler > 0:
            row[cohort] = max(1, suckler // 20)

    row["Lowland ewes"] = 12
    row["Lowland lamb_less_1_yr"] = 8
    return row


def _panel() -> pd.DataFrame:
    rows = []
    for year, scale in ((2020, 1.0), (2025, 0.9)):
        rows.extend(
            [
                _row(year, "A", "Mayo", int(100 * scale), int(80 * scale)),
                # B is a dairy-origin receiver: DxD/DxB cohorts but no dairy cows.
                _row(
                    year,
                    "B",
                    "Mayo",
                    0,
                    int(60 * scale),
                    dairy_receiver=True,
                ),
                _row(year, "C", "Cork", int(80 * scale), int(70 * scale)),
            ]
        )
    return pd.DataFrame(rows)


def test_cattle_study_records_exact_18_cohort_ed_relationships_and_receiver_ripple(
    tmp_path: Path,
) -> None:
    definition = make_cattle_scenario(
        name="DAIRY_30",
        baseline_year=2020,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.0,
    )
    run = run_cattle_study(
        _panel(),
        definition,
        expected_eds=3,
        include_standard_output=False,
        output_dir=tmp_path / "scenario",
    )

    assert len(run.dependency) == 3 * 18
    assert set(run.dependency["COHORT"]) == set(PRE_ADULT_CATTLE_COHORTS)
    assert "bulls" not in set(run.dependency["COHORT"])

    receiver = run.dependency.loc[
        (run.dependency["CSOED"] == "B")
        & (run.dependency["COHORT"] == "DxB_calves_m")
    ].iloc[0]
    assert receiver["BASE_ORIGIN_ADULTS"] == 0
    assert receiver["COHORT_SPATIAL_ROLE"] == "COUNTY_RECEIVER"
    assert receiver["ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO"] > 0

    receiver_path = run.cohort_audit.loc[
        (run.cohort_audit["CSOED"] == "B")
        & (run.cohort_audit["COHORT"] == "DxB_calves_m")
    ]
    assert (receiver_path["APPLIED_SIGNAL_SOURCE"] == "COUNTY_RECEIVER").all()
    assert receiver_path["CUMULATIVE_REDUCTION_HEAD"].iloc[-1] > 0

    # Suckler-origin cohorts do not fall in a dairy-only scenario.
    bxb = run.cohort_audit.loc[run.cohort_audit["COHORT"].str.startswith("BxB_")]
    assert int(bxb["CUMULATIVE_REDUCTION_HEAD"].sum()) == 0

    # The wrapper writes the publication/audit outputs explicitly.
    assert run.output_dir == tmp_path / "scenario"
    expected_files = {
        "scenario_schedule.csv",
        "scenario_national_summary.csv",
        "scenario_ed_results.csv",
        "baseline_ed_18_cohort_relationships.csv",
        "scenario_ed_18_cohort_audit.csv",
    }
    assert {path.name for path in run.output_dir.iterdir()} == expected_files


def test_same_workflow_accepts_2025_starting_state() -> None:
    definition = make_cattle_scenario(
        name="BOTH_30_2025",
        baseline_year=2025,
        target_year=2050,
        dairy_reduction=0.30,
        suckler_reduction=0.30,
    )
    run = run_cattle_study(
        _panel(),
        definition,
        expected_eds=3,
        include_standard_output=False,
    )
    assert set(run.baseline["YEAR"]) == {2025}
    assert set(run.scenario.ed["PATHWAY_BASELINE_YEAR"]) == {2025}
    assert run.scenario.schedule["MILESTONE_YEAR"].tolist() == [2030, 2040, 2050]
    assert run.scenario.schedule["dairy_reduction"].tolist() == [0.06, 0.18, 0.30]
