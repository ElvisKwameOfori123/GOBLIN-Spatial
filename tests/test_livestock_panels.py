"""Tests for the merged annual ED livestock panels (13 CSO groups, 31 cohorts)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.export.livestock_panels import (
    CONTROL_PREFIX,
    CSO_13,
    ID_COLS,
    NAME_13,
    NAME_31,
    COHORTS_31,
    build_livestock_panels,
    export_sqlite,
    run_checks,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    panel13, panel31 = build_livestock_panels(cfg)
    return cfg, panel13, panel31


def test_every_accounting_check_passes() -> None:
    cfg, panel13, panel31 = _built()
    checks = run_checks(panel13, panel31, cfg)
    assert len(checks) >= 15
    assert checks["PASS"].all(), checks.loc[~checks["PASS"]]


def test_names_and_contract_match_the_export_module() -> None:
    from goblin_spatial.export.workbook import CSO_13_COHORTS

    assert NAME_13 == "CSO_13_Cohort_Annual_Panel_2015_2025"
    assert NAME_31 == "GOBLIN_31_Cohort_Annual_Panel_2015_2025"
    assert CSO_13 == CSO_13_COHORTS


def test_column_sets() -> None:
    _, panel13, panel31 = _built()
    assert len(CSO_13) == 13 and len(COHORTS_31) == 31
    assert set(CSO_13) <= set(panel13.columns)
    assert not set(COHORTS_31) & set(panel13.columns)
    assert set(COHORTS_31) <= set(panel31.columns)
    assert set(CONTROL_PREFIX.values()) <= set(panel31.columns)
    # no two columns differ only by case (SQLite ignores case)
    for panel in (panel13, panel31):
        lowered = [c.lower() for c in panel.columns]
        assert len(lowered) == len(set(lowered))




def test_complete_ed_spine_and_identifiers_are_preserved() -> None:
    cfg, panel13, panel31 = _built()
    anchor = pd.read_csv(cfg.files["cso_ed_2020"], dtype={"CSOED": str})
    expected = set(anchor["CSOED"])

    assert len(ID_COLS) == 11
    assert set(ID_COLS) <= set(panel13.columns)
    assert set(ID_COLS) <= set(panel31.columns)

    for year in range(2015, 2026):
        p13 = panel13.loc[panel13["YEAR"] == year]
        p31 = panel31.loc[panel31["YEAR"] == year]
        assert set(p13["CSOED"].astype(str)) == expected
        assert set(p31["CSOED"].astype(str)) == expected
        assert len(p13) == len(anchor) == 2857
        assert len(p31) == len(anchor) == 2857

    for column in (
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED_RAW",
        "EDNAME",
        "COUNTYNAME",
    ):
        assert panel13[column].notna().all()
        assert panel31[column].notna().all()


def test_zero_species_eds_remain_in_the_study_panel() -> None:
    cfg, panel13, panel31 = _built()
    anchor = pd.read_csv(cfg.files["cso_ed_2020"], dtype={"CSOED": str})
    p13 = panel13.loc[panel13["YEAR"] == 2020].set_index("CSOED")
    p31 = panel31.loc[panel31["YEAR"] == 2020].set_index("CSOED")

    zero_cattle = anchor.loc[anchor["TOTAL_CATTLE"].eq(0), "CSOED"].astype(str)
    zero_sheep = anchor.loc[anchor["TOTAL_SHEEP"].eq(0), "CSOED"].astype(str)
    assert len(zero_cattle) > 0
    assert len(zero_sheep) > 0

    assert set(zero_cattle) <= set(p13.index)
    assert set(zero_sheep) <= set(p13.index)
    assert (p13.loc[zero_cattle, "TOTAL_CATTLE"] == 0).all()
    assert (p13.loc[zero_sheep, "TOTAL_SHEEP"] == 0).all()

    assert set(zero_cattle) <= set(p31.index)
    assert set(zero_sheep) <= set(p31.index)
    assert (p31.loc[zero_cattle, "CSO_TOTAL_CATTLE"] == 0).all()
    assert (p31.loc[zero_sheep, "CSO_TOTAL_SHEEP"] == 0).all()


def test_panels_match_the_finished_chains() -> None:
    from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
    from goblin_spatial.sheep import build_annual_sheep_panel

    cfg, panel13, _ = _built()
    cattle, _ = build_annual_ed_panel(cfg)
    sheep, _ = build_annual_sheep_panel(cfg)
    key = ["YEAR", "CSOED"]
    left = panel13.set_index(key)
    for frame, cols in ((cattle, ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]),
                        (sheep, ["TOTAL_SHEEP", "EWES_2_PLUS", "EWES_UNDER_2", "RAMS", "OTHER_SHEEP"])):
        right = frame.assign(CSOED=frame["CSOED"].astype(str)).set_index(key)[cols]
        assert (left.loc[right.index, cols].to_numpy() == right.to_numpy()).all()


def test_sqlite_round_trip(tmp_path) -> None:
    import sqlite3

    cfg, panel13, panel31 = _built()
    path = export_sqlite(panel13, panel31, run_checks(panel13, panel31, cfg), tmp_path / "x.sqlite")
    with sqlite3.connect(path) as con:
        back = pd.read_sql(f'select * from "{NAME_13}"', con)
        n31 = con.execute(f'select count(*) from "{NAME_31}"').fetchone()[0]
    assert len(back) == len(panel13) and n31 == len(panel31)
    assert (back[CSO_13].to_numpy() == panel13[CSO_13].to_numpy()).all()
