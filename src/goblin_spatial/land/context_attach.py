"""Attach the frozen 08B subset of the canonical 2020 land context.

The canonical land context is already resolved to the exact 2,857 model EDs.
Its ``SOIL_PROFILE_SOURCE`` values therefore record the validated final 08B
provenance, including the 37 county fallbacks. Principal runtime must preserve
that provenance rather than re-running the source-resolution hierarchy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.land.context import read_land_context_table
from goblin_spatial.soil import canonical_csoed


CLASS_SHARE_COLUMNS = tuple(f"SOIL_USE_CLASS_{i}_SHARE" for i in range(1, 7))
GROUP_SHARE_COLUMNS = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in range(1, 4))
FROZEN_08B_COLUMNS = (
    "SOIL_PROFILE_SOURCE",
    "SOIL_SOURCE_HOLDINGS",
    "SOIL_SOURCE_UAA_HA",
    *CLASS_SHARE_COLUMNS,
    *GROUP_SHARE_COLUMNS,
    "FOREST_YC_WEIGHTED_MEAN",
    "IFS_PEAT_CUTOVER_UAA_SHARE",
)


def add_frozen_08b_context(
    master: pd.DataFrame,
    land_context,
) -> pd.DataFrame:
    """Attach exact model-ED 08B capability and derive grassland capacities."""

    required = {"CSOED", "ALL_GRASSLAND"}
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"frozen 08B attachment missing master columns: {missing}")

    overlap = sorted(set(FROZEN_08B_COLUMNS) & set(master.columns))
    if overlap:
        raise ValueError(
            "frozen 08B fields are already present in the master; refusing an "
            f"ambiguous second attachment: {overlap}"
        )

    context = read_land_context_table(land_context)
    attach = context[["CSOED", *FROZEN_08B_COLUMNS]].copy()
    attach["_LAND_CONTEXT_KEY"] = attach["CSOED"].map(canonical_csoed)
    attach = attach.drop(columns="CSOED")

    out = master.copy()
    out["_LAND_CONTEXT_KEY"] = out["CSOED"].map(canonical_csoed)
    if out["_LAND_CONTEXT_KEY"].eq("").any():
        raise ValueError("master contains blank CSOED keys")

    available = set(attach["_LAND_CONTEXT_KEY"])
    needed = set(out["_LAND_CONTEXT_KEY"])
    missing_keys = sorted(needed - available)
    if missing_keys:
        raise ValueError(
            "frozen land context does not cover the model ED universe; "
            f"missing={len(missing_keys)}, examples={missing_keys[:10]}"
        )

    out = out.merge(
        attach,
        on="_LAND_CONTEXT_KEY",
        how="left",
        validate="many_to_one",
    )

    classes = out[list(CLASS_SHARE_COLUMNS)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    groups = out[list(GROUP_SHARE_COLUMNS)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if not np.allclose(classes.sum(axis=1), 1.0, atol=1e-8):
        raise AssertionError("frozen 08B Class1-6 shares do not close to one")
    if not np.allclose(groups.sum(axis=1), 1.0, atol=1e-8):
        raise AssertionError("frozen 08B G1/G2/G3 shares do not close to one")

    grass = pd.to_numeric(out["ALL_GRASSLAND"], errors="raise").to_numpy(float)
    if (~np.isfinite(grass)).any() or (grass < -1e-10).any():
        raise ValueError("ALL_GRASSLAND must be finite and non-negative")
    grass = np.maximum(grass, 0.0)

    for index in range(6):
        out[f"SOIL_USE_CLASS_{index + 1}_GRASSLAND_HA"] = grass * classes[:, index]
    for index in range(3):
        out[f"GOBLIN_SOIL_G{index + 1}_GRASSLAND_HA"] = grass * groups[:, index]

    if not np.allclose(
        out[[f"SOIL_USE_CLASS_{i}_GRASSLAND_HA" for i in range(1, 7)]].sum(axis=1),
        grass,
        atol=1e-7,
    ):
        raise AssertionError("frozen 08B class capacity does not close to ALL_GRASSLAND")
    if not np.allclose(
        out[[f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in range(1, 4)]].sum(axis=1),
        grass,
        atol=1e-7,
    ):
        raise AssertionError("frozen 08B group capacity does not close to ALL_GRASSLAND")

    source_counts = context["SOIL_PROFILE_SOURCE"].astype(str).value_counts().to_dict()
    if source_counts != {"ED": 2820, "COUNTY_FALLBACK": 37}:
        raise AssertionError(f"frozen 08B provenance changed: {source_counts}")

    out["SOIL_CONTEXT_08B_PRECOMPUTED"] = True
    out["SOIL_CONTEXT_08B_RUNTIME_ROLE"] = "FROZEN_MODEL_ED_CONTROL_NO_RE_RESOLUTION"
    return out.drop(columns="_LAND_CONTEXT_KEY")
