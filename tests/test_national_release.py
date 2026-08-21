from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure import (
    allocate_category_resolved_goblin_land_release,
    allocate_national_goblin_land_release,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _profile():
    p = {c: 0.0 for c in (*FINAL_21_COHORTS, *GOBLIN_SHEEP_10)}
    p["dairy_cows"] = 1.0
    return p


def _frame(grass=(1000.0, 1000.0)):
    rows = []
    scenario = {2030: (80, 90), 2050: (60, 80)}
    for year in (2030, 2050):
        for i, ed in enumerate(("E1", "E2")):
            row = {"CSOED": ed, "PATHWAY_BASELINE_YEAR": 2020, "MILESTONE_YEAR": year, "ALL_GRASSLAND": grass[i]}
            for c in FINAL_21_COHORTS:
                row[f"BASE_COHORT_{c}"] = 100 if c == "dairy_cows" else 0
                row[f"SCENARIO_COHORT_{c}"] = scenario[year][i] if c == "dairy_cows" else 0
            for c in GOBLIN_SHEEP_10:
                row[f"BASE_SHEEP_COHORT_{c}"] = 0
                row[f"SCENARIO_SHEEP_COHORT_{c}"] = 0
            rows.append(row)
    return pd.DataFrame(rows)


def test_release_closes_and_follows_pressure():
    profiles = {y: _profile() for y in (2020, 2030, 2050)}
    out = allocate_national_goblin_land_release(_frame(), {2030: 300.0, 2050: 600.0}, profiles)
    national = out.groupby("MILESTONE_YEAR")["GOBLIN_RELEASED_GRASSLAND_HA"].sum()
    assert national.loc[2030] == pytest.approx(300.0)
    assert national.loc[2050] == pytest.approx(600.0)
    first = out[out["MILESTONE_YEAR"].eq(2030)].set_index("CSOED")
    assert first.loc["E1", "GOBLIN_RELEASED_GRASSLAND_HA"] == pytest.approx(200.0)
    assert first.loc["E2", "GOBLIN_RELEASED_GRASSLAND_HA"] == pytest.approx(100.0)
    ordered = out.sort_values(["CSOED", "MILESTONE_YEAR"])
    assert (ordered.groupby("CSOED")["GOBLIN_RELEASED_GRASSLAND_HA"].diff().dropna() >= -1e-9).all()
    assert np.allclose(out["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"], 0.0)


def test_release_respects_grassland_capacity():
    profiles = {y: _profile() for y in (2020, 2030, 2050)}
    out = allocate_national_goblin_land_release(_frame((150.0, 1000.0)), {2030: 300.0, 2050: 500.0}, profiles)
    assert (out["GOBLIN_RELEASED_GRASSLAND_HA"] <= out["ALL_GRASSLAND"] + 1e-9).all()
    assert out[out["MILESTONE_YEAR"].eq(2050)]["GOBLIN_RELEASED_GRASSLAND_HA"].sum() == pytest.approx(500.0)


def test_targets_must_match_and_not_fall():
    profiles = {y: _profile() for y in (2020, 2030, 2050)}
    with pytest.raises(ValueError, match="exactly match"):
        allocate_national_goblin_land_release(_frame(), {2050: 600.0}, profiles)
    with pytest.raises(ValueError, match="cannot fall"):
        allocate_national_goblin_land_release(_frame(), {2030: 600.0, 2050: 500.0}, profiles)


def test_positive_release_requires_pressure_reduction():
    frame = _frame()
    for c in FINAL_21_COHORTS:
        frame[f"SCENARIO_COHORT_{c}"] = frame[f"BASE_COHORT_{c}"]
    profiles = {y: _profile() for y in (2020, 2030, 2050)}
    with pytest.raises(ValueError, match="cannot be spatialised"):
        allocate_national_goblin_land_release(frame, {2030: 100.0, 2050: 200.0}, profiles)


def _category_profile():
    return {c: 1.0 for c in (*FINAL_21_COHORTS, *GOBLIN_SHEEP_10)}


def _category_frame():
    rows = []
    for ed, grass, bd, sd, bs, ss, sheep in [
        ("A", 120.0, 20, 25, 30, 10, 20),
        ("B", 180.0, 10, 12, 50, 20, 30),
    ]:
        row = {
            "CSOED": ed,
            "County": "Test",
            "PATHWAY_BASELINE_YEAR": 2020,
            "MILESTONE_YEAR": 2050,
            "ALL_GRASSLAND": grass,
        }
        for cohort in FINAL_21_COHORTS:
            base = 0
            scenario = 0
            if cohort == "dairy_cows":
                base, scenario = bd, sd
            elif cohort == "suckler_cows":
                base, scenario = bs, ss
            elif cohort == "bulls":
                base, scenario = 2, 1
            elif cohort.startswith("DxD_") or cohort.startswith("DxB_"):
                base, scenario = (4 if ed == "A" else 2), (5 if ed == "A" else 3)
            elif cohort.startswith("BxB_"):
                base, scenario = (6 if ed == "A" else 10), (2 if ed == "A" else 4)
            row[f"BASE_COHORT_{cohort}"] = base
            row[f"SCENARIO_COHORT_{cohort}"] = scenario
        for cohort in GOBLIN_SHEEP_10:
            row[f"BASE_SHEEP_COHORT_{cohort}"] = sheep
            row[f"SCENARIO_SHEEP_COHORT_{cohort}"] = sheep
        rows.append(row)
    return pd.DataFrame(rows)


def test_category_release_closes_system_targets_and_shared_ed_capacity():
    profiles = {2020: _category_profile(), 2050: _category_profile()}
    out = allocate_category_resolved_goblin_land_release(
        _category_frame(),
        {"DAIRY": 20.0, "BEEF": 100.0, "SHEEP": 10.0},
        profiles,
    )
    assert out["GOBLIN_RELEASED_DAIRY_LAND_HA"].sum() == pytest.approx(20.0)
    assert out["GOBLIN_RELEASED_BEEF_LAND_HA"].sum() == pytest.approx(100.0)
    assert out["GOBLIN_RELEASED_SHEEP_LAND_HA"].sum() == pytest.approx(10.0)
    assert out["GOBLIN_RELEASED_GRASSLAND_HA"].sum() == pytest.approx(130.0)
    assert (out["GOBLIN_RELEASED_GRASSLAND_HA"] <= out["ALL_GRASSLAND"] + 1e-9).all()


def test_category_release_handles_dairy_land_efficiency_with_more_dairy_heads():
    profiles = {2020: _category_profile(), 2050: _category_profile()}
    out = allocate_category_resolved_goblin_land_release(
        _category_frame(),
        {"DAIRY": 15.0, "BEEF": 0.0, "SHEEP": 0.0},
        profiles,
    )
    assert (
        out["SCENARIO_DAIRY_SYSTEM_PASTURE_DM_T"]
        > out["BASE_DAIRY_SYSTEM_PASTURE_DM_T"]
    ).all()
    assert out["GOBLIN_RELEASED_DAIRY_LAND_HA"].sum() == pytest.approx(15.0)
    assert (out["GOBLIN_RELEASED_DAIRY_LAND_HA"] > 0).all()


def test_category_release_handles_fixed_sheep_with_sourced_land_efficiency_shift():
    profiles = {2020: _category_profile(), 2050: _category_profile()}
    out = allocate_category_resolved_goblin_land_release(
        _category_frame(),
        {"DAIRY": 0.0, "BEEF": 0.0, "SHEEP": 6.0},
        profiles,
    )
    assert np.allclose(
        out["BASE_SHEEP_SYSTEM_PASTURE_DM_T"],
        out["SCENARIO_SHEEP_SYSTEM_PASTURE_DM_T"],
    )
    assert out["GOBLIN_RELEASED_SHEEP_LAND_HA"].sum() == pytest.approx(6.0)
