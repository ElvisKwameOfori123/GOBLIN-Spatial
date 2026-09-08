"""Frozen 2020 Colm physical-soil and LPIS runtime context.

SC1 does not read this module. SC2 reads the frozen ED-level physical-soil and
agricultural-use context only after livestock transition incidence and released
land have been fixed. The context contains two independent evidence layers:

* seven mapped Colm physical-soil area categories;
* LPIS 2020 agricultural-use and management context.

The repository-directory reader verifies checksums and the exact ED universe.
DataFrame inputs remain useful for unit testing and are validated structurally.
No future land use, suitability, opportunity or adoption is inferred here.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

LAND_CONTEXT_YEAR = 2020
LAND_CONTEXT_EXPECTED_EDS = 2857
LAND_CONTEXT_EXPECTED_COLUMNS = 26

COLM_PHYSICAL_FILE = "ED_Colm_Physical_Soil_2020.csv"
LPIS_CONTEXT_FILE = "ED_LPIS_Context_2020.csv"
COLM_PHYSICAL_SHA256 = "9892059c3f67c92d04427ad48220aa7565325df0251be6d53090388046b6bae4"
LPIS_CONTEXT_SHA256 = "c8a6b66c9166ea3da0121def6225698037951d3022af02e5b42f2b54f4f13b2b"

PHYSICAL_AREA_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
)
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


def canonical_csoed(value: object) -> str:
    """Return a compound-aware canonical Electoral Division identifier."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    parts = [part.strip() for part in re.split(r"[/;,]", text) if part.strip()]
    normalised: list[str] = []
    for part in parts:
        part = re.sub(r"\.0$", "", part)
        if part[:1].upper() == "E" and part[1:].isdigit():
            part = part[1:]
        if part.isdigit():
            part = part.lstrip("0") or "0"
        normalised.append(part)
    return "/".join(normalised)


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
    out["_CONTEXT_KEY"] = out[key].map(canonical_csoed)
    if out["_CONTEXT_KEY"].eq("").any() or out["_CONTEXT_KEY"].duplicated().any():
        raise ValueError(f"{label} CSOED keys must be non-empty and unique")
    return out


def validate_colm_lpis_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a merged Colm physical-soil + LPIS context table."""
    required = {"CSOED", *PHYSICAL_AREA_COLUMNS, *REQUIRED_LPIS_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Colm+LPIS runtime context missing columns: {missing}")

    out = frame[["CSOED", *PHYSICAL_AREA_COLUMNS, *REQUIRED_LPIS_COLUMNS]].copy()
    out["CSOED"] = out["CSOED"].map(canonical_csoed)
    if out["CSOED"].eq("").any() or out["CSOED"].duplicated().any():
        raise ValueError("Colm+LPIS runtime context must contain unique ED keys")

    years = pd.to_numeric(out["LPIS_YEAR"], errors="raise").astype(int)
    if not years.eq(LAND_CONTEXT_YEAR).all():
        raise ValueError(f"Colm+LPIS runtime context must use LPIS_YEAR={LAND_CONTEXT_YEAR}")

    physical = out[list(PHYSICAL_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    if (~np.isfinite(physical)).any() or (physical < -1e-9).any():
        raise ValueError("Colm physical-soil areas must be finite and non-negative")
    if (physical.sum(axis=1) <= 0).any():
        raise ValueError("every ED requires positive mapped physical-soil area")

    for column in REQUIRED_LPIS_COLUMNS:
        if column == "LPIS_YEAR":
            continue
        values = pd.to_numeric(out[column], errors="coerce").to_numpy(dtype=float)
        if np.isfinite(values).any() and np.nanmin(values) < -1e-9:
            raise ValueError(f"{column} cannot be negative")

    if len(out.columns) != LAND_CONTEXT_EXPECTED_COLUMNS:
        raise AssertionError(
            f"runtime context column contract changed: expected "
            f"{LAND_CONTEXT_EXPECTED_COLUMNS}, found={len(out.columns)}"
        )
    return out.sort_values("CSOED", kind="stable").reset_index(drop=True)


def read_colm_lpis_context(
    source: str | Path | pd.DataFrame,
    *,
    verify_sha256: bool = True,
) -> pd.DataFrame:
    """Read the frozen two-file Colm+LPIS runtime context."""
    if isinstance(source, pd.DataFrame):
        return validate_colm_lpis_context(source)

    path = Path(source)
    if path.is_dir():
        physical_path = path / COLM_PHYSICAL_FILE
        lpis_path = path / LPIS_CONTEXT_FILE
        missing = [str(item) for item in (physical_path, lpis_path) if not item.is_file()]
        if missing:
            raise FileNotFoundError(
                "Colm+LPIS runtime context is incomplete; missing: " + ", ".join(missing)
            )
        if verify_sha256:
            for label, component, expected in (
                ("Colm physical soil", physical_path, COLM_PHYSICAL_SHA256),
                ("LPIS 2020", lpis_path, LPIS_CONTEXT_SHA256),
            ):
                actual = _sha256(component)
                if actual != expected:
                    raise AssertionError(
                        f"{label} SHA256 mismatch; expected={expected}, actual={actual}"
                    )

        physical = _keyed(pd.read_csv(physical_path, low_memory=False), label="Colm physical soil")
        lpis = _keyed(pd.read_csv(lpis_path, low_memory=False), label="LPIS 2020")
        if set(physical["_CONTEXT_KEY"]) != set(lpis["_CONTEXT_KEY"]):
            raise AssertionError("Colm physical soil and LPIS do not share the same ED universe")

        physical_missing = sorted(set(PHYSICAL_AREA_COLUMNS) - set(physical.columns))
        lpis_missing = sorted(set(REQUIRED_LPIS_COLUMNS) - set(lpis.columns))
        if physical_missing:
            raise ValueError(f"Colm physical context missing columns: {physical_missing}")
        if lpis_missing:
            raise ValueError(f"LPIS context missing columns: {lpis_missing}")

        merged = physical[["_CONTEXT_KEY", *PHYSICAL_AREA_COLUMNS]].merge(
            lpis[["_CONTEXT_KEY", *REQUIRED_LPIS_COLUMNS]],
            on="_CONTEXT_KEY",
            how="inner",
            validate="one_to_one",
        ).rename(columns={"_CONTEXT_KEY": "CSOED"})
        out = validate_colm_lpis_context(merged)
        if len(out) != LAND_CONTEXT_EXPECTED_EDS:
            raise ValueError(
                f"repository runtime context must contain {LAND_CONTEXT_EXPECTED_EDS} EDs; "
                f"found={len(out)}"
            )
        return out

    return validate_colm_lpis_context(pd.read_csv(path, low_memory=False))


def attach_colm_physical_context(frame: pd.DataFrame, physical_context: pd.DataFrame) -> pd.DataFrame:
    """Attach the seven mapped physical-soil categories to model EDs."""
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

    out = left.merge(
        right.drop(columns="CSOED"),
        on="_COLM_PHYSICAL_KEY",
        how="left",
        validate="many_to_one",
    ).drop(columns="_COLM_PHYSICAL_KEY")

    physical = out[list(PHYSICAL_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    if (~np.isfinite(physical)).any() or (physical < -1e-9).any():
        raise ValueError("attached Colm physical areas must be finite and non-negative")
    totals = physical.sum(axis=1)
    if (totals <= 0).any():
        raise ValueError("attached Colm physical context has zero mapped area")

    shares = physical / totals[:, None]
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-10):
        raise AssertionError("Colm physical shares do not close to one")
    for index, column in enumerate(COLM_PHYSICAL_SHARE_COLUMNS):
        out[column] = shares[:, index]

    out["IFS_MAP_AG_SOIL_HA"] = totals
    out["COLM_PHYSICAL_PROFILE_SOURCE"] = "FROZEN_ED_MAPPED_PHYSICAL_SOIL"
    return out
