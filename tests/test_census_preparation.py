"""Stage 00 contract: suppression-aware preparation of the 2010 and 2020 census inputs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.preparation import census_suppression as cs
from goblin_spatial.preparation.stage00 import LIVESTOCK_COLUMNS, Stage00Paths, prepare

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
    assert set(cells["CONFIDENCE_CLASS"]) <= {"HIGH", "MODERATE", "LOW"}
    assert set(cells["SHRINKAGE_LAMBDA"]) <= set(cs.SHRINKAGE_GRID)


def test_county_controls_hold_within_rounding_except_recorded_cap_spill() -> None:
    units = pd.read_csv(AUDIT / "unit_closure.csv")
    y2020 = units.loc[units["YEAR"].eq(2020)]
    over = y2020.loc[y2020["DEVIATION_FROM_CONTROL"].abs() > cs.ROUNDING_TOLERANCE_HEAD]
    # A unit may leave its rounding window only by passing animals it cannot
    # hold under the cow cap to other units.
    assert (over["PASSED_OUT_UNDER_CAP"] > 0).all()
    assert int(y2020["PASSED_OUT_UNDER_CAP"].sum()) == int(y2020["RECEIVED_UNDER_CAP"].sum())


def test_shrinkage_is_selected_by_the_hidden_cell_test() -> None:
    scores = pd.read_csv(AUDIT / "hidden_cell_test.csv")
    selection = pd.read_csv(AUDIT / "shrinkage_selection.csv").set_index(["YEAR", "VARIABLE"])["SHRINKAGE_LAMBDA"]
    expected = cs.select_shrinkage(scores)
    assert expected.sort_index().equals(selection.sort_index())


def test_stage00_regenerates_committed_outputs_exactly() -> None:
    result = prepare(PATHS)
    for name, payload in result.files.items():
        assert Path(name).read_bytes() == payload, name


def test_capped_hamilton_respects_capacity_and_total() -> None:
    alloc, left = cs.capped_hamilton(np.array([5.0, 1.0, 1.0]), np.array([3, 10, 10]), 12)
    assert left == 0 and alloc.sum() == 12 and alloc[0] == 3
    alloc, left = cs.capped_hamilton(np.array([1.0, 1.0]), np.array([2, 2]), 7)
    assert left == 3 and alloc.tolist() == [2, 2]


def test_unit_targets_close_national_total_within_tolerance() -> None:
    published = pd.Series({"A": 1000, "B": 2000})
    controls = pd.Series({"A": 1100, "B": 2100})
    plan = cs.unit_targets(published, {"A", "B"}, controls, hidden_national=230)
    assert int(plan["TARGET"].sum()) == 230
    assert (plan["TARGET"] - plan["ROUNDED_GAP"]).abs().max() <= cs.ROUNDING_TOLERANCE_HEAD
    with pytest.raises(AssertionError):
        cs.unit_targets(published, {"A", "B"}, controls, hidden_national=400)


def test_shrunk_weights() -> None:
    w = cs.shrunk_weights(np.array([3.0, 1.0]), 0.5)
    assert np.allclose(w, [0.5 * 0.75 + 0.25, 0.5 * 0.25 + 0.25])
    assert np.allclose(cs.shrunk_weights(np.zeros(4), 1.0), 0.25)
