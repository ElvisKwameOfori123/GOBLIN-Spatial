"""SC2 evidence handoff after a frozen SC1 cattle/land-release result.

SC2 begins from an immutable ED release row total.  This module attaches the
validated 08B agricultural-capability profile, the baseline-matched LPIS ED
profile, and an optional compact 08C physical-soil profile without changing the
SC1 cattle state or released hectares.

The only hectare partition performed here is the explicit modelling handoff
already adopted for 08B:

    released_Gi(ed) = frozen_release(ed) * 08B_Gi_share(ed)

This is a proportional within-ED partition of already released land.  It is not
an observation of the exact parcels released from livestock production.

08C remains independent physical context.  Its mapped-soil shares are attached
but are not multiplied by release and are not blended with 08B into a synthetic
soil score.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.soil import add_ed_agricultural_soil, canonical_csoed


PHYSICAL_SOIL_SHARE_COLUMNS = (
    "PHYSICAL_SOIL_DEEP_WELL_DRAINED_SHARE",
    "PHYSICAL_SOIL_SHALLOW_WELL_DRAINED_SHARE",
    "PHYSICAL_SOIL_POORLY_DRAINED_SHARE",
    "PHYSICAL_SOIL_POORLY_DRAINED_PEATY_SHARE",
    "PHYSICAL_SOIL_ALLUVIUM_SHARE",
    "PHYSICAL_SOIL_PEAT_SHARE",
    "PHYSICAL_SOIL_MISCELLANEOUS_SHARE",
)


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC2 context missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def read_physical_soil_context(
    source: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Read the compact 08C ED physical-soil contract.

    The table must contain one row per model ED and the seven canonical physical
    soil shares.  Shares describe the mapped physical-soil frame only.  They do
    not claim to be observed grassland-by-soil shares or rewettable hectares.
    """

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source), low_memory=False)
    required = {"CSOED", *PHYSICAL_SOIL_SHARE_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"08C physical-soil context missing columns: {missing}")

    out = frame[["CSOED", *PHYSICAL_SOIL_SHARE_COLUMNS]].copy()
    out["CSOED_CANONICAL"] = out["CSOED"].map(canonical_csoed)
    if out["CSOED_CANONICAL"].eq("").any() or out["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("08C physical-soil context must contain one valid row per CSOED")

    values = []
    for column in PHYSICAL_SOIL_SHARE_COLUMNS:
        numeric = pd.to_numeric(out[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(numeric)).any() or ((numeric < -1e-12) | (numeric > 1.0 + 1e-12)).any():
            raise ValueError(f"{column} must contain finite shares in [0, 1]")
        numeric = np.clip(numeric, 0.0, 1.0)
        out[column] = numeric
        values.append(numeric)
    share_sum = np.sum(np.column_stack(values), axis=1)
    if not np.allclose(share_sum, 1.0, atol=1e-8):
        raise ValueError("08C physical-soil shares must close to one within ED")
    return out


def add_physical_soil_context(
    frame: pd.DataFrame,
    source: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Attach independent 08C physical-soil shares without altering SC1 release."""

    if "CSOED" not in frame.columns:
        raise ValueError("08C attachment requires CSOED")
    physical = read_physical_soil_context(source)
    out = frame.copy()
    original_csoed = out["CSOED"].copy()
    out["_SC2_PHYSICAL_KEY"] = out["CSOED"].map(canonical_csoed)
    attach = physical.drop(columns="CSOED").rename(
        columns={"CSOED_CANONICAL": "_SC2_PHYSICAL_KEY"}
    )
    out = out.merge(
        attach,
        on="_SC2_PHYSICAL_KEY",
        how="left",
        validate="many_to_one",
    )
    if out[list(PHYSICAL_SOIL_SHARE_COLUMNS)].isna().any().any():
        raise ValueError("08C physical-soil context does not cover every SC2 ED")
    out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"] = True
    out["CSOED"] = original_csoed.to_numpy()
    return out.drop(columns="_SC2_PHYSICAL_KEY")


def prepare_sc2_context(
    sc1_ed: pd.DataFrame,
    *,
    agricultural_soil_profile: str | Path | pd.DataFrame,
    lpis_profile: str | Path | pd.DataFrame,
    baseline_year: int,
    physical_soil_context: str | Path | pd.DataFrame | None = None,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Build the policy-neutral SC2 evidence frame from one frozen SC1 endpoint.

    The returned table still contains exactly the same release quantity in every
    ED.  08B partitions that release by G1/G2/G3 agricultural capability.  LPIS
    adds the matching 2020/2025 parcel-management context.  08C, when supplied,
    remains independent mapped physical-soil evidence.
    """

    required = {"CSOED", "County", "ALL_GRASSLAND", release_column}
    missing = sorted(required - set(sc1_ed.columns))
    if missing:
        raise ValueError(f"SC2 context missing frozen SC1 columns: {missing}")
    if sc1_ed["CSOED"].duplicated().any():
        raise ValueError("SC2 endpoint context requires one row per ED")

    release_before = _numeric(sc1_ed, release_column).copy()
    grass = _numeric(sc1_ed, "ALL_GRASSLAND")
    if (release_before < -1e-9).any():
        raise ValueError("frozen SC1 release cannot be negative")
    if (release_before - grass > 1e-7).any():
        raise ValueError("frozen SC1 release exceeds ED ALL_GRASSLAND capacity")
    release_before = np.maximum(release_before, 0.0)

    out = sc1_ed.copy()
    if "GOBLIN_SOIL_G1_SHARE" not in out.columns:
        out = add_ed_agricultural_soil(out, agricultural_soil_profile)

    shares = []
    for group in (1, 2, 3):
        column = f"GOBLIN_SOIL_G{group}_SHARE"
        share = _numeric(out, column)
        if ((share < -1e-12) | (share > 1.0 + 1e-12)).any():
            raise ValueError(f"{column} must lie in [0, 1]")
        share = np.clip(share, 0.0, 1.0)
        shares.append(share)
        out[f"SC2_RELEASED_G{group}_HA"] = release_before * share
    if not np.allclose(np.sum(np.column_stack(shares), axis=1), 1.0, atol=1e-8):
        raise AssertionError("08B G1/G2/G3 shares do not close before SC2 release partition")
    if not np.allclose(
        out[[f"SC2_RELEASED_G{i}_HA" for i in (1, 2, 3)]].sum(axis=1).to_numpy(dtype=float),
        release_before,
        atol=1e-7,
    ):
        raise AssertionError("SC2 08B released-land partition does not close to frozen SC1 release")

    out["SC2_POTENTIAL_RELEASE_HA"] = release_before
    out["SC2_08B_RELEASE_PARTITION_METHOD"] = "ED_08B_SHARE_PROPORTIONAL"

    if "IFS_PEAT_CUTOVER_UAA_SHARE" in out.columns:
        peat_share = pd.to_numeric(
            out["IFS_PEAT_CUTOVER_UAA_SHARE"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(peat_share)
        peat_share = np.where(valid, np.clip(peat_share, 0.0, 1.0), np.nan)
        out["SC2_08B_PEAT_CUTOVER_RELEASE_CONTEXT_HA_PROXY"] = release_before * peat_share
        out["SC2_08B_PEAT_CUTOVER_CONTEXT_AVAILABLE"] = valid

    if "LPIS_GRASS_CONTEXT_AVAILABLE" not in out.columns:
        out = add_ed_lpis_context(
            out,
            lpis_profile,
            baseline_year=int(baseline_year),
        )
    if not (pd.to_numeric(out["LPIS_PROFILE_YEAR"], errors="raise").astype(int) == int(baseline_year)).all():
        raise AssertionError("SC2 LPIS context does not match the selected run baseline year")

    if "LPIS_PEAT_GRASS_SHARE" in out.columns:
        peat_grass = pd.to_numeric(out["LPIS_PEAT_GRASS_SHARE"], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(peat_grass)
        peat_grass = np.where(valid, np.clip(peat_grass, 0.0, 1.0), np.nan)
        out["SC2_LPIS_PEAT_GRASS_RELEASE_CONTEXT_HA_PROXY"] = release_before * peat_grass
        out["SC2_LPIS_PEAT_GRASS_CONTEXT_AVAILABLE"] = valid

    if physical_soil_context is not None:
        out = add_physical_soil_context(out, physical_soil_context)
    else:
        out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"] = False

    release_after = _numeric(out, release_column)
    if not np.array_equal(release_before, release_after):
        raise AssertionError("SC2 context attachment changed the frozen SC1 release vector")
    if not np.allclose(
        pd.to_numeric(out["SC2_POTENTIAL_RELEASE_HA"], errors="raise").to_numpy(dtype=float),
        release_before,
        atol=0.0,
    ):
        raise AssertionError("SC2 potential release no longer equals frozen SC1 release")

    out["SC2_CONTEXT_VERSION"] = "1.0"
    return out
