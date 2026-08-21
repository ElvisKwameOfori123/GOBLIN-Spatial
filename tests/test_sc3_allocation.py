from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy")

from goblin_spatial.land.sc3_allocation import (
    SC3_USES,
    STAGE_A_USES,
    allocate_sc3_targets,
    summarise_sc3_allocation,
)


def _context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["1", "2", "3"],
            "SC2_POTENTIAL_RELEASE_HA": [100.0, 100.0, 100.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 100.0, 100.0],
            "ALL_GRASSLAND": [1000.0, 1000.0, 1000.0],
            "IFS_PEAT_CUTOVER_UAA_SHARE": [0.20, 0.10, 0.05],
            "RELEASED_ORGANIC_WEIGHT_HA": [20.0, 10.0, 5.0],
            "RELEASED_TILLAGE_ELIGIBLE_HA": [40.0, 40.0, 40.0],
            "RELEASED_TILLAGE_STRICT_ELIGIBLE_HA": [30.0, 30.0, 30.0],
            "RELEASED_WILLOW_ELIGIBLE_HA": [40.0, 40.0, 40.0],
            "RELEASED_WILLOW_WIDE_ELIGIBLE_HA": [60.0, 60.0, 60.0],
            "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA": [70.0, 70.0, 70.0],
            "RELEASED_FOREST_ELIGIBLE_HA": [100.0, 100.0, 100.0],
            "AD_GRASS_OPPORTUNITY_SCORE": [1.0, 0.7, 0.2],
            "WILLOW_OPPORTUNITY_SCORE": [0.3, 1.0, 0.5],
            "GOBLIN_SOIL_PRODUCTIVITY_SCORE": [1.0, 0.8, 0.6],
            "FORESTRY_OPPORTUNITY_SCORE": [0.2, 0.6, 1.0],
            "FOREST_YC_WEIGHTED_MEAN": [20.0, 18.0, 16.0],
        }
    )


def _zero_targets() -> dict[str, float]:
    return {use: 0.0 for use in SC3_USES}


def test_sc3_v27_joint_stage_a_then_rewetting_closes_exactly() -> None:
    targets = {
        "AD_GRASS": 50.0,
        "BIOREFINERY_GRASS": 30.0,
        "WILLOW": 40.0,
        "ADDITIONAL_TILLAGE": 30.0,
        "FOREST": 50.0,
        "REWETTING": 20.0,
    }
    out = allocate_sc3_targets(
        _context(),
        targets,
        drained_organic_grassland_ha=60.0,
    )

    for use, target in targets.items():
        assert np.isclose(out[f"SC3_REALIZED_{use}_HA"].sum(), target)
        assert np.isclose(out[f"SC3_NATIONAL_UNMET_{use}_HA"].iloc[0], 0.0)

    assert np.isclose(out["SC3_STAGE_A_REALIZED_HA"].sum(), 200.0)
    assert np.isclose(out["SC3_STAGE_A_AVAILABLE_HA"].sum(), 100.0)
    assert np.isclose(out["SC3_REALIZED_REWETTING_HA"].sum(), 20.0)
    assert np.isclose(out["SC3_RESIDUAL_AVAILABLE_LAND_HA"].sum(), 80.0)
    assert np.allclose(
        out["SC3_REALISED_CONVERSION_HA"]
        + out["SC3_RESIDUAL_AVAILABLE_LAND_HA"],
        out["SC2_POTENTIAL_RELEASE_HA"],
    )
    assert np.isclose(out["SC3_ACCOUNTING_CLOSURE_HA"].abs().max(), 0.0)
    assert set(out["SC3_ALLOCATION_VERSION"]) == {"2.7"}

    summary = summarise_sc3_allocation(out).iloc[0]
    assert np.isclose(summary["POTENTIAL_RELEASE_HA"], 300.0)
    assert np.isclose(summary["REALISED_CONVERSION_HA"], 220.0)
    assert np.isclose(summary["RESIDUAL_AVAILABLE_LAND_HA"], 80.0)
    assert np.isclose(summary["TOTAL_UNMET_TARGET_HA"], 0.0)
    assert np.isclose(summary["ACCOUNTING_CLOSURE_HA"], 0.0)


def test_sc3_joint_lp_reports_shared_pool_shortfall_instead_of_double_using_land() -> None:
    targets = _zero_targets()
    targets["WILLOW"] = 80.0
    targets["ADDITIONAL_TILLAGE"] = 80.0

    out = allocate_sc3_targets(
        _context(),
        targets,
        drained_organic_grassland_ha=60.0,
    )

    # Each use has 120 ha of individual capacity, but both share the same
    # Classes-1-3 mineral pool of 120 ha nationally. The joint LP therefore
    # reports 40 ha unmet rather than allocating the same pool twice.
    realised = (
        out["SC3_REALIZED_WILLOW_HA"].sum()
        + out["SC3_REALIZED_ADDITIONAL_TILLAGE_HA"].sum()
    )
    unmet = (
        out["SC3_NATIONAL_UNMET_WILLOW_HA"].iloc[0]
        + out["SC3_NATIONAL_UNMET_ADDITIONAL_TILLAGE_HA"].iloc[0]
    )
    assert np.isclose(realised, 120.0)
    assert np.isclose(unmet, 40.0)
    assert np.isclose(out["SC3_POOL_TILLAGE_WILLOW_USED_HA"].sum(), 120.0)
    assert np.isclose(out["SC3_POOL_TILLAGE_WILLOW_CAPACITY_HA"].sum(), 120.0)
    assert (
        out["SC3_POOL_TILLAGE_WILLOW_USED_HA"]
        <= out["SC3_POOL_TILLAGE_WILLOW_CAPACITY_HA"] + 1e-8
    ).all()


def test_sc3_rewetting_is_limited_to_post_stage_a_available_land() -> None:
    context = _context()
    context["AD_GRASS_OPPORTUNITY_SCORE"] = [1.0, 0.0, 0.0]
    targets = _zero_targets()
    targets["AD_GRASS"] = 70.0
    targets["REWETTING"] = 60.0

    out = allocate_sc3_targets(
        context,
        targets,
        drained_organic_grassland_ha=60.0,
    )

    assert (
        out["SC3_REALIZED_REWETTING_HA"]
        <= out["SC3_REWETTING_POST_STAGE_A_CAPACITY_HA"] + 1e-8
    ).all()
    assert (
        out["SC3_REWETTING_POST_STAGE_A_CAPACITY_HA"]
        <= out["SC3_STAGE_A_AVAILABLE_HA"] + 1e-8
    ).all()
    assert np.allclose(
        out["SC3_STAGE_A_REALIZED_HA"]
        + out["SC3_REALIZED_REWETTING_HA"]
        + out["SC3_RESIDUAL_AVAILABLE_LAND_HA"],
        out["SC2_POTENTIAL_RELEASE_HA"],
    )


def test_sc3_forest_yc_is_a_hard_capacity_rule() -> None:
    context = _context()
    context.loc[context["CSOED"].eq("3"), "FOREST_YC_WEIGHTED_MEAN"] = np.nan
    targets = _zero_targets()
    targets["FOREST"] = 250.0

    out = allocate_sc3_targets(
        context,
        targets,
        drained_organic_grassland_ha=60.0,
    )

    assert np.isclose(out["SC3_FOREST_ELIGIBLE_BEFORE_YC_HA"].iloc[0], 300.0)
    assert np.isclose(out["SC3_FOREST_ELIGIBLE_AFTER_YC_HA"].iloc[0], 200.0)
    assert np.isclose(out["SC3_FOREST_YC_REMOVED_HA"].iloc[0], 100.0)
    assert np.isclose(out["SC3_REALIZED_FOREST_HA"].sum(), 200.0)
    assert np.isclose(out["SC3_NATIONAL_UNMET_FOREST_HA"].iloc[0], 50.0)


def test_sc3_rejects_old_sequential_stage_a_priority_api() -> None:
    with pytest.raises(ValueError, match="joint LP"):
        allocate_sc3_targets(
            _context(),
            _zero_targets(),
            stage_a_priority=STAGE_A_USES,
            drained_organic_grassland_ha=60.0,
        )
