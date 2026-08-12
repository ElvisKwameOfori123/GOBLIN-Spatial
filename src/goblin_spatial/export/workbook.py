"""Clean Excel export for GOBLIN-Spatial."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

IDENTIFIERS = [
    "YEAR",
    "ELECTORAL_DIVISIONS",
    "ED",
    "County",
    "EDID",
    "CSOED",
    "CSOED_RAW",
    "EDNAME",
    "COUNTYNAME",
]
CSO_LIVESTOCK = [
    "DAIRY_COW",
    "OTHER_COW",
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
    "BULLS",
    "CATTLE_MALE_UNDER_1",
    "CATTLE_FEMALE_UNDER_1",
    "CATTLE_MALE_1_2",
    "CATTLE_FEMALE_1_2",
    "CATTLE_MALE_2_PLUS",
    "CATTLE_FEMALE_2_PLUS",
    "TOTAL_SHEEP",
    "EWES",
    "EWES_2_PLUS",
    "EWES_UNDER_2",
    "RAMS",
    "OTHER_SHEEP",
    "BREEDING_SHEEP",
]
SE_LAND = [
    "AVERAGE_SIZE_OF_HOLDINGS",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER",
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "OTHER_CROPS_HA",
]
GOBLIN_31 = [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
STANDARD_OUTPUT = [
    "FADN_REGION",
    "FADN_REGION_LABEL",
    "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR",
    "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR",
    "SO_LIVESTOCK_2020_EUR",
    "SO_CEREALS_2020_EUR",
    "SO_COVERED_TOTAL_2020_EUR",
    "SO_OTHER_CROPS_UNVALUED_HA",
    "SO_COVERED_PER_HOLDING_2020_EUR",
]
SOIL_PROFILE = [
    "ALL_GRASSLAND",
    "SOIL_PROFILE_SOURCE",
    "SOIL_SOURCE_HOLDINGS",
    "SOIL_SOURCE_UAA_HA",
    "SOIL_USE_CLASS_1_SHARE",
    "SOIL_USE_CLASS_2_SHARE",
    "SOIL_USE_CLASS_3_SHARE",
    "SOIL_USE_CLASS_4_SHARE",
    "SOIL_USE_CLASS_5_SHARE",
    "SOIL_USE_CLASS_6_SHARE",
    "GOBLIN_SOIL_G1_SHARE",
    "GOBLIN_SOIL_G2_SHARE",
    "GOBLIN_SOIL_G3_SHARE",
    "GOBLIN_SOIL_G1_GRASSLAND_HA",
    "GOBLIN_SOIL_G2_GRASSLAND_HA",
    "GOBLIN_SOIL_G3_GRASSLAND_HA",
    "FOREST_YC_14_SHARE",
    "FOREST_YC_18_SHARE",
    "FOREST_YC_20_SHARE",
    "FOREST_YC_24_SHARE",
    "FOREST_YC_SOURCE_UAA_HA",
    "FOREST_YC_WEIGHTED_MEAN",
    "IFS_SOIL_DOMINANT",
    "IFS_SOIL_DOMINANT_SHARE",
    "IFS_SOIL_N_CLASSES",
]
BANNED_TOKENS = [
    "STATUS",
    "METHOD",
    "SOURCE_YEAR",
    "COEFFICIENT",
    "TARGET",
    "ALLOCATED",
    "VALIDATION",
    "_DIFF",
    "INTERPRETATION",
    "AQA06_REGION",
    "STRUCTURAL_BASE_YEAR",
    "COHORT_TOTAL",
    "TOTAL_CATTLE_PLUS_SHEEP",
    "LSU",
]


def _existing(frame: pd.DataFrame, requested: list[str]) -> list[str]:
    return [column for column in requested if column in frame.columns]


def _check_clean(frame: pd.DataFrame, name: str) -> None:
    bad = [
        column
        for column in frame.columns
        if any(token in str(column).upper() for token in BANNED_TOKENS)
    ]
    if bad:
        raise AssertionError(
            f"{name}: diagnostic/model columns selected: {bad}"
        )
    if frame["CSOED"].isna().any():
        raise AssertionError(f"{name}: missing CSOED")
    empty = frame.columns[frame.isna().all(axis=0)].tolist()
    if empty:
        raise AssertionError(f"{name}: completely empty columns: {empty}")


def build_clean_sheets(
    master: pd.DataFrame, base_year: int = 2020
) -> dict[str, pd.DataFrame]:
    """Return clean biological, structural, SO and optional soil tables.

    ``LSU`` is intentionally excluded from the current baseline export because
    the historical source field is a static 2020 context value, not an annual
    reconstructed indicator. Scenario-consistent LSU belongs in the pressure
    layer.

    Standard Output and agricultural soil context are kept on separate sheets
    so those downstream/contextual additions do not alter the validated
    CSO/GOBLIN biological schemas.
    """

    ids = _existing(master, IDENTIFIERS)
    cso_columns = list(
        dict.fromkeys(
            ids
            + _existing(master, CSO_LIVESTOCK)
            + _existing(master, SE_LAND)
        )
    )
    goblin_columns = list(
        dict.fromkeys(
            ids
            + _existing(master, ["TOTAL_CATTLE", "TOTAL_SHEEP"])
            + GOBLIN_31
            + _existing(master, SE_LAND)
        )
    )

    missing = [column for column in GOBLIN_31 if column not in master.columns]
    if missing:
        raise ValueError(
            f"cannot export workbook; missing GOBLIN cohorts: {missing}"
        )

    cso_all = (
        master[cso_columns]
        .sort_values(["YEAR", "CSOED"], kind="stable")
        .reset_index(drop=True)
    )
    goblin_all = (
        master[goblin_columns]
        .sort_values(["YEAR", "CSOED"], kind="stable")
        .reset_index(drop=True)
    )
    cso_2020 = (
        cso_all.loc[cso_all["YEAR"] == base_year].copy().reset_index(drop=True)
    )
    goblin_2020 = (
        goblin_all.loc[goblin_all["YEAR"] == base_year]
        .copy()
        .reset_index(drop=True)
    )

    sheets = {
        "CSO_All_Years": cso_all,
        "GOBLIN_All_Years": goblin_all,
        "CSO_2020": cso_2020,
        "GOBLIN_2020": goblin_2020,
    }

    so_columns = list(dict.fromkeys(ids + _existing(master, STANDARD_OUTPUT)))
    if any(column.startswith("SO_") for column in so_columns):
        so_all = (
            master[so_columns]
            .sort_values(["YEAR", "CSOED"], kind="stable")
            .reset_index(drop=True)
        )
        sheets["Standard_Output"] = so_all

    if "GOBLIN_SOIL_G1_SHARE" in master.columns:
        soil_base = master.loc[master["YEAR"] == base_year].copy()
        requested = list(dict.fromkeys(ids + SOIL_PROFILE))
        soil_columns = [
            column
            for column in requested
            if column in soil_base.columns
            and not soil_base[column].isna().all()
        ]
        soil_frame = (
            soil_base[soil_columns]
            .sort_values(["CSOED"], kind="stable")
            .reset_index(drop=True)
        )
        sheets["Soil_Profile"] = soil_frame

    for name, frame in sheets.items():
        _check_clean(frame, name)

    if not cso_all.loc[
        cso_all["YEAR"] == base_year
    ].reset_index(drop=True).equals(cso_2020):
        raise AssertionError(
            "CSO_2020 is not the exact subset of CSO_All_Years"
        )
    if not goblin_all.loc[
        goblin_all["YEAR"] == base_year
    ].reset_index(drop=True).equals(goblin_2020):
        raise AssertionError(
            "GOBLIN_2020 is not the exact subset of GOBLIN_All_Years"
        )

    return sheets


def _format_sheet(
    writer: pd.ExcelWriter, name: str, frame: pd.DataFrame
) -> None:
    workbook = writer.book
    worksheet = writer.sheets[name]
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(1, 1)
    worksheet.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    integer = workbook.add_format({"num_format": "#,##0"})
    decimal = workbook.add_format({"num_format": "#,##0.00"})
    currency = workbook.add_format({"num_format": "€#,##0.00"})
    percent = workbook.add_format({"num_format": "0.00%"})
    age = workbook.add_format({"num_format": "0.00"})

    for col, value in enumerate(frame.columns):
        worksheet.write(0, col, value, header)
    worksheet.set_row(0, 28)

    integer_names = set(CSO_LIVESTOCK + GOBLIN_31 + ["AGRICULTURAL_HOLDINGS"])
    decimal_names = {
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AREA_FARMED",
        "ALL_GRASSLAND",
        "TOTAL_CEREALS",
        "OTHER_CROPS_HA",
        "SO_OTHER_CROPS_UNVALUED_HA",
        "SOIL_SOURCE_UAA_HA",
        "GOBLIN_SOIL_G1_GRASSLAND_HA",
        "GOBLIN_SOIL_G2_GRASSLAND_HA",
        "GOBLIN_SOIL_G3_GRASSLAND_HA",
        "FOREST_YC_SOURCE_UAA_HA",
        "FOREST_YC_WEIGHTED_MEAN",
    }
    age_names = {"AVERAGE_AGE_OF_HOLDER", "MEDIAN_AGE_OF_HOLDER"}

    for col_idx, column in enumerate(frame.columns):
        width = max(12, min(30, len(str(column)) + 2))
        fmt = None
        if column in integer_names or column in {
            "SOIL_SOURCE_HOLDINGS",
            "IFS_SOIL_N_CLASSES",
        }:
            fmt = integer
        elif column.endswith("_SHARE"):
            fmt = percent
        elif column in decimal_names:
            fmt = decimal
        elif column in age_names:
            fmt = age
        elif column.startswith("SO_") and column.endswith("_EUR"):
            fmt = currency

        if column in {"ELECTORAL_DIVISIONS", "EDNAME", "COUNTYNAME"}:
            width = 24
        elif column == "County":
            width = 14
        worksheet.set_column(col_idx, col_idx, width, fmt)


def export_clean_workbook(
    master: pd.DataFrame,
    output_path: str | Path,
    base_year: int = 2020,
) -> dict[str, pd.DataFrame]:
    """Write the final clean workbook and return its tables."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = build_clean_sheets(master, base_year=base_year)

    with pd.ExcelWriter(
        output_path,
        engine="xlsxwriter",
        engine_kwargs={
            "options": {
                "strings_to_urls": False,
                "constant_memory": False,
            }
        },
    ) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            _format_sheet(writer, name, frame)

    if not output_path.exists():
        raise AssertionError("final clean workbook was not created")
    return sheets
