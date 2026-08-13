"""Memory-bounded GeoParquet reader for the LPIS-to-ED bridge."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
import shapely

from goblin_spatial.soil.overlay import canonical_csoed
from .lpis import LPIS_PROFILE_AREA_COLUMNS
from .lpis_spatial import build_ed_lpis_profile


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
    numeric_columns = [
        *LPIS_PROFILE_AREA_COLUMNS,
        "LPIS_INTERSECTION_GEOMETRY_HA",
        "LPIS_SOURCE_RECORDS_INTERSECTING_ED",
        "LPIS_GRASS_SOURCE_RECORDS_INTERSECTING_ED",
    ]

    for number, batch in enumerate(parquet.iter_batches(batch_size=batch_size), start=1):
        gdf = _batch_to_gdf(batch, geometry_column, source_crs)
        rows_seen += len(gdf)
        profile = build_ed_lpis_profile(
            gdf,
            ed_gdf,
            baseline,
            year=year,
            chunk_size=max(len(gdf), 1),
        )
        keep = [column for column in numeric_columns if column in profile.columns]
        partials.append(profile[["CSOED_CANONICAL", *keep]])
        print(f"LPIS {year} batch {number}: {rows_seen:,} source rows processed")

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
    result["LPIS_PROFILE_VERSION"] = "2.0"
    return result
