"""Canonical Stage-1 adapter for Colm's mapped soil evidence.

This module deliberately stops before any G1/G2/G3 capability classification.
Its only scientific job is to take the direct ``ed_soil_shares.csv`` evidence
from Colm's soil-group package, validate it, and resolve it onto the exact
GOBLIN-Spatial model ED universe without inventing county or national fallback
soil.

The source physical categories are retained as areas and shares. Agricultural
capability is a separate, later modelling transformation and must not be folded
into this source-ingestion step.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .overlay import canonical_csoed


COLM_ED_SOIL_VERSION = "1.0.0"
COLM_ZIP_MEMBER_BASENAME = "ed_soil_shares.csv"

COLM_PHYSICAL_AREA_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
)
COLM_PHYSICAL_SHARE_COLUMNS = tuple(
    column.replace("_HA", "_SHARE") for column in COLM_PHYSICAL_AREA_COLUMNS
)

_OPTIONAL_SOURCE_COLUMNS = (
    "COUNTYNAME",
    "IFS_MAP_PARENT_MATERIAL_DOM",
    "IFS_MAP_SOURCE",
)


def read_colm_ed_soil_source(source) -> pd.DataFrame:
    """Read Colm's direct ED soil table from a DataFrame, CSV, or package ZIP."""

    if isinstance(source, pd.DataFrame):
        return source.copy()

    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Colm soil source not found: {path}")

    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            matches = [
                name
                for name in archive.namelist()
                if PurePosixPath(name).name == COLM_ZIP_MEMBER_BASENAME
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Colm soil package must contain exactly one "
                    f"{COLM_ZIP_MEMBER_BASENAME}; found={matches}"
                )
            with archive.open(matches[0]) as handle:
                return pd.read_csv(handle, low_memory=False)

    return pd.read_csv(path, low_memory=False)


def prepare_colm_ed_soil_source(source) -> pd.DataFrame:
    """Validate and standardise direct Colm ED soil evidence only.

    No capability group is derived here. The returned table contains the seven
    mapped physical-soil area categories, their area shares, source provenance,
    and an explicit marker that G1/G2/G3 classification has not yet been done.
    """

    frame = read_colm_ed_soil_source(source)
    required = {"CSOED", *COLM_PHYSICAL_AREA_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Colm ED soil source missing columns: {missing}")

    out = frame.copy()
    out["CSOED_CANONICAL"] = out["CSOED"].map(canonical_csoed)
    if out["CSOED_CANONICAL"].eq("").any():
        raise ValueError("Colm ED soil source contains blank CSOED keys")
    if out["CSOED_CANONICAL"].duplicated().any():
        bad = (
            out.loc[
                out["CSOED_CANONICAL"].duplicated(keep=False),
                "CSOED_CANONICAL",
            ]
            .astype(str)
            .unique()
            .tolist()[:10]
        )
        raise ValueError(f"Colm ED soil source contains duplicate ED keys: {bad}")

    areas = out[list(COLM_PHYSICAL_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    if (~np.isfinite(areas)).any():
        raise ValueError("Colm ED soil areas must be finite")
    if (areas < -1e-10).any():
        raise ValueError("Colm ED soil areas must be non-negative")
    areas = np.maximum(areas, 0.0)

    mapped_total = areas.sum(axis=1)
    if (mapped_total <= 0).any():
        bad = out.loc[mapped_total <= 0, "CSOED"].astype(str).tolist()[:10]
        raise ValueError(
            f"Colm ED soil source has zero mapped soil area for EDs: {bad}"
        )

    for index, column in enumerate(COLM_PHYSICAL_AREA_COLUMNS):
        out[column] = areas[:, index]

    if "IFS_MAP_AG_SOIL_HA" in out.columns:
        supplied_total = pd.to_numeric(
            out["IFS_MAP_AG_SOIL_HA"], errors="coerce"
        ).to_numpy(dtype=float)
        comparable = np.isfinite(supplied_total)
        if comparable.any() and not np.allclose(
            supplied_total[comparable],
            mapped_total[comparable],
            rtol=0.0,
            atol=1e-6,
        ):
            raise AssertionError(
                "Colm IFS_MAP_AG_SOIL_HA does not equal the sum of physical areas"
            )
    out["IFS_MAP_AG_SOIL_HA"] = mapped_total

    for index, column in enumerate(COLM_PHYSICAL_SHARE_COLUMNS):
        calculated = areas[:, index] / mapped_total
        if column in frame.columns:
            supplied = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
            comparable = np.isfinite(supplied)
            if comparable.any() and not np.allclose(
                supplied[comparable],
                calculated[comparable],
                rtol=0.0,
                atol=1e-8,
            ):
                raise AssertionError(
                    f"Colm {column} is inconsistent with the source areas"
                )
        out[column] = calculated

    shares = out[list(COLM_PHYSICAL_SHARE_COLUMNS)].to_numpy(dtype=float)
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-10):
        raise AssertionError("Colm ED physical-soil shares do not close to one")

    keep = [
        "CSOED",
        "CSOED_CANONICAL",
        *[column for column in _OPTIONAL_SOURCE_COLUMNS if column in out.columns],
        "IFS_MAP_AG_SOIL_HA",
        *COLM_PHYSICAL_AREA_COLUMNS,
        *COLM_PHYSICAL_SHARE_COLUMNS,
    ]
    result = out[keep].copy()
    result["COLM_SOIL_SOURCE"] = "soil-group-package/ed_soil_shares.csv"
    result["COLM_SOIL_ED_ADAPTER_VERSION"] = COLM_ED_SOIL_VERSION
    result["COLM_G1_G2_G3_STATUS"] = "NOT_DERIVED_STAGE_1"
    return result


def _aggregate_component_areas(block: pd.DataFrame) -> dict[str, float]:
    row = {
        column: float(pd.to_numeric(block[column], errors="raise").sum())
        for column in COLM_PHYSICAL_AREA_COLUMNS
    }
    total = float(sum(row.values()))
    if total <= 0:
        raise ValueError("compound Colm ED aggregation has zero mapped soil area")
    row["IFS_MAP_AG_SOIL_HA"] = total
    for area_column, share_column in zip(
        COLM_PHYSICAL_AREA_COLUMNS,
        COLM_PHYSICAL_SHARE_COLUMNS,
        strict=True,
    ):
        row[share_column] = row[area_column] / total
    return row


def build_colm_model_ed_soil_profile(model: pd.DataFrame, source) -> pd.DataFrame:
    """Resolve direct Colm soil evidence onto the exact model ED universe.

    Direct model ED matches are retained. A compound model ED may be rebuilt only
    when every component ED is present in Colm's source. Missing spatial evidence
    is an ED-bridge/data problem and is never replaced with county or national
    average soil.
    """

    if "CSOED" not in model.columns:
        raise ValueError("model ED frame requires CSOED")

    model_keys = model[["CSOED"]].drop_duplicates().copy()
    model_keys["CSOED_CANONICAL"] = model_keys["CSOED"].map(canonical_csoed)
    if model_keys["CSOED_CANONICAL"].eq("").any():
        raise ValueError("model ED frame contains blank CSOED keys")
    if model_keys["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("model ED frame must contain unique canonical CSOED keys")

    prepared = prepare_colm_ed_soil_source(source)
    by_key = prepared.set_index("CSOED_CANONICAL", drop=False)

    rows: list[dict[str, object]] = []
    unresolved: list[tuple[object, str]] = []

    for original, key in model_keys[["CSOED", "CSOED_CANONICAL"]].itertuples(
        index=False, name=None
    ):
        if key in by_key.index:
            source_row = by_key.loc[key]
            record: dict[str, object] = {
                "IFS_MAP_AG_SOIL_HA": float(source_row["IFS_MAP_AG_SOIL_HA"]),
                **{
                    column: float(source_row[column])
                    for column in (
                        *COLM_PHYSICAL_AREA_COLUMNS,
                        *COLM_PHYSICAL_SHARE_COLUMNS,
                    )
                },
                "COLM_SOIL_PROFILE_SOURCE": "ED",
                "COLM_SOURCE_COMPONENTS": key,
            }
            for column in ("COUNTYNAME", "IFS_MAP_PARENT_MATERIAL_DOM"):
                if column in prepared.columns:
                    record[column] = source_row[column]
        else:
            parts = [part for part in key.split("/") if part]
            if len(parts) > 1 and all(part in by_key.index for part in parts):
                block = by_key.loc[parts].copy()
                if isinstance(block, pd.Series):
                    block = block.to_frame().T
                record = _aggregate_component_areas(block)
                record["COLM_SOIL_PROFILE_SOURCE"] = "COMPOUND_COMPONENTS"
                record["COLM_SOURCE_COMPONENTS"] = ";".join(parts)
                if "COUNTYNAME" in prepared.columns:
                    counties = sorted(
                        block["COUNTYNAME"].dropna().astype(str).unique().tolist()
                    )
                    record["COUNTYNAME"] = ";".join(counties)
                if "IFS_MAP_PARENT_MATERIAL_DOM" in prepared.columns:
                    record["IFS_MAP_PARENT_MATERIAL_DOM"] = pd.NA
            else:
                unresolved.append((original, key))
                continue

        record["CSOED"] = original
        record["CSOED_CANONICAL"] = key
        record["COLM_SOIL_SOURCE"] = "soil-group-package/ed_soil_shares.csv"
        record["COLM_SOIL_ED_ADAPTER_VERSION"] = COLM_ED_SOIL_VERSION
        record["COLM_G1_G2_G3_STATUS"] = "NOT_DERIVED_STAGE_1"
        rows.append(record)

    if unresolved:
        examples = "; ".join(
            f"{original!r}->{key}" for original, key in unresolved[:10]
        )
        raise ValueError(
            f"{len(unresolved)} model EDs have no direct Colm soil record or "
            "complete compound components. No county/national fallback is "
            f"permitted. Examples: {examples}"
        )

    result = pd.DataFrame(rows)
    if len(result) != len(model_keys):
        raise AssertionError("Colm ED adapter did not create one profile per model ED")
    if result["CSOED_CANONICAL"].duplicated().any():
        raise AssertionError("Colm ED adapter produced duplicate model ED keys")

    shares = result[list(COLM_PHYSICAL_SHARE_COLUMNS)].to_numpy(dtype=float)
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-10):
        raise AssertionError("Colm model-ED physical-soil shares do not close to one")

    return result


def colm_ed_soil_diagnostics(profile: pd.DataFrame) -> dict[str, object]:
    """Return compact QA diagnostics for a completed Stage-1 ED soil profile."""

    required = {
        "CSOED",
        "IFS_MAP_AG_SOIL_HA",
        *COLM_PHYSICAL_AREA_COLUMNS,
        *COLM_PHYSICAL_SHARE_COLUMNS,
    }
    missing = sorted(required - set(profile.columns))
    if missing:
        raise ValueError(f"Colm ED profile missing diagnostic columns: {missing}")

    shares = profile[list(COLM_PHYSICAL_SHARE_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    profile_source = profile.get(
        "COLM_SOIL_PROFILE_SOURCE", pd.Series(index=profile.index, dtype="string")
    ).astype("string")

    return {
        "rows": int(len(profile)),
        "mapped_soil_ha": float(
            pd.to_numeric(profile["IFS_MAP_AG_SOIL_HA"], errors="raise").sum()
        ),
        "physical_share_closure_max_abs": float(
            np.max(np.abs(shares.sum(axis=1) - 1.0))
        ),
        "direct_ed_profiles": int(profile_source.eq("ED").sum()),
        "compound_profiles": int(profile_source.eq("COMPOUND_COMPONENTS").sum()),
        "grouping_status": sorted(
            profile.get(
                "COLM_G1_G2_G3_STATUS",
                pd.Series(index=profile.index, dtype="string"),
            )
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
    }
