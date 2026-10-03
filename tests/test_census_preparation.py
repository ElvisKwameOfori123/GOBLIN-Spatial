"""Stage 00 contract: suppression-aware preparation of the 2010 and 2020 census inputs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.preparation import census_suppression as cs
from goblin_spatial.preparation.stage00 import (
    LIVESTOCK_COLUMNS,
    MONTE_CARLO_FILES,
    Stage00Paths,
    compare_outputs,
    prepare,
)

ROOT = Path(__file__).resolve().parents[1]
PATHS = Stage00Paths.default(ROOT)
AUDIT = PATHS.audit_dir


@lru_cache(maxsize=1)
def _raw():
    return cs.load_ava42(PATHS.ava42)


def _prepared(year: int) -> pd.DataFrame:
    path = PATHS.ed_2020 if year == 2020 else PATHS.ed_2010
    frame = pd.read_csv(path, dtype={"CSOED": str}, encoding="utf-8-sig", keep_default_na=False)
    frame.index = frame["CSOED"].map(cs.canonical_key)
    return frame


@pytest.mark.parametrize("year", [2010, 2020])
def test_published_cells_are_unchanged(year: int) -> None:
    census, _ = _raw()
    raw = census[year]
    prepared = _prepared(year)
    for v, column in cs.MODEL_COLUMNS.items():
        cells = raw.loc[raw.index.isin(prepared.index) & raw[v].notna(), v]
        assert len(cells) > 0
        values = pd.to_numeric(prepared.loc[cells.index, column])
        assert (values.to_numpy() == cells.to_numpy()).all(), column


@pytest.mark.parametrize("year", [2010, 2020])
def test_livestock_identity_and_no_blanks(year: int) -> None:
    prepared = _prepared(year)
    values = {c: pd.to_numeric(prepared[c], errors="raise") for c in LIVESTOCK_COLUMNS}
    for column, series in values.items():
        assert series.notna().all() and (series >= 0).all(), column
    assert (
        values["DAIRY_COW"] + values["OTHER_COW"] + values["OTHER_CATTLE"] == values["TOTAL_CATTLE"]
    ).all()


def test_census_universes() -> None:
    assert len(_prepared(2020)) == 2857
    assert len(_prepared(2010)) == 3409


def test_state_totals_are_exact() -> None:
    _, state = _raw()
    closure = pd.read_csv(AUDIT / "state_closure.csv")
    assert closure["DIFFERENCE_FROM_STATE"].eq(0).all()
    # 2010 file holds the full census universe.
    prepared = _prepared(2010)
    for v, column in cs.MODEL_COLUMNS.items():
        assert int(pd.to_numeric(prepared[column]).sum()) == int(state.loc[2010, v])
    # 2020 model universe plus the reported outside-model residual equals the State.
    prepared = _prepared(2020)
    rows = closure.loc[closure["YEAR"].eq(2020)].set_index("VARIABLE")
    for v, column in cs.MODEL_COLUMNS.items():
        inside = int(pd.to_numeric(prepared[column]).sum())
        assert inside == int(rows.at[column, "MODEL_UNIVERSE_TOTAL"])
        assert inside + int(rows.at[column, "FILLED_OUTSIDE_MODEL"]) == int(state.loc[2020, v])


def test_every_filled_cell_carries_source_and_measured_error() -> None:
    census, _ = _raw()
    cells = pd.read_csv(AUDIT / "filled_cells.csv")
    for year in (2010, 2020):
        for v, column in cs.MODEL_COLUMNS.items():
            n = int(census[year][v].isna().sum())
            assert int((cells["YEAR"].eq(year) & cells["VARIABLE"].eq(column)).sum()) == n
    assert cells["SOURCE"].notna().all()
    assert cells["TEST_ERROR_PCT"].notna().all()
    assert set(cells["CONFIDENCE_CLASS"]) <= {"EXACT", "HIGH", "MODERATE", "LOW"}
    modelled = cells["SOURCE"].ne(cs.IDENTIFIED_SOURCE)
    assert set(cells.loc[modelled, "SHRINKAGE_LAMBDA"]) <= set(cs.SHRINKAGE_GRID)
    # A county's only blank cell is identified exactly by the county margin.
    singles = cells.groupby(["YEAR", "VARIABLE", "COUNTY"])["KEY"].transform("size").eq(1)
    assert cells.loc[singles, "SOURCE"].eq(cs.IDENTIFIED_SOURCE).all()
    assert cells.loc[~singles, "SOURCE"].ne(cs.IDENTIFIED_SOURCE).all()
    assert cells.loc[singles, "CONFIDENCE_CLASS"].eq("EXACT").all()
    assert cells.loc[~modelled, "SHRINKAGE_LAMBDA"].isna().all()


def test_census_county_totals_are_exact_in_both_years() -> None:
    counties = cs.load_census_county(PATHS.census_county)
    census, _ = _raw()
    # 2010 file holds the full census universe: county sums equal the census.
    prepared = _prepared(2010)
    county = census[2010]["COUNTY"].reindex(prepared.index)
    for v, column in cs.MODEL_COLUMNS.items():
        sums = pd.to_numeric(prepared[column]).groupby(county).sum()
        assert sums.reindex(counties[2010].index).eq(counties[2010][v]).all(), column
    # Both years, including EDs outside the model universe, via the audit.
    closure = pd.read_csv(AUDIT / "county_closure.csv")
    assert (closure["PUBLISHED_SUM"] + closure["FILLED"]).eq(closure["CENSUS_COUNTY_TOTAL"]).all()
    assert closure["FILLED"].eq(closure["HIDDEN_TOTAL"]).all()


def test_census_county_table_agrees_with_annual_controls() -> None:
    checks = pd.read_csv(AUDIT / "county_control_checks.csv")
    gaps = checks["CENSUS_MINUS_CONTROL"].dropna().abs()
    assert len(gaps) == 3 * 26 + 7
    assert gaps.max() <= 50


def test_cow_cap_is_exceeded_only_where_recorded() -> None:
    closure = pd.read_csv(AUDIT / "county_closure.csv")
    cells = pd.read_csv(AUDIT / "filled_cells.csv")
    assert int(closure["FILLED_ABOVE_COW_CAP"].sum()) > 0
    flagged = cells.loc[cells["ABOVE_COW_CAP"]]
    assert set(flagged["VARIABLE"]) <= {"DAIRY_COW", "OTHER_COW"}
    over = closure.loc[closure["FILLED_ABOVE_COW_CAP"] > 0, ["YEAR", "COUNTY"]]
    assert set(zip(flagged["YEAR"], flagged["COUNTY"])) <= set(zip(over["YEAR"], over["COUNTY"]))


def test_shrinkage_follows_the_one_standard_error_rule() -> None:
    table = pd.read_csv(AUDIT / "shrinkage_selection.csv")
    for _, g in table.groupby(["YEAR", "VARIABLE"]):
        assert int(g["SELECTED"].sum()) == 1
        chosen = g.loc[g["SELECTED"]].iloc[0]
        assert bool(chosen["ADMISSIBLE"])
        assert chosen["LAMBDA"] == g.loc[g["ADMISSIBLE"], "LAMBDA"].min()
    cells = pd.read_csv(AUDIT / "filled_cells.csv")
    chosen = table.loc[table["SELECTED"]].set_index(["YEAR", "VARIABLE"])["LAMBDA"]
    modelled = cells.loc[cells["SHRINKAGE_LAMBDA"].notna()]
    for (year, variable), lam in chosen.items():
        used = modelled.loc[modelled["YEAR"].eq(year) & modelled["VARIABLE"].eq(variable), "SHRINKAGE_LAMBDA"]
        assert used.eq(lam).all()


def test_stage00_regenerates_committed_outputs() -> None:
    result = prepare(PATHS)
    for name, payload in result.files.items():
        verdict = compare_outputs(name, Path(name).read_bytes(), payload)
        assert verdict is None or verdict.startswith("WITHIN_TOLERANCE"), (name, verdict)
        if Path(name).name not in MONTE_CARLO_FILES:
            assert verdict is None, name


def test_capped_hamilton_respects_capacity_and_total() -> None:
    alloc, left = cs.capped_hamilton(np.array([5.0, 1.0, 1.0]), np.array([3, 10, 10]), 12)
    assert left == 0 and alloc.sum() == 12 and alloc[0] == 3
    alloc, left = cs.capped_hamilton(np.array([1.0, 1.0]), np.array([2, 2]), 7)
    assert left == 3 and alloc.tolist() == [2, 2]


def test_aim_matching_discards_ambiguous_names() -> None:
    census, _ = _raw()
    local, _ = cs.load_aim(PATHS.aim)
    matched = cs.match_aim(census[2020], local)
    # 'Kilbarry' and 'Kilbarry (Part Rural)' share an unqualified AIM name;
    # 'Cootehill Rural' and 'Cootehill Urban' likewise.
    for key in ("24020", "25074", "32050", "32051"):
        assert matched.at[key, "AIM_MATCH"] == "NONE"
    assert not matched.index.duplicated().any()


def test_shrunk_weights() -> None:
    w = cs.shrunk_weights(np.array([3.0, 1.0]), 0.5)
    assert np.allclose(w, [0.5 * 0.75 + 0.25, 0.5 * 0.25 + 0.25])
    assert np.allclose(cs.shrunk_weights(np.zeros(4), 1.0), 0.25)
