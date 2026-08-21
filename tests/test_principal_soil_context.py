from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.soil.principal_context import (
    MAP_SG_SHARE_COLUMNS,
    PHYSICAL_AREA_COLUMNS,
    PHYSICAL_SHARE_COLUMNS,
    add_principal_08c_context,
)


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


def test_08c_accepts_direct_and_compound_ed_only() -> None:
    master = pd.DataFrame(
        {
            "CSOED": ["1001/1002", "1003"],
            "County": ["A", "B"],
            "ALL_GRASSLAND": [250.0, 100.0],
        }
    )
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
