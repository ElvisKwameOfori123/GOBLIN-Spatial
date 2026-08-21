from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.land.sc3_allocation import (
    SC3_USES,
    allocate_sc3_targets,
    summarise_sc3_allocation,
)


def _context() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "CSOED": ["1", "2"],
            "SC2_POTENTIAL_RELEASE_HA": [100.0, 100.0],
        }
    )
    for use in SC3_USES:
        frame[f"CAP_{use}"] = [100.0, 100.0]
        frame[f"SCORE_{use}"] = [1.0, 0.5]
    return frame


def _columns(prefix: str) -> dict[str, str]:
    return {use: f"{prefix}_{use}" for use in SC3_USES}


def test_sc3_stage_a_then_rewetting_closes_to_frozen_release() -> None:
    targets = {
        "AD_GRASS": 60.0,
        "BIOREFINERY_GRASS": 50.0,
        "WILLOW": 50.0,
        "ADDITIONAL_TILLAGE": 0.0,
        "FOREST": 0.0,
        "REWETTING": 20.0,
    }
    out = allocate_sc3_targets(
        _context(),
        targets,
        capacity_columns=_columns("CAP"),
        score_columns=_columns("SCORE"),
    )

    assert np.isclose(out[[f"SC3_REALIZED_{use}_HA" for use in SC3_USES]].sum().sum(), 180.0)
    assert np.isclose(out["SC3_STAGE_A_AVAILABLE_HA"].sum(), 40.0)
    assert np.isclose(out["SC3_REALIZED_REWETTING_HA"].sum(), 20.0)
    assert np.isclose(out["SC3_RESIDUAL_AVAILABLE_LAND_HA"].sum(), 20.0)
    assert np.allclose(
        out["SC3_REALISED_CONVERSION_HA"] + out["SC3_RESIDUAL_AVAILABLE_LAND_HA"],
        out["SC2_POTENTIAL_RELEASE_HA"],
    )

    summary = summarise_sc3_allocation(out).iloc[0]
    assert np.isclose(summary["POTENTIAL_RELEASE_HA"], 200.0)
    assert np.isclose(summary["REALISED_CONVERSION_HA"], 180.0)
    assert np.isclose(summary["RESIDUAL_AVAILABLE_LAND_HA"], 20.0)
    assert np.isclose(summary["ACCOUNTING_CLOSURE_HA"], 0.0)


def test_sc3_reports_unmet_target_instead_of_forcing_ineligible_land() -> None:
    context = _context()
    context["CAP_FOREST"] = [10.0, 0.0]
    context["SCORE_FOREST"] = [1.0, 0.0]
    targets = {
        "AD_GRASS": 0.0,
        "BIOREFINERY_GRASS": 0.0,
        "WILLOW": 0.0,
        "ADDITIONAL_TILLAGE": 0.0,
        "FOREST": 50.0,
        "REWETTING": 0.0,
    }
    out = allocate_sc3_targets(
        context,
        targets,
        capacity_columns=_columns("CAP"),
        score_columns=_columns("SCORE"),
    )

    assert np.isclose(out["SC3_REALIZED_FOREST_HA"].sum(), 10.0)
    assert np.isclose(out["SC3_NATIONAL_UNMET_FOREST_HA"].iloc[0], 40.0)
    assert np.isclose(out["SC3_RESIDUAL_AVAILABLE_LAND_HA"].sum(), 190.0)


def test_sc3_does_not_allocate_when_explicit_score_is_zero() -> None:
    context = _context()
    context["SCORE_WILLOW"] = [0.0, 0.0]
    targets = {
        "AD_GRASS": 0.0,
        "BIOREFINERY_GRASS": 0.0,
        "WILLOW": 50.0,
        "ADDITIONAL_TILLAGE": 0.0,
        "FOREST": 0.0,
        "REWETTING": 0.0,
    }
    out = allocate_sc3_targets(
        context,
        targets,
        capacity_columns=_columns("CAP"),
        score_columns=_columns("SCORE"),
    )
    assert np.isclose(out["SC3_REALIZED_WILLOW_HA"].sum(), 0.0)
    assert np.isclose(out["SC3_NATIONAL_UNMET_WILLOW_HA"].iloc[0], 50.0)
