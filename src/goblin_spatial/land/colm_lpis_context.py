"""Runtime reader and direct attachment for Colm physical soil + LPIS evidence.

The Colm-direct architecture does not require the legacy 08B capability file.
This module loads only the frozen 08C physical-soil component and LPIS 2020
component from the repository land-context directory, verifies their published
checksums, normalises ED identifiers and merges them one-to-one.

The direct physical attachment deliberately retains Colm's seven mapped physical
categories. It does not derive synthetic SG1/SG2/SG3 groups, a farmed-peat
fraction, or any land-use suitability class. Those transformations belonged to
the legacy dual-soil implementation and are outside the Colm-direct core.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.context import (
    LAND_CONTEXT_COMPONENT_FILES,
    LAND_CONTEXT_COMPONENT_SHA256,
    LAND_CONTEXT_YEAR,
    PHYSICAL_AREA_COLUMNS,
)
from goblin_spatial.soil.overlay import canonical_csoed


COLM_PHYSICAL_SHARE_COLUMNS = tuple(
    column.replace("_HA", "_SHARE") for column in PHYSICAL_AREA_COLUMNS
)

REQUIRED_LPIS_COLUMNS = (
    "LPIS_YEAR",
    "LPIS_CLAIMED_AG_HA",
    "LPIS_ELIGIBLE_AG_HA",
    "LPIS_SPATIAL_FOOTPRINT_HA",
    "LPIS_CLAIMED_GRASS_HA",
    "LPIS_ELIGIBLE_GRASS_HA",
    "LPIS_PERMANENT_PASTURE_HA",
    "LPIS_LOW_INPUT_GRASS_HA",
    "LPIS_TEMPORARY_GRASS_HA",
    "LPIS_HAY_MEADOW_HA",
    "LPIS_OTHER_GRASS_HA",
    "LPIS_COMMONAGE_GRASS_HA",
    "LPIS_ANC_GRASS_HA",
    "LPIS_ENV_SCHEME_GRASS_HA",
    "LPIS_ORGANIC_GRASS_HA",
    "LPIS_BOG_PEAT_CONTEXT_HA",
    "LPIS_HABITAT_CONTEXT_HA",
    "LPIS_FORESTRY_CONTEXT_HA",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _keyed(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    key = "CSOED_CANONICAL" if "CSOED_CANONICAL" in frame.columns else "CSOED"
    if key not in frame.columns:
        raise ValueError(f"{label} missing CSOED join key")
    out = frame.copy()
    out["_COLM_LPIS_KEY"] = out[key].map(canonical_csoed)
    if out["_COLM_LPIS_KEY"].eq("").any() or out["_COLM_LPIS_KEY"].duplicated().any():
        raise ValueError(f"{label} CSOED keys must be non-empty and unique")
    return out


def _validate(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"CSOED", *PHYSICAL_AREA_COLUMNS, *REQUIRED_LPIS_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Colm+LPIS runtime context missing columns: {missing}")
    out = frame.copy()
    out["CSOED"] = out["CSOED"].map(canonical_csoed)
    if out["CSOED"].eq("").any() or out["CSOED"].duplicated().any():
        raise ValueError("Colm+LPIS runtime context must contain unique ED keys")

    years = pd.to_numeric(out["LPIS_YEAR"], errors="raise").astype(int)
    if not years.eq(LAND_CONTEXT_YEAR).all():
        raise ValueError("Colm+LPIS runtime context must use LPIS_YEAR=2020")

    physical = out[list(PHYSICAL_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(float)
    if (~np.isfinite(physical)).any() or (physical < -1e-9).any():
        raise ValueError("Colm physical-soil areas must be finite and non-negative")
    if (physical.sum(axis=1) <= 0).any():
        raise ValueError("every ED requires positive Colm mapped physical-soil area")

    for column in REQUIRED_LPIS_COLUMNS:
        if column == "LPIS_YEAR":
            continue
        values = pd.to_numeric(out[column], errors="coerce").to_numpy(float)
        if np.isfinite(values).any() and np.nanmin(values) < -1e-9:
            raise ValueError(f"{column} cannot be negative")
    return out.sort_values("CSOED", kind="stable").reset_index(drop=True)


def read_colm_lpis_context(
    source: str | Path | pd.DataFrame,
    *,
    verify_sha256: bool = True,
) -> pd.DataFrame:
    """Read only Colm physical soil and LPIS context, with no 08B dependency."""

    if isinstance(source, pd.DataFrame):
        return _validate(source)

    path = Path(source)
    if path.is_dir():
        physical_path = path / LAND_CONTEXT_COMPONENT_FILES["08C"]
        lpis_path = path / LAND_CONTEXT_COMPONENT_FILES["LPIS_2020"]
        missing = [str(item) for item in (physical_path, lpis_path) if not item.is_file()]
        if missing:
            raise FileNotFoundError(
                "Colm-direct runtime context is incomplete; missing: " + ", ".join(missing)
            )
        if verify_sha256:
            for label, component in (("08C", physical_path), ("LPIS_2020", lpis_path)):
                expected = LAND_CONTEXT_COMPONENT_SHA256[label]
                actual = _sha256(component)
                if actual != expected:
                    raise AssertionError(
                        f"{label} context SHA256 mismatch; expected={expected}, actual={actual}"
                    )

        physical = _keyed(pd.read_csv(physical_path, low_memory=False), label="Colm 08C")
        lpis = _keyed(pd.read_csv(lpis_path, low_memory=False), label="LPIS 2020")
        if set(physical["_COLM_LPIS_KEY"]) != set(lpis["_COLM_LPIS_KEY"]):
            raise AssertionError("Colm physical soil and LPIS do not share the same ED universe")

        physical_missing = sorted(set(PHYSICAL_AREA_COLUMNS) - set(physical.columns))
        lpis_missing = sorted(set(REQUIRED_LPIS_COLUMNS) - set(lpis.columns))
        if physical_missing:
            raise ValueError(f"Colm physical context missing columns: {physical_missing}")
        if lpis_missing:
            raise ValueError(f"LPIS context missing columns: {lpis_missing}")

        merged = physical[["_COLM_LPIS_KEY", *PHYSICAL_AREA_COLUMNS]].merge(
            lpis[["_COLM_LPIS_KEY", *REQUIRED_LPIS_COLUMNS]],
            on="_COLM_LPIS_KEY",
            how="inner",
            validate="one_to_one",
        )
        merged = merged.rename(columns={"_COLM_LPIS_KEY": "CSOED"})
        return _validate(merged)

    frame = pd.read_csv(path, low_memory=False)
    # A merged legacy 40-column context is accepted for compatibility, but only
    # the Colm physical and LPIS columns are retained.
    key = "CSOED_CANONICAL" if "CSOED_CANONICAL" in frame.columns else "CSOED"
    if key not in frame.columns:
        raise ValueError("Colm+LPIS context file missing CSOED")
    frame = frame.rename(columns={key: "CSOED"}) if key != "CSOED" else frame
    keep = ["CSOED", *PHYSICAL_AREA_COLUMNS, *REQUIRED_LPIS_COLUMNS]
    missing = sorted(set(keep) - set(frame.columns))
    if missing:
        raise ValueError(f"Colm+LPIS context file missing columns: {missing}")
    return _validate(frame[keep].copy())


def attach_colm_physical_context(
    frame: pd.DataFrame,
    physical_context: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the seven Colm physical categories directly to model EDs.

    The input is already a frozen ED-level mapped physical-soil profile. The
    attachment therefore performs only an exact ED join and area-to-share
    conversion. It intentionally does not call the legacy 08C helper because
    that helper also derives synthetic three-group soil classes and a farmed-peat
    assumption that are not part of the Colm-direct architecture.
    """

    if "CSOED" not in frame.columns:
        raise ValueError("Colm physical attachment requires CSOED")
    missing = sorted(set(("CSOED", *PHYSICAL_AREA_COLUMNS)) - set(physical_context.columns))
    if missing:
        raise ValueError(f"Colm physical attachment missing columns: {missing}")

    left = frame.copy()
    left["_COLM_PHYSICAL_KEY"] = left["CSOED"].map(canonical_csoed)
    if left["_COLM_PHYSICAL_KEY"].eq("").any():
        raise ValueError("model frame contains blank ED keys")

    right = physical_context[["CSOED", *PHYSICAL_AREA_COLUMNS]].copy()
    right["_COLM_PHYSICAL_KEY"] = right["CSOED"].map(canonical_csoed)
    if right["_COLM_PHYSICAL_KEY"].eq("").any() or right["_COLM_PHYSICAL_KEY"].duplicated().any():
        raise ValueError("Colm physical context requires unique non-empty ED keys")

    missing_eds = sorted(set(left["_COLM_PHYSICAL_KEY"]) - set(right["_COLM_PHYSICAL_KEY"]))
    if missing_eds:
        raise ValueError(
            f"Colm physical context is missing {len(missing_eds)} model EDs; "
            f"examples={missing_eds[:10]}"
        )

    attach = right.drop(columns="CSOED")
    out = left.merge(
        attach,
        on="_COLM_PHYSICAL_KEY",
        how="left",
        validate="many_to_one",
    ).drop(columns="_COLM_PHYSICAL_KEY")

    physical = out[list(PHYSICAL_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(float)
    if (~np.isfinite(physical)).any() or (physical < -1e-9).any():
        raise ValueError("attached Colm physical areas must be finite and non-negative")
    totals = physical.sum(axis=1)
    if (totals <= 0).any():
        raise ValueError("attached Colm physical context has zero mapped area")

    shares = physical / totals[:, None]
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-10):
        raise AssertionError("direct Colm physical shares do not close to one")
    for index, column in enumerate(COLM_PHYSICAL_SHARE_COLUMNS):
        out[column] = shares[:, index]

    out["IFS_MAP_AG_SOIL_HA"] = totals
    out["COLM_PHYSICAL_PROFILE_SOURCE"] = "FROZEN_ED_MAPPED_PHYSICAL_SOIL"
    out["COLM_PHYSICAL_CONTEXT_ROLE"] = "SEVEN_CATEGORY_DIRECT_NO_SYNTHETIC_SOIL_GROUPS"
    out["COLM_PHYSICAL_SYNTHETIC_SG_USED"] = False
    out["COLM_PHYSICAL_FARMED_PEAT_ASSUMPTION_USED"] = False
    return out
