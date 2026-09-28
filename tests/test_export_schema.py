"""Compact regression tests for the final clean export schema."""

import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.export.workbook import (
    CSO_13_COHORTS,
    CSO_LIVESTOCK,
    IDENTIFIERS,
    SE_LAND,
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
