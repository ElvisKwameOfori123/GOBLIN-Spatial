"""GOBLIN cattle cohort disaggregation of the CSO ED cattle panel.

The CSO ED panel is the controlling livestock population. GOBLIN cohort data
supply biological relationships used only to subdivide the six existing CSO
pre-adult age-sex containers into DxD, DxB and BxB cohorts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import (
    hamilton_allocate,
    integerise_matrix,
    ipf_reconcile,
)


YEARS = tuple(range(2015, 2026))
GENETICS = ("DxD", "DxB", "BxB")
HIERARCHICAL_SUPPORT = 1.0

CONTAINERS = {
    "CATTLE_MALE_UNDER_1": {
        "DxD": "DxD_calves_m",
        "DxB": "DxB_calves_m",
        "BxB": "BxB_calves_m",
    },
    "CATTLE_FEMALE_UNDER_1": {
        "DxD": "DxD_calves_f",
        "DxB": "DxB_calves_f",
        "BxB": "BxB_calves_f",
    },
    "CATTLE_FEMALE_1_2": {
        "DxD": "DxD_heifers_less_2_yr",
        "DxB": "DxB_heifers_less_2_yr",
        "BxB": "BxB_heifers_less_2_yr",
    },
    "CATTLE_MALE_1_2": {
        "DxD": "DxD_steers_less_2_yr",
        "DxB": "DxB_steers_less_2_yr",
        "BxB": "BxB_steers_less_2_yr",
    },
    "CATTLE_FEMALE_2_PLUS": {
        "DxD": "DxD_heifers_more_2_yr",
        "DxB": "DxB_heifers_more_2_yr",
        "BxB": "BxB_heifers_more_2_yr",
    },
    "CATTLE_MALE_2_PLUS": {
        "DxD": "DxD_steers_more_2_yr",
        "DxB": "DxB_steers_more_2_yr",
        "BxB": "BxB_steers_more_2_yr",
    },
}

FINAL_21_COHORTS = [
    "dairy_cows",
    "suckler_cows",
    "DxD_calves_m",
    "DxD_calves_f",
    "DxB_calves_m",
    "DxB_calves_f",
    "BxB_calves_m",
    "BxB_calves_f",
    "DxD_heifers_less_2_yr",
    "DxD_steers_less_2_yr",
    "DxB_heifers_less_2_yr",
    "DxB_steers_less_2_yr",
    "BxB_heifers_less_2_yr",
    "BxB_steers_less_2_yr",
    "DxD_heifers_more_2_yr",
    "DxD_steers_more_2_yr",
    "DxB_heifers_more_2_yr",
    "DxB_steers_more_2_yr",
    "BxB_heifers_more_2_yr",
    "BxB_steers_more_2_yr",
    "bulls",
]

CATTLE_CONTROL_COLS = [
    "DAIRY_COW",
    "OTHER_COW",
    "BULLS",
    *CONTAINERS.keys(),
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
]


def _load_goblin(path) -> pd.DataFrame:
    goblin = pd.read_csv(path)
    goblin.columns = [str(column).strip() for column in goblin.columns]

    cohort_columns = [column for column in goblin.columns if column.lower() == "cohorts"]
    if len(cohort_columns) != 1:
        raise ValueError("could not uniquely identify the GOBLIN Cohorts column")
    if cohort_columns[0] != "Cohorts":
        goblin = goblin.rename(columns={cohort_columns[0]: "Cohorts"})

    goblin["Cohorts"] = goblin["Cohorts"].astype(str).str.strip()
    for year in range(2012, 2021):
        column = str(year)
        if column not in goblin.columns:
            raise ValueError(f"GOBLIN cohort data missing year {year}")
        goblin[column] = pd.to_numeric(goblin[column], errors="raise")

    required = {"dairy_cows", "suckler_cows", "bulls"}
    for mapping in CONTAINERS.values():
        required.update(mapping.values())

    available = set(goblin["Cohorts"])
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"GOBLIN cohort data missing required cattle cohorts: {missing}")

    counts = goblin.loc[goblin["Cohorts"].isin(required), "Cohorts"].value_counts()
    if (counts != 1).any():
        raise AssertionError("required GOBLIN cattle cohort rows are not unique")

    return goblin


def _goblin_value(goblin: pd.DataFrame, cohort: str, year: int) -> float:
    row = goblin.loc[goblin["Cohorts"] == cohort]
    if len(row) != 1:
        raise AssertionError(f"expected one GOBLIN row for {cohort}")
    value = float(row.iloc[0][str(year)])
    if not np.isfinite(value) or value < 0:
        raise AssertionError(f"invalid GOBLIN value for {cohort}, {year}")
    return value


def _build_biological_controls(
    cattle: pd.DataFrame, goblin: pd.DataFrame
) -> tuple[dict[tuple[int, str], np.ndarray], dict[tuple[int, str], np.ndarray]]:
    """Return exact national genetic targets and cow-to-cohort coefficients."""

    targets: dict[tuple[int, str], np.ndarray] = {}
    coefficients: dict[tuple[int, str], np.ndarray] = {}

    for year in YEARS:
        source_year = year if year <= 2020 else 2020
        goblin_dairy = _goblin_value(goblin, "dairy_cows", source_year)
        goblin_suckler = _goblin_value(goblin, "suckler_cows", source_year)
        if goblin_dairy <= 0 or goblin_suckler <= 0:
            raise AssertionError(f"{source_year}: non-positive GOBLIN adult cow population")

        year_frame = cattle.loc[cattle["YEAR"] == year]
        cso_dairy = int(year_frame["DAIRY_COW"].sum())
        cso_suckler = int(year_frame["OTHER_COW"].sum())

        for container, mapping in CONTAINERS.items():
            coeff = np.array(
                [
                    _goblin_value(goblin, mapping["DxD"], source_year) / goblin_dairy,
                    _goblin_value(goblin, mapping["DxB"], source_year) / goblin_dairy,
                    _goblin_value(goblin, mapping["BxB"], source_year) / goblin_suckler,
                ],
                dtype=float,
            )
            if (coeff < 0).any():
                raise AssertionError(f"{year} {container}: negative biological coefficient")

            raw_expectation = np.array(
                [
                    coeff[0] * cso_dairy,
                    coeff[1] * cso_dairy,
                    coeff[2] * cso_suckler,
                ],
                dtype=float,
            )
            if float(raw_expectation.sum()) <= 0:
                raise AssertionError(f"{year} {container}: zero GOBLIN expectation")

            shares = raw_expectation / raw_expectation.sum()
            container_total = int(year_frame[container].sum())
            targets[(year, container)] = hamilton_allocate(shares, container_total)
            coefficients[(year, container)] = coeff

    return targets, coefficients


def add_cattle_cohorts(cattle_panel: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Express the fixed ED cattle population in the 21 GOBLIN cattle cohorts.

    The spatial distribution and age-sex structure are fixed by the CSO ED
    cattle panel. The GOBLIN cohort structure is used only to divide each
    existing age-sex population into DxD, DxB and BxB cohorts. No ED, county or
    national cattle total is changed.
    """

    cattle = cattle_panel.copy()
    required = ["YEAR", "CSOED", "County", *CATTLE_CONTROL_COLS]
    missing = [column for column in required if column not in cattle.columns]
    if missing:
        raise ValueError(f"cattle cohort module missing required columns: {missing}")

    expected_rows = config.expected_eds * len(YEARS)
    if len(cattle) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} cattle rows")
    if cattle[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED cattle rows")
    if cattle["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("cattle ED coverage changed before cohort disaggregation")
    if set(cattle["YEAR"].unique()) != set(YEARS):
        raise AssertionError("cattle years are not exactly 2015-2025")

    for column in CATTLE_CONTROL_COLS:
        values = pd.to_numeric(cattle[column], errors="raise")
        rounded = np.rint(values.to_numpy(dtype=float))
        if np.max(np.abs(values.to_numpy(dtype=float) - rounded)) > 1e-8:
            raise AssertionError(f"{column} contains non-integer cattle counts")
        if (rounded < 0).any():
            raise AssertionError(f"{column} contains negative cattle counts")
        cattle[column] = rounded.astype(np.int64)

    pre_adult = list(CONTAINERS)
    if int((cattle["BULLS"] + cattle[pre_adult].sum(axis=1) - cattle["OTHER_CATTLE"]).abs().max()) != 0:
        raise AssertionError("input OTHER_CATTLE accounting does not close")
    if int((cattle["DAIRY_COW"] + cattle["OTHER_COW"] + cattle["OTHER_CATTLE"] - cattle["TOTAL_CATTLE"]).abs().max()) != 0:
        raise AssertionError("input TOTAL_CATTLE accounting does not close")

    original_controls = cattle[["YEAR", "CSOED", *CATTLE_CONTROL_COLS]].copy()

    goblin_path = config.files["goblin_cohorts"]
    if not goblin_path.exists():
        raise FileNotFoundError(goblin_path)
    goblin = _load_goblin(goblin_path)
    national_targets, coefficients = _build_biological_controls(cattle, goblin)

    cattle["dairy_cows"] = cattle["DAIRY_COW"].astype(np.int64)
    cattle["suckler_cows"] = cattle["OTHER_COW"].astype(np.int64)
    cattle["bulls"] = cattle["BULLS"].astype(np.int64)
    for mapping in CONTAINERS.values():
        for cohort in mapping.values():
            cattle[cohort] = 0

    for year in YEARS:
        year_index = cattle.index[cattle["YEAR"] == year]
        year_frame = cattle.loc[year_index].copy()

        national_dairy = float(year_frame["DAIRY_COW"].sum())
        national_suckler = float(year_frame["OTHER_COW"].sum())
        national_cows = national_dairy + national_suckler
        if national_cows <= 0:
            raise AssertionError(f"{year}: national adult cow total is non-positive")

        dairy_share = national_dairy / national_cows
        suckler_share = national_suckler / national_cows

        county = year_frame.groupby("County")[["DAIRY_COW", "OTHER_COW"]].sum()
        county["TOTAL_COWS"] = county["DAIRY_COW"] + county["OTHER_COW"]
        county["DAIRY_CONTEXT"] = (
            county["DAIRY_COW"] + HIERARCHICAL_SUPPORT * dairy_share
        ) / (county["TOTAL_COWS"] + HIERARCHICAL_SUPPORT)
        county["SUCKLER_CONTEXT"] = (
            county["OTHER_COW"] + HIERARCHICAL_SUPPORT * suckler_share
        ) / (county["TOTAL_COWS"] + HIERARCHICAL_SUPPORT)

        county_dairy = year_frame["County"].map(county["DAIRY_CONTEXT"]).to_numpy(dtype=float)
        county_suckler = year_frame["County"].map(county["SUCKLER_CONTEXT"]).to_numpy(dtype=float)
        if not np.isfinite(county_dairy).all() or not np.isfinite(county_suckler).all():
            raise AssertionError(f"{year}: non-finite county cow context")

        dairy_score = year_frame["DAIRY_COW"].to_numpy(dtype=float) + HIERARCHICAL_SUPPORT * county_dairy
        suckler_score = year_frame["OTHER_COW"].to_numpy(dtype=float) + HIERARCHICAL_SUPPORT * county_suckler

        for container, mapping in CONTAINERS.items():
            row_totals = year_frame[container].to_numpy(dtype=np.int64)
            col_targets = national_targets[(year, container)]
            coeff = coefficients[(year, container)]

            prior = np.column_stack(
                [
                    dairy_score * coeff[0],
                    dairy_score * coeff[1],
                    suckler_score * coeff[2],
                ]
            )
            prior[row_totals == 0, :] = 0.0

            fractional = ipf_reconcile(
                prior,
                row_totals,
                col_targets,
                tolerance=1e-8,
                max_iterations=20000,
            )
            allocation = integerise_matrix(fractional, row_totals, col_targets)

            for j, genetic in enumerate(GENETICS):
                cattle.loc[year_index, mapping[genetic]] = allocation[:, j]

            if not np.array_equal(allocation.sum(axis=1), row_totals):
                raise AssertionError(f"{year} {container}: ED age-sex totals changed")
            if not np.array_equal(allocation.sum(axis=0), col_targets):
                raise AssertionError(f"{year} {container}: national genetic targets failed")

    for cohort in FINAL_21_COHORTS:
        cattle[cohort] = pd.to_numeric(cattle[cohort], errors="raise").astype(np.int64)
        if (cattle[cohort] < 0).any():
            raise AssertionError(f"negative GOBLIN cattle cohort: {cohort}")

    for container, mapping in CONTAINERS.items():
        cohort_columns = [mapping[genetic] for genetic in GENETICS]
        difference = cattle[cohort_columns].sum(axis=1) - cattle[container]
        if int(difference.abs().max()) != 0:
            raise AssertionError(f"GOBLIN cohorts do not close to {container}")

    cattle["GOBLIN_21_CATTLE_COHORT_TOTAL"] = cattle[FINAL_21_COHORTS].sum(axis=1)
    if int((cattle["GOBLIN_21_CATTLE_COHORT_TOTAL"] - cattle["TOTAL_CATTLE"]).abs().max()) != 0:
        raise AssertionError("21 GOBLIN cattle cohorts do not reproduce TOTAL_CATTLE")

    post_controls = cattle[["YEAR", "CSOED", *CATTLE_CONTROL_COLS]]
    check = original_controls.merge(
        post_controls,
        on=["YEAR", "CSOED"],
        validate="one_to_one",
        suffixes=("_BEFORE", "_AFTER"),
    )
    for column in CATTLE_CONTROL_COLS:
        if not np.array_equal(
            check[f"{column}_BEFORE"].to_numpy(),
            check[f"{column}_AFTER"].to_numpy(),
        ):
            raise AssertionError(f"cohort disaggregation changed CSO control {column}")

    return cattle
