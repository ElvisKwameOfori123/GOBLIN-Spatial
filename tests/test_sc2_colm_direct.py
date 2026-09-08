from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.sc2_colm_direct import (
    COLM_PHYSICAL_CATEGORIES,
    COLM_RELEASED_AREA_COLUMNS,
    add_colm_direct_eligibility,
    add_colm_released_soil_resource,
    build_colm_direct_sc2_physical,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["1001", "1002"],
            "ALL_GRASSLAND": [500.0, 200.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 50.0],
            "IFS_MAP_DEEP_WELL_DRAINED_SHARE": [0.40, 0.10],
            "IFS_MAP_SHALLOW_WELL_DRAINED_SHARE": [0.20, 0.10],
            "IFS_MAP_POORLY_DRAINED_SHARE": [0.15, 0.30],
            "IFS_MAP_POORLY_DRAINED_PEATY_SHARE": [0.10, 0.20],
            "IFS_MAP_ALLUVIUM_SHARE": [0.05, 0.10],
            "IFS_MAP_PEAT_SHARE": [0.05, 0.15],
            "IFS_MAP_MISCELLANEOUS_SHARE": [0.05, 0.05],
        }
    )


def test_colm_released_resource_closes_to_frozen_sc1_release() -> None:
    frame = _frame()
    before = frame["GOBLIN_RELEASED_GRASSLAND_HA"].copy()

    out = add_colm_released_soil_resource(frame)

    assert np.array_equal(out["GOBLIN_RELEASED_GRASSLAND_HA"], before)
    assert np.allclose(out[list(COLM_RELEASED_AREA_COLUMNS)].sum(axis=1), before)
    assert "COLM_DIRECT_G1_G2_G3_USED" not in out.columns
    assert out["COLM_DIRECT_SC2_RULE_STATUS"].eq("PHYSICAL_RESOURCE_ONLY").all()


def test_colm_direct_builder_has_no_implicit_suitability_rules() -> None:
    out = build_colm_direct_sc2_physical(_frame())

    assert not any(column.endswith("_ELIGIBLE_HA") for column in out.columns)
    assert out["COLM_DIRECT_SC2_RULE_STATUS"].eq("PHYSICAL_RESOURCE_ONLY").all()


def test_explicit_rules_generate_auditable_use_specific_capacity() -> None:
    rules = {
        "TEST_USE": {
            category: coefficient
            for category, coefficient in zip(
                COLM_PHYSICAL_CATEGORIES,
                (1.0, 0.8, 0.5, 0.2, 0.4, 0.0, 0.0),
                strict=True,
            )
        }
    }

    out = add_colm_direct_eligibility(
        _frame(),
        rules=rules,
        rule_version="test-v1",
        evidence_note="unit-test coefficients only",
    )

    expected_first = 100.0 * (
        0.40 * 1.0
        + 0.20 * 0.8
        + 0.15 * 0.5
        + 0.10 * 0.2
        + 0.05 * 0.4
    )
    assert out.loc[0, "COLM_DIRECT_TEST_USE_ELIGIBLE_HA"] == pytest.approx(
        expected_first
    )
    assert out["COLM_DIRECT_SC2_RULE_VERSION"].eq("test-v1").all()
    assert out["COLM_DIRECT_SC2_RULE_EVIDENCE"].eq(
        "unit-test coefficients only"
    ).all()
    assert "COLM_DIRECT_G1_G2_G3_USED" not in out.columns


def test_rule_table_must_cover_every_colm_category() -> None:
    incomplete = {
        "TILLAGE": {
            "DEEP_WELL_DRAINED": 1.0,
            "SHALLOW_WELL_DRAINED": 0.5,
        }
    }

    with pytest.raises(ValueError, match="explicitly cover all Colm categories"):
        add_colm_direct_eligibility(
            _frame(),
            rules=incomplete,
            rule_version="x",
            evidence_note="x",
        )


def test_rule_coefficients_must_be_bounded() -> None:
    invalid = {
        "TILLAGE": {category: 0.5 for category in COLM_PHYSICAL_CATEGORIES}
    }
    invalid["TILLAGE"]["PEAT"] = 1.2

    with pytest.raises(ValueError, match=r"must lie in \[0,1\]"):
        add_colm_direct_eligibility(
            _frame(),
            rules=invalid,
            rule_version="x",
            evidence_note="x",
        )
