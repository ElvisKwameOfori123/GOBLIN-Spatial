"""Tests for the merged annual ED livestock panels (13 CSO groups, 31 cohorts)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.export.livestock_panels import (
    CONTROL_PREFIX,
    CSO_13,
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
        back = pd.read_sql("select * from annual_livestock_cso_13_groups_2015_2025", con)
        n31 = con.execute("select count(*) from annual_livestock_31_cohorts_2015_2025").fetchone()[0]
    assert len(back) == len(panel13) and n31 == len(panel31)
    assert (back[CSO_13].to_numpy() == panel13[CSO_13].to_numpy()).all()
