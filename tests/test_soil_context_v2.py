"""Regression tests for the compound-aware agricultural soil context."""

import numpy as np
import pandas as pd

from goblin_spatial.soil import (
    add_ed_agricultural_soil,
    build_ed_agricultural_soil_profile,
)


def test_continuous_ifs_peat_share_is_source_uaa_weighted() -> None:
    source = pd.DataFrame(
        {
            "cso_ed": [8045, 8045, 8046, 8046],
            "fsizuaa": [60.0, 40.0, 20.0, 80.0],
            "soil_code_nfs": [1, 5, 2, 6],
            "yc": [24, 14, 20, 18],
            "ifs_soil": ["AminDW", "BktPt", "CUT", "AminPD"],
        }
    )

    profile = build_ed_agricultural_soil_profile(source).set_index("CSOED")
    assert np.isclose(profile.loc[8045, "IFS_PEAT_CUTOVER_UAA_SHARE"], 0.40)
    assert np.isclose(profile.loc[8046, "IFS_PEAT_CUTOVER_UAA_SHARE"], 0.20)


def test_compound_model_ed_uses_components_and_preserves_identifier() -> None:
    source = pd.DataFrame(
        {
            "cso_ed": [8045, 8046, 10008],
            "fsizuaa": [75.0, 25.0, 100.0],
            "soil_code_nfs": [1, 6, 3],
            "yc": [24, 14, 20],
            "ifs_soil": ["AminDW", "CUT", "AminDW"],
        }
    )
    profile = build_ed_agricultural_soil_profile(source)
    master = pd.DataFrame(
        {
            "YEAR": [2020, 2020],
            "CSOED": ["08045/08046", "10008"],
            "County": ["Laois", "Louth"],
            "ALL_GRASSLAND": [1000.0, 500.0],
        }
    )

    result = add_ed_agricultural_soil(master, profile)
    compound = result.loc[result["CSOED"].eq("08045/08046")].iloc[0]

    assert compound["SOIL_PROFILE_SOURCE"] == "COMPOUND_COMPONENTS"
    assert compound["CSOED"] == "08045/08046"
    assert np.isclose(compound["GOBLIN_SOIL_G1_SHARE"], 0.75)
    assert np.isclose(compound["GOBLIN_SOIL_G3_SHARE"], 0.25)
    assert np.isclose(compound["IFS_PEAT_CUTOVER_UAA_SHARE"], 0.25)
    assert np.isclose(
        compound["GOBLIN_SOIL_G1_GRASSLAND_HA"]
        + compound["GOBLIN_SOIL_G2_GRASSLAND_HA"]
        + compound["GOBLIN_SOIL_G3_GRASSLAND_HA"],
        1000.0,
    )
