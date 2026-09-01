"""Tests for the principal authoritative released-land spatialisation route."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure import allocate_national_goblin_land_release
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _profile() -> dict[str, float]:
    """Small deterministic pasture-DM fixture with all systems represented."""

    return {cohort: 1.0 for cohort in (*FINAL_21_COHORTS, *GOBLIN_SHEEP_10)}


def _frame(*, years=(2050,), grass=(1000.0, 1000.0)) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scenarios = {
        2030: {"E1": (85, 40), "E2": (45, 80)},
        2050: {"E1": (70, 30), "E2": (40, 60)},
    }
    baseline = {"E1": (100, 50), "E2": (50, 100)}

    for year in years:
        for index, ed in enumerate(("E1", "E2")):
            base_dairy, base_suckler = baseline[ed]
            scenario_dairy, scenario_suckler = scenarios[int(year)][ed]
            row: dict[str, object] = {
                "CSOED": ed,
                "PATHWAY_NAME": "TEST_PATHWAY",
                "PATHWAY_BASELINE_YEAR": 2020,
                "MILESTONE_YEAR": int(year),
                "ALL_GRASSLAND": float(grass[index]),
                "GOBLIN_SOIL_G1_SHARE": 0.50,
                "GOBLIN_SOIL_G2_SHARE": 0.30,
                "GOBLIN_SOIL_G3_SHARE": 0.20,
                "GOBLIN_SOIL_G1_GRASSLAND_HA": float(grass[index]) * 0.50,
                "GOBLIN_SOIL_G2_GRASSLAND_HA": float(grass[index]) * 0.30,
                "GOBLIN_SOIL_G3_GRASSLAND_HA": float(grass[index]) * 0.20,
            }

            for cohort in FINAL_21_COHORTS:
                base = 0
                scenario = 0
                if cohort == "dairy_cows":
                    base, scenario = base_dairy, scenario_dairy
                elif cohort == "suckler_cows":
                    base, scenario = base_suckler, scenario_suckler
                row[f"BASE_COHORT_{cohort}"] = base
                row[f"SCENARIO_COHORT_{cohort}"] = scenario

            # Sheep are deliberately fixed in the current principal cattle study.
            for cohort in GOBLIN_SHEEP_10:
                row[f"BASE_SHEEP_COHORT_{cohort}"] = 5
                row[f"SCENARIO_SHEEP_COHORT_{cohort}"] = 5

            rows.append(row)

    return pd.DataFrame(rows)


def test_principal_release_closes_to_authoritative_national_total() -> None:
    profiles = {2020: _profile(), 2050: _profile()}
    out = allocate_national_goblin_land_release(
        _frame(),
        {2050: 500.0},
        profiles,
    )

    assert out["GOBLIN_RELEASED_GRASSLAND_HA"].sum() == pytest.approx(500.0)
    assert out["GOBLIN_NATIONAL_RELEASE_ACTUAL_HA"].iloc[0] == pytest.approx(500.0)
    assert np.allclose(out["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"], 0.0)
    assert set(out["GOBLIN_RELEASE_ACCOUNTING_ROLE"]) == {
        "AUTHORITATIVE_RUNTIME_TOTAL_SPATIALISED_WITH_08B_CAPACITY"
    }
    assert set(out["GOBLIN_RELEASE_SYSTEM_SPLIT_SOURCE"]) == {
        "DERIVED_ACTUAL_DM_WEIGHT_ROUTE_RESCALED_ALL_PATHWAYS"
    }
    assert not out["GOBLIN_RELEASE_08C_USED"].any()


def test_principal_release_respects_ed_and_08b_soil_capacity() -> None:
    profiles = {2020: _profile(), 2050: _profile()}
    out = allocate_national_goblin_land_release(
        _frame(),
        {2050: 500.0},
        profiles,
    )

    released_groups = out[
        ["GOBLIN_RELEASED_G1_HA", "GOBLIN_RELEASED_G2_HA", "GOBLIN_RELEASED_G3_HA"]
    ].sum(axis=1)
    assert np.allclose(released_groups, out["GOBLIN_RELEASED_GRASSLAND_HA"])
    assert (out["GOBLIN_RELEASED_GRASSLAND_HA"] <= out["ALL_GRASSLAND"] + 1e-8).all()

    for group in (1, 2, 3):
        assert (
            out[f"GOBLIN_RELEASED_G{group}_HA"]
            <= out[f"GOBLIN_SOIL_G{group}_GRASSLAND_HA"] + 1e-8
        ).all()
        target = out[f"GOBLIN_NATIONAL_RELEASE_G{group}_TARGET_HA"].iloc[0]
        actual = out[f"GOBLIN_RELEASED_G{group}_HA"].sum()
        assert actual == pytest.approx(target)


def test_system_attribution_is_accounting_only_and_closes_to_same_release() -> None:
    profiles = {2020: _profile(), 2050: _profile()}
    out = allocate_national_goblin_land_release(
        _frame(),
        {2050: 500.0},
        profiles,
    )

    system_sum = out[
        [
            "GOBLIN_RELEASED_DAIRY_LAND_HA",
            "GOBLIN_RELEASED_BEEF_LAND_HA",
            "GOBLIN_RELEASED_SHEEP_LAND_HA",
        ]
    ].sum(axis=1)
    assert np.allclose(system_sum, out["GOBLIN_RELEASED_GRASSLAND_HA"])

    for system in ("DAIRY", "BEEF", "SHEEP"):
        target = out[f"GOBLIN_DERIVED_SYSTEM_RELEASE_TARGET_{system}_HA"].iloc[0]
        actual = out[f"GOBLIN_RELEASED_{system}_LAND_HA"].sum()
        assert actual == pytest.approx(target)


def test_independent_dm_diagnostic_is_not_rescaled_to_parent_release() -> None:
    profiles = {2020: _profile(), 2050: _profile()}
    out = allocate_national_goblin_land_release(
        _frame(),
        {2050: 600.0},
        profiles,
    )

    # The solved livestock fixture implies 500 ha of net release from its own
    # pasture-DM balance. The parent pathway control is deliberately set to 600
    # ha and must remain a separate authoritative quantity.
    assert out["GOBLIN_RELEASED_GRASSLAND_HA"].sum() == pytest.approx(600.0)
    assert out["SIGNED_GRASSLAND_BALANCE_HA"].sum() == pytest.approx(500.0)
    assert out["POTENTIAL_SPARED_GRASSLAND_HA"].sum() == pytest.approx(500.0)
    assert out["ADDITIONAL_GRASSLAND_REQUIRED_HA"].sum() == pytest.approx(0.0)
    assert out["DM_DIAGNOSTIC_NET_RELEASE_NATIONAL_HA"].iloc[0] == pytest.approx(500.0)
    assert out["GOBLIN_MINUS_DM_DIAGNOSTIC_NET_RELEASE_HA"].iloc[0] == pytest.approx(100.0)
    assert set(out["DM_DIAGNOSTIC_ACCOUNTING_ROLE"]) == {
        "INDEPENDENT_PASTURE_DM_REQUIREMENT_NOT_RESCALED_TO_GOBLIN_RELEASE"
    }


def test_dm_diagnostic_preserves_local_additional_grassland_requirement() -> None:
    frame = _frame()
    e1 = frame["CSOED"].eq("E1")
    e2 = frame["CSOED"].eq("E2")

    # E1 expands its local pasture-DM demand by 10%, while E2 contracts enough
    # for the national diagnostic still to show net release.
    frame.loc[e1, "SCENARIO_COHORT_dairy_cows"] = 120
    frame.loc[e1, "SCENARIO_COHORT_suckler_cows"] = 50
    frame.loc[e2, "SCENARIO_COHORT_dairy_cows"] = 0
    frame.loc[e2, "SCENARIO_COHORT_suckler_cows"] = 50

    profiles = {2020: _profile(), 2050: _profile()}
    out = allocate_national_goblin_land_release(
        frame,
        {2050: 450.0},
        profiles,
    )

    assert out["POTENTIAL_SPARED_GRASSLAND_HA"].sum() == pytest.approx(500.0)
    assert out["ADDITIONAL_GRASSLAND_REQUIRED_HA"].sum() == pytest.approx(100.0)
    assert out["SIGNED_GRASSLAND_BALANCE_HA"].sum() == pytest.approx(400.0)
    assert out["DM_DIAGNOSTIC_GROSS_SPATIAL_MOVEMENT_NATIONAL_HA"].iloc[0] == pytest.approx(600.0)
    assert out["GOBLIN_MINUS_DM_DIAGNOSTIC_NET_RELEASE_HA"].iloc[0] == pytest.approx(50.0)
    assert out.loc[e1.to_numpy(), "ADDITIONAL_GRASSLAND_REQUIRED_HA"].iloc[0] == pytest.approx(100.0)


def test_targets_must_match_milestones_and_cannot_fall() -> None:
    frame = _frame(years=(2030, 2050))
    profiles = {2020: _profile(), 2030: _profile(), 2050: _profile()}

    with pytest.raises(ValueError, match="exactly match"):
        allocate_national_goblin_land_release(frame, {2050: 500.0}, profiles)

    with pytest.raises(ValueError, match="cannot fall"):
        allocate_national_goblin_land_release(
            frame,
            {2030: 600.0, 2050: 500.0},
            profiles,
        )


def test_release_cannot_exceed_selected_baseline_grassland() -> None:
    profiles = {2020: _profile(), 2050: _profile()}
    with pytest.raises(ValueError, match="exceeds selected baseline grassland"):
        allocate_national_goblin_land_release(
            _frame(grass=(100.0, 100.0)),
            {2050: 250.0},
            profiles,
        )
