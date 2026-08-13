"""Tests for the policy-neutral spared-land opportunity envelope."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land import (
    add_spared_land_opportunity_envelope,
    summarise_spared_land_opportunity_envelope,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["A", "B", "C", "A", "B", "C"],
            "MILESTONE_YEAR": [2030, 2030, 2030, 2050, 2050, 2050],
            "POTENTIAL_SPARED_GRASSLAND_HA": [10.0, 20.0, 30.0, 20.0, 40.0, 60.0],
            "GOBLIN_SOIL_G1_SHARE": [0.6, 0.2, 0.0, 0.6, 0.2, 0.0],
            "GOBLIN_SOIL_G2_SHARE": [0.3, 0.5, 0.0, 0.3, 0.5, 0.0],
            "GOBLIN_SOIL_G3_SHARE": [0.1, 0.3, 1.0, 0.1, 0.3, 1.0],
            "FOREST_YC_WEIGHTED_MEAN": [24.0, 19.0, np.nan, 24.0, 19.0, np.nan],
            "IFS_SOIL_DOMINANT": ["AminPDPT", "AminDW", "CUT", "AminPDPT", "AminDW", "CUT"],
            "IFS_SOIL_DOMINANT_SHARE": [0.7, 0.8, 0.5, 0.7, 0.8, 0.5],
        }
    )


def test_opportunity_envelope_is_policy_neutral_overlapping_and_bounded() -> None:
    screened = add_spared_land_opportunity_envelope(_frame())

    for land_use in ("FOREST", "REWETTING", "AD_GRASS", "WILLOW", "ENERGY_GRASS", "NATURE"):
        eligible = screened[f"ELIGIBLE_{land_use}_SPARED_GRASSLAND_HA"].to_numpy(dtype=float)
        weighted = screened[f"SCORE_WEIGHTED_{land_use}_OPPORTUNITY_HA"].to_numpy(dtype=float)
        spared = screened["POTENTIAL_SPARED_GRASSLAND_HA"].to_numpy(dtype=float)
        assert (eligible >= -1e-12).all()
        assert (weighted >= -1e-12).all()
        assert (eligible <= spared + 1e-12).all()
        assert (weighted <= spared + 1e-12).all()

    # Rewetting evidence exists for A (PT suffix) and C (CUT), but not B.
    b = screened["CSOED"].eq("B")
    assert np.isclose(
        screened.loc[b, "ELIGIBLE_REWETTING_SPARED_GRASSLAND_HA"].sum(),
        0.0,
    )
    assert screened.loc[~b, "ELIGIBLE_REWETTING_SPARED_GRASSLAND_HA"].sum() > 0

    # Pure G3 has zero productive-biomass score under the current GOBLIN yield-gap screen.
    c = screened["CSOED"].eq("C")
    assert np.isclose(
        screened.loc[c, "SCORE_WEIGHTED_AD_GRASS_OPPORTUNITY_HA"].sum(),
        0.0,
    )

    # Opportunity envelopes overlap: they are not a partition of spared land.
    row = screened.iloc[0]
    assert row["ELIGIBLE_FOREST_SPARED_GRASSLAND_HA"] == row["POTENTIAL_SPARED_GRASSLAND_HA"]
    assert row["ELIGIBLE_AD_GRASS_SPARED_GRASSLAND_HA"] == row["POTENTIAL_SPARED_GRASSLAND_HA"]


def test_opportunity_envelope_summary_preserves_spared_total_without_allocating() -> None:
    screened = add_spared_land_opportunity_envelope(_frame())
    summary = summarise_spared_land_opportunity_envelope(screened).set_index("MILESTONE_YEAR")

    assert np.isclose(summary.loc[2030, "POTENTIAL_SPARED_GRASSLAND_HA"], 60.0)
    assert np.isclose(summary.loc[2050, "POTENTIAL_SPARED_GRASSLAND_HA"], 120.0)
    assert int(summary.loc[2050, "EDS_WITH_SPARED_GRASSLAND"]) == 3
    assert int(summary.loc[2050, "EDS_ELIGIBLE_REWETTING"]) == 2
    assert "must not be summed" in summary.loc[2050, "OPPORTUNITY_ENVELOPE_NOTE"]

    # No realised allocation columns are created by the envelope stage.
    assert not any(column.startswith("CUMULATIVE_FOREST_HA") for column in screened.columns)


def test_opportunity_envelope_rejects_negative_spared_land() -> None:
    frame = _frame()
    frame.loc[0, "POTENTIAL_SPARED_GRASSLAND_HA"] = -1.0
    with pytest.raises(ValueError, match="non-negative"):
        add_spared_land_opportunity_envelope(frame)
