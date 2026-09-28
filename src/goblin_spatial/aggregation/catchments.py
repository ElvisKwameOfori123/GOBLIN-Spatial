"""Catchment and county aggregation for validated GOBLIN-Spatial baselines.

This module does not change baseline science. It creates alternative reporting
geographies from the validated ED x year master table.

The authoritative hydrological output preserves the official 46 EPA WFD
catchments. A second compatibility view collapses the detailed Upper and Lower
Shannon units to the 37-name system used by GOBLIN-Proj/catchment_data_api.
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
    "Ballyteigue-Bannow",
    "Bandon-Ilen",
    "Barrow",
    "Blacksod-Broadhaven",
    "Blackwater (Munster)",
    "Boyne",
    "Colligan-Mahon",
    "Corrib",
    "Donagh-Moville",
    "Donegal Bay North",
    "Dunmanus-Bantry-Kenmare",
    "Erne",
    "Erriff-Clew Bay",
    "Foyle",
    "Galway Bay North",
    "Galway Bay South East",
    "Gweebarra-Sheephaven",
    "Laune-Maine-Dingle Bay",
    "Lee, Cork Harbour and Youghal Bay",
    "Liffey and Dublin Bay",
    "Lough Neagh & Lower Bann",
    "Lough Swilly",
    "Lower Shannon",
    "Mal Bay",
    "Moy & Killala Bay",
    "Nanny-Delvin",
    "Newry, Fane, Glyde and Dee",
    "Nore",
    "Ovoca-Vartry",
    "Owenavorragh",
    "Shannon Estuary North",
    "Shannon Estuary South",
    "Slaney & Wexford Harbour",
    "Sligo Bay",
    "Suir",
    "Tralee Bay-Feale",
    "Upper Shannon",
)

# The official WFD system has 46 units because Lower Shannon is split into
# 25A-25D and Upper Shannon into 26A-26G. Colm's compatibility system collapses
# those subdivisions, giving 37 catchments.
WFD_ID_TO_COLM = {
    "01": "Foyle",
    "03": "Lough Neagh & Lower Bann",
    "06": "Newry, Fane, Glyde and Dee",
    "07": "Boyne",
    "08": "Nanny-Delvin",
    "09": "Liffey and Dublin Bay",
    "10": "Ovoca-Vartry",
    "11": "Owenavorragh",
    "12": "Slaney & Wexford Harbour",
    "13": "Ballyteigue-Bannow",
    "14": "Barrow",
    "15": "Nore",
    "16": "Suir",
    "17": "Colligan-Mahon",
    "18": "Blackwater (Munster)",
    "19": "Lee, Cork Harbour and Youghal Bay",
    "20": "Bandon-Ilen",
    "21": "Dunmanus-Bantry-Kenmare",
    "22": "Laune-Maine-Dingle Bay",
    "23": "Tralee Bay-Feale",
    "24": "Shannon Estuary South",
    "27": "Shannon Estuary North",
    "28": "Mal Bay",
    "29": "Galway Bay South East",
    "30": "Corrib",
    "31": "Galway Bay North",
    "32": "Erriff-Clew Bay",
    "33": "Blacksod-Broadhaven",
    "34": "Moy & Killala Bay",
    "35": "Sligo Bay",
    "36": "Erne",
    "37": "Donegal Bay North",
    "38": "Gweebarra-Sheephaven",
    "39": "Lough Swilly",
    "40": "Donagh-Moville",
}

ADDITIVE_LAND = (
    "AGRICULTURAL_HOLDINGS",
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "OTHER_CROPS_HA",
)
ADDITIVE_SO = (
    "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR",
    "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR",
    "SO_LIVESTOCK_2020_EUR",
    "SO_CEREALS_2020_EUR",
    "SO_OTHER_CROPS_2020_EUR",
    "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
    "SO_COVERED_TOTAL_2020_EUR",
    "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
    "SO_OTHER_CROPS_IMPUTED_HA",
)
DEFAULT_ADDITIVE_COLUMNS = tuple(
    dict.fromkeys(
        [
            *CSO_LIVESTOCK,
            *FINAL_21_COHORTS,
            *GOBLIN_SHEEP_10,
            *ADDITIVE_LAND,
            *ADDITIVE_SO,
        ]
    )
)

NON_ADDITIVE_STRUCTURE_COLUMNS = (
    "AVERAGE_SIZE_OF_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER",
    "SO_COVERED_PER_HOLDING_2020_EUR",
    "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
)


def _name_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


_COLM_BY_KEY = {_name_key(name): name for name in COLM_CATCHMENTS}
_COLM_BY_KEY["blackwater"] = "Blackwater (Munster)"
_COLM_BY_KEY["sligo bay and drowse"] = "Sligo Bay"


def _normalise_wfd_id(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = re.sub(r"\.0$", "", str(value).strip().upper())
    match = re.fullmatch(r"0*(\d{1,2})([A-Z]?)", text)
    if match:
        return f"{int(match.group(1)):02d}{match.group(2)}"
    return text


def canonical_wfd_catchment_name(value: object) -> str:
    """Preserve the official WFD catchment name, trimming only whitespace."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def to_colm_catchment_name(
    value: object,
    catchment_id: object | None = None,
) -> str:
    """Map an official WFD unit to Colm Duffy's 37-name compatibility system."""
    code = _normalise_wfd_id(catchment_id)
    if code:
        if code.startswith("25"):
            return "Lower Shannon"
        if code.startswith("26"):
            return "Upper Shannon"
        if code in WFD_ID_TO_COLM:
            return WFD_ID_TO_COLM[code]

    key = _name_key(value)
    if not key:
        return ""
    if "lower shannon" in key:
        return "Lower Shannon"
    if "upper shannon" in key:
        return "Upper Shannon"

    key_without_code = re.sub(r"\s+\d{2}[a-z]?$", "", key)
    mapped = _COLM_BY_KEY.get(key) or _COLM_BY_KEY.get(key_without_code)
    if mapped is None:
        raise ValueError(
            f"No Colm catchment mapping for WFD catchment: {value!r}, "
            f"id={catchment_id!r}"
        )
    return mapped


# Backward-compatible public name from the first bridge implementation.
canonical_catchment_name = to_colm_catchment_name


def _infer_catchment_column(frame: pd.DataFrame) -> str:
    candidates = (
        "Catchment",
        "CATCHMENT",
        "catchment",
        "CatchmentName",
        "CATCHMENTNAME",
        "NAME",
        "Name",
        "name",
    )
    for column in candidates:
        if column in frame.columns:
            return column
    raise ValueError(
        "Could not infer catchment-name field. Pass catchment_name_col explicitly."
    )


def _infer_catchment_id_column(frame: pd.DataFrame) -> str | None:
    candidates = (
        "CATCHMENTI",
        "CATCHMENT_ID",
        "CatchmentID",
        "catchment_id",
        "CATCH_ID",
        "ID",
        "Id",
        "id",
    )
    return next((column for column in candidates if column in frame.columns), None)


def _existing_additive(
    master: pd.DataFrame,
    columns: Iterable[str] | None,
) -> list[str]:
    requested = (
        list(columns) if columns is not None else list(DEFAULT_ADDITIVE_COLUMNS)
    )
    existing = [
        column
        for column in requested
        if column in master.columns and column not in NON_ADDITIVE_STRUCTURE_COLUMNS
    ]
    if not existing:
        raise ValueError("No requested additive GOBLIN-Spatial columns were found.")
    return existing


def _attach_structure_metrics(
    frame: pd.DataFrame,
    *,
    age_numerator: pd.Series | np.ndarray | None = None,
    age_denominator: pd.Series | np.ndarray | None = None,
) -> pd.DataFrame:
    """Attach valid higher-level farm-structure indicators.

    Average holding size is recomputed from aggregate area and holdings.
    Average holder age is holdings-weighted. Median holder age is deliberately
    not propagated because an aggregate median cannot be recovered from ED
    medians.
    """

    out = frame.copy()
    if {"AREA_FARMED", "AGRICULTURAL_HOLDINGS"}.issubset(out.columns):
        area = pd.to_numeric(out["AREA_FARMED"], errors="raise").to_numpy(dtype=float)
        holdings = pd.to_numeric(
            out["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        out["AVERAGE_SIZE_OF_HOLDINGS"] = np.divide(
            area,
            holdings,
            out=np.full(len(out), np.nan, dtype=float),
            where=holdings > 0,
        )

    if age_numerator is not None and age_denominator is not None:
        numerator = np.asarray(age_numerator, dtype=float)
        denominator = np.asarray(age_denominator, dtype=float)
        out["AVERAGE_AGE_OF_HOLDER"] = np.divide(
            numerator,
            denominator,
            out=np.full(len(out), np.nan, dtype=float),
            where=denominator > 0,
        )

    if "AGRICULTURAL_HOLDINGS" in out.columns:
        holdings = pd.to_numeric(
            out["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        for total_column, per_holding_column in (
            ("SO_COVERED_TOTAL_2020_EUR", "SO_COVERED_PER_HOLDING_2020_EUR"),
            (
                "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
                "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
            ),
        ):
            if total_column in out.columns:
                total = pd.to_numeric(
                    out[total_column], errors="raise"
                ).to_numpy(dtype=float)
                out[per_holding_column] = np.divide(
                    total,
                    holdings,
                    out=np.full(len(out), np.nan, dtype=float),
                    where=holdings > 0,
                )
    return out


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

    The official WFD units are preserved. Weights are normalised within each
    model ED so every ED contributes exactly 100% of each additive quantity to
    the hydrological geography.
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
        base_keys,
        ed_geometries,
        baseline_key=baseline_key,
        ed_key=ed_key,
    ).copy()

    name_col = catchment_name_col or _infer_catchment_column(catchment_geometries)
    id_col = catchment_id_col or _infer_catchment_id_column(catchment_geometries)
    keep = [name_col, "geometry"] + ([id_col] if id_col else [])
    catchments = catchment_geometries[keep].copy()

    catchments["WFD_CATCHMENT"] = catchments[name_col].map(
        canonical_wfd_catchment_name
    )
    if catchments["WFD_CATCHMENT"].eq("").any():
        raise ValueError("Catchment geometry contains blank catchment names.")

    if id_col:
        catchments["WFD_CATCHMENT_ID"] = catchments[id_col].map(_normalise_wfd_id)
    else:
        catchments["WFD_CATCHMENT_ID"] = catchments["WFD_CATCHMENT"]

    source_count = int(catchments["WFD_CATCHMENT_ID"].nunique())
    if (
        expected_wfd_catchments is not None
        and source_count != expected_wfd_catchments
    ):
        raise ValueError(
            f"Expected {expected_wfd_catchments} WFD catchments, "
            f"found {source_count}."
        )

    catchments["COLM_CATCHMENT"] = [
        to_colm_catchment_name(name, catchment_id)
        for name, catchment_id in zip(
            catchments["WFD_CATCHMENT"],
            catchments["WFD_CATCHMENT_ID"],
        )
    ]
    if expected_wfd_catchments == EXPECTED_WFD_CATCHMENTS:
        colm_count = int(catchments["COLM_CATCHMENT"].nunique())
        if colm_count != len(COLM_CATCHMENTS):
            raise ValueError(
                f"Expected {len(COLM_CATCHMENTS)} Colm compatibility catchments, "
                f"found {colm_count}."
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
        by=["WFD_CATCHMENT_ID", "WFD_CATCHMENT", "COLM_CATCHMENT"],
        as_index=False,
    )

    selected["_ED_AREA_HA"] = selected.geometry.area / 10000.0
    overlay = gpd.overlay(
        selected[["CSOED_CANONICAL", "_ED_AREA_HA", "geometry"]],
        catchments[
            [
                "WFD_CATCHMENT_ID",
                "WFD_CATCHMENT",
                "COLM_CATCHMENT",
                "geometry",
            ]
        ],
        how="intersection",
        keep_geom_type=False,
    )
    if overlay.empty:
        raise ValueError("ED/catchment overlay produced no intersections.")

    overlay["INTERSECT_AREA_HA"] = overlay.geometry.area / 10000.0
    grouped = (
        overlay.groupby(
            [
                "CSOED_CANONICAL",
                "WFD_CATCHMENT_ID",
                "WFD_CATCHMENT",
                "COLM_CATCHMENT",
            ],
            as_index=False,
        )
        .agg(
            INTERSECT_AREA_HA=("INTERSECT_AREA_HA", "sum"),
            ED_AREA_HA=("_ED_AREA_HA", "first"),
        )
    )

    intersect_total = grouped.groupby("CSOED_CANONICAL")[
        "INTERSECT_AREA_HA"
    ].transform("sum")
    grouped["ED_CATCHMENT_WEIGHT"] = (
        grouped["INTERSECT_AREA_HA"] / intersect_total
    )
    grouped["ED_COVERAGE_SHARE"] = intersect_total / grouped["ED_AREA_HA"]
    grouped["ASSIGNMENT_METHOD"] = "polygon_intersection"
    grouped["NEAREST_DISTANCE_M"] = 0.0

    # WFD catchment polygons do not necessarily cover every offshore island.
    # Preserve national closure by assigning any model ED with no polygon
    # intersection to its nearest official WFD catchment. This fallback is
    # explicit in the crosswalk and does not alter the ED baseline itself.
    missing_canonical = sorted(
        set(selected["CSOED_CANONICAL"])
        - set(grouped["CSOED_CANONICAL"])
    )
    if missing_canonical:
        fallback_rows = []
        catchment_geometry = catchments.set_index("WFD_CATCHMENT_ID")
        for canonical_key in missing_canonical:
            ed_row = selected.loc[
                selected["CSOED_CANONICAL"] == canonical_key
            ].iloc[0]
            distances = catchments.geometry.distance(ed_row.geometry)
            nearest_idx = distances.idxmin()
            nearest = catchments.loc[nearest_idx]
            fallback_rows.append(
                {
                    "CSOED_CANONICAL": canonical_key,
                    "WFD_CATCHMENT_ID": nearest["WFD_CATCHMENT_ID"],
                    "WFD_CATCHMENT": nearest["WFD_CATCHMENT"],
                    "COLM_CATCHMENT": nearest["COLM_CATCHMENT"],
                    "INTERSECT_AREA_HA": 0.0,
                    "ED_AREA_HA": float(ed_row["_ED_AREA_HA"]),
                    "ED_CATCHMENT_WEIGHT": 1.0,
                    "ED_COVERAGE_SHARE": 0.0,
                    "ASSIGNMENT_METHOD": "nearest_catchment_fallback",
                    "NEAREST_DISTANCE_M": float(distances.loc[nearest_idx]),
                }
            )
        grouped = pd.concat(
            [grouped, pd.DataFrame(fallback_rows)],
            ignore_index=True,
            sort=False,
        )

    source = base_keys.copy()
    source["CSOED_CANONICAL"] = source[baseline_key].map(canonical_csoed)
    if source["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("Baseline contains duplicate canonical ED identifiers.")
    grouped = grouped.merge(
        source,
        on="CSOED_CANONICAL",
        how="left",
        validate="many_to_one",
    )

    missing = sorted(
        set(source["CSOED_CANONICAL"])
        - set(grouped["CSOED_CANONICAL"])
    )
    if missing:
        raise ValueError(
            f"{len(missing)} model EDs remain unassigned after nearest-catchment "
            f"fallback; examples={missing[:10]}"
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
            "ASSIGNMENT_METHOD",
            "NEAREST_DISTANCE_M",
        ]
    ].sort_values(
        [baseline_key, "WFD_CATCHMENT_ID"],
        kind="stable",
    ).reset_index(drop=True)


def aggregate_to_wfd_catchments(
    master: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
    ed_key: str = "CSOED",
) -> pd.DataFrame:
    """Aggregate the ED x year master to official WFD catchment x year.

    Additive quantities are split by ED-catchment area weights. Higher-level
    average holding size is recomputed from aggregate area/holdings, while
    average holder age is weighted by the holdings represented in each
    fractional ED contribution.
    """
    columns = _existing_additive(master, additive_columns)
    if master.duplicated([year_col, ed_key]).any():
        raise ValueError("Master must contain one row per ED x year.")

    source_columns = [year_col, ed_key, *columns]
    include_age = (
        "AVERAGE_AGE_OF_HOLDER" in master.columns
        and "AGRICULTURAL_HOLDINGS" in columns
    )
    if include_age:
        source_columns.append("AVERAGE_AGE_OF_HOLDER")

    weights = crosswalk[
        [
            ed_key,
            "WFD_CATCHMENT_ID",
            "WFD_CATCHMENT",
            "ED_CATCHMENT_WEIGHT",
        ]
    ].copy()
    merged = master[source_columns].merge(
        weights,
        on=ed_key,
        how="left",
        validate="many_to_many",
    )
    if merged["ED_CATCHMENT_WEIGHT"].isna().any():
        missing = (
            merged.loc[
                merged["ED_CATCHMENT_WEIGHT"].isna(),
                ed_key,
            ]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(f"Crosswalk missing model EDs; examples={missing[:10]}")

    w = pd.to_numeric(
        merged["ED_CATCHMENT_WEIGHT"], errors="raise"
    ).to_numpy(dtype=float)
    weighted = merged[columns].apply(pd.to_numeric, errors="raise").multiply(
        w,
        axis=0,
    )
    weighted[year_col] = merged[year_col].to_numpy()
    weighted["WFD_CATCHMENT_ID"] = merged["WFD_CATCHMENT_ID"].to_numpy()
    weighted["WFD_CATCHMENT"] = merged["WFD_CATCHMENT"].to_numpy()

    group_keys = [year_col, "WFD_CATCHMENT_ID", "WFD_CATCHMENT"]
    out = weighted.groupby(group_keys, as_index=False)[columns].sum()

    age_numerator = age_denominator = None
    if include_age:
        holdings = pd.to_numeric(
            merged["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        age = pd.to_numeric(
            merged["AVERAGE_AGE_OF_HOLDER"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(age)
        age_work = merged[group_keys].copy()
        age_work["_AGE_NUM"] = np.where(valid, age * holdings * w, 0.0)
        age_work["_AGE_DEN"] = np.where(valid, holdings * w, 0.0)
        age_grouped = age_work.groupby(group_keys, as_index=False)[
            ["_AGE_NUM", "_AGE_DEN"]
        ].sum()
        out = out.merge(age_grouped, on=group_keys, how="left", validate="one_to_one")
        age_numerator = out.pop("_AGE_NUM")
        age_denominator = out.pop("_AGE_DEN")

    out = _attach_structure_metrics(
        out,
        age_numerator=age_numerator,
        age_denominator=age_denominator,
    )
    return out.sort_values(
        [year_col, "WFD_CATCHMENT_ID"],
        kind="stable",
    ).reset_index(drop=True)


# Backward-compatible alias from the first bridge implementation.
aggregate_to_catchments = aggregate_to_wfd_catchments


def aggregate_wfd_to_colm(
    wfd_catchment_year: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
) -> pd.DataFrame:
    """Collapse the official 46 WFD units to Colm's 37 catchment groups.

    Only additive quantities are summed. Farm-structure averages are recomputed
    after aggregation rather than summed across WFD units.
    """
    if "WFD_CATCHMENT" not in wfd_catchment_year.columns:
        raise ValueError("WFD catchment table is missing WFD_CATCHMENT.")

    columns = _existing_additive(wfd_catchment_year, additive_columns)
    id_cols = ["WFD_CATCHMENT"]
    if "WFD_CATCHMENT_ID" in wfd_catchment_year.columns:
        id_cols.append("WFD_CATCHMENT_ID")

    source_columns = [year_col, *id_cols, *columns]
    include_age = (
        "AVERAGE_AGE_OF_HOLDER" in wfd_catchment_year.columns
        and "AGRICULTURAL_HOLDINGS" in columns
    )
    if include_age:
        source_columns.append("AVERAGE_AGE_OF_HOLDER")
    work = wfd_catchment_year[source_columns].copy()

    if "WFD_CATCHMENT_ID" in work.columns:
        work["COLM_CATCHMENT"] = [
            to_colm_catchment_name(name, catchment_id)
            for name, catchment_id in zip(
                work["WFD_CATCHMENT"],
                work["WFD_CATCHMENT_ID"],
            )
        ]
    else:
        work["COLM_CATCHMENT"] = work["WFD_CATCHMENT"].map(
            to_colm_catchment_name
        )

    unknown = sorted(set(work["COLM_CATCHMENT"]) - set(COLM_CATCHMENTS))
    if unknown:
        raise ValueError(
            f"Unexpected Colm catchment names after harmonisation: {unknown}"
        )

    group_keys = [year_col, "COLM_CATCHMENT"]
    out = work.groupby(group_keys, as_index=False)[columns].sum()

    age_numerator = age_denominator = None
    if include_age:
        holdings = pd.to_numeric(
            work["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        age = pd.to_numeric(
            work["AVERAGE_AGE_OF_HOLDER"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(age)
        age_work = work[group_keys].copy()
        age_work["_AGE_NUM"] = np.where(valid, age * holdings, 0.0)
        age_work["_AGE_DEN"] = np.where(valid, holdings, 0.0)
        age_grouped = age_work.groupby(group_keys, as_index=False)[
            ["_AGE_NUM", "_AGE_DEN"]
        ].sum()
        out = out.merge(age_grouped, on=group_keys, how="left", validate="one_to_one")
        age_numerator = out.pop("_AGE_NUM")
        age_denominator = out.pop("_AGE_DEN")

    out = _attach_structure_metrics(
        out,
        age_numerator=age_numerator,
        age_denominator=age_denominator,
    )
    return out.sort_values(
        [year_col, "COLM_CATCHMENT"],
        kind="stable",
    ).reset_index(drop=True)


def aggregate_to_counties(
    master: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
    county_col: str = "County",
) -> pd.DataFrame:
    """Aggregate ED quantities to county x year with valid structure metrics."""
    columns = _existing_additive(master, additive_columns)
    if county_col not in master.columns:
        raise ValueError(f"Master is missing county column: {county_col}")

    group_keys = [year_col, county_col]
    out = master.groupby(group_keys, as_index=False)[columns].sum()

    age_numerator = age_denominator = None
    if (
        "AVERAGE_AGE_OF_HOLDER" in master.columns
        and "AGRICULTURAL_HOLDINGS" in columns
    ):
        holdings = pd.to_numeric(
            master["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        age = pd.to_numeric(
            master["AVERAGE_AGE_OF_HOLDER"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(age)
        age_work = master[group_keys].copy()
        age_work["_AGE_NUM"] = np.where(valid, age * holdings, 0.0)
        age_work["_AGE_DEN"] = np.where(valid, holdings, 0.0)
        age_grouped = age_work.groupby(group_keys, as_index=False)[
            ["_AGE_NUM", "_AGE_DEN"]
        ].sum()
        out = out.merge(age_grouped, on=group_keys, how="left", validate="one_to_one")
        age_numerator = out.pop("_AGE_NUM")
        age_denominator = out.pop("_AGE_DEN")

    out = _attach_structure_metrics(
        out,
        age_numerator=age_numerator,
        age_denominator=age_denominator,
    )
    return out.sort_values(
        [year_col, county_col],
        kind="stable",
    ).reset_index(drop=True)


def aggregate_to_national(
    master: pd.DataFrame,
    *,
    additive_columns: Iterable[str] | None = None,
    year_col: str = "YEAR",
) -> pd.DataFrame:
    """Aggregate ED quantities to one Ireland row per year."""

    columns = _existing_additive(master, additive_columns)
    out = master.groupby(year_col, as_index=False)[columns].sum()

    age_numerator = age_denominator = None
    if (
        "AVERAGE_AGE_OF_HOLDER" in master.columns
        and "AGRICULTURAL_HOLDINGS" in columns
    ):
        holdings = pd.to_numeric(
            master["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        age = pd.to_numeric(
            master["AVERAGE_AGE_OF_HOLDER"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(age)
        age_work = master[[year_col]].copy()
        age_work["_AGE_NUM"] = np.where(valid, age * holdings, 0.0)
        age_work["_AGE_DEN"] = np.where(valid, holdings, 0.0)
        age_grouped = age_work.groupby(year_col, as_index=False)[
            ["_AGE_NUM", "_AGE_DEN"]
        ].sum()
        out = out.merge(age_grouped, on=year_col, how="left", validate="one_to_one")
        age_numerator = out.pop("_AGE_NUM")
        age_denominator = out.pop("_AGE_DEN")

    out = _attach_structure_metrics(
        out,
        age_numerator=age_numerator,
        age_denominator=age_denominator,
    )
    out.insert(1, "GEOGRAPHY", "Ireland")
    return out.sort_values(year_col, kind="stable").reset_index(drop=True)


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
    national = (
        master.groupby(year_col, as_index=False)[columns]
        .sum()
        .set_index(year_col)
    )
    derived = (
        aggregated.groupby(year_col, as_index=False)[columns]
        .sum()
        .set_index(year_col)
    )
    if set(national.index) != set(derived.index):
        raise AssertionError(
            f"{geography_col} aggregation has a different year universe."
        )

    rows = []
    failed = []
    for year in national.index:
        for column in columns:
            expected = float(national.loc[year, column])
            actual = float(derived.loc[year, column])
            diff = actual - expected
            rows.append(
                {
                    year_col: year,
                    "GEOGRAPHY": geography_col,
                    "VARIABLE": column,
                    "NATIONAL": expected,
                    "AGGREGATED": actual,
                    "DIFF": diff,
                }
            )
            if not np.isclose(actual, expected, rtol=0, atol=atol):
                failed.append((year, column, diff))

    if failed:
        raise AssertionError(
            f"{geography_col} aggregation failed national closure; "
            f"examples={failed[:10]}"
        )
    return pd.DataFrame(rows)
