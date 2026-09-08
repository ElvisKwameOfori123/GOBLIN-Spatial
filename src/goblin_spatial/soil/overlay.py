"""Neutral Electoral Division geometry and soil-association overlay utilities.

These helpers prepare source-level spatial evidence only. They do not alter the
GOBLIN-Spatial livestock pathway, released-land quantity, future-use eligibility
or SC3 allocation.
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
except ImportError as exc:  # pragma: no cover
    gpd = None
    make_valid = None
    _GEO_IMPORT_ERROR = exc
else:
    _GEO_IMPORT_ERROR = None


@dataclass(frozen=True)
class SoilOverlayDiagnostics:
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
            "Spatial overlay requires optional geospatial dependencies. "
            "Install with: pip install 'goblin-spatial[geo]'"
        ) from _GEO_IMPORT_ERROR


def canonical_csoed(value: object) -> str:
    """Return a compound-aware canonical CSO Electoral Division key."""
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


def _with_canonical_key(df: pd.DataFrame, key_col: str, out_col: str = "CSOED_CANONICAL") -> pd.DataFrame:
    if key_col not in df.columns:
        raise ValueError(f"missing ED key column: {key_col}")
    out = df.copy()
    out[out_col] = out[key_col].map(canonical_csoed)
    if out[out_col].eq("").any():
        raise ValueError(f"{key_col} contains blank ED identifiers")
    return out


def select_baseline_ed_geometries(
    baseline: pd.DataFrame,
    ed_geometries,
    *,
    baseline_key: str = "CSOED",
    ed_key: str = "CSOED",
):
    """Select exactly the model ED universe from a geometry layer."""
    _require_geo()
    base = _with_canonical_key(baseline[[baseline_key]].drop_duplicates(), baseline_key)
    if base["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("baseline contains duplicate canonical ED identifiers")
    eds = _with_canonical_key(ed_geometries, ed_key)
    if eds["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("geometry contains duplicate canonical ED identifiers")
    selected = eds.loc[eds["CSOED_CANONICAL"].isin(set(base["CSOED_CANONICAL"]))].copy()
    missing = sorted(set(base["CSOED_CANONICAL"]) - set(selected["CSOED_CANONICAL"]))
    if missing:
        raise ValueError(f"geometry is missing {len(missing)} model EDs; examples={missing[:10]}")
    return selected


def overlay_soil_associations(
    baseline: pd.DataFrame,
    ed_geometries,
    soil_geometries,
    *,
    baseline_key: str = "CSOED",
    ed_key: str = "CSOED",
    soil_association_column: str = "ASSOCIATION",
):
    """Build a neutral long-form ED x soil-association area profile."""
    _require_geo()
    if soil_association_column not in soil_geometries.columns:
        raise ValueError(f"soil geometry missing {soil_association_column}")

    selected = select_baseline_ed_geometries(
        baseline, ed_geometries, baseline_key=baseline_key, ed_key=ed_key
    ).copy()
    soil = soil_geometries.copy()
    if selected.crs is None or soil.crs is None:
        raise ValueError("ED and soil geometry must have defined CRS")
    if selected.crs != soil.crs:
        soil = soil.to_crs(selected.crs)

    selected["geometry"] = selected.geometry.map(make_valid)
    soil["geometry"] = soil.geometry.map(make_valid)
    ed_area = selected.set_index("CSOED_CANONICAL").geometry.area / 10000.0
    intersect = gpd.overlay(
        selected[["CSOED_CANONICAL", "geometry"]],
        soil[[soil_association_column, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    intersect["AREA_HA"] = intersect.geometry.area / 10000.0
    grouped = (
        intersect.groupby(["CSOED_CANONICAL", soil_association_column], as_index=False)["AREA_HA"]
        .sum()
        .sort_values(["CSOED_CANONICAL", soil_association_column], kind="stable")
    )
    totals = grouped.groupby("CSOED_CANONICAL")["AREA_HA"].transform("sum")
    grouped["ASSOCIATION_SHARE"] = np.divide(
        grouped["AREA_HA"], totals, out=np.zeros(len(grouped)), where=totals.to_numpy() > 0
    )

    coverage = grouped.groupby("CSOED_CANONICAL")["AREA_HA"].sum().div(ed_area).dropna()
    diagnostics = SoilOverlayDiagnostics(
        baseline_rows=int(len(baseline)),
        baseline_unique_keys=int(baseline[baseline_key].map(canonical_csoed).nunique()),
        ed_rows_available=int(len(ed_geometries)),
        ed_rows_selected=int(len(selected)),
        ed_unique_keys_selected=int(selected["CSOED_CANONICAL"].nunique()),
        missing_baseline_keys=0,
        soil_polygons=int(len(soil)),
        soil_associations=int(soil[soil_association_column].nunique()),
        intersect_rows=int(len(intersect)),
        eds_with_soil=int(grouped["CSOED_CANONICAL"].nunique()),
        total_ed_area_ha=float(ed_area.sum()),
        total_intersect_area_ha=float(grouped["AREA_HA"].sum()),
        mean_soil_coverage=float(coverage.mean()) if not coverage.empty else float("nan"),
        median_soil_coverage=float(coverage.median()) if not coverage.empty else float("nan"),
    )
    return grouped.reset_index(drop=True), diagnostics
