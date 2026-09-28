"""Clean Excel export for the validated historical GOBLIN-Spatial baseline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

IDENTIFIERS = [
    "YEAR", "ELECTORAL_DIVISIONS", "ED", "County", "EDID", "CSOED",
    "CSOED_RAW", "EDNAME", "COUNTYNAME",
]
CSO_13_COHORTS = [
    # Cattle: two adult cow groups plus the seven CSO age-sex groups.
    "DAIRY_COW",
    "OTHER_COW",
    "BULLS",
    "CATTLE_MALE_UNDER_1",
    "CATTLE_FEMALE_UNDER_1",
    "CATTLE_MALE_1_2",
    "CATTLE_FEMALE_1_2",
    "CATTLE_MALE_2_PLUS",
    "CATTLE_FEMALE_2_PLUS",
    # Sheep: the four atomic AAA09 classes.
    "EWES_2_PLUS",
    "EWES_UNDER_2",
    "RAMS",
    "OTHER_SHEEP",
]
CSO_LIVESTOCK = [
    *CSO_13_COHORTS,
    # Retained control/derived fields for audit and convenient use.
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
    "TOTAL_SHEEP",
    "EWES",
    "BREEDING_SHEEP",
]
SE_LAND = [
    "AVERAGE_SIZE_OF_HOLDINGS", "AGRICULTURAL_HOLDINGS", "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER", "AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS",
    "OTHER_CROPS_HA",
]
GOBLIN_31 = [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
STANDARD_OUTPUT = [
    "FADN_REGION", "FADN_REGION_LABEL", "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR", "SO_BULLS_2020_EUR", "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR", "SO_LIVESTOCK_2020_EUR", "SO_CEREALS_2020_EUR",
    "SO_OTHER_CROPS_2020_EUR", "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
    "SO_COVERED_TOTAL_2020_EUR", "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
    "SO_OTHER_CROPS_IMPUTED_HA", "SO_COVERED_PER_HOLDING_2020_EUR",
    "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
]
BANNED_TOKENS = [
    "STATUS", "METHOD", "SOURCE_YEAR", "COEFFICIENT", "TARGET", "ALLOCATED",
    "VALIDATION", "_DIFF", "INTERPRETATION", "AQA06_REGION",
    "STRUCTURAL_BASE_YEAR", "COHORT_TOTAL", "TOTAL_CATTLE_PLUS_SHEEP", "LSU",
]


def _existing(frame: pd.DataFrame, requested: list[str]) -> list[str]:
    return [column for column in requested if column in frame.columns]


def _check_clean(frame: pd.DataFrame, name: str) -> None:
    bad = [column for column in frame.columns if any(token in str(column).upper() for token in BANNED_TOKENS)]
    if bad:
        raise AssertionError(f"{name}: diagnostic/model columns selected: {bad}")
    if frame["CSOED"].isna().any():
        raise AssertionError(f"{name}: missing CSOED")
    empty = frame.columns[frame.isna().all(axis=0)].tolist()
    if empty:
        raise AssertionError(f"{name}: completely empty columns: {empty}")


def build_clean_sheets(master: pd.DataFrame, base_year: int = 2020) -> dict[str, pd.DataFrame]:
    """Return clean historical biological, structural and Standard Output tables."""

    ids = _existing(master, IDENTIFIERS)
    cso_columns = list(dict.fromkeys(ids + _existing(master, CSO_LIVESTOCK) + _existing(master, SE_LAND)))
    goblin_columns = list(dict.fromkeys(ids + _existing(master, ["TOTAL_CATTLE", "TOTAL_SHEEP"]) + GOBLIN_31 + _existing(master, SE_LAND)))

    missing_cso = [column for column in CSO_13_COHORTS if column not in master.columns]
    if missing_cso:
        raise ValueError(
            f"cannot export workbook; missing CSO 13 cohort fields: {missing_cso}"
        )
    if len(CSO_13_COHORTS) != 13:
        raise AssertionError("CSO cohort contract must contain exactly 13 groups")

    missing = [column for column in GOBLIN_31 if column not in master.columns]
    if missing:
        raise ValueError(f"cannot export workbook; missing GOBLIN cohorts: {missing}")
    if len(GOBLIN_31) != 31:
        raise AssertionError("GOBLIN cohort contract must contain exactly 31 groups")

    cso_all = master[cso_columns].sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)
    goblin_all = master[goblin_columns].sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)
    cso_2020 = cso_all.loc[cso_all["YEAR"] == base_year].copy().reset_index(drop=True)
    goblin_2020 = goblin_all.loc[goblin_all["YEAR"] == base_year].copy().reset_index(drop=True)

    sheets = {
        "CSO_13_Cohort_All_Years": cso_all,
        "GOBLIN_31_Cohort_All_Years": goblin_all,
        "CSO_13_Cohort_2020": cso_2020,
        "GOBLIN_31_Cohort_2020": goblin_2020,
    }
    so_columns = list(dict.fromkeys(ids + _existing(master, STANDARD_OUTPUT)))
    if any(column.startswith("SO_") for column in so_columns):
        sheets["Standard_Output"] = master[so_columns].sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)

    for name, frame in sheets.items():
        _check_clean(frame, name)
    if not cso_all.loc[cso_all["YEAR"] == base_year].reset_index(drop=True).equals(cso_2020):
        raise AssertionError(
            "CSO_13_Cohort_2020 is not the exact subset of CSO_13_Cohort_All_Years"
        )
    if not goblin_all.loc[goblin_all["YEAR"] == base_year].reset_index(drop=True).equals(goblin_2020):
        raise AssertionError(
            "GOBLIN_31_Cohort_2020 is not the exact subset of GOBLIN_31_Cohort_All_Years"
        )
    return sheets


def _format_sheet(writer: pd.ExcelWriter, name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[name]
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(1, 1)
    worksheet.autofilter(0, 0, len(frame), len(frame.columns) - 1)
    header = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78", "border": 1})
    for col_num, value in enumerate(frame.columns.values):
        worksheet.write(0, col_num, value, header)
        width = min(max(len(str(value)) + 2, 12), 28)
        worksheet.set_column(col_num, col_num, width)


def export_clean_workbook(master: pd.DataFrame, output_path: str | Path, base_year: int = 2020) -> Path:
    """Write the clean historical workbook."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = build_clean_sheets(master, base_year=base_year)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            _format_sheet(writer, name, frame)
    return path
