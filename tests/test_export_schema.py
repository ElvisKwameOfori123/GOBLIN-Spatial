"""Compact regression tests for the final clean export schema."""

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.export.workbook import (
    CSO_13_COHORTS,
    CSO_LIVESTOCK,
    IDENTIFIERS,
    SE_LAND,
    STANDARD_OUTPUT,
    build_clean_sheets,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def test_clean_schema_ignores_stale_lsu() -> None:
    row = {column: 0 for column in IDENTIFIERS}
    row.update({column: 0 for column in CSO_LIVESTOCK})
    row.update({column: 0 for column in FINAL_21_COHORTS})
    row.update({column: 0 for column in GOBLIN_SHEEP_10})
    row.update({column: 0.0 for column in SE_LAND})
    row.update(
        {
            "YEAR": 2020,
            "CSOED": "TEST001",
            "ELECTORAL_DIVISIONS": "Test ED",
            "ED": "Test ED",
            "County": "Test",
            "EDID": "TEST001",
            "LSU": 999.0,
        }
    )
    frame = pd.DataFrame([row])

    sheets = build_clean_sheets(frame, base_year=2020)

    assert len(CSO_13_COHORTS) == 13
    assert sheets["CSO_13_Cohort_All_Years"].shape[1] == 37
    assert sheets["GOBLIN_31_Cohort_All_Years"].shape[1] == 66
    assert "LSU" not in sheets["CSO_13_Cohort_All_Years"].columns
    assert "LSU" not in sheets["GOBLIN_31_Cohort_All_Years"].columns
    assert "CSO_TOTAL_CATTLE" in sheets["GOBLIN_31_Cohort_All_Years"].columns
    assert "CSO_BULLS" in sheets["GOBLIN_31_Cohort_All_Years"].columns


def test_clean_schema_keeps_complete_ed_identity_block() -> None:
    assert IDENTIFIERS == [
        "YEAR",
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED",
        "CSOED_RAW",
        "EDNAME",
        "COUNTYNAME",
        "Region",
        "NUTS2",
    ]



def test_clean_schema_keeps_standard_output_as_dedicated_sheet() -> None:
    row = {column: 0 for column in IDENTIFIERS}
    row.update({column: 0 for column in CSO_LIVESTOCK})
    row.update({column: 0 for column in FINAL_21_COHORTS})
    row.update({column: 0 for column in GOBLIN_SHEEP_10})
    row.update({column: 0.0 for column in SE_LAND})
    row.update(
        {
            "YEAR": 2020,
            "CSOED": "TEST001",
            "ELECTORAL_DIVISIONS": "Test ED",
            "ED": "Test ED",
            "County": "Mayo",
            "EDID": "TEST001",
            "EDNAME": "Test ED",
            "COUNTYNAME": "Mayo",
            "Region": "West",
            "NUTS2": "Northern and Western",
        }
    )
    for column in STANDARD_OUTPUT:
        if column == "FADN_REGION":
            row[column] = "381"
        elif column == "FADN_REGION_LABEL":
            row[column] = "Border, Midland and Western"
        else:
            row[column] = 0.0

    sheets = build_clean_sheets(pd.DataFrame([row]), base_year=2020)

    assert "Standard_Output" in sheets
    standard_output = sheets["Standard_Output"]
    assert list(standard_output.columns) == IDENTIFIERS + STANDARD_OUTPUT
    assert len(standard_output) == 1
    assert not any(
        column.startswith("SO_")
        for column in sheets["CSO_13_Cohort_All_Years"].columns
    )
    assert not any(
        column.startswith("SO_")
        for column in sheets["GOBLIN_31_Cohort_All_Years"].columns
    )
