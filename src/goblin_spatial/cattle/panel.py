"""CSO cattle baseline and annual ED cattle-panel construction.

This module is the modular equivalent of the validated 2020 cattle
reconciliation and 2015-2025 annual ED cattle reconstruction stages.

Fine-scale CSO ED data provide the within-county spatial pattern. Annual CSO
AAA10 county statistics provide the controlling cattle totals and age-sex
composition. The 2020 ED baseline is copied exactly into the annual panel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate, integer_transport


YEARS = tuple(range(2015, 2026))

AGE_SEX_MAP = {
    "Bulls": "BULLS",
    "Cattle male: under 1 year": "CATTLE_MALE_UNDER_1",
    "Cattle female: under 1 year": "CATTLE_FEMALE_UNDER_1",
    "Cattle male: 1-2 years": "CATTLE_MALE_1_2",
    "Cattle female: 1-2 years": "CATTLE_FEMALE_1_2",
    "Cattle male: 2 years and over": "CATTLE_MALE_2_PLUS",
    "Cattle female: 2 years and over": "CATTLE_FEMALE_2_PLUS",
}

AAA_AGE_SEX_COLS = list(AGE_SEX_MAP)
AGE_SEX_COLS = list(AGE_SEX_MAP.values())
MAIN_CATTLE_COLS = ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def _as_nonnegative_integer(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{label}: missing/non-numeric values in {column}")
        if (values < 0).any():
            raise ValueError(f"{label}: negative values in {column}")
        frame[column] = np.rint(values).astype(np.int64)


def _load_aaa10(path) -> pd.DataFrame:
    county = pd.read_csv(path)
    required = [
        "Year",
        "Region and County",
        "UNIT",
        "Total cattle",
        "Dairy cows",
        "Other cows",
        *AAA_AGE_SEX_COLS,
    ]
    _require_columns(county, required, "AAA10 county cattle data")

    county["Year"] = pd.to_numeric(county["Year"], errors="raise").astype(int)
    county["County"] = county["Region and County"].map(_normalise_county)
    county = county.loc[county["Year"].isin(YEARS)].copy()

    if not (county["UNIT"] == "000 Head").all():
        raise ValueError("AAA10 cattle input must use UNIT='000 Head'")

    numeric = ["Total cattle", "Dairy cows", "Other cows", *AAA_AGE_SEX_COLS]
    for column in numeric:
        values = pd.to_numeric(county[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"AAA10 contains invalid values in {column}")
        county[column] = values
        county[f"{column}__HEAD"] = np.rint(values * 1000.0).astype(np.int64)

    return county


def _build_2020_baseline(ed_source, county: pd.DataFrame, expected_eds: int) -> pd.DataFrame:
    """Reconcile the fixed 2020 ED cattle baseline to AAA10 county controls."""

    ed = pd.read_csv(ed_source)
    required = [
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED",
        *MAIN_CATTLE_COLS,
    ]
    _require_columns(ed, required, "2020 ED cattle baseline")

    ed["County"] = ed["County"].map(_normalise_county)
    ed = ed.sort_values(["County", "CSOED"], kind="stable").reset_index(drop=True)
    _as_nonnegative_integer(ed, MAIN_CATTLE_COLS, "2020 ED cattle baseline")

    if len(ed) != expected_eds or ed["CSOED"].nunique() != expected_eds:
        raise AssertionError(f"expected {expected_eds:,} unique EDs in 2020 baseline")
    if ed["CSOED"].duplicated().any():
        raise AssertionError("duplicate CSOED values in 2020 baseline")

    initial_identity = (
        ed["TOTAL_CATTLE"] - ed["DAIRY_COW"] - ed["OTHER_COW"] - ed["OTHER_CATTLE"]
    )
    if int(initial_identity.abs().max()) != 0:
        raise AssertionError("input 2020 cattle identity does not close")

    county_2020 = county.loc[county["Year"] == 2020].copy()
    if len(county_2020) != 26 or county_2020["County"].duplicated().any():
        raise AssertionError("AAA10 2020 must contain one row for each of 26 counties")

    ed_counties = set(ed["County"].unique())
    if set(county_2020["County"].unique()) != ed_counties:
        raise AssertionError("county coverage differs between ED baseline and AAA10")

    controls = {
        "DAIRY_COW": "Dairy cows__HEAD",
        "OTHER_COW": "Other cows__HEAD",
        "TOTAL_CATTLE": "Total cattle__HEAD",
    }

    for county_name in sorted(ed_counties):
        idx = ed.index[ed["County"] == county_name]
        source = county_2020.loc[county_2020["County"] == county_name].iloc[0]

        for ed_column, target_column in controls.items():
            weights = ed.loc[idx, ed_column].to_numpy(dtype=float)
            target = int(source[target_column])
            if target > 0 and float(weights.sum()) <= 0:
                raise ValueError(
                    f"{county_name}: positive {ed_column} target with zero ED support"
                )
            ed.loc[idx, ed_column] = hamilton_allocate(weights, target)

    ed["OTHER_CATTLE"] = (
        ed["TOTAL_CATTLE"] - ed["DAIRY_COW"] - ed["OTHER_COW"]
    ).astype(np.int64)
    if (ed["OTHER_CATTLE"] < 0).any():
        raise AssertionError("2020 reconciliation produced negative OTHER_CATTLE")

    for output_column in AGE_SEX_COLS:
        ed[output_column] = 0

    for county_name in sorted(ed_counties):
        idx = ed.index[ed["County"] == county_name]
        row_totals = ed.loc[idx, "OTHER_CATTLE"].to_numpy(dtype=np.int64)
        source = county_2020.loc[county_2020["County"] == county_name].iloc[0]

        components = np.array(
            [source[f"{column}__HEAD"] for column in AAA_AGE_SEX_COLS],
            dtype=float,
        )
        if float(components.sum()) <= 0:
            raise AssertionError(f"{county_name}: zero AAA10 age-sex component sum")

        column_targets = hamilton_allocate(components / components.sum(), int(row_totals.sum()))
        allocation = integer_transport(row_totals, column_targets)
        for j, output_column in enumerate(AGE_SEX_COLS):
            ed.loc[idx, output_column] = allocation[:, j]

    _as_nonnegative_integer(ed, MAIN_CATTLE_COLS + AGE_SEX_COLS, "2020 reconciled cattle")
    _validate_ed_cattle_accounting(ed, "2020 reconciled cattle")
    _validate_county_controls(ed, county_2020, 2020)

    return ed


def _validate_ed_cattle_accounting(frame: pd.DataFrame, label: str) -> None:
    other_difference = frame["OTHER_CATTLE"] - frame[AGE_SEX_COLS].sum(axis=1)
    total_difference = (
        frame["TOTAL_CATTLE"]
        - frame["DAIRY_COW"]
        - frame["OTHER_COW"]
        - frame["OTHER_CATTLE"]
    )
    if int(other_difference.abs().max()) != 0:
        raise AssertionError(f"{label}: OTHER_CATTLE age-sex closure failed")
    if int(total_difference.abs().max()) != 0:
        raise AssertionError(f"{label}: TOTAL_CATTLE identity failed")


def _validate_county_controls(frame: pd.DataFrame, county_year: pd.DataFrame, year: int) -> None:
    observed = (
        frame.groupby("County", as_index=False)
        .agg(
            DAIRY_COW=("DAIRY_COW", "sum"),
            OTHER_COW=("OTHER_COW", "sum"),
            OTHER_CATTLE=("OTHER_CATTLE", "sum"),
            TOTAL_CATTLE=("TOTAL_CATTLE", "sum"),
        )
    )
    target = county_year[
        ["County", "Total cattle__HEAD", "Dairy cows__HEAD", "Other cows__HEAD"]
    ].copy()
    target["OTHER_CATTLE_TARGET"] = (
        target["Total cattle__HEAD"]
        - target["Dairy cows__HEAD"]
        - target["Other cows__HEAD"]
    )
    check = observed.merge(target, on="County", how="left", validate="one_to_one")
    differences = np.column_stack(
        [
            check["DAIRY_COW"] - check["Dairy cows__HEAD"],
            check["OTHER_COW"] - check["Other cows__HEAD"],
            check["OTHER_CATTLE"] - check["OTHER_CATTLE_TARGET"],
            check["TOTAL_CATTLE"] - check["Total cattle__HEAD"],
        ]
    )
    if int(np.abs(differences).max()) != 0:
        raise AssertionError(f"{year}: county AAA10 cattle controls do not close")


def build_cattle_panel(config: SpatialConfig) -> pd.DataFrame:
    """Build the validated CSO-controlled annual cattle ED panel.

    2020 is the fixed ED spatial anchor. Other years preserve its within-county
    spatial support while reproducing each year's AAA10 county cattle totals and
    same-year other-cattle age-sex composition exactly.

    Returns
    -------
    pandas.DataFrame
        2,857 EDs x 11 years for the Ireland 2015-2025 configuration.
    """

    ed_path = config.files["cso_ed_2020"]
    county_path = config.files["cso_cattle_county"]
    if not ed_path.exists():
        raise FileNotFoundError(ed_path)
    if not county_path.exists():
        raise FileNotFoundError(county_path)

    county = _load_aaa10(county_path)
    baseline = _build_2020_baseline(ed_path, county, config.expected_eds)
    expected_counties = set(baseline["County"].unique())

    if len(expected_counties) != 26:
        raise AssertionError("cattle baseline must contain exactly 26 counties")

    for year in YEARS:
        source = county.loc[county["Year"] == year]
        if len(source) != 26 or source["County"].duplicated().any():
            raise AssertionError(f"{year}: AAA10 county coverage is incomplete")
        if set(source["County"].unique()) != expected_counties:
            raise AssertionError(f"{year}: AAA10 county names differ from 2020 baseline")

    fixed_weights: dict[str, dict[str, object]] = {}
    for county_name in sorted(expected_counties):
        idx = baseline.index[baseline["County"] == county_name]
        fixed_weights[county_name] = {
            "index": idx,
            "DAIRY_COW": baseline.loc[idx, "DAIRY_COW"].to_numpy(dtype=np.int64),
            "OTHER_COW": baseline.loc[idx, "OTHER_COW"].to_numpy(dtype=np.int64),
            "OTHER_CATTLE": baseline.loc[idx, "OTHER_CATTLE"].to_numpy(dtype=np.int64),
        }

    annual: list[pd.DataFrame] = []

    for year in YEARS:
        frame = baseline.copy()
        frame.insert(0, "YEAR", year)
        frame.insert(1, "STATIC_CONTEXT_YEAR", config.base_year)

        if year == config.base_year:
            frame["LIVESTOCK_DATA_STATUS"] = "FIXED_2020_RECONCILED_ANCHOR"
        else:
            frame["LIVESTOCK_DATA_STATUS"] = (
                "RECONSTRUCTED_FROM_2020_ED_WEIGHTS_AND_ANNUAL_AAA10_COUNTY_CONTROLS"
            )
            for column in MAIN_CATTLE_COLS + AGE_SEX_COLS:
                frame[column] = 0

            for county_name in sorted(expected_counties):
                support = fixed_weights[county_name]
                idx = support["index"]
                source = county.loc[
                    (county["Year"] == year) & (county["County"] == county_name)
                ].iloc[0]

                total_target = int(source["Total cattle__HEAD"])
                dairy_target = int(source["Dairy cows__HEAD"])
                other_cow_target = int(source["Other cows__HEAD"])
                other_cattle_target = total_target - dairy_target - other_cow_target
                if other_cattle_target < 0:
                    raise AssertionError(f"{county_name} {year}: negative OTHER_CATTLE target")

                dairy = hamilton_allocate(support["DAIRY_COW"], dairy_target)
                other_cows = hamilton_allocate(support["OTHER_COW"], other_cow_target)
                other_cattle = hamilton_allocate(support["OTHER_CATTLE"], other_cattle_target)

                frame.loc[idx, "DAIRY_COW"] = dairy
                frame.loc[idx, "OTHER_COW"] = other_cows
                frame.loc[idx, "OTHER_CATTLE"] = other_cattle
                frame.loc[idx, "TOTAL_CATTLE"] = dairy + other_cows + other_cattle

                components = np.array(
                    [source[f"{column}__HEAD"] for column in AAA_AGE_SEX_COLS],
                    dtype=float,
                )
                if float(components.sum()) <= 0:
                    raise AssertionError(f"{county_name} {year}: zero age-sex component sum")
                age_targets = hamilton_allocate(
                    components / components.sum(), other_cattle_target
                )
                allocation = integer_transport(other_cattle, age_targets)
                for j, output_column in enumerate(AGE_SEX_COLS):
                    frame.loc[idx, output_column] = allocation[:, j]

        _as_nonnegative_integer(
            frame, MAIN_CATTLE_COLS + AGE_SEX_COLS, f"{year} cattle panel"
        )
        _validate_ed_cattle_accounting(frame, f"{year} cattle panel")
        _validate_county_controls(frame, county.loc[county["Year"] == year], year)

        if year != config.base_year:
            for county_name in sorted(expected_counties):
                support = fixed_weights[county_name]
                idx = support["index"]
                for column in ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE"):
                    zero_support = support[column] == 0
                    if (
                        frame.loc[idx, column].to_numpy(dtype=np.int64)[zero_support] != 0
                    ).any():
                        raise AssertionError(
                            f"{year} {county_name}: fixed 2020 support rule failed for {column}"
                        )

        annual.append(frame)

    panel = pd.concat(annual, ignore_index=True)
    expected_rows = config.expected_eds * len(YEARS)
    if len(panel) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} cattle ED-year rows")
    if panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED cattle rows")
    if panel["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("cattle ED coverage changed")
    if set(panel["YEAR"].unique()) != set(YEARS):
        raise AssertionError("cattle panel years are not exactly 2015-2025")

    # The 2020 panel must be an exact numeric copy of the reconciled baseline.
    p2020 = panel.loc[panel["YEAR"] == config.base_year].sort_values("CSOED").reset_index(drop=True)
    b2020 = baseline.sort_values("CSOED").reset_index(drop=True)
    for column in MAIN_CATTLE_COLS + AGE_SEX_COLS:
        if not np.array_equal(p2020[column].to_numpy(), b2020[column].to_numpy()):
            raise AssertionError(f"2020 cattle lock failed for {column}")

    return panel
