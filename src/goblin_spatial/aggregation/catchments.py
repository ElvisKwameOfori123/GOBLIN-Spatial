"""Catchment and county aggregation for validated GOBLIN-Spatial baselines.

This module does not change baseline science. It creates alternative reporting
geographies from the validated ED x year master table.

The authoritative hydrological output preserves the official 46 EPA WFD
catchments. A second, optional compatibility view collapses the detailed Upper
and Lower Shannon units to the 37-name system used by
GOBLIN-Proj/catchment_data_api.
"""
from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.export.workbook import CSO_LIVESTOCK
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries

EXPECTED_WFD_CATCHMENTS = 46

COLM_CATCHMENTS = (
    "Ballyteigue-Bannow", "Bandon-Ilen", "Barrow", "Blacksod-Broadhaven",
    "Blackwater (Munster)", "Boyne", "Colligan-Mahon", "Corrib",
    "Donagh-Moville", "Donegal Bay North", "Dunmanus-Bantry-Kenmare", "Erne",
    "Erriff-Clew Bay", "Foyle", "Galway Bay North", "Galway Bay South East",
    "Gweebarra-Sheephaven", "Laune-Maine-Dingle Bay",
    "Lee, Cork Harbour and Youghal Bay", "Liffey and Dublin Bay",
    "Lough Neagh & Lower Bann", "Lough Swilly", "Lower Shannon", "Mal Bay",
    "Moy & Killala Bay", "Nanny-Delvin", "Newry, Fane, Glyde and Dee", "Nore",
    "Ovoca-Vartry", "Owenavorragh", "Shannon Estuary North",
    "Shannon Estuary South", "Slaney & Wexford Harbour", "Sligo Bay", "Suir",
    "Tralee Bay-Feale", "Upper Shannon",
)

ADDITIVE_LAND = (
    "AGRICULTURAL_HOLDINGS", "AREA_FARMED", "ALL_GRASSLAND",
    "TOTAL_CEREALS", "OTHER_CROPS_HA",
)
ADDITIVE_SO = (
    "SO_DAIRY_COWS_2020_EUR", "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR", "SO_FOLLOWERS_2020_EUR", "SO_SHEEP_2020_EUR",
    "SO_LIVESTOCK_2020_EUR", "SO_CEREALS_2020_EUR",
    "SO_OTHER_CROPS_2020_EUR", "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
    "SO_COVERED_TOTAL_2020_EUR", "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
    "SO_OTHER_CROPS_IMPUTED_HA",
)
DEFAULT_ADDITIVE_COLUMNS = tuple(dict.fromkeys(
    [*CSO_LIVESTOCK, *FINAL_21_COHORTS, *GOBLIN_SHEEP_10, *ADDITIVE_LAND, *ADDITIVE_SO]
))


def _name_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


_COLM_BY_KEY = {_name_key(name): name for name in COLM_CATCHMENTS}
_COLM_BY_KEY["blackwater"] = "Blackwater (Munster)"
_COLM_BY_KEY["sligo bay and drowse"] = "Sligo Bay"


def canonical_wfd_catchment_name(value: object) -> str:
    """Preserve the official WFD catchment name, trimming only whitespace."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def to_colm_catchment_name(value: object) -> str:
    """Map official WFD catchment names to Colm Duffy's 37-name compatibility system."""
    key = _name_key(value)
    if not key:
        return ""
    if "lower shannon" in key:
        return "Lower Shannon"
    if "upper shannon" in key:
        return "Upper Shannon"
    key_without_code = re.sub(r"\\s+\\d{2}[a-z]?$", "", key)
    mapped = _COLM_BY_KEY.get(key) or _COLM_BY_KEY.get(key_without_code)
    if mapped is None:
        raise ValueError(f"No Colm catchment mapping for WFD catchment: {value!r}")
    return mapped


# Backward-compatible public name from the first bridge implementation.
canonical_catchment_name = to_colm_catchment_name


def _infer_catchment_column(frame: pd.DataFrame) -> str:
    candidates = (
        "Catchment", "CATCHMENT", "catchment", "CatchmentName",
        "CATCHMENTNAME", "NAME", "Name", "name",
    )
    for column in candidates:
        if column in frame.columns:
            return column
    raise ValueError(
        "Could not infer catchment-name field. Pass catchment_name_col explicitly."
    )


def _infer_catchment_id_column(frame: pd.DataFrame) -> str | None:
    candidates = (
        "CATCHMENTI", "CATCHMENT_ID", "CatchmentID", "catchment_id",
        "CATCH_ID", "ID", "Id", "id",
    )
    return next((column for column in candidates if column in frame.columns), None)


def _existing_additive(master: pd.DataFrame, columns: Iterable[str] | None) -> list[str]:
    requested = list(columns) if columns is not None else list(DEFAULT_ADDITIVE_COLUMNS)
    existing = [c for c in requested if c in master.columns]
    if not existing:
        raise ValueError("No requested additive GOBLIN-Spatial columns were found.")
    return existing


def build_ed_catchment_crosswalk(
    baseline: pd.DataFrame,
    ed_geometries,
    catchment_geometries,
    *,
    baseline_key: str = "CSOED",
    ed_key: str = "CSOED",
    catchment_name_col: str | None = None,
    catchment_id_col: str | None = None,
    expected_wfd_catchments: int | None = EXPECTED_WFD_CATCHMENTS,
):
    """Build a conservative ED-to-WFD-catchment fractional-area crosswalk.

    The official WFD catchment units are preserved. Weights are normalised
    within each model ED so every ED contributes exactly 100% of each additive
    quantity to the hydrological geography.
    """
    try:
        import geopandas as gpd
        from shapely.validation import make_valid
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Catchment aggregation requires geospatial dependencies. "
            "Install with: pip install 'goblin-spatial[geo]'"
        ) from exc

    base_keys = baseline[[baseline_key]].drop_duplicates().copy()
    selected = select_baseline_ed_geometries(
        base_keys, ed_geometries, baseline_key=baseline_key, ed_key=ed_key
    ).copy()

    name_col = catchment_name_col or _infer_catchment_column(catchment_geometries)
    id_col = catchment_id_col or _infer_catchment_id_column(catchment_geometries)
    keep = [name_col, "geometry"] + ([id_col] if id_col else [])
    catchments = catchment_geometries[keep].copy()
    catchments["WFD_CATCHMENT"] = catchments[name_col].map(canonical_wfd_catchment_name)
    if catchments["WFD_CATCHMENT"].eq("").any():
        raise ValueError("Catchment geometry contains blank catchment names.")

    if id_col:
        catchments["WFD_CATCHMENT_ID"] = catchments[id_col].astype(str).str.strip()
    else:
        catchments["WFD_CATCHMENT_ID"] = catchments["WFD_CATCHMENT"]

    source_count = int(catchments["WFD_CATCHMENT_ID"].nunique())
    if expected_wfd_catchments is not None and source_count != expected_wfd_catchments:
        raise ValueError(
            f"Expected {expected_wfd_catchments} WFD catchments, found {source_count}."
        )

    if selected.crs is None or catchments.crs is None:
        raise ValueError("ED and catchment geometries must both have a defined CRS.")
    if selected.crs != catchments.crs:
        catchments = catchments.to_crs(selected.crs)
    if getattr(selected.crs, "is_geographic", False):
        selected = selected.to_crs(2157)
        catchments = catchments.to_crs(2157)

    selected["geometry"] = selected.geometry.map(make_valid)
    catchments["geometry"] = catchments.geometry.map(make_valid)
    catchments = catchments.dissolve(
        by=["WFD_CATCHMENT_ID", "WFD_CATCHMENT"], as_index=False
    )

    selected["_ED_AREA_HA"] = selected.geometry.area / 10000.0
    overlay = gpd.overlay(
        selected[["CSOED_CANONICAL", "_ED_AREA_HA", "geometry"]],
        catchments[["WFD_CATCHMENT_ID", "WFD_CATCHMENT", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    if overlay.empty:
        raise ValueError("ED/catchment overlay produced no intersections.")

    overlay["INTERSECT_AREA_HA"] = overlay.geometry.area / 10000.0
    grouped = (
        overlay.groupby(
            ["CSOED_CANONICAL", "WFD_CATCHMENT_ID", "WFD_CATCHMENT"],
            as_index=False,
        )
        .agg(
            INTERSECT_AREA_HA=("INTERSECT_AREA_HA", "sum"),
            ED_AREA_HA=("_ED_AREA_HA", "first"),
        )
    )
    intersect_total = grouped.groupby("CSOED_CANONICAL")["INTERSECT_AREA_HA"].transform("sum")
    grouped["ED_CATCHMENT_WEIGHT"] = grouped["INTERSECT_AREA_HA"] / intersect_total
    grouped["ED_COVERAGE_SHARE"] = intersect_total / grouped["ED_AREA_HA"]
    grouped["COLM_CATCHMENT"] = grouped["WFD_CATCHMENT"].map(to_colm_catchment_name)

    source = base_keys.copy()
    source["CSOED_CANONICAL"] = source[baseline_key].map(canonical_csoed)
    if source["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("Baseline contains duplicate canonical ED identifiers.")
    grouped = grouped.merge(source, on="CSOED_CANONICAL", how="left", validate="many_to_one")

    missing = sorted(
        set(source["CSOED_CANONICAL"]) - set(grouped["CSOED_CANONICAL"])
    )
    if missing:
        raise ValueError(
            f"{len(missing)} model EDs do not intersect a WFD catchment; examples={missing[:10]}"
        )

    closure = grouped.groupby(baseline_key)["ED_CATCHMENT_WEIGHT"].sum()
    if not np.allclose(closure.to_numpy(), 1.0, rtol=0, atol=1e-10):
        raise AssertionError("ED-to-catchment weights do not close to 1.0.")

    return grouped[
        [
            baseline_key,
            "CSOED_CANONICAL",
            "WFD_CATCHMENT_ID",
            "WFD_CATCHMENT",
            "COLM_CATCHMENT",
            "INTERSECT_AREA_HA",
            "ED_AREA_HA",
            "ED_COVERAGE_SHARE",
            "ED_CATCHMENT_WEIGHT",
        ]
    ].sort_values(
        [baseline_key, "WFD_CATCHMENT_ID"], kind="stable"
    ).reset_index(drop=True)


def aggregate_to_wfd_catchments(
    master: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
    ed_key: str = "CSOED",
) -> pd.DataFrame:
    """Aggregate the ED x year master to the official WFD catchment x year geography."""
    columns = _existing_additive(master, additive_columns)
    if master.duplicated([year_col, ed_key]).any():
        raise ValueError("Master must contain one row per ED x year.")

    weight_cols = [
        ed_key, "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "ED_CATCHMENT_WEIGHT"
    ]
    weights = crosswalk[weight_cols].copy()
    merged = master[[year_col, ed_key, *columns]].merge(
        weights, on=ed_key, how="left", validate="many_to_many"
    )
    if merged["ED_CATCHMENT_WEIGHT"].isna().any():
        missing = (
            merged.loc[merged["ED_CATCHMENT_WEIGHT"].isna(), ed_key]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(f"Crosswalk missing model EDs; examples={missing[:10]}")

    weighted = merged[columns].multiply(merged["ED_CATCHMENT_WEIGHT"], axis=0)
    weighted[year_col] = merged[year_col].to_numpy()
    weighted["WFD_CATCHMENT_ID"] = merged["WFD_CATCHMENT_ID"].to_numpy()
    weighted["WFD_CATCHMENT"] = merged["WFD_CATCHMENT"].to_numpy()
    out = weighted.groupby(
        [year_col, "WFD_CATCHMENT_ID", "WFD_CATCHMENT"], as_index=False
    )[columns].sum()
    return out.sort_values(
        [year_col, "WFD_CATCHMENT_ID"], kind="stable"
    ).reset_index(drop=True)


# Backward-compatible alias.
aggregate_to_catchments = aggregate_to_wfd_catchments


def aggregate_wfd_to_colm(
    wfd_catchment_year: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
) -> pd.DataFrame:
    """Collapse the official 46 WFD units to Colm's 37 catchment groups."""
    if "WFD_CATCHMENT" not in wfd_catchment_year.columns:
        raise ValueError("WFD catchment table is missing WFD_CATCHMENT.")

    if additive_columns is None:
        excluded = {year_col, "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "COLM_CATCHMENT"}
        columns = [
            c for c in wfd_catchment_year.columns
            if c not in excluded and pd.api.types.is_numeric_dtype(wfd_catchment_year[c])
        ]
    else:
        columns = [c for c in additive_columns if c in wfd_catchment_year.columns]

    work = wfd_catchment_year[[year_col, "WFD_CATCHMENT", *columns]].copy()
    work["COLM_CATCHMENT"] = work["WFD_CATCHMENT"].map(to_colm_catchment_name)
    unknown = sorted(set(work["COLM_CATCHMENT"]) - set(COLM_CATCHMENTS))
    if unknown:
        raise ValueError(f"Unexpected Colm catchment names after harmonisation: {unknown}")

    out = work.groupby([year_col, "COLM_CATCHMENT"], as_index=False)[columns].sum()
    return out.sort_values([year_col, "COLM_CATCHMENT"], kind="stable").reset_index(drop=True)


def aggregate_to_counties(
    master: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
    county_col: str = "County",
) -> pd.DataFrame:
    """Aggregate additive ED quantities to county x year."""
    columns = _existing_additive(master, additive_columns)
    if county_col not in master.columns:
        raise ValueError(f"Master is missing county column: {county_col}")
    out = master.groupby([year_col, county_col], as_index=False)[columns].sum()
    return out.sort_values([year_col, county_col], kind="stable").reset_index(drop=True)


def validate_aggregation_closure(
    master: pd.DataFrame,
    aggregated: pd.DataFrame,
    *,
    geography_col: str,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
    atol: float = 1e-6,
) -> pd.DataFrame:
    """Return per-year closure diagnostics and fail if any additive total changes."""
    columns = _existing_additive(master, additive_columns)
    national = master.groupby(year_col, as_index=False)[columns].sum().set_index(year_col)
    derived = aggregated.groupby(year_col, as_index=False)[columns].sum().set_index(year_col)
    if set(national.index) != set(derived.index):
        raise AssertionError(f"{geography_col} aggregation has a different year universe.")

    rows = []
    failed = []
    for year in national.index:
        for column in columns:
            expected = float(national.loc[year, column])
            actual = float(derived.loc[year, column])
            diff = actual - expected
            rows.append({
                year_col: year,
                "GEOGRAPHY": geography_col,
                "VARIABLE": column,
                "NATIONAL": expected,
                "AGGREGATED": actual,
                "DIFF": diff,
            })
            if not np.isclose(actual, expected, rtol=0, atol=atol):
                failed.append((year, column, diff))
    if failed:
        raise AssertionError(
            f"{geography_col} aggregation failed national closure; examples={failed[:10]}"
        )
    return pd.DataFrame(rows)
