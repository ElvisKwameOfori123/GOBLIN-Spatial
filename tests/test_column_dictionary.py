"""Column dictionary and SQLite naming for the historical release bundle."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.export.column_dictionary import (
    describe,
    describe_table,
    sqlite_safe_names,
    undescribed_columns,
)
from goblin_spatial.export.livestock_panels import (
    CONTEXT_COLUMNS,
    CONTROL_PREFIX,
    CSO_13,
    CSO_TOTALS,
    COHORTS_31,
    ID_COLS,
    PROVENANCE,
)
from goblin_spatial.synthesis.historical import SIGNATURE_METRICS

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
    "SO_OTHER_CROPS_2020_EUR",
    "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
    "SO_OTHER_CROPS_IMPUTED_HA",
    "SO_COVERED_TOTAL_2020_EUR",
    "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
    "SO_COVERED_PER_HOLDING_2020_EUR",
    "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
]


def _frame(columns) -> pd.DataFrame:
    return pd.DataFrame(columns=list(dict.fromkeys(columns)))


def test_every_canonical_panel_column_is_described() -> None:
    panel13 = _frame([*ID_COLS, *CSO_TOTALS, *CSO_13, *CONTEXT_COLUMNS, *PROVENANCE])
    panel31 = _frame([*ID_COLS, *CONTROL_PREFIX.values(), *COHORTS_31, *CONTEXT_COLUMNS, *PROVENANCE])
    assert undescribed_columns(panel13) == []
    assert undescribed_columns(panel31) == []


def test_standard_output_and_signature_columns_are_described() -> None:
    assert undescribed_columns(_frame([*STANDARD_OUTPUT, *SIGNATURE_METRICS])) == []


def test_units_follow_the_quantity() -> None:
    assert describe("TOTAL_CATTLE")[0] == "head"
    assert describe("DxB_calves_m")[0] == "head"
    assert describe("CSO_EWES_2_PLUS")[0] == "head"
    assert describe("AREA_FARMED")[0] == "ha"
    assert describe("SO_COVERED_TOTAL_2020_EUR")[0] == "EUR"
    assert describe("SO_COVERED_PER_HOLDING_2020_EUR")[0] == "EUR per holding"
    assert describe("EWES_2_PLUS_MOUNTAIN_CROSS")[0] == "head"
    assert describe("NOT_A_COLUMN") is None


def test_describe_table_reports_every_column_in_order() -> None:
    table = describe_table("t", pd.DataFrame({"YEAR": [2020], "CSOED": ["1"], "UNKNOWN": [1.0]}))
    assert table["COLUMN_NAME"].tolist() == ["YEAR", "CSOED", "UNKNOWN"]
    assert table["POSITION"].tolist() == [1, 2, 3]
    assert table.loc[table["COLUMN_NAME"] == "UNKNOWN", "DESCRIPTION"].item() == ""


def test_sqlite_names_resolve_case_only_clashes() -> None:
    rename = sqlite_safe_names(["YEAR", "BULLS", "dairy_cows", "bulls", "DAIRY_COW"])
    assert rename == {"bulls": "bulls_goblin"}
    renamed = [rename.get(c, c) for c in ["YEAR", "BULLS", "dairy_cows", "bulls", "DAIRY_COW"]]
    assert len({c.lower() for c in renamed}) == len(renamed)
    columns = ["a", "A", "a_goblin"]
    names = [sqlite_safe_names(columns).get(c, c) for c in columns]
    assert len({c.lower() for c in names}) == len(columns)
