"""Tests for the Colm-direct SC2 context contract."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.sc2_colm_direct import COLM_RELEASED_AREA_COLUMNS
from goblin_spatial.land.sc2_context import prepare_sc2_context


def _sc1() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["1001", "1002"],
            "County": ["A", "B"],
            "ALL_GRASSLAND": [1000.0, 500.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [300.0, 100.0],
            "SCENARIO_BASELINE_YEAR": [2020, 2020],
        }
    )


def _context() -> pd.DataFrame:
    rows = []
    for ed in ("1001", "1002"):
        rows.append(
            {
                "CSOED": ed,
                "IFS_MAP_DEEP_WELL_DRAINED_HA": 35.0,
                "IFS_MAP_SHALLOW_WELL_DRAINED_HA": 20.0,
                "IFS_MAP_POORLY_DRAINED_HA": 15.0,
                "IFS_MAP_POORLY_DRAINED_PEATY_HA": 10.0,
                "IFS_MAP_ALLUVIUM_HA": 5.0,
                "IFS_MAP_PEAT_HA": 10.0,
                "IFS_MAP_MISCELLANEOUS_HA": 5.0,
                "LPIS_YEAR": 2020,
                "LPIS_CLAIMED_AG_HA": 100.0,
                "LPIS_ELIGIBLE_AG_HA": 90.0,
                "LPIS_SPATIAL_FOOTPRINT_HA": 120.0,
                "LPIS_CLAIMED_GRASS_HA": 90.0,
                "LPIS_ELIGIBLE_GRASS_HA": 80.0,
                "LPIS_PERMANENT_PASTURE_HA": 60.0,
                "LPIS_LOW_INPUT_GRASS_HA": 10.0,
                "LPIS_TEMPORARY_GRASS_HA": 10.0,
                "LPIS_HAY_MEADOW_HA": 5.0,
                "LPIS_OTHER_GRASS_HA": 5.0,
                "LPIS_COMMONAGE_GRASS_HA": 0.0,
                "LPIS_ANC_GRASS_HA": 50.0,
                "LPIS_ENV_SCHEME_GRASS_HA": 20.0,
                "LPIS_ORGANIC_GRASS_HA": 5.0,
                "LPIS_BOG_PEAT_CONTEXT_HA": 2.0,
                "LPIS_HABITAT_CONTEXT_HA": 3.0,
                "LPIS_FORESTRY_CONTEXT_HA": 4.0,
            }
        )
    return pd.DataFrame(rows)


def test_sc2_preserves_frozen_release_and_partitions_to_colm_categories() -> None:
    sc1 = _sc1()
    original_release = sc1["GOBLIN_RELEASED_GRASSLAND_HA"].copy()
    out = prepare_sc2_context(sc1, land_context=_context(), baseline_year=2020)

    assert np.array_equal(out["GOBLIN_RELEASED_GRASSLAND_HA"], original_release)
    assert np.allclose(
        out[list(COLM_RELEASED_AREA_COLUMNS)].sum(axis=1),
        original_release,
    )
    assert np.allclose(out["COLM_RELEASED_DEEP_WELL_DRAINED_HA"], original_release * 0.35)
    assert np.allclose(out["COLM_RELEASED_PEAT_HA"], original_release * 0.10)
    assert out["SC2_COLM_PHYSICAL_CONTEXT_AVAILABLE"].all()
    assert out["SC2_LPIS_CONTEXT_AVAILABLE"].all()
    assert out["SC2_G1_G2_G3_USED"].eq(False).all()
    assert out["SC2_SYNTHETIC_SOIL_GROUPS_USED"].eq(False).all()
    assert out["SC2_FARMED_PEAT_FRACTION_ASSUMPTION_USED"].eq(False).all()
    assert out["COLM_PHYSICAL_SYNTHETIC_SG_USED"].eq(False).all()
    assert out["COLM_PHYSICAL_FARMED_PEAT_ASSUMPTION_USED"].eq(False).all()
    assert set(out["SC2_CONTEXT_VERSION"]) == {"COLM_DIRECT_1.1"}
    assert set(out["SC2_OPPORTUNITY_STATUS"]) == {
        "CONTEXT_EVIDENCE_ONLY_NO_ARBITRARY_COMPOSITE"
    }
    assert not any(column.startswith("SC2_RELEASED_G") for column in out.columns)
    for legacy in (
        "IFS_MAP_SG1_SHARE",
        "IFS_MAP_SG2_SHARE",
        "IFS_MAP_SG3_SHARE",
        "IFS_MAP_EFFECTIVE_FARMED_PEAT_HA",
    ):
        assert legacy not in out.columns


def test_sc2_attaches_lpis_as_context_without_changing_release() -> None:
    out = prepare_sc2_context(_sc1(), land_context=_context(), baseline_year=2020)
    assert out["LPIS_PROFILE_YEAR"].eq(2020).all()
    assert np.allclose(out["LPIS_LOW_INPUT_GRASS_SHARE"], 10.0 / 90.0)
    assert np.allclose(out["SC2_LPIS_LOW_INPUT_GRASS_SHARE"], 10.0 / 90.0)
    assert set(out["SC2_LAND_CONTEXT_ROLE"]) == {
        "COLM_PHYSICAL_SOIL_PLUS_LPIS_BASELINE_EVIDENCE"
    }


def test_sc2_is_invariant_to_legacy_08b_fields_in_a_merged_context() -> None:
    """Legacy capability fields may coexist in a source file but cannot affect SC2."""

    clean = _context()
    reference = prepare_sc2_context(_sc1(), land_context=clean, baseline_year=2020)

    contaminated = clean.copy()
    contaminated["GOBLIN_SOIL_G1_SHARE"] = [1.0, 0.0]
    contaminated["GOBLIN_SOIL_G2_SHARE"] = [0.0, 1.0]
    contaminated["GOBLIN_SOIL_G3_SHARE"] = [0.0, 0.0]
    contaminated["SOIL_USE_CLASS_1_SHARE"] = [1.0, 0.0]
    contaminated["SOIL_USE_CLASS_6_SHARE"] = [0.0, 1.0]
    changed = prepare_sc2_context(
        _sc1(),
        land_context=contaminated,
        baseline_year=2020,
    )

    assert np.array_equal(
        reference["GOBLIN_RELEASED_GRASSLAND_HA"].to_numpy(float),
        changed["GOBLIN_RELEASED_GRASSLAND_HA"].to_numpy(float),
    )
    for column in COLM_RELEASED_AREA_COLUMNS:
        assert np.array_equal(
            reference[column].to_numpy(float),
            changed[column].to_numpy(float),
        )
    assert "GOBLIN_SOIL_G1_SHARE" not in changed.columns
    assert "SOIL_USE_CLASS_1_SHARE" not in changed.columns


def test_sc2_applies_only_explicit_versioned_soil_rules() -> None:
    rules = {
        "ADDITIONAL_TILLAGE": {
            "DEEP_WELL_DRAINED": 1.0,
            "SHALLOW_WELL_DRAINED": 0.5,
            "POORLY_DRAINED": 0.0,
            "POORLY_DRAINED_PEATY": 0.0,
            "ALLUVIUM": 0.5,
            "PEAT": 0.0,
            "MISCELLANEOUS": 0.0,
        }
    }
    out = prepare_sc2_context(
        _sc1(),
        land_context=_context(),
        baseline_year=2020,
        eligibility_rules=rules,
        rule_version="test-v1",
        evidence_note="unit-test rule only",
    )
    expected_share = 0.35 + 0.5 * 0.20 + 0.5 * 0.05
    assert np.allclose(
        out["COLM_DIRECT_ADDITIONAL_TILLAGE_ELIGIBLE_HA"],
        out["GOBLIN_RELEASED_GRASSLAND_HA"] * expected_share,
    )
    assert set(out["COLM_DIRECT_SC2_RULE_VERSION"]) == {"test-v1"}


def test_sc2_does_not_allow_rewetting_from_mapped_soil_alone() -> None:
    rules = {
        "REWETTING": {
            "DEEP_WELL_DRAINED": 0.0,
            "SHALLOW_WELL_DRAINED": 0.0,
            "POORLY_DRAINED": 0.0,
            "POORLY_DRAINED_PEATY": 1.0,
            "ALLUVIUM": 0.0,
            "PEAT": 1.0,
            "MISCELLANEOUS": 0.0,
        }
    }
    with pytest.raises(ValueError, match="cannot be derived from Colm soil"):
        prepare_sc2_context(
            _sc1(),
            land_context=_context(),
            baseline_year=2020,
            eligibility_rules=rules,
            rule_version="x",
            evidence_note="x",
        )


def test_sc2_rejects_2025_until_separate_frozen_context_exists() -> None:
    with pytest.raises(ValueError, match="baseline_year=2020"):
        prepare_sc2_context(_sc1(), land_context=_context(), baseline_year=2025)
