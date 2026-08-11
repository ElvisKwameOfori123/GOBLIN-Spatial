"""DAFM sheep composition enrichment and GOBLIN sheep cohort disaggregation."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate, integer_transport


YEARS = tuple(range(2015, 2026))
ANCHOR_YEARS = (2016, 2020, 2022, 2025)
CATEGORIES = ("EWES", "RAMS", "OTHER")
BREEDS = ("MOUNTAIN", "MOUNTAIN_CROSS", "LOWLAND", "LOWLAND_CROSS")
GROUP_SOURCE = {"EWES": "EWES", "RAMS": "RAMS", "OTHER": "OTHER_SHEEP"}
SYSTEMS = ("LOWLAND", "UPLAND")
RESIDUAL_KEYS = ("LAMB_LT1", "MALE_LT1", "LAMB_GT1")

GOBLIN_NAMES = {
    "LOWLAND": {
        "EWES": "Lowland ewes",
        "LAMB_LT1": "Lowland lamb_less_1_yr",
        "MALE_LT1": "Lowland male_less_1_yr",
        "LAMB_GT1": "Lowland lamb_more_1_yr",
        "RAM": "Lowland ram",
    },
    "UPLAND": {
        "EWES": "Upland ewes",
        "LAMB_LT1": "Upland lamb_less_1_yr",
        "MALE_LT1": "Upland male_less_1_yr",
        "LAMB_GT1": "Upland lamb_more_1_yr",
        "RAM": "Upland ram",
    },
}

GOBLIN_SHEEP_10 = [
    "Lowland ewes",
    "Upland ewes",
    "Lowland lamb_less_1_yr",
    "Lowland male_less_1_yr",
    "Lowland lamb_more_1_yr",
    "Lowland ram",
    "Upland lamb_less_1_yr",
    "Upland male_less_1_yr",
    "Upland lamb_more_1_yr",
    "Upland ram",
]

SHEEP_CONTROLS = [
    "TOTAL_SHEEP",
    "EWES",
    "RAMS",
    "OTHER_SHEEP",
    "EWES_2_PLUS",
    "EWES_UNDER_2",
]


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _read_anchors(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("sheep breed anchor ZIP must contain exactly one CSV")
            with archive.open(names[0]) as handle:
                anchors = pd.read_csv(handle)
    else:
        anchors = pd.read_csv(path)

    required = [
        "YEAR",
        "CATEGORY",
        "County",
        "TOTAL_DAFM",
        "MOUNTAIN_COUNT",
        "MOUNTAIN_CROSS_COUNT",
        "LOWLAND_COUNT",
        "LOWLAND_CROSS_COUNT",
    ]
    missing = [column for column in required if column not in anchors.columns]
    if missing:
        raise ValueError(f"DAFM sheep breed anchors missing columns: {missing}")

    anchors["YEAR"] = pd.to_numeric(anchors["YEAR"], errors="raise").astype(int)
    anchors["CATEGORY"] = anchors["CATEGORY"].astype(str).str.strip().str.upper()
    anchors["County"] = anchors["County"].map(_normalise_county)

    count_columns = ["TOTAL_DAFM", *[f"{breed}_COUNT" for breed in BREEDS]]
    for column in count_columns:
        values = pd.to_numeric(anchors[column], errors="raise")
        rounded = np.rint(values.to_numpy(dtype=float)).astype(np.int64)
        if (rounded < 0).any():
            raise ValueError(f"negative DAFM sheep breed counts in {column}")
        anchors[column] = rounded

    if sorted(anchors["YEAR"].unique()) != list(ANCHOR_YEARS):
        raise AssertionError("DAFM sheep composition anchors must be 2016, 2020, 2022 and 2025")
    if set(anchors["CATEGORY"].unique()) != set(CATEGORIES):
        raise AssertionError("DAFM sheep composition categories must be EWES, RAMS and OTHER")
    if anchors[["YEAR", "CATEGORY", "County"]].duplicated().any():
        raise AssertionError("duplicate DAFM sheep breed anchor rows")
    if anchors["County"].nunique() != 26:
        raise AssertionError("DAFM sheep breed anchors must cover all 26 counties")

    breed_sum = anchors[[f"{breed}_COUNT" for breed in BREEDS]].sum(axis=1)
    if not np.array_equal(
        breed_sum.to_numpy(dtype=np.int64),
        anchors["TOTAL_DAFM"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("DAFM sheep breed counts do not close to TOTAL_DAFM")

    return anchors


def _interpolation_rule(year: int) -> tuple[int, int, float, str]:
    if year == 2015:
        return 2016, 2016, 0.0, "PROXY_FROM_DAFM_2016"
    if year in ANCHOR_YEARS:
        return year, year, 0.0, f"OBSERVED_DAFM_{year}"
    if 2016 < year < 2020:
        start, end = 2016, 2020
    elif 2020 < year < 2022:
        start, end = 2020, 2022
    elif 2022 < year < 2025:
        start, end = 2022, 2025
    else:
        raise ValueError(f"unsupported sheep composition year: {year}")
    alpha = (year - start) / (end - start)
    return start, end, alpha, f"INTERPOLATED_DAFM_{start}_{end}"


def build_annual_sheep_composition(anchor_path: str | Path) -> pd.DataFrame:
    """Interpolate county breed shares from the four validated DAFM anchors."""

    anchors = _read_anchors(anchor_path).copy()
    count_columns = [f"{breed}_COUNT" for breed in BREEDS]
    counts = anchors[count_columns].to_numpy(dtype=np.int64)
    totals = counts.sum(axis=1)
    if (totals <= 0).any():
        raise AssertionError("DAFM sheep breed anchor row has zero total")

    for j, breed in enumerate(BREEDS):
        anchors[f"{breed}_SHARE"] = counts[:, j] / totals

    rows: list[dict[str, object]] = []
    for county in sorted(anchors["County"].unique()):
        for category in CATEGORIES:
            subset = anchors.loc[
                (anchors["County"] == county) & (anchors["CATEGORY"] == category)
            ].set_index("YEAR")
            for year in YEARS:
                start, end, alpha, status = _interpolation_rule(year)
                shares = np.array(
                    [
                        float(subset.loc[start, f"{breed}_SHARE"])
                        + alpha
                        * (
                            float(subset.loc[end, f"{breed}_SHARE"])
                            - float(subset.loc[start, f"{breed}_SHARE"])
                        )
                        for breed in BREEDS
                    ],
                    dtype=float,
                )
                shares = np.maximum(shares, 0.0)
                shares = shares / shares.sum()
                row: dict[str, object] = {
                    "YEAR": year,
                    "County": county,
                    "CATEGORY": category,
                    "SOURCE_STATUS": status,
                    "ANCHOR_START_YEAR": start,
                    "ANCHOR_END_YEAR": end,
                }
                row.update(
                    {f"{breed}_SHARE": float(shares[j]) for j, breed in enumerate(BREEDS)}
                )
                rows.append(row)

    long = pd.DataFrame(rows)
    status = long[
        ["YEAR", "County", "SOURCE_STATUS", "ANCHOR_START_YEAR", "ANCHOR_END_YEAR"]
    ].drop_duplicates()
    wide = status.copy()
    for category in CATEGORIES:
        part = long.loc[
            long["CATEGORY"] == category,
            ["YEAR", "County", *[f"{breed}_SHARE" for breed in BREEDS]],
        ].copy()
        part = part.rename(
            columns={
                f"{breed}_SHARE": f"{category}_{breed}_SHARE" for breed in BREEDS
            }
        )
        wide = wide.merge(part, on=["YEAR", "County"], validate="one_to_one")

    for category in CATEGORIES:
        wide[f"{category}_MOUNTAIN_TYPE_SHARE"] = (
            wide[f"{category}_MOUNTAIN_SHARE"]
            + wide[f"{category}_MOUNTAIN_CROSS_SHARE"]
        )
        wide[f"{category}_LOWLAND_TYPE_SHARE"] = (
            wide[f"{category}_LOWLAND_SHARE"]
            + wide[f"{category}_LOWLAND_CROSS_SHARE"]
        )

    return wide.sort_values(["YEAR", "County"], kind="stable").reset_index(drop=True)


def _load_goblin(path: str | Path) -> pd.DataFrame:
    goblin = pd.read_csv(path)
    goblin.columns = [str(column).strip() for column in goblin.columns]
    if "Cohorts" not in goblin.columns:
        matches = [column for column in goblin.columns if column.lower() == "cohorts"]
        if len(matches) != 1:
            raise ValueError("could not identify GOBLIN cohort-name column")
        goblin = goblin.rename(columns={matches[0]: "Cohorts"})
    goblin["Cohorts"] = goblin["Cohorts"].astype(str).str.strip()

    missing = sorted(set(GOBLIN_SHEEP_10) - set(goblin["Cohorts"]))
    if missing:
        raise ValueError(f"GOBLIN cohort data missing sheep cohorts: {missing}")
    for year in range(2012, 2021):
        column = str(year)
        if column not in goblin.columns:
            raise ValueError(f"GOBLIN cohort data missing year {year}")
        goblin[column] = pd.to_numeric(goblin[column], errors="raise")
    return goblin


def _goblin_value(goblin: pd.DataFrame, cohort: str, year: int) -> float:
    row = goblin.loc[goblin["Cohorts"] == cohort]
    if len(row) != 1:
        raise AssertionError(f"expected one GOBLIN row for {cohort}")
    value = float(row.iloc[0][str(year)])
    if not np.isfinite(value) or value < 0:
        raise AssertionError(f"invalid GOBLIN sheep value for {cohort}, {year}")
    return value


def add_sheep_cohorts(
    sheep_panel: pd.DataFrame, config: SpatialConfig
) -> pd.DataFrame:
    """Add DAFM breed composition and the 10 GOBLIN sheep cohorts exactly.

    Mountain + Mountain Cross is used operationally as the GOBLIN upland-type
    proxy. It is not an independently observed ED hill-farm classification.
    The CSO sheep population remains the controlling total.
    """

    sheep = sheep_panel.copy()
    required = ["YEAR", "CSOED", "County", *SHEEP_CONTROLS]
    missing = [column for column in required if column not in sheep.columns]
    if missing:
        raise ValueError(f"sheep cohort module missing required columns: {missing}")

    expected_rows = config.expected_eds * len(YEARS)
    if len(sheep) != expected_rows or sheep["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("sheep panel dimensions changed before cohort enrichment")
    if sheep[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED sheep rows")

    sheep["County"] = sheep["County"].map(_normalise_county)
    for column in SHEEP_CONTROLS:
        values = pd.to_numeric(sheep[column], errors="raise")
        rounded = np.rint(values.to_numpy(dtype=float)).astype(np.int64)
        if (rounded < 0).any():
            raise AssertionError(f"negative sheep values in {column}")
        sheep[column] = rounded

    original_controls = sheep[["YEAR", "CSOED", *SHEEP_CONTROLS]].copy()
    anchor_path = config.files["sheep_breed_anchors"]
    goblin_path = config.files["goblin_cohorts"]
    if not anchor_path.exists():
        raise FileNotFoundError(anchor_path)
    if not goblin_path.exists():
        raise FileNotFoundError(goblin_path)

    composition = build_annual_sheep_composition(anchor_path)
    county = (
        sheep.groupby(["YEAR", "County"], as_index=False)[
            ["EWES", "RAMS", "OTHER_SHEEP"]
        ]
        .sum()
        .merge(composition, on=["YEAR", "County"], validate="one_to_one")
    )

    for group, source_column in GROUP_SOURCE.items():
        for breed in BREEDS:
            county[f"{group}_{breed}_TARGET"] = 0
            sheep[f"{group}_{breed}"] = 0

        for idx in county.index:
            targets = hamilton_allocate(
                [county.at[idx, f"{group}_{breed}_SHARE"] for breed in BREEDS],
                int(county.at[idx, source_column]),
            )
            for breed, value in zip(BREEDS, targets):
                county.at[idx, f"{group}_{breed}_TARGET"] = int(value)

        for (year, county_name), indices in sheep.groupby(
            ["YEAR", "County"], sort=True
        ).groups.items():
            row_totals = sheep.loc[indices, source_column].to_numpy(dtype=np.int64)
            control = county.loc[
                (county["YEAR"] == year) & (county["County"] == county_name)
            ]
            if len(control) != 1:
                raise AssertionError(
                    f"{county_name} {year}: missing sheep composition control"
                )
            control = control.iloc[0]
            column_targets = np.array(
                [int(control[f"{group}_{breed}_TARGET"]) for breed in BREEDS],
                dtype=np.int64,
            )
            allocation = integer_transport(row_totals, column_targets)
            for j, breed in enumerate(BREEDS):
                sheep.loc[indices, f"{group}_{breed}"] = allocation[:, j]

    for age in ("EWES_2_PLUS", "EWES_UNDER_2"):
        for breed in BREEDS:
            sheep[f"{age}_{breed}"] = 0

    for idx in sheep.index:
        allocation = integer_transport(
            [int(sheep.at[idx, "EWES_2_PLUS"]), int(sheep.at[idx, "EWES_UNDER_2"])],
            [int(sheep.at[idx, f"EWES_{breed}"]) for breed in BREEDS],
        )
        for j, breed in enumerate(BREEDS):
            sheep.at[idx, f"EWES_2_PLUS_{breed}"] = int(allocation[0, j])
            sheep.at[idx, f"EWES_UNDER_2_{breed}"] = int(allocation[1, j])

    for group in GROUP_SOURCE:
        sheep[f"{group}_MOUNTAIN_TYPE"] = (
            sheep[f"{group}_MOUNTAIN"] + sheep[f"{group}_MOUNTAIN_CROSS"]
        )
        sheep[f"{group}_LOWLAND_TYPE"] = (
            sheep[f"{group}_LOWLAND"] + sheep[f"{group}_LOWLAND_CROSS"]
        )

    sheep["OTHER_SHEEP_MOUNTAIN_TYPE"] = sheep["OTHER_MOUNTAIN_TYPE"]
    sheep["OTHER_SHEEP_LOWLAND_TYPE"] = sheep["OTHER_LOWLAND_TYPE"]
    for age in ("EWES_2_PLUS", "EWES_UNDER_2"):
        sheep[f"{age}_MOUNTAIN_TYPE"] = (
            sheep[f"{age}_MOUNTAIN"] + sheep[f"{age}_MOUNTAIN_CROSS"]
        )
        sheep[f"{age}_LOWLAND_TYPE"] = (
            sheep[f"{age}_LOWLAND"] + sheep[f"{age}_LOWLAND_CROSS"]
        )

    goblin = _load_goblin(goblin_path)
    for cohort in GOBLIN_SHEEP_10:
        sheep[cohort] = 0

    sheep["Lowland ewes"] = sheep["EWES_LOWLAND_TYPE"]
    sheep["Upland ewes"] = sheep["EWES_MOUNTAIN_TYPE"]
    sheep["Lowland ram"] = sheep["RAMS_LOWLAND_TYPE"]
    sheep["Upland ram"] = sheep["RAMS_MOUNTAIN_TYPE"]

    for year in YEARS:
        source_year = year if year <= 2020 else 2020
        indices = sheep.index[sheep["YEAR"] == year]
        for system in SYSTEMS:
            names = GOBLIN_NAMES[system]
            other_column = (
                "OTHER_SHEEP_LOWLAND_TYPE"
                if system == "LOWLAND"
                else "OTHER_SHEEP_MOUNTAIN_TYPE"
            )
            ewe_column = (
                "EWES_LOWLAND_TYPE" if system == "LOWLAND" else "EWES_MOUNTAIN_TYPE"
            )
            output_columns = [names[key] for key in RESIDUAL_KEYS]
            residual = np.array(
                [
                    _goblin_value(goblin, names[key], source_year)
                    for key in RESIDUAL_KEYS
                ],
                dtype=float,
            )
            ewe_reference = _goblin_value(goblin, names["EWES"], source_year)
            if ewe_reference <= 0:
                raise AssertionError(
                    f"{source_year}: non-positive GOBLIN {system} ewe reference"
                )

            coefficient = residual / ewe_reference
            current_ewes = int(sheep.loc[indices, ewe_column].sum())
            row_totals = sheep.loc[indices, other_column].to_numpy(dtype=np.int64)
            total_other = int(row_totals.sum())
            raw = coefficient * current_ewes
            if float(raw.sum()) > 0:
                shares = raw / raw.sum()
            elif float(residual.sum()) > 0:
                shares = residual / residual.sum()
            else:
                raise AssertionError(f"{year} {system}: zero GOBLIN residual structure")

            targets = hamilton_allocate(shares, total_other)
            allocation = integer_transport(row_totals, targets)
            for j, cohort in enumerate(output_columns):
                sheep.loc[indices, cohort] = allocation[:, j]

    for cohort in GOBLIN_SHEEP_10:
        sheep[cohort] = pd.to_numeric(sheep[cohort], errors="raise").astype(np.int64)
        if (sheep[cohort] < 0).any():
            raise AssertionError(f"negative GOBLIN sheep cohort: {cohort}")

    sheep["GOBLIN_10_SHEEP_COHORT_TOTAL"] = sheep[GOBLIN_SHEEP_10].sum(axis=1)
    if int(
        (
            sheep["GOBLIN_10_SHEEP_COHORT_TOTAL"] - sheep["TOTAL_SHEEP"]
        ).abs().max()
    ) != 0:
        raise AssertionError("10 GOBLIN sheep cohorts do not reproduce TOTAL_SHEEP")

    post_controls = sheep[["YEAR", "CSOED", *SHEEP_CONTROLS]]
    check = original_controls.merge(
        post_controls,
        on=["YEAR", "CSOED"],
        validate="one_to_one",
        suffixes=("_BEFORE", "_AFTER"),
    )
    for column in SHEEP_CONTROLS:
        if not np.array_equal(
            check[f"{column}_BEFORE"].to_numpy(),
            check[f"{column}_AFTER"].to_numpy(),
        ):
            raise AssertionError(f"sheep enrichment changed control {column}")

    return sheep
