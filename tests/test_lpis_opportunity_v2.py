"""Tests for LPIS harmonisation and the preferred opportunity screen."""

import numpy as np
import pandas as pd

from goblin_spatial.land.lpis import add_ed_lpis_context, normalise_lpis_records
from goblin_spatial.land.opportunity_v2 import add_ed_land_opportunity_scores_v2


def test_commonage_fraction_does_not_adjust_claimed_area_twice() -> None:
    source = pd.DataFrame(
        {
            "par_lab": ["A", "B"],
            "claim_area": [10.0, 8.0],
            "digitised": [12.0, 9.0],
            "eh_area": [11.0, 8.5],
            "ref_area": [10.2, 8.1],
            "crop": ["Permanent Pasture", "Low Input Peat Grassland"],
            "commonage_ind": ["Y", "N"],
            "commonage_num": [1.0, np.nan],
            "commonage_den": [4.0, np.nan],
            "grasslnd": ["Y", "Y"],
        }
    )
    out = normalise_lpis_records(source, 2025)
    assert np.isclose(out.loc[0, "CLAIMED_AREA_HA"], 10.0)
    assert np.isclose(out.loc[0, "COMMONAGE_FRACTION"], 0.25)
    assert np.isclose(out.loc[0, "SHARE_ELIGIBLE_HA"], 2.75)
    assert np.isclose(out.loc[0, "SHARE_REFERENCE_HA"], 2.55)
    assert out.loc[0, "IS_GRASSLAND"]
    assert out.loc[1, "IS_PEAT_GRASSLAND"]


def test_lpis_profile_attaches_only_selected_baseline_snapshot() -> None:
    scenario = pd.DataFrame(
        {
            "CSOED": ["01003", "08045/08046"],
            "ALL_GRASSLAND": [100.0, 200.0],
        }
    )
    profile = pd.DataFrame(
        {
            "LPIS_YEAR": [2020, 2020, 2025, 2025],
            "CSOED": ["1003", "8045/8046", "01003", "08045/08046"],
            "LPIS_CLAIMED_GRASS_HA": [80.0, 150.0, 90.0, 160.0],
            "LPIS_ELIGIBLE_GRASS_HA": [85.0, 155.0, 95.0, 165.0],
            "LPIS_PERMANENT_PASTURE_HA": [40.0, 75.0, 45.0, 80.0],
            "LPIS_LOW_INPUT_GRASS_HA": [20.0, 30.0, 18.0, 32.0],
            "LPIS_PEAT_GRASS_HA": [8.0, 15.0, 9.0, 16.0],
            "LPIS_RIPARIAN_GRASS_HA": [4.0, 5.0, 5.0, 6.0],
        }
    )

    out = add_ed_lpis_context(scenario, profile, baseline_year=2025)
    assert out["LPIS_PROFILE_YEAR"].eq(2025).all()
    assert np.isclose(out.loc[0, "LPIS_CLAIMED_GRASS_HA"], 90.0)
    assert np.isclose(out.loc[1, "LPIS_CLAIMED_GRASS_HA"], 160.0)
    assert np.isclose(out.loc[0, "LPIS_PEAT_GRASS_SHARE"], 0.10)
    assert scenario["ALL_GRASSLAND"].tolist() == [100.0, 200.0]
    assert out["ALL_GRASSLAND"].tolist() == [100.0, 200.0]


def test_opportunity_v2_uses_sensitive_lpis_context_without_nature_floor() -> None:
    frame = pd.DataFrame(
        {
            "CSOED": ["A", "B"],
            "GOBLIN_SOIL_G1_SHARE": [1.0, 1.0],
            "GOBLIN_SOIL_G2_SHARE": [0.0, 0.0],
            "GOBLIN_SOIL_G3_SHARE": [0.0, 0.0],
            "FOREST_YC_WEIGHTED_MEAN": [24.0, 24.0],
            "IFS_PEAT_CUTOVER_UAA_SHARE": [0.0, 0.0],
            "LPIS_GRASS_CONTEXT_AVAILABLE": [True, True],
            "LPIS_LOW_INPUT_GRASS_SHARE": [0.0, 0.5],
            "LPIS_PEAT_GRASS_SHARE": [0.0, 0.2],
            "LPIS_RIPARIAN_GRASS_SHARE": [0.0, 0.1],
        }
    )
    out = add_ed_land_opportunity_scores_v2(frame)

    # Productive ED remains high for forestry/biomass and gets no arbitrary
    # nature floor when there is no restoration evidence or soil constraint.
    assert np.isclose(out.loc[0, "FORESTRY_OPPORTUNITY_SCORE"], 1.0)
    assert np.isclose(out.loc[0, "AD_GRASS_OPPORTUNITY_SCORE"], 1.0)
    assert np.isclose(out.loc[0, "NATURE_OPPORTUNITY_SCORE"], 0.0)

    # Sensitive grass context reduces conversion-oriented uses and raises nature.
    assert np.isclose(out.loc[1, "LPIS_SENSITIVE_GRASS_SHARE"], 0.8)
    assert np.isclose(out.loc[1, "AD_GRASS_OPPORTUNITY_SCORE"], 0.2)
    assert np.isclose(out.loc[1, "REWETTING_OPPORTUNITY_SCORE"], 0.2)
    assert np.isclose(out.loc[1, "NATURE_OPPORTUNITY_SCORE"], 0.5)
    assert out["OPPORTUNITY_SCREEN_VERSION"].eq("2.0").all()
