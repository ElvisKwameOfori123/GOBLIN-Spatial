"""Memory-bounded GeoParquet reader for the LPIS-to-ED bridge.

The frozen production path uses the corrected 2020-v2 LPIS derivative and the
validated 2025-v1 derivative pinned in ``LPIS_SOURCE_PINS.yaml``. Both current
sources are expected to carry complete commonage fractions. The reader also
retains a conservative legacy fallback for an explicitly supplied 2020-v1 file:
claimed area remains usable, while share-adjusted eligible/digitised/reference
diagnostics are flagged incomplete rather than inventing an ownership share.

The two published derivatives use a few different semantic flag names. Those
source names are harmonised here before the shared LPIS normaliser is called so
the compact ED control preserves forestry context in both snapshots without
modifying the frozen source files. The corrected 2020 ``IS_PERMANENT_GRASS``
flag is intentionally not copied directly because it is broader than the
mutually exclusive core permanent-pasture class and overlaps low-input grass.
For that snapshot the disjoint permanent-pasture flag is reconstructed from the
published ``LAND_USE_GROUP`` category instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely

from goblin_spatial.soil.overlay import canonical_csoed
from .lpis import LPIS_PROFILE_AREA_COLUMNS
from .lpis_spatial import build_ed_lpis_profile


_PUBLISHED_SEMANTIC_ALIASES = {
    # Corrected 2020-v2 source name.
    "IS_FORESTRY_CONTEXT": "IS_FORESTRY_EXISTING",
    # Validated 2025-v1 source names.
    "IS_FORESTRY_ELIGIBLE_2025": "IS_FORESTRY_ELIGIBLE_SOURCE",
    "IS_FORESTRY_INELIGIBLE_2025": "IS_FORESTRY_INELIGIBLE_SOURCE",
}


def _harmonise_published_semantic_aliases(
    frame: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Map snapshot-specific published fields to the shared LPIS contract.

    Existing canonical columns always win. For corrected 2020 data, the source
    boolean ``IS_PERMANENT_GRASS`` is deliberately ignored because it includes
    low-input grass. ``LAND_USE_GROUP == GRASS_PERMANENT`` is the disjoint
    published category used to construct ``IS_PERMANENT_PASTURE``.
    """

    out = frame.copy()
    for source, target in _PUBLISHED_SEMANTIC_ALIASES.items():
        if target not in out.columns and source in out.columns:
            out[target] = out[source]

    if "IS_PERMANENT_PASTURE" not in out.columns and "LAND_USE_GROUP" in out.columns:
        groups = out["LAND_USE_GROUP"].astype("string").str.strip().str.upper()
        out["IS_PERMANENT_PASTURE"] = groups.isin(
            {"GRASS_PERMANENT", "PERMANENT_PASTURE"}
        ).fillna(False)

    return out


def _geometry_column(parquet: pq.ParquetFile) -> str:
    metadata = parquet.schema_arrow.metadata or {}
    raw = metadata.get(b"geo")
    if raw:
        try:
            name = json.loads(raw.decode("utf-8")).get("primary_column")
            if name in parquet.schema_arrow.names:
                return str(name)
        except Exception:
            pass
    if "geometry" in parquet.schema_arrow.names:
        return "geometry"
    raise ValueError("GeoParquet has no detectable geometry column")


def _batch_to_gdf(batch, geometry_column: str, crs: str) -> gpd.GeoDataFrame:
    frame = batch.to_pandas()
    values = frame.pop(geometry_column).to_numpy()
    geometry = shapely.from_wkb(values)
    return gpd.GeoDataFrame(frame, geometry=geometry, crs=crs)


def _first_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    lookup = {str(column).lower(): column for column in frame.columns}
    for alias in aliases:
        found = lookup.get(alias.lower())
        if found is not None:
            return found
    return None


def _bool_values(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.astype("string").str.strip().str.upper()
    return text.isin({"Y", "YES", "TRUE", "T", "1"}).fillna(False)


def _prepare_legacy_commonage(
    frame: gpd.GeoDataFrame,
    *,
    year: int,
) -> tuple[gpd.GeoDataFrame, int]:
    """Recover commonage fractions where possible and flag legacy 2020-v1 gaps."""

    out = frame.copy()
    common_col = _first_column(out, ("IS_COMMONAGE", "COM_IND", "commonage_ind"))
    fraction_col = _first_column(
        out, ("COMMONAGE_FRACTION", "COMMONAGE_SHARE", "COM_SHARE")
    )
    numerator_col = _first_column(
        out,
        (
            "COMMONAGE_NUMERATOR",
            "COMMONAGE_NUM",
            "COM_NUMERATOR",
            "COM_NUM",
            "commonage_num",
        ),
    )
    denominator_col = _first_column(
        out,
        (
            "COMMONAGE_DENOMINATOR",
            "COMMONAGE_DEN",
            "COM_DENOMINATOR",
            "COM_DEN",
            "commonage_den",
        ),
    )

    if common_col is not None:
        commonage = _bool_values(out[common_col])
    elif numerator_col is not None and denominator_col is not None:
        numerator = pd.to_numeric(out[numerator_col], errors="coerce")
        denominator = pd.to_numeric(out[denominator_col], errors="coerce")
        commonage = numerator.notna() & denominator.gt(0)
    else:
        commonage = pd.Series(False, index=out.index, dtype=bool)

    if fraction_col is not None:
        fraction = pd.to_numeric(out[fraction_col], errors="coerce").astype(float)
    else:
        fraction = pd.Series(np.nan, index=out.index, dtype=float)

    if numerator_col is not None and denominator_col is not None:
        numerator = pd.to_numeric(out[numerator_col], errors="coerce").astype(float)
        denominator = pd.to_numeric(out[denominator_col], errors="coerce").astype(float)
        derive = commonage & fraction.isna() & denominator.gt(0)
        fraction.loc[derive] = numerator.loc[derive] / denominator.loc[derive]

    unknown = commonage & (
        fraction.isna()
        | ~np.isfinite(fraction)
        | fraction.le(0.0)
        | fraction.gt(1.0 + 1e-12)
    )
    missing = int(unknown.sum())

    if missing == 0:
        if fraction_col is None and commonage.any():
            out["COMMONAGE_FRACTION"] = fraction
        return out, 0

    if int(year) != 2020:
        # Never relax the validated 2025 commonage contract.
        return out, missing

    # Technical sentinel only: adjusted-area diagnostics for these rows are set
    # to zero/unavailable below, so 1.0 is never interpreted as ownership.
    fraction.loc[unknown] = 1.0
    out["COMMONAGE_FRACTION"] = fraction

    for column in ("SHARE_DIGITISED_HA", "SHARE_ELIGIBLE_HA"):
        if column not in out.columns:
            out[column] = np.nan
        out.loc[unknown, column] = 0.0
    if "SHARE_REFERENCE_HA" not in out.columns:
        out["SHARE_REFERENCE_HA"] = np.nan
    out.loc[unknown, "SHARE_REFERENCE_HA"] = np.nan

    return out, missing


def build_ed_lpis_profile_from_parquet(
    path: str | Path,
    ed_gdf: gpd.GeoDataFrame,
    baseline: pd.DataFrame,
    *,
    year: int,
    batch_size: int = 50_000,
    source_crs: str = "EPSG:2157",
) -> pd.DataFrame:
    """Stream one LPIS snapshot and aggregate it to the exact model ED universe."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    parquet = pq.ParquetFile(path)
    geometry_column = _geometry_column(parquet)
    partials: list[pd.DataFrame] = []
    rows_seen = 0
    missing_commonage_total = 0
    numeric_columns = [
        *LPIS_PROFILE_AREA_COLUMNS,
        "LPIS_INTERSECTION_GEOMETRY_HA",
        "LPIS_SOURCE_RECORDS_INTERSECTING_ED",
        "LPIS_GRASS_SOURCE_RECORDS_INTERSECTING_ED",
    ]

    print(f"LPIS {year} GeoParquet columns: {', '.join(parquet.schema_arrow.names)}")

    for number, batch in enumerate(parquet.iter_batches(batch_size=batch_size), start=1):
        gdf = _batch_to_gdf(batch, geometry_column, source_crs)
        gdf = _harmonise_published_semantic_aliases(gdf)
        rows_seen += len(gdf)
        gdf, missing_commonage = _prepare_legacy_commonage(gdf, year=int(year))
        missing_commonage_total += missing_commonage
        if missing_commonage and int(year) != 2020:
            raise ValueError(
                f"LPIS {year} has {missing_commonage:,} commonage rows in batch {number} "
                "without a usable ownership fraction"
            )

        profile = build_ed_lpis_profile(
            gdf,
            ed_gdf,
            baseline,
            year=year,
            chunk_size=max(len(gdf), 1),
        )
        keep = [column for column in numeric_columns if column in profile.columns]
        partials.append(profile[["CSOED_CANONICAL", *keep]])
        print(
            f"LPIS {year} batch {number}: {rows_seen:,} source rows processed; "
            f"legacy missing commonage fractions={missing_commonage_total:,}"
        )

    if not partials:
        raise ValueError(f"LPIS {year} contains no readable records")

    summed = (
        pd.concat(partials, ignore_index=True)
        .groupby("CSOED_CANONICAL", as_index=False)
        .sum(numeric_only=True)
    )
    labels = baseline[["CSOED", "EDNAME", "COUNTYNAME"]].drop_duplicates("CSOED").copy()
    labels["CSOED_CANONICAL"] = labels["CSOED"].map(canonical_csoed)
    result = labels.merge(summed, on="CSOED_CANONICAL", how="left", validate="one_to_one")
    for column in summed.columns:
        if column != "CSOED_CANONICAL":
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result.insert(0, "LPIS_YEAR", int(year))
    result["LPIS_PROFILE_VERSION"] = "2.1"
    result["LPIS_SNAPSHOT_COMMONAGE_FRACTION_MISSING_RECORDS"] = missing_commonage_total
    result["LPIS_SNAPSHOT_ADJUSTED_AREA_COMPLETE"] = missing_commonage_total == 0
    result["LPIS_SNAPSHOT_ADJUSTED_AREA_STATUS"] = np.where(
        missing_commonage_total == 0,
        "COMPLETE",
        "CLAIMED_AREA_VALID_ADJUSTED_AREA_INCOMPLETE",
    )

    if missing_commonage_total:
        print(
            f"WARNING: LPIS {year} contains {missing_commonage_total:,} commonage records "
            "whose ownership fraction is absent from the published reduced file. "
            "Claimed-area composition remains usable; share-adjusted eligible/digitised "
            "diagnostics are incomplete and are explicitly flagged."
        )
    return result
