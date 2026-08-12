"""Neutral ED x SIS soil-association overlay utilities.

This module deliberately stops before interpreting SIS associations as GOBLIN
soil groups or future land uses. The authoritative livestock baseline defines
which Electoral Divisions are in scope; the ED shapefile supplies geometry;
and the SIS shapefile supplies raw soil-association polygons.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

try:
    import geopandas as gpd
    from shapely.validation import make_valid
except ImportError as exc:  # pragma: no cover - import guard only
    gpd = None
    make_valid = None
    _GEO_IMPORT_ERROR = exc
else:
    _GEO_IMPORT_ERROR = None


@dataclass(frozen=True)
class SoilOverlayDiagnostics:
    """Headline validation statistics for one ED x SIS overlay run."""

    baseline_rows: int
    baseline_unique_keys: int
    ed_rows_available: int
    ed_rows_selected: int
    ed_unique_keys_selected: int
    missing_baseline_keys: int
    soil_polygons: int
    soil_associations: int
    intersect_rows: int
    eds_with_soil: int
    total_ed_area_ha: float
    total_intersect_area_ha: float
    mean_soil_coverage: float
    median_soil_coverage: float


def _require_geo() -> None:
    if gpd is None:
        raise ImportError(
            "Soil overlay requires the optional geospatial dependencies. "
            "Install with: pip install 'goblin-spatial[geo]'"
        ) from _GEO_IMPORT_ERROR


def canonical_csoed(value: object) -> str:
    """Return a compound-aware canonical CSO Electoral Division key.

    Examples
    --------
    ``01001`` -> ``1001``
    ``08045/08046`` -> ``8045/8046``

    Leading-zero removal is applied to every compound member separately.
    """

    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
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


def _with_canonical_key(
    df: pd.DataFrame,
    key_col: str,
    out_col: str = "CSOED_CANONICAL",
) -> pd.DataFrame:
    if key_col not in df.columns:
        raise KeyError(f"Missing ED key column: {key_col}")

    out = df.copy()
    out[out_col] = out[key_col].map(canonical_csoed)

    if (out[out_col] == "").any():
        raise ValueError(f"Blank canonical ED keys found in {key_col}")

    duplicates = out.loc[out[out_col].duplicated(keep=False), out_col].unique().tolist()
    if duplicates:
        raise ValueError(f"Duplicate canonical ED keys found: {duplicates[:10]}")

    return out


def select_baseline_ed_geometries(
    baseline: pd.DataFrame,
    ed_gdf,
    *,
    baseline_key_col: str = "CSOED",
    ed_key_col: str = "CSOED",
):
    """Filter the national ED geography to exactly the baseline ED universe.

    The baseline is authoritative: extra ED polygons are ignored and every
    baseline ED must have exactly one polygon record after canonicalisation.
    """

    _require_geo()
    baseline_keyed = _with_canonical_key(baseline, baseline_key_col)
    ed_keyed = _with_canonical_key(ed_gdf, ed_key_col)

    baseline_keys = set(baseline_keyed["CSOED_CANONICAL"])
    selected = ed_keyed.loc[ed_keyed["CSOED_CANONICAL"].isin(baseline_keys)].copy()
    selected_keys = set(selected["CSOED_CANONICAL"])

    missing = sorted(baseline_keys - selected_keys)
    if missing:
        raise ValueError(
            f"ED shapefile is missing {len(missing)} baseline CSOED keys; "
            f"examples: {missing[:10]}"
        )

    if len(selected) != len(baseline_keyed):
        raise ValueError(
            "Baseline-to-ED geometry selection is not one-to-one: "
            f"baseline rows={len(baseline_keyed)}, selected ED rows={len(selected)}"
        )

    return baseline_keyed, selected


def _repair_polygon_geometries(gdf):
    _require_geo()
    out = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    invalid = ~out.geometry.is_valid

    if invalid.any():
        out.loc[invalid, "geometry"] = out.loc[invalid, "geometry"].map(make_valid)

    out = out.explode(index_parts=False, ignore_index=True)
    out = out.loc[out.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return out


def overlay_soil_associations(
    baseline: pd.DataFrame,
    ed_gdf,
    soil_gdf,
    *,
    baseline_key_col: str = "CSOED",
    ed_key_col: str = "CSOED",
    association_col: str = "Associatio",
    target_crs: str = "EPSG:2157",
    min_intersection_ha: float = 0.01,
    carry_ed_columns: Iterable[str] = ("EDNAME", "COUNTYNAME", "COUNTY"),
):
    """Build a neutral long-form ED x SIS soil-association profile.

    No functional soil class, GOBLIN G1/G2/G3 class, grass-yield factor or
    future land-use suitability is inferred here.  The returned association
    shares describe the mapped SIS composition of each selected ED and are not
    yet restricted to agricultural grassland.
    """

    _require_geo()

    if association_col not in soil_gdf.columns:
        raise KeyError(f"Missing SIS association column: {association_col}")
    if ed_gdf.crs is None or soil_gdf.crs is None:
        raise ValueError("Both ED and SIS layers must have a defined CRS")

    baseline_keyed, ed_selected = select_baseline_ed_geometries(
        baseline,
        ed_gdf,
        baseline_key_col=baseline_key_col,
        ed_key_col=ed_key_col,
    )

    ed_selected = _repair_polygon_geometries(ed_selected).to_crs(target_crs)
    soil = _repair_polygon_geometries(soil_gdf).to_crs(target_crs)

    keep_ed = ["CSOED_CANONICAL", "geometry"]
    for col in carry_ed_columns:
        if col in ed_selected.columns and col not in keep_ed:
            keep_ed.append(col)

    ed_overlay = ed_selected[keep_ed].copy()
    soil_overlay = soil[[association_col, "geometry"]].copy()
    soil_overlay[association_col] = soil_overlay[association_col].astype(str).str.strip()

    ed_area = ed_overlay[["CSOED_CANONICAL"]].copy()
    ed_area["ED_AREA_HA"] = ed_overlay.geometry.area / 10_000.0
    ed_area = ed_area.groupby("CSOED_CANONICAL", as_index=False)["ED_AREA_HA"].sum()

    intersection = gpd.overlay(
        ed_overlay,
        soil_overlay,
        how="intersection",
        keep_geom_type=True,
    )
    intersection["INTERSECTION_HA"] = intersection.geometry.area / 10_000.0
    intersection = intersection.loc[
        intersection["INTERSECTION_HA"] >= float(min_intersection_ha)
    ].copy()

    group_cols = ["CSOED_CANONICAL", association_col]
    for col in carry_ed_columns:
        if col in intersection.columns and col not in group_cols:
            group_cols.append(col)

    long = (
        intersection.groupby(group_cols, dropna=False, as_index=False)["INTERSECTION_HA"]
        .sum()
        .rename(columns={association_col: "SIS_ASSOCIATION"})
    )

    totals = (
        long.groupby("CSOED_CANONICAL", as_index=False)["INTERSECTION_HA"]
        .sum()
        .rename(columns={"INTERSECTION_HA": "MAPPED_SOIL_HA"})
        .merge(ed_area, on="CSOED_CANONICAL", how="left", validate="one_to_one")
    )
    totals["SOIL_COVERAGE_FRAC"] = np.where(
        totals["ED_AREA_HA"] > 0,
        totals["MAPPED_SOIL_HA"] / totals["ED_AREA_HA"],
        np.nan,
    )

    long = long.merge(
        totals,
        on="CSOED_CANONICAL",
        how="left",
        validate="many_to_one",
    )
    long["ASSOCIATION_SHARE_WITHIN_MAPPED_SOIL"] = np.where(
        long["MAPPED_SOIL_HA"] > 0,
        long["INTERSECTION_HA"] / long["MAPPED_SOIL_HA"],
        0.0,
    )

    missing_profile = set(baseline_keyed["CSOED_CANONICAL"]) - set(long["CSOED_CANONICAL"])
    if missing_profile:
        raise ValueError(
            f"{len(missing_profile)} baseline EDs have no SIS soil overlap; "
            f"examples: {sorted(missing_profile)[:10]}"
        )

    diagnostics = SoilOverlayDiagnostics(
        baseline_rows=len(baseline_keyed),
        baseline_unique_keys=baseline_keyed["CSOED_CANONICAL"].nunique(),
        ed_rows_available=len(ed_gdf),
        ed_rows_selected=ed_selected["CSOED_CANONICAL"].nunique(),
        ed_unique_keys_selected=ed_selected["CSOED_CANONICAL"].nunique(),
        missing_baseline_keys=0,
        soil_polygons=len(soil_gdf),
        soil_associations=soil_overlay[association_col].nunique(dropna=True),
        intersect_rows=len(intersection),
        eds_with_soil=long["CSOED_CANONICAL"].nunique(),
        total_ed_area_ha=float(ed_area["ED_AREA_HA"].sum()),
        total_intersect_area_ha=float(long["INTERSECTION_HA"].sum()),
        mean_soil_coverage=float(totals["SOIL_COVERAGE_FRAC"].mean()),
        median_soil_coverage=float(totals["SOIL_COVERAGE_FRAC"].median()),
    )

    long = long.sort_values(
        ["CSOED_CANONICAL", "INTERSECTION_HA"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return long, diagnostics
