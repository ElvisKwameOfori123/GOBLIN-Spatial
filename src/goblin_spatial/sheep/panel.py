"""CSO sheep hierarchy and annual ED sheep-panel construction.

The sheep module is independent of cattle. Annual detailed-region AAA09
statistics are the controlling official time series. The fixed 2020 ED sheep
footprint supplies fine-scale spatial weights. County totals are reconstructed
inside regions and are not treated as independent observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate, integer_transport


YEARS = tuple(range(2015, 2026))

REGION_SOURCE_COLS = [
    "Ewes: 2 years and over",
    "Ewes: under 2 years",
    "Rams",
    "Other sheep",
]

ED_CLASS_COLS = [
    "EWES_2_PLUS",
    "EWES_UNDER_2",
    "RAMS",
    "OTHER_SHEEP",
]

IDENTIFIER_CANDIDATES = [
    "ELECTORAL_DIVISIONS",
    "ED",
    "County",
    "EDID",
    "CSOED",
    "CSOED_RAW",
    "EDNAME",
    "COUNTYNAME",
]


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def _load_region_controls(path) -> pd.DataFrame:
    region = pd.read_csv(path)
    required = [
        "Year",
        "Region",
        "Region_Level",
        "UNIT",
        "Total sheep",
        *REGION_SOURCE_COLS,
    ]
    _require_columns(region, required, "AAA09 sheep region controls")

    region["Year"] = pd.to_numeric(region["Year"], errors="raise").astype(int)
    region = region.loc[
        (region["Region_Level"] == "Detailed region")
        & region["Year"].isin(YEARS)
    ].copy()

    if len(region) != 7 * len(YEARS):
        raise AssertionError("AAA09 must contain seven detailed regions for every year")
    if region[["Year", "Region"]].duplicated().any():
        raise AssertionError("duplicate detailed region-year sheep rows")

    numeric = ["Total sheep", *REGION_SOURCE_COLS]
    for column in numeric:
        values = pd.to_numeric(region[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"invalid AAA09 sheep values in {column}")
        region[column] = values
        region[f"{column}__HEAD"] = np.rint(values * 1000.0).astype(np.int64)

    return region


def _load_county_region_map(path) -> pd.DataFrame:
    crosswalk = pd.read_csv(path)
    _require_columns(crosswalk, ["County", "NUTS3_REGION"], "county-region map")
    crosswalk["County"] = crosswalk["County"].map(_normalise_county)
    crosswalk = crosswalk[["County", "NUTS3_REGION"]].drop_duplicates().copy()

    if len(crosswalk) != 26 or crosswalk["County"].nunique() != 26:
        raise AssertionError("county-region map must contain exactly 26 counties")
    if crosswalk["County"].duplicated().any():
        raise AssertionError("county-region map contains duplicate counties")

    return crosswalk.rename(columns={"NUTS3_REGION": "Region"})


def _build_reconciled_2020_anchor(
    ed_path,
    crosswalk: pd.DataFrame,
    region: pd.DataFrame,
    expected_eds: int,
) -> pd.DataFrame:
    ed = pd.read_csv(ed_path)
    _require_columns(ed, ["CSOED", "County", "TOTAL_SHEEP"], "2020 ED baseline")

    ed["County"] = ed["County"].map(_normalise_county)
    ed["TOTAL_SHEEP"] = (
        pd.to_numeric(ed["TOTAL_SHEEP"], errors="raise").round().astype(np.int64)
    )
    if (ed["TOTAL_SHEEP"] < 0).any():
        raise AssertionError("2020 ED baseline contains negative TOTAL_SHEEP")

    if len(ed) != expected_eds or ed["CSOED"].nunique() != expected_eds:
        raise AssertionError(f"expected exactly {expected_eds:,} EDs")
    if ed["CSOED"].duplicated().any():
        raise AssertionError("duplicate CSOED in 2020 ED baseline")

    ed = ed.merge(crosswalk, on="County", how="left", validate="many_to_one")
    if ed["Region"].isna().any():
        missing = sorted(ed.loc[ed["Region"].isna(), "County"].unique())
        raise AssertionError(f"missing county-to-region mapping: {missing}")

    detailed_regions = sorted(region["Region"].unique())
    if set(ed["Region"].unique()) != set(detailed_regions):
        raise AssertionError("ED and AAA09 detailed-region coverage differs")

    ed = ed.sort_values(["County", "CSOED"], kind="stable").reset_index(drop=True)
    ed["TOTAL_SHEEP_2020_ED_INPUT"] = ed["TOTAL_SHEEP"].astype(np.int64)
    ed["ZERO_2020_SPATIAL_WEIGHT"] = ed["TOTAL_SHEEP_2020_ED_INPUT"] == 0
    ed["TOTAL_SHEEP_2020_RECONCILED"] = 0

    for region_name in detailed_regions:
        idx = ed.index[ed["Region"] == region_name]
        weights = ed.loc[idx, "TOTAL_SHEEP_2020_ED_INPUT"].to_numpy(dtype=np.int64)
        source = region.loc[
            (region["Year"] == 2020) & (region["Region"] == region_name)
        ]
        if len(source) != 1:
            raise AssertionError(f"{region_name}: invalid 2020 AAA09 row")
        target = int(source.iloc[0]["Total sheep__HEAD"])
        ed.loc[idx, "TOTAL_SHEEP_2020_RECONCILED"] = hamilton_allocate(
            weights, target
        )

    validation = (
        ed.groupby("Region", as_index=False)["TOTAL_SHEEP_2020_RECONCILED"]
        .sum()
        .merge(
            region.loc[
                region["Year"] == 2020, ["Region", "Total sheep__HEAD"]
            ],
            on="Region",
            how="left",
            validate="one_to_one",
        )
    )
    if int(
        (
            validation["TOTAL_SHEEP_2020_RECONCILED"]
            - validation["Total sheep__HEAD"]
        ).abs().max()
    ) != 0:
        raise AssertionError("2020 ED sheep anchor does not close to AAA09 regions")

    return ed


def _build_county_controls(anchor: pd.DataFrame, region: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct annual county totals/classes inside detailed AAA09 regions."""

    county_anchor = (
        anchor.groupby(["County", "Region"], as_index=False)
        .agg(
            TOTAL_SHEEP_2020_ED_INPUT=("TOTAL_SHEEP_2020_ED_INPUT", "sum"),
            TOTAL_SHEEP_2020_RECONCILED=("TOTAL_SHEEP_2020_RECONCILED", "sum"),
        )
    )
    if len(county_anchor) != 26:
        raise AssertionError("expected 26 reconstructed county sheep anchors")

    rows: list[dict[str, object]] = []

    for year in YEARS:
        for region_name in sorted(region["Region"].unique()):
            counties = (
                county_anchor.loc[county_anchor["Region"] == region_name]
                .sort_values("County", kind="stable")
                .reset_index(drop=True)
            )
            source = region.loc[
                (region["Year"] == year) & (region["Region"] == region_name)
            ]
            if len(source) != 1:
                raise AssertionError(f"{region_name} {year}: invalid AAA09 row")
            source = source.iloc[0]

            total_target = int(source["Total sheep__HEAD"])
            county_weights = counties["TOTAL_SHEEP_2020_RECONCILED"].to_numpy(
                dtype=np.int64
            )
            if year == 2020:
                county_totals = county_weights.copy()
                if int(county_totals.sum()) != total_target:
                    raise AssertionError(
                        f"{region_name}: corrected 2020 county anchors do not close"
                    )
            else:
                county_totals = hamilton_allocate(county_weights, total_target)

            raw_components = np.array(
                [source[f"{column}__HEAD"] for column in REGION_SOURCE_COLS],
                dtype=float,
            )
            if float(raw_components.sum()) <= 0:
                raise AssertionError(f"{region_name} {year}: zero sheep class total")
            regional_class_targets = hamilton_allocate(
                raw_components / raw_components.sum(), total_target
            )
            county_matrix = integer_transport(county_totals, regional_class_targets)

            for i, county_row in counties.iterrows():
                ewe_2_plus = int(county_matrix[i, 0])
                ewe_under_2 = int(county_matrix[i, 1])
                rams = int(county_matrix[i, 2])
                other = int(county_matrix[i, 3])
                ewes = ewe_2_plus + ewe_under_2
                rows.append(
                    {
                        "YEAR": year,
                        "County": county_row["County"],
                        "Region": region_name,
                        "TOTAL_SHEEP": int(county_totals[i]),
                        "EWES_2_PLUS": ewe_2_plus,
                        "EWES_UNDER_2": ewe_under_2,
                        "EWES": ewes,
                        "RAMS": rams,
                        "OTHER_SHEEP": other,
                        "BREEDING_SHEEP": ewes + rams,
                    }
                )

            if not np.array_equal(county_matrix.sum(axis=0), regional_class_targets):
                raise AssertionError(f"{region_name} {year}: regional class closure failed")

    county = pd.DataFrame(rows)
    if len(county) != 26 * len(YEARS):
        raise AssertionError("annual county sheep panel must contain 286 rows")
    if county[["YEAR", "County"]].duplicated().any():
        raise AssertionError("duplicate county-year rows in reconstructed sheep controls")

    atomic = county[ED_CLASS_COLS].sum(axis=1)
    if not np.array_equal(atomic.to_numpy(dtype=np.int64), county["TOTAL_SHEEP"]):
        raise AssertionError("county sheep atomic classes do not close")

    return county


def build_sheep_panel(config: SpatialConfig) -> pd.DataFrame:
    """Build the CSO-controlled annual sheep ED panel.

    The method reproduces the validated hierarchy:

    1. reconcile the observed 2020 ED sheep footprint to exact 2020 AAA09
       detailed-region totals;
    2. aggregate that corrected footprint to county anchors;
    3. reconstruct each year's county totals within each region;
    4. allocate the same year's AAA09 demographic classes jointly to counties;
    5. allocate county totals/classes to EDs using the fixed corrected 2020 ED
       footprint.

    Non-2020 ED values are reconstructed spatial estimates, not directly
    observed ED statistics.
    """

    ed_path = config.files["cso_ed_2020"]
    region_path = config.files["cso_sheep_region"]
    map_path = config.files["county_region_map"]

    for path in (ed_path, region_path, map_path):
        if not path.exists():
            raise FileNotFoundError(path)

    region = _load_region_controls(region_path)
    crosswalk = _load_county_region_map(map_path)
    anchor = _build_reconciled_2020_anchor(
        ed_path, crosswalk, region, config.expected_eds
    )
    county = _build_county_controls(anchor, region)

    identifier_cols = [
        column for column in IDENTIFIER_CANDIDATES if column in anchor.columns
    ]
    if "CSOED" not in identifier_cols or "County" not in identifier_cols:
        raise AssertionError("sheep panel requires CSOED and County identifiers")

    outputs: list[pd.DataFrame] = []

    for year in YEARS:
        for county_name in sorted(anchor["County"].unique()):
            ed_rows = (
                anchor.loc[anchor["County"] == county_name]
                .sort_values("CSOED", kind="stable")
                .reset_index(drop=True)
            )
            weights = ed_rows["TOTAL_SHEEP_2020_RECONCILED"].to_numpy(
                dtype=np.int64
            )
            target_row = county.loc[
                (county["YEAR"] == year) & (county["County"] == county_name)
            ]
            if len(target_row) != 1:
                raise AssertionError(f"{county_name} {year}: county sheep target problem")
            target_row = target_row.iloc[0]

            total_target = int(target_row["TOTAL_SHEEP"])
            if year == config.base_year:
                ed_totals = weights.copy()
                status = "FIXED_2020_RECONCILED_ED_ANCHOR"
                if int(ed_totals.sum()) != total_target:
                    raise AssertionError(
                        f"{county_name}: corrected 2020 ED sheep anchor mismatch"
                    )
            else:
                ed_totals = hamilton_allocate(weights, total_target)
                status = (
                    "RECONSTRUCTED_FROM_2020_ED_WEIGHTS_AND_AAA09_HIERARCHY"
                )

            class_targets = np.array(
                [int(target_row[column]) for column in ED_CLASS_COLS],
                dtype=np.int64,
            )
            if int(class_targets.sum()) != total_target:
                raise AssertionError(f"{county_name} {year}: sheep classes do not close")

            allocation = integer_transport(ed_totals, class_targets)
            result = ed_rows[identifier_cols + ["Region"]].copy()
            result.insert(0, "YEAR", year)
            result["TOTAL_SHEEP"] = ed_totals
            result["EWES_2_PLUS"] = allocation[:, 0]
            result["EWES_UNDER_2"] = allocation[:, 1]
            result["RAMS"] = allocation[:, 2]
            result["OTHER_SHEEP"] = allocation[:, 3]
            result["EWES"] = result["EWES_2_PLUS"] + result["EWES_UNDER_2"]
            result["BREEDING_SHEEP"] = result["EWES"] + result["RAMS"]
            result["SHEEP_DATA_STATUS"] = status

            if not np.array_equal(allocation.sum(axis=1), ed_totals):
                raise AssertionError(f"{county_name} {year}: ED sheep row closure failed")
            if not np.array_equal(allocation.sum(axis=0), class_targets):
                raise AssertionError(f"{county_name} {year}: county sheep closure failed")

            zero_mask = ed_rows["ZERO_2020_SPATIAL_WEIGHT"].to_numpy(dtype=bool)
            if (result.loc[zero_mask, ["TOTAL_SHEEP", *ED_CLASS_COLS]].to_numpy() != 0).any():
                raise AssertionError(
                    f"{county_name} {year}: 2020 sheep structural-zero support failed"
                )

            outputs.append(result)

    sheep = pd.concat(outputs, ignore_index=True)
    expected_rows = config.expected_eds * len(YEARS)
    if len(sheep) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} sheep ED-year rows")
    if sheep[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED sheep rows")
    if sheep["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("sheep ED coverage changed")
    if set(sheep["YEAR"].unique()) != set(YEARS):
        raise AssertionError("sheep years are not exactly 2015-2025")
    if (sheep[["TOTAL_SHEEP", *ED_CLASS_COLS, "EWES", "BREEDING_SHEEP"]] < 0).any().any():
        raise AssertionError("negative sheep values generated")

    if not np.array_equal(
        sheep[ED_CLASS_COLS].sum(axis=1).to_numpy(dtype=np.int64),
        sheep["TOTAL_SHEEP"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("ED sheep classes do not reproduce TOTAL_SHEEP")

    # Exact 2020 lock against the corrected spatial anchor.
    check2020 = sheep.loc[sheep["YEAR"] == config.base_year, ["CSOED", "TOTAL_SHEEP"]].merge(
        anchor[["CSOED", "TOTAL_SHEEP_2020_RECONCILED"]],
        on="CSOED",
        validate="one_to_one",
    )
    if int(
        (
            check2020["TOTAL_SHEEP"]
            - check2020["TOTAL_SHEEP_2020_RECONCILED"]
        ).abs().max()
    ) != 0:
        raise AssertionError("2020 corrected ED sheep anchor was not reproduced exactly")

    return sheep
