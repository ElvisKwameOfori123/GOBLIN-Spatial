from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure import allocate_national_goblin_land_release
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
