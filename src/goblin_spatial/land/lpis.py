"""LPIS parcel preprocessing and Electoral Division opportunity context.

The historical GOBLIN-Spatial baseline remains non-spatial and authoritative for
livestock and land accounting.  LPIS is attached only downstream as a 2020/2025
spatial context layer.  Parcel geometry is intersected with the exact SAPS ED
universe used by the model and aggregated to a compact ED-year control table.

Important accounting rules
--------------------------

* ``CLAIMED_AREA_HA`` is the principal LPIS agricultural accounting quantity.
* Commonage fractions are applied to eligible/digitised/reference diagnostics,
  not to claimed area a second time.
* ``ALL_GRASSLAND`` in the validated GOBLIN-Spatial ED baseline remains the
  controlling grassland total.  LPIS describes observed grass composition and
  spatial context; it never replaces that total.
* LPIS 2020 is used only with a 2020 scenario baseline and LPIS 2025 only with a
  2025 scenario baseline.  No intervening or future LPIS state is fabricated.
* Parcel intersections create the model ``CSOED`` linkage from geometry.  ED
  names are retained for QA only and are not the joining authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries

try:  # optional geospatial dependency
    import geopandas as gpd
    import shapely
except ImportError as exc:  # pragma: no cover - import guard only
    gpd = None
    shapely = None
    _GEO_IMPORT_ERROR = exc
else:
    _GEO_IMPORT_ERROR = None


SUPPORTED_LPIS_YEARS = (2020, 2025)

LPIS_PROFILE_AREA_COLUMNS = (
    "LPIS_CLAIMED_AG_HA",
    "LPIS_ELIGIBLE_AG_HA",
    "LPIS_REFERENCE_AG_HA",
    "LPIS_SPATIAL_FOOTPRINT_HA",
    "LPIS_CLAIMED_GRASS_HA",
    "LPIS_ELIGIBLE_GRASS_HA",
    "LPIS_PERMANENT_PASTURE_HA",
    "LPIS_LOW_INPUT_GRASS_HA",
    "LPIS_TEMPORARY_GRASS_HA",
    "LPIS_HAY_MEADOW_HA",
    "LPIS_PEAT_GRASS_HA",
    "LPIS_RIPARIAN_GRASS_HA",
    "LPIS_OTHER_GRASS_HA",
    "LPIS_COMMONAGE_GRASS_HA",
    "LPIS_ANC_GRASS_HA",
    "LPIS_ENV_SCHEME_GRASS_HA",
    "LPIS_ORGANIC_GRASS_HA",
    "LPIS_BOG_PEAT_CONTEXT_HA",
    "LPIS_HABITAT_CONTEXT_HA",
    "LPIS_FORESTRY_EXISTING_CONTEXT_HA",
    "LPIS_FORESTRY_ELIGIBLE_CONTEXT_HA",
    "LPIS_FORESTRY_INELIGIBLE_CONTEXT_HA",
)

LPIS_GRASS_SHARE_COLUMNS = {
    "LPIS_PERMANENT_PASTURE_SHARE": "LPIS_PERMANENT_PASTURE_HA",
    "LPIS_LOW_INPUT_GRASS_SHARE": "LPIS_LOW_INPUT_GRASS_HA",
    "LPIS_TEMPORARY_GRASS_SHARE": "LPIS_TEMPORARY_GRASS_HA",
    "LPIS_HAY_MEADOW_SHARE": "LPIS_HAY_MEADOW_HA",
    "LPIS_PEAT_GRASS_SHARE": "LPIS_PEAT_GRASS_HA",
    "LPIS_RIPARIAN_GRASS_SHARE": "LPIS_RIPARIAN_GRASS_HA",
    "LPIS_OTHER_GRASS_SHARE": "LPIS_OTHER_GRASS_HA",
    "LPIS_COMMONAGE_GRASS_SHARE": "LPIS_COMMONAGE_GRASS_HA",
    "LPIS_ANC_GRASS_SHARE": "LPIS_ANC_GRASS_HA",
    "LPIS_ENV_SCHEME_GRASS_SHARE": "LPIS_ENV_SCHEME_GRASS_HA",
    "LPIS_ORGANIC_GRASS_SHARE": "LPIS_ORGANIC_GRASS_HA",
}


def _require_geo() -> None:
    if gpd is None or shapely is None:
        raise ImportError(
            "LPIS spatial preprocessing requires optional geospatial dependencies. "
            "Install with: pip install 'goblin-spatial[geo]'"
        ) from _GEO_IMPORT_ERROR


def _first_column(frame: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    lookup = {str(column).lower(): column for column in frame.columns}
    for alias in aliases:
        found = lookup.get(str(alias).lower())
        if found is not None:
            return found
    return None


def _numeric_from(
    frame: pd.DataFrame,
    aliases: Iterable[str],
    *,
    default: float = np.nan,
) -> pd.Series:
    column = _first_column(frame, aliases)
    if column is None:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _string_from(frame: pd.DataFrame, aliases: Iterable[str]) -> pd.Series:
    column = _first_column(frame, aliases)
    if column is None:
        return pd.Series(pd.NA, index=frame.index, dtype="string")
    return frame[column].astype("string")


def _bool_from(frame: pd.DataFrame, aliases: Iterable[str]) -> pd.Series | None:
    column = _first_column(frame, aliases)
    if column is None:
        return None
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
        return numeric.ne(0.0)
    text = values.astype("string").str.strip().str.upper()
    true_values = {"Y", "YES", "TRUE", "T", "1"}
    false_values = {"N", "NO", "FALSE", "F", "0", "", "<NA>", "NAN", "NONE"}
    unknown = text.dropna().loc[~text.isin(true_values | false_values)].unique().tolist()
    if unknown:
        raise ValueError(
            f"LPIS flag column {column!r} contains unrecognised values: {unknown[:10]}"
        )
    return text.isin(true_values).fillna(False).astype(bool)


def _fallback_land_use_group(crop: object) -> str:
    text = "" if pd.isna(crop) else str(crop).strip().upper()
    if not text:
        return "UNKNOWN"
    if "LOW INPUT PEAT GRASS" in text:
        return "PEAT_GRASSLAND"
    if "RIPARIAN" in text and "GRASS" in text:
        return "RIPARIAN_GRASS"
    if ("LOW INPUT" in text or "EXTENSIVELY GRAZED" in text) and (
        "GRASS" in text or "PASTURE" in text
    ):
        return "LOW_INPUT_GRASS"
    if "HAY MEADOW" in text:
        return "HAY_MEADOW"
    if (
        "GRASS YEAR" in text
        or "GRASS YEARS" in text
        or "RED CLOVER GRASS" in text
        or "ARABLE SILAGE" in text and "GRASS" in text
    ):
        return "TEMPORARY_GRASS"
    if "PERMANENT PASTURE" in text:
        return "PERMANENT_PASTURE"
    if "BOG" in text or "PEAT" in text and "GRASS" not in text:
        return "BOG_PEAT"
    if "DESIGNATED HABITAT" in text or text == "HABITAT" or " HABITAT" in text:
        return "HABITAT"
    if "FORESTRY INELIGIBLE" in text:
        return "FORESTRY_INELIGIBLE"
    if "FORESTRY ELIGIBLE" in text:
        return "FORESTRY_ELIGIBLE"
    if "FORESTRY" in text or "WOODLAND" in text:
        return "FORESTRY_EXISTING"
    if text == "WILLOW" or "WILLOW" in text:
        return "WILLOW"
    if "MISCANTHUS" in text or "ENERGY GRASS" in text:
        return "ENERGY_GRASS"
    if "SHORT ROTATION COPPICE" in text:
        return "SHORT_ROTATION_COPPICE"
    if "SCRUB" in text:
        return "SCRUB"
    if "GRASS" in text or "PASTURE" in text:
        return "OTHER_GRASS"
    if any(value in text for value in ("BUILDING", "FARMYARD", "ROAD", "WATER")):
        return "NON_AGRICULTURAL"
    return "OTHER_AGRICULTURE"


def normalise_lpis_records(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    """Return the harmonised LPIS fields required by the ED overlay.

    The function accepts either the already reduced GOBLIN LPIS schema or the
    corresponding source aliases used in the 2020/2025 DAFM releases.  It is
    intentionally conservative: original crop descriptions remain available and
    the official 2025 grassland flag is preferred when present.
    """

    year = int(year)
    if year not in SUPPORTED_LPIS_YEARS:
        raise ValueError(f"LPIS year must be one of {SUPPORTED_LPIS_YEARS}")

    out = frame.copy()
    out["LPIS_YEAR"] = year
    if "LPIS_ROW_ID" not in out.columns:
        out["LPIS_ROW_ID"] = np.arange(1, len(out) + 1, dtype=np.int64)

    out["PARCEL_ID"] = _string_from(out, ("PARCEL_ID", "PARC_LAB", "par_lab"))
    out["CLAIMED_AREA_HA"] = _numeric_from(
        out, ("CLAIMED_AREA_HA", "CLAIM_AREA", "claim_area"), default=0.0
    ).fillna(0.0)
    out["PARCEL_AREA_HA"] = _numeric_from(
        out, ("PARCEL_AREA_HA", "DIGIT_AREA", "digitised"), default=0.0
    ).fillna(0.0)
    out["ELIGIBLE_AREA_HA"] = _numeric_from(
        out, ("ELIGIBLE_AREA_HA", "MEA", "eh_area"), default=0.0
    ).fillna(0.0)
    out["REFERENCE_AREA_HA"] = _numeric_from(
        out, ("REFERENCE_AREA_HA", "ref_area"), default=np.nan
    )
    out["CROP_DESCRIPTION"] = _string_from(
        out, ("CROP_DESCRIPTION", "CROP_DESC", "crop")
    )

    commonage = _bool_from(out, ("IS_COMMONAGE", "COM_IND", "commonage_ind"))
    numerator = _numeric_from(
        out, ("COMMONAGE_NUMERATOR", "COM_NUM", "commonage_num"), default=np.nan
    )
    denominator = _numeric_from(
        out, ("COMMONAGE_DENOMINATOR", "COM_DEN", "commonage_den"), default=np.nan
    )
    existing_fraction = _numeric_from(
        out, ("COMMONAGE_FRACTION",), default=np.nan
    )
    if commonage is None:
        commonage = (numerator.notna() & denominator.gt(0)).astype(bool)
    fraction = existing_fraction.copy()
    derive = fraction.isna() & commonage
    fraction.loc[derive] = numerator.loc[derive] / denominator.loc[derive]
    fraction.loc[~commonage] = 1.0
    malformed = commonage & (
        fraction.isna() | ~np.isfinite(fraction) | fraction.le(0.0) | fraction.gt(1.0 + 1e-12)
    )
    if malformed.any():
        raise ValueError(
            f"{int(malformed.sum()):,} commonage LPIS rows have no usable ownership fraction"
        )
    out["IS_COMMONAGE"] = commonage.astype(bool)
    out["COMMONAGE_FRACTION"] = fraction.clip(0.0, 1.0).astype(float)

    share_digitised = _numeric_from(out, ("SHARE_DIGITISED_HA",), default=np.nan)
    share_eligible = _numeric_from(out, ("SHARE_ELIGIBLE_HA",), default=np.nan)
    share_reference = _numeric_from(out, ("SHARE_REFERENCE_HA",), default=np.nan)
    out["SHARE_DIGITISED_HA"] = share_digitised.fillna(
        out["PARCEL_AREA_HA"] * out["COMMONAGE_FRACTION"]
    )
    out["SHARE_ELIGIBLE_HA"] = share_eligible.fillna(
        out["ELIGIBLE_AREA_HA"] * out["COMMONAGE_FRACTION"]
    )
    reference_derived = out["REFERENCE_AREA_HA"] * out["COMMONAGE_FRACTION"]
    out["SHARE_REFERENCE_HA"] = share_reference.where(
        share_reference.notna(), reference_derived
    )

    existing_group = _string_from(out, ("LAND_USE_GROUP",))
    fallback_group = out["CROP_DESCRIPTION"].map(_fallback_land_use_group).astype("string")
    out["LAND_USE_GROUP"] = existing_group.where(existing_group.notna(), fallback_group)

    official_grass = _bool_from(out, ("IS_GRASSLAND",))
    if official_grass is None and year == 2025:
        official_grass = _bool_from(out, ("grasslnd",))
    crop_grass = out["LAND_USE_GROUP"].isin(
        {
            "PEAT_GRASSLAND",
            "RIPARIAN_GRASS",
            "LOW_INPUT_GRASS",
            "HAY_MEADOW",
            "TEMPORARY_GRASS",
            "PERMANENT_PASTURE",
            "OTHER_GRASS",
        }
    )
    out["IS_GRASSLAND"] = (
        official_grass.astype(bool) if official_grass is not None else crop_grass.astype(bool)
    )
    out["GRASSLAND_METHOD"] = "DAFM_FLAG" if official_grass is not None and year == 2025 else "CROP_DERIVED"

    subtype_groups: Mapping[str, set[str]] = {
        "IS_PERMANENT_PASTURE": {"PERMANENT_PASTURE"},
        "IS_LOW_INPUT_GRASS": {"LOW_INPUT_GRASS"},
        "IS_HAY_MEADOW": {"HAY_MEADOW"},
        "IS_TEMPORARY_GRASS": {"TEMPORARY_GRASS"},
        "IS_PEAT_GRASSLAND": {"PEAT_GRASSLAND"},
        "IS_RIPARIAN_GRASS": {"RIPARIAN_GRASS"},
    }
    for flag, groups in subtype_groups.items():
        existing = _bool_from(out, (flag,))
        out[flag] = (
            existing.astype(bool)
            if existing is not None
            else out["LAND_USE_GROUP"].isin(groups).astype(bool)
        )
    subtype_union = np.zeros(len(out), dtype=bool)
    for flag in subtype_groups:
        subtype_union |= out[flag].to_numpy(dtype=bool)
    out["IS_OTHER_GRASS"] = out["IS_GRASSLAND"].to_numpy(dtype=bool) & ~subtype_union

    direct_flags = {
        "IS_ANC": ("IS_ANC", "ANC_IND", "anc"),
        "IS_AGRI_ENVIRONMENT": (
            "IS_AGRI_ENVIRONMENT",
            "IS_ACRES",
            "GLAS_IND",
            "acres",
        ),
        "IS_ORGANIC": ("IS_ORGANIC", "ORG_STATUS", "organics"),
        "IS_BOG_PEAT": ("IS_BOG_PEAT",),
        "IS_HABITAT": ("IS_HABITAT",),
        "IS_FORESTRY_EXISTING": ("IS_FORESTRY_EXISTING",),
        "IS_FORESTRY_ELIGIBLE_SOURCE": ("IS_FORESTRY_ELIGIBLE_SOURCE",),
        "IS_FORESTRY_INELIGIBLE_SOURCE": ("IS_FORESTRY_INELIGIBLE_SOURCE",),
    }
    group_defaults = {
        "IS_BOG_PEAT": {"BOG_PEAT"},
        "IS_HABITAT": {"HABITAT"},
        "IS_FORESTRY_EXISTING": {"FORESTRY_EXISTING"},
        "IS_FORESTRY_ELIGIBLE_SOURCE": {"FORESTRY_ELIGIBLE"},
        "IS_FORESTRY_INELIGIBLE_SOURCE": {"FORESTRY_INELIGIBLE"},
    }
    for flag, aliases in direct_flags.items():
        existing = _bool_from(out, aliases)
        if existing is not None:
            out[flag] = existing.astype(bool)
        elif flag in group_defaults:
            out[flag] = out["LAND_USE_GROUP"].isin(group_defaults[flag]).astype(bool)
        else:
            out[flag] = False

    out["RECORD_CLASS"] = np.where(
        out["CLAIMED_AREA_HA"].gt(0), "CLAIMED_LPIS", "CONTEXT_ONLY_LPIS"
    )
    return out


def _profile_metric_arrays(candidate: pd.DataFrame, fraction: np.ndarray) -> dict[str, np.ndarray]:
    claimed = pd.to_numeric(candidate["CLAIMED_AREA_HA"], errors="coerce").fillna(0.0).to_numpy(float)
    eligible = pd.to_numeric(candidate["SHARE_ELIGIBLE_HA"], errors="coerce").fillna(0.0).to_numpy(float)
    digitised = pd.to_numeric(candidate["SHARE_DIGITISED_HA"], errors="coerce").fillna(0.0).to_numpy(float)
    reference = pd.to_numeric(candidate["SHARE_REFERENCE_HA"], errors="coerce").fillna(0.0).to_numpy(float)
    grass = candidate["IS_GRASSLAND"].astype(bool).to_numpy()

    def claim_flag(column: str) -> np.ndarray:
        return claimed * candidate[column].astype(bool).to_numpy() * fraction

    metrics = {
        "LPIS_CLAIMED_AG_HA": claimed * fraction,
        "LPIS_ELIGIBLE_AG_HA": eligible * fraction,
        "LPIS_REFERENCE_AG_HA": reference * fraction,
        "LPIS_SPATIAL_FOOTPRINT_HA": digitised * fraction,
        "LPIS_CLAIMED_GRASS_HA": claimed * grass * fraction,
        "LPIS_ELIGIBLE_GRASS_HA": eligible * grass * fraction,
        "LPIS_PERMANENT_PASTURE_HA": claim_flag("IS_PERMANENT_PASTURE"),
        "LPIS_LOW_INPUT_GRASS_HA": claim_flag("IS_LOW_INPUT_GRASS"),
        "LPIS_TEMPORARY_GRASS_HA": claim_flag("IS_TEMPORARY_GRASS"),
        "LPIS_HAY_MEADOW_HA": claim_flag("IS_HAY_MEADOW"),
        "LPIS_PEAT_GRASS_HA": claim_flag("IS_PEAT_GRASSLAND"),
        "LPIS_RIPARIAN_GRASS_HA": claim_flag("IS_RIPARIAN_GRASS"),
        "LPIS_OTHER_GRASS_HA": claim_flag("IS_OTHER_GRASS"),
        "LPIS_COMMONAGE_GRASS_HA": claimed * grass * candidate["IS_COMMONAGE"].astype(bool).to_numpy() * fraction,
        "LPIS_ANC_GRASS_HA": claimed * grass * candidate["IS_ANC"].astype(bool).to_numpy() * fraction,
        "LPIS_ENV_SCHEME_GRASS_HA": claimed * grass * candidate["IS_AGRI_ENVIRONMENT"].astype(bool).to_numpy() * fraction,
        "LPIS_ORGANIC_GRASS_HA": claimed * grass * candidate["IS_ORGANIC"].astype(bool).to_numpy() * fraction,
        "LPIS_BOG_PEAT_CONTEXT_HA": eligible * candidate["IS_BOG_PEAT"].astype(bool).to_numpy() * fraction,
        "LPIS_HABITAT_CONTEXT_HA": eligible * candidate["IS_HABITAT"].astype(bool).to_numpy() * fraction,
        "LPIS_FORESTRY_EXISTING_CONTEXT_HA": eligible * candidate["IS_FORESTRY_EXISTING"].astype(bool).to_numpy() * fraction,
        "LPIS_FORESTRY_ELIGIBLE_CONTEXT_HA": eligible * candidate["IS_FORESTRY_ELIGIBLE_SOURCE"].astype(bool).to_numpy() * fraction,
        "LPIS_FORESTRY_INELIGIBLE_CONTEXT_HA": eligible * candidate["IS_FORESTRY_INELIGIBLE_SOURCE"].astype(bool).to_numpy() * fraction,
    }
    return metrics


def build_ed_lpis_profile(
    lpis,
    ed_gdf,
    baseline: pd.DataFrame,
    *,
    year: int,
    baseline_key_col: str = "CSOED",
    ed_key_col: str = "CSOED",
    target_crs: str = "EPSG:2157",
    chunk_size: int = 50_000,
) -> pd.DataFrame:
    """Intersect one LPIS snapshot with the exact GOBLIN-Spatial ED universe.

    Record-level accounting values are distributed by the fraction of each LPIS
    source geometry falling inside an ED.  This is the only spatial operation
    that creates the LPIS-to-model ED link.
    """

    _require_geo()
    year = int(year)
    if year not in SUPPORTED_LPIS_YEARS:
        raise ValueError(f"LPIS year must be one of {SUPPORTED_LPIS_YEARS}")
    if int(chunk_size) <= 0:
        raise ValueError("chunk_size must be positive")
    if not isinstance(lpis, gpd.GeoDataFrame):
        raise TypeError("lpis must be a GeoDataFrame")
    if lpis.crs is None or ed_gdf.crs is None:
        raise ValueError("LPIS and ED geometry must both have a defined CRS")

    baseline_one = baseline.drop_duplicates(subset=[baseline_key_col]).copy()
    baseline_keyed = baseline_one.copy()
    baseline_keyed["CSOED_CANONICAL"] = baseline_keyed[baseline_key_col].map(
        canonical_csoed
    )
    if baseline_keyed["CSOED_CANONICAL"].eq("").any():
        raise ValueError(f"{baseline_key_col} contains blank ED identifiers")
    if baseline_keyed["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("baseline contains duplicate canonical ED identifiers")
    ed_selected = select_baseline_ed_geometries(
        baseline_one,
        ed_gdf,
        baseline_key=baseline_key_col,
        ed_key=ed_key_col,
    )
    ed_selected = ed_selected.to_crs(target_crs).copy()
    invalid_ed = ~ed_selected.geometry.is_valid
    if invalid_ed.any():
        ed_selected.loc[invalid_ed, "geometry"] = ed_selected.loc[invalid_ed, "geometry"].map(
            shapely.make_valid
        )
    if ed_selected.geometry.isna().any() or ed_selected.geometry.is_empty.any():
        raise ValueError("selected model ED geography contains empty geometry")

    work = normalise_lpis_records(lpis, year)
    if not isinstance(work, gpd.GeoDataFrame):
        work = gpd.GeoDataFrame(work, geometry=lpis.geometry.name, crs=lpis.crs)
    work = work.to_crs(target_crs)
    work = work.loc[work.geometry.notna() & ~work.geometry.is_empty].copy()
    invalid = ~work.geometry.is_valid
    if invalid.any():
        work.loc[invalid, "geometry"] = work.loc[invalid, "geometry"].map(shapely.make_valid)
    work["_SOURCE_GEOMETRY_HA"] = work.geometry.area / 10_000.0
    work = work.loc[work["_SOURCE_GEOMETRY_HA"].gt(0)].copy()

    metric_columns = [
        "LPIS_ROW_ID",
        "CLAIMED_AREA_HA",
        "SHARE_ELIGIBLE_HA",
        "SHARE_DIGITISED_HA",
        "SHARE_REFERENCE_HA",
        "IS_GRASSLAND",
        "IS_PERMANENT_PASTURE",
        "IS_LOW_INPUT_GRASS",
        "IS_TEMPORARY_GRASS",
        "IS_HAY_MEADOW",
        "IS_PEAT_GRASSLAND",
        "IS_RIPARIAN_GRASS",
        "IS_OTHER_GRASS",
        "IS_COMMONAGE",
        "IS_ANC",
        "IS_AGRI_ENVIRONMENT",
        "IS_ORGANIC",
        "IS_BOG_PEAT",
        "IS_HABITAT",
        "IS_FORESTRY_EXISTING",
        "IS_FORESTRY_ELIGIBLE_SOURCE",
        "IS_FORESTRY_INELIGIBLE_SOURCE",
        "_SOURCE_GEOMETRY_HA",
        "geometry",
    ]
    ed_spatial = ed_selected[["CSOED_CANONICAL", "geometry"]].copy()
    partials: list[pd.DataFrame] = []

    for start in range(0, len(work), int(chunk_size)):
        chunk = work.iloc[start : start + int(chunk_size)][metric_columns].copy()
        candidate = gpd.sjoin(
            chunk,
            ed_spatial,
            how="inner",
            predicate="intersects",
        )
        if candidate.empty:
            continue
        right_geometry = ed_spatial.geometry.iloc[
            candidate["index_right"].to_numpy(dtype=int)
        ].to_numpy()
        intersection = shapely.intersection(candidate.geometry.to_numpy(), right_geometry)
        intersection_ha = shapely.area(intersection) / 10_000.0
        source_ha = pd.to_numeric(candidate["_SOURCE_GEOMETRY_HA"], errors="raise").to_numpy(float)
        fraction = np.divide(
            intersection_ha,
            source_ha,
            out=np.zeros(len(candidate), dtype=float),
            where=source_ha > 0,
        )
        fraction = np.clip(fraction, 0.0, 1.0)
        positive = intersection_ha > 1e-10
        if not positive.any():
            continue
        candidate = candidate.loc[positive].copy()
        fraction = fraction[positive]
        intersection_ha = intersection_ha[positive]

        metrics = _profile_metric_arrays(candidate, fraction)
        block = pd.DataFrame({"CSOED_CANONICAL": candidate["CSOED_CANONICAL"].astype(str).to_numpy()})
        for column, values in metrics.items():
            block[column] = values
        block["LPIS_INTERSECTION_GEOMETRY_HA"] = intersection_ha
        block["LPIS_SOURCE_RECORDS_INTERSECTING_ED"] = 1
        block["LPIS_GRASS_SOURCE_RECORDS_INTERSECTING_ED"] = candidate[
            "IS_GRASSLAND"
        ].astype(int).to_numpy()
        partials.append(block.groupby("CSOED_CANONICAL", as_index=False).sum(numeric_only=True))

    if partials:
        aggregated = (
            pd.concat(partials, ignore_index=True)
            .groupby("CSOED_CANONICAL", as_index=False)
            .sum(numeric_only=True)
        )
    else:
        aggregated = pd.DataFrame(columns=["CSOED_CANONICAL", *LPIS_PROFILE_AREA_COLUMNS])

    label_columns = [baseline_key_col]
    for column in ("EDNAME", "COUNTYNAME", "County", "ED"):
        if column in baseline_keyed.columns and column not in label_columns:
            label_columns.append(column)
    labels = baseline_keyed[["CSOED_CANONICAL", *label_columns]].copy()
    result = labels.merge(aggregated, on="CSOED_CANONICAL", how="left", validate="one_to_one")
    numeric_profile = [
        *LPIS_PROFILE_AREA_COLUMNS,
        "LPIS_INTERSECTION_GEOMETRY_HA",
        "LPIS_SOURCE_RECORDS_INTERSECTING_ED",
        "LPIS_GRASS_SOURCE_RECORDS_INTERSECTING_ED",
    ]
    for column in numeric_profile:
        if column not in result.columns:
            result[column] = 0.0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)

    result.insert(0, "LPIS_YEAR", year)
    result = result.rename(columns={baseline_key_col: "CSOED"})
    result["LPIS_PROFILE_VERSION"] = "2.0"
    if len(result) != baseline_keyed["CSOED_CANONICAL"].nunique():
        raise AssertionError("LPIS ED profile does not contain exactly the model ED universe")
    if result["CSOED_CANONICAL"].duplicated().any():
        raise AssertionError("LPIS ED profile contains duplicate model ED keys")
    return result.sort_values("CSOED_CANONICAL", kind="stable").reset_index(drop=True)


def read_ed_lpis_profile(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Read and validate the compact two-snapshot ED LPIS control."""

    if isinstance(source, pd.DataFrame):
        frame = source.copy()
    else:
        path = Path(source)
        if path.suffix.lower() == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_csv(path, low_memory=False)
    required = {"LPIS_YEAR", "CSOED", "LPIS_CLAIMED_GRASS_HA", "LPIS_ELIGIBLE_GRASS_HA"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"ED LPIS profile missing columns: {missing}")
    frame["LPIS_YEAR"] = pd.to_numeric(frame["LPIS_YEAR"], errors="raise").astype(int)
    if not set(frame["LPIS_YEAR"].unique()).issubset(SUPPORTED_LPIS_YEARS):
        raise ValueError(f"ED LPIS profile contains unsupported years; expected {SUPPORTED_LPIS_YEARS}")
    frame["CSOED_CANONICAL"] = frame["CSOED"].map(canonical_csoed)
    if (frame["CSOED_CANONICAL"] == "").any():
        raise ValueError("ED LPIS profile contains blank CSOED keys")
    if frame[["LPIS_YEAR", "CSOED_CANONICAL"]].duplicated().any():
        raise ValueError("ED LPIS profile must contain one row per LPIS_YEAR and CSOED")
    for column in LPIS_PROFILE_AREA_COLUMNS:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="raise").astype(float)
            if (~np.isfinite(values)).any() or (values < -1e-9).any():
                raise ValueError(f"{column} must be finite and non-negative")
            frame[column] = np.maximum(values, 0.0)
    return frame


def add_ed_lpis_context(
    frame: pd.DataFrame,
    profile: str | Path | pd.DataFrame,
    *,
    baseline_year: int | None = None,
) -> pd.DataFrame:
    """Attach the matching 2020/2025 LPIS snapshot to downstream ED results.

    The merge is exact on canonical ``CSOED`` and never alters the model's own
    identifier or ``ALL_GRASSLAND``.  Composition shares use LPIS claimed grass
    as their denominator; EDs with zero LPIS claimed grass retain missing shares
    and therefore fall back to the soil-only opportunity screen.
    """

    if "CSOED" not in frame.columns:
        raise ValueError("LPIS context attachment requires CSOED")
    if baseline_year is None:
        if "SCENARIO_BASELINE_YEAR" in frame.columns:
            years = pd.to_numeric(frame["SCENARIO_BASELINE_YEAR"], errors="raise").astype(int).unique()
            if len(years) != 1:
                raise ValueError("scenario output contains more than one baseline year")
            baseline_year = int(years[0])
        elif "YEAR" in frame.columns:
            years = pd.to_numeric(frame["YEAR"], errors="coerce").dropna().astype(int).unique()
            supported = [year for year in years if year in SUPPORTED_LPIS_YEARS]
            if len(supported) == 1 and len(years) == 1:
                baseline_year = int(supported[0])
        if baseline_year is None:
            raise ValueError(
                "LPIS context needs baseline_year=2020/2025 or a unique SCENARIO_BASELINE_YEAR"
            )
    baseline_year = int(baseline_year)
    if baseline_year not in SUPPORTED_LPIS_YEARS:
        raise ValueError(f"LPIS context supports baseline years {SUPPORTED_LPIS_YEARS}")

    lpis = read_ed_lpis_profile(profile)
    lpis = lpis.loc[lpis["LPIS_YEAR"].eq(baseline_year)].copy()
    if lpis.empty:
        raise ValueError(f"ED LPIS profile has no {baseline_year} snapshot")

    out = frame.copy()
    out["_LPIS_CSOED_KEY"] = out["CSOED"].map(canonical_csoed)
    if (out["_LPIS_CSOED_KEY"] == "").any():
        raise ValueError("downstream frame contains blank CSOED keys")
    available = set(lpis["CSOED_CANONICAL"])
    required = set(out["_LPIS_CSOED_KEY"])
    missing = sorted(required - available)
    if missing:
        raise ValueError(
            f"LPIS {baseline_year} profile is missing {len(missing)} model EDs; examples: {missing[:10]}"
        )

    drop_labels = [
        column
        for column in ("CSOED", "EDNAME", "COUNTYNAME", "County", "ED")
        if column in lpis.columns
    ]
    attach = lpis.drop(columns=drop_labels).rename(columns={"CSOED_CANONICAL": "_LPIS_CSOED_KEY"})
    out = out.merge(attach, on="_LPIS_CSOED_KEY", how="left", validate="many_to_one")
    out["LPIS_PROFILE_YEAR"] = baseline_year

    denominator = pd.to_numeric(out["LPIS_CLAIMED_GRASS_HA"], errors="raise").to_numpy(float)
    has_grass = denominator > 1e-12
    out["LPIS_GRASS_CONTEXT_AVAILABLE"] = has_grass
    for share_column, area_column in LPIS_GRASS_SHARE_COLUMNS.items():
        if area_column not in out.columns:
            out[share_column] = np.nan
            continue
        numerator = pd.to_numeric(out[area_column], errors="raise").to_numpy(float)
        out[share_column] = np.divide(
            numerator,
            denominator,
            out=np.full(len(out), np.nan, dtype=float),
            where=has_grass,
        )

    if "ALL_GRASSLAND" in out.columns:
        model_grass = pd.to_numeric(out["ALL_GRASSLAND"], errors="coerce").to_numpy(float)
        out["LPIS_CLAIMED_GRASS_TO_MODEL_GRASS_RATIO"] = np.divide(
            denominator,
            model_grass,
            out=np.full(len(out), np.nan, dtype=float),
            where=model_grass > 1e-12,
        )
    out = out.drop(columns="_LPIS_CSOED_KEY")
    return out
