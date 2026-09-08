from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.sc2_colm_direct import COLM_PHYSICAL_CATEGORIES
from goblin_spatial.land.sc3_colm_allocation import (
    STAGE_A_USES,
    allocate_colm_sc3_targets,
    summarise_colm_sc3_allocation,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["E1", "E2"],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 100.0],
            "COLM_RELEASED_DEEP_WELL_DRAINED_HA": [50.0, 10.0],
            "COLM_RELEASED_SHALLOW_WELL_DRAINED_HA": [30.0, 20.0],
            "COLM_RELEASED_POORLY_DRAINED_HA": [20.0, 40.0],
            "COLM_RELEASED_POORLY_DRAINED_PEATY_HA": [0.0, 20.0],
            "COLM_RELEASED_ALLUVIUM_HA": [0.0, 0.0],
            "COLM_RELEASED_PEAT_HA": [0.0, 10.0],
            "COLM_RELEASED_MISCELLANEOUS_HA": [0.0, 0.0],
        }
    )


def _rules() -> dict[str, dict[str, float]]:
    zero = {category: 0.0 for category in COLM_PHYSICAL_CATEGORIES}
    rules: dict[str, dict[str, float]] = {}

    rules["AD_GRASS"] = dict(zero)
    rules["BIOREFINERY_GRASS"] = dict(zero)
    for use in ("AD_GRASS", "BIOREFINERY_GRASS"):
        for category in (
            "DEEP_WELL_DRAINED",
            "SHALLOW_WELL_DRAINED",
            "POORLY_DRAINED",
            "ALLUVIUM",
        ):
            rules[use][category] = 1.0

    rules["WILLOW"] = dict(zero)
    rules["WILLOW"]["DEEP_WELL_DRAINED"] = 1.0
    rules["WILLOW"]["SHALLOW_WELL_DRAINED"] = 1.0

    rules["ADDITIONAL_TILLAGE"] = dict(zero)
    rules["ADDITIONAL_TILLAGE"]["DEEP_WELL_DRAINED"] = 1.0
    rules["ADDITIONAL_TILLAGE"]["SHALLOW_WELL_DRAINED"] = 0.5

    rules["FOREST"] = dict(zero)
    for category in (
        "DEEP_WELL_DRAINED",
        "SHALLOW_WELL_DRAINED",
        "POORLY_DRAINED",
        "ALLUVIUM",
    ):
        rules["FOREST"][category] = 1.0
    return rules


def _targets(*, rewetting: float = 0.0) -> dict[str, float]:
    return {
        "AD_GRASS": 30.0,
        "BIOREFINERY_GRASS": 20.0,
        "WILLOW": 20.0,
        "ADDITIONAL_TILLAGE": 20.0,
        "FOREST": 50.0,
        "REWETTING": rewetting,
    }


def test_joint_stage_a_closes_without_double_counting_resource_cells() -> None:
    frame = _frame()
    out = allocate_colm_sc3_targets(
        frame,
        _targets(),
        eligibility_rules=_rules(),
    )

    assert out["SC3_G1_G2_G3_USED"].eq(False).all()
    assert out["SC3_OPPORTUNITY_RANKING_APPLIED"].eq(False).all()
    assert out["SC3_TOTAL_ALLOCATED_HA"].sum() == pytest.approx(140.0)
    assert out["SC3_RESIDUAL_RELEASED_HA"].sum() == pytest.approx(60.0)

    for category in COLM_PHYSICAL_CATEGORIES:
        allocated = sum(
            out[f"SC3_{use}_{category}_HA"].to_numpy(float)
            for use in STAGE_A_USES
        )
        resource = out[f"COLM_RELEASED_{category}_HA"].to_numpy(float)
        assert np.all(allocated <= resource + 1e-8)

    for use, target in _targets().items():
        realised = out[f"SC3_{use}_ALLOCATED_HA"].sum()
        unmet = out[f"SC3_{use}_NATIONAL_UNMET_HA"].iloc[0]
        assert realised + unmet == pytest.approx(target)

    assert np.allclose(
        out["SC3_TOTAL_ALLOCATED_HA"] + out["SC3_RESIDUAL_RELEASED_HA"],
        out["GOBLIN_RELEASED_GRASSLAND_HA"],
    )


def test_positive_rewetting_target_requires_validated_capacity_not_mapped_peat_only() -> None:
    with pytest.raises(ValueError, match="positive REWETTING target requires explicit"):
        allocate_colm_sc3_targets(
            _frame(),
            _targets(rewetting=10.0),
            eligibility_rules=_rules(),
        )


def test_rewetting_uses_only_explicit_residual_capacity_columns() -> None:
    frame = _frame()
    frame["VALIDATED_REWET_PEAT_HA"] = [0.0, 8.0]
    frame["VALIDATED_REWET_PEATY_HA"] = [0.0, 5.0]

    out = allocate_colm_sc3_targets(
        frame,
        _targets(rewetting=10.0),
        eligibility_rules=_rules(),
        rewetting_capacity_columns={
            "PEAT": "VALIDATED_REWET_PEAT_HA",
            "POORLY_DRAINED_PEATY": "VALIDATED_REWET_PEATY_HA",
        },
    )

    assert out["SC3_REWETTING_ALLOCATED_HA"].sum() == pytest.approx(10.0)
    assert out["SC3_REWETTING_NATIONAL_UNMET_HA"].iloc[0] == pytest.approx(0.0)
    assert set(out["SC3_REWETTING_CAPACITY_STATUS"]) == {
        "VALIDATED_EXPLICIT_CAPACITY"
    }
    assert np.allclose(
        out["SC3_TOTAL_ALLOCATED_HA"] + out["SC3_RESIDUAL_RELEASED_HA"],
        out["GOBLIN_RELEASED_GRASSLAND_HA"],
    )


def test_summary_reports_realised_unmet_and_residual() -> None:
    out = allocate_colm_sc3_targets(
        _frame(),
        _targets(),
        eligibility_rules=_rules(),
    )
    summary = summarise_colm_sc3_allocation(out).iloc[0]
    assert summary["TOTAL_RELEASED_HA"] == pytest.approx(200.0)
    assert summary["TOTAL_ALLOCATED_HA"] == pytest.approx(140.0)
    assert summary["RESIDUAL_RELEASED_HA"] == pytest.approx(60.0)
