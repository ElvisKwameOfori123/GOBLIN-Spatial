from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.land.sc2_context import (
    PHYSICAL_SOIL_SHARE_COLUMNS,
    prepare_sc2_context,
)


def _sc1() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": [1001, 1002],
            "County": ["A", "B"],
            "ALL_GRASSLAND": [1000.0, 500.0],
            "GOBLIN_RELEASED_GRASSLAND_HA": [300.0, 100.0],
            "SCENARIO_BASELINE_YEAR": [2020, 2020],
        }
    )


def _soil() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": [1001, 1002],
            "SOIL_SOURCE_HOLDINGS": [10, 5],
            "SOIL_SOURCE_UAA_HA": [100.0, 50.0],
            "GOBLIN_SOIL_G1_SHARE": [0.5, 0.2],
            "GOBLIN_SOIL_G2_SHARE": [0.3, 0.5],
            "GOBLIN_SOIL_G3_SHARE": [0.2, 0.3],
            "IFS_PEAT_CUTOVER_UAA_SHARE": [0.10, 0.40],
        }
    )


def _lpis() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LPIS_YEAR": [2020, 2020],
            "CSOED": [1001, 1002],
            "LPIS_CLAIMED_GRASS_HA": [800.0, 400.0],
            "LPIS_ELIGIBLE_GRASS_HA": [750.0, 380.0],
            "LPIS_PEAT_GRASS_HA": [80.0, 100.0],
        }
    )


def _physical() -> pd.DataFrame:
    rows = []
    shares = [0.20, 0.10, 0.20, 0.10, 0.10, 0.20, 0.10]
    for ed in (1001, 1002):
        row = {"CSOED": ed}
        row.update(dict(zip(PHYSICAL_SOIL_SHARE_COLUMNS, shares, strict=True)))
        rows.append(row)
    return pd.DataFrame(rows)


def test_sc2_keeps_release_fixed_and_partitions_08b_within_ed() -> None:
    out = prepare_sc2_context(
        _sc1(),
        agricultural_soil_profile=_soil(),
        lpis_profile=_lpis(),
        baseline_year=2020,
        physical_soil_context=_physical(),
    )

    assert out["GOBLIN_RELEASED_GRASSLAND_HA"].tolist() == [300.0, 100.0]
    assert out["SC2_POTENTIAL_RELEASE_HA"].tolist() == [300.0, 100.0]
    assert np.allclose(
        out[["SC2_RELEASED_G1_HA", "SC2_RELEASED_G2_HA", "SC2_RELEASED_G3_HA"]].sum(axis=1),
        out["GOBLIN_RELEASED_GRASSLAND_HA"],
    )
    assert out.loc[0, "SC2_RELEASED_G1_HA"] == 150.0
    assert out.loc[1, "SC2_RELEASED_G3_HA"] == 30.0
    assert out["LPIS_PROFILE_YEAR"].tolist() == [2020, 2020]
    assert out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"].all()


def test_sc2_peat_quantities_are_explicit_context_proxies_not_release_controls() -> None:
    out = prepare_sc2_context(
        _sc1(),
        agricultural_soil_profile=_soil(),
        lpis_profile=_lpis(),
        baseline_year=2020,
    )

    assert out.loc[0, "SC2_08B_PEAT_CUTOVER_RELEASE_CONTEXT_HA_PROXY"] == 30.0
    assert out.loc[1, "SC2_08B_PEAT_CUTOVER_RELEASE_CONTEXT_HA_PROXY"] == 40.0
    assert out.loc[0, "SC2_LPIS_PEAT_GRASS_RELEASE_CONTEXT_HA_PROXY"] == 30.0
    assert out.loc[1, "SC2_LPIS_PEAT_GRASS_RELEASE_CONTEXT_HA_PROXY"] == 25.0
    assert not out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"].any()
