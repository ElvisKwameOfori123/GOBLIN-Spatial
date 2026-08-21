from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.soil.principal_context import (
    CLASS_SHARE_COLUMNS,
    GROUP_SHARE_COLUMNS,
    MAP_SG_SHARE_COLUMNS,
    PHYSICAL_AREA_COLUMNS,
    PHYSICAL_SHARE_COLUMNS,
    add_principal_08b_context,
    add_principal_08c_context,
)


def _agricultural_profile() -> pd.DataFrame:
    classes = {
        "1001": (0.30, 0.20, 0.20, 0.10, 0.10, 0.10),
        "1002": (0.20, 0.20, 0.20, 0.20, 0.10, 0.10),
        "1003": (0.10, 0.20, 0.20, 0.20, 0.20, 0.10),
    }
    rows = []
    for ed, shares in classes.items():
        row = {
            "CSOED": ed,
            "SOIL_SOURCE_UAA_HA": 100.0,
            "SOIL_SOURCE_HOLDINGS": 10.0,
        }
        row.update(dict(zip(CLASS_SHARE_COLUMNS, shares, strict=True)))
        row["GOBLIN_SOIL_G1_SHARE"] = shares[0] + shares[1]
        row["GOBLIN_SOIL_G2_SHARE"] = shares[2] + shares[3]
        row["GOBLIN_SOIL_G3_SHARE"] = shares[4] + shares[5]
        rows.append(row)
    return pd.DataFrame(rows)


def _physical_profile() -> pd.DataFrame:
    rows = []
    values = {
        "1001": (40.0, 20.0, 15.0, 10.0, 5.0, 5.0, 5.0),
        "1002": (20.0, 20.0, 20.0, 15.0, 5.0, 15.0, 5.0),
        "1003": (30.0, 10.0, 20.0, 10.0, 10.0, 15.0, 5.0),
    }
    for ed, areas in values.items():
        row = {"CSOED": ed}
        row.update(dict(zip(PHYSICAL_AREA_COLUMNS, areas, strict=True)))
        rows.append(row)
    return pd.DataFrame(rows)


def _master() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CSOED": ["1001/1002", "1003"],
            "County": ["A", "B"],
            "ALL_GRASSLAND": [250.0, 100.0],
        }
    )


def test_08b_accepts_direct_and_compound_ed_and_closes_to_grassland() -> None:
    master = _master()
    original_grass = master["ALL_GRASSLAND"].copy()

    out = add_principal_08b_context(master, _agricultural_profile())

    assert out["SOIL_PROFILE_SOURCE"].tolist() == ["COMPOUND_COMPONENTS", "ED"]
    assert np.array_equal(out["ALL_GRASSLAND"], original_grass)
    assert np.allclose(out[list(CLASS_SHARE_COLUMNS)].sum(axis=1), 1.0)
    assert np.allclose(out[list(GROUP_SHARE_COLUMNS)].sum(axis=1), 1.0)
    assert np.allclose(
        out[[f"SOIL_USE_CLASS_{i}_GRASSLAND_HA" for i in range(1, 7)]].sum(axis=1),
        original_grass,
    )
    assert np.allclose(
        out[[f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in (1, 2, 3)]].sum(axis=1),
        original_grass,
    )


def test_08c_accepts_direct_and_compound_ed_only() -> None:
    master = _master()
    original_grass = master["ALL_GRASSLAND"].copy()

    out = add_principal_08c_context(master, _physical_profile())

    assert out["IFS_MAP_PROFILE_SOURCE"].tolist() == ["COMPOUND_COMPONENTS", "ED"]
    assert np.array_equal(out["ALL_GRASSLAND"], original_grass)
    assert np.allclose(out[list(PHYSICAL_SHARE_COLUMNS)].sum(axis=1), 1.0)
    assert np.allclose(out[list(MAP_SG_SHARE_COLUMNS)].sum(axis=1), 1.0)
    assert out["SOIL_CONTEXT_08C_PRECOMPUTED"].all()
    assert out["SOIL_CONTEXT_08C_ROLE"].eq(
        "INDEPENDENT_PHYSICAL_CONTEXT_NOT_SC1_RELEASE_DRIVER"
    ).all()


def test_08c_refuses_county_or_national_fallback() -> None:
    master = pd.DataFrame(
        {
            "CSOED": ["1001", "9999"],
            "County": ["A", "A"],
            "ALL_GRASSLAND": [100.0, 100.0],
        }
    )

    with pytest.raises(ValueError, match="does not invent county/national fallback soil"):
        add_principal_08c_context(master, _physical_profile())
