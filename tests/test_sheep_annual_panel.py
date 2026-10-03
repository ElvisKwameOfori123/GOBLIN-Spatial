"""Tests for the CSO-controlled annual ED sheep panel (2020 unchanged)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.sheep.annual_panel import (
    ED_CLASS_COLS,
    KNOWN_YEAR,
    YEARS,
    build_annual_sheep_panel,
)
from goblin_spatial.sheep.panel import _load_workbook, _normalise_county

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    panel, log = build_annual_sheep_panel(cfg)
    return cfg, panel, log


def _published(cfg) -> pd.DataFrame:
    e = pd.read_csv(cfg.files["cso_ed_2020"])
    e["CSOED"] = e["CSOED"].astype(str)
    e["County"] = e["County"].map(_normalise_county)
    return e.set_index("CSOED")


def test_shape_integers_and_class_identity() -> None:
    _, panel, _ = _built()
    assert len(panel) == 2857 * len(YEARS)
    assert not panel[["YEAR", "CSOED"]].duplicated().any()
    cols = ["TOTAL_SHEEP", *ED_CLASS_COLS, "EWES", "BREEDING_SHEEP"]
    assert all(np.issubdtype(panel[c].dtype, np.integer) for c in cols)
    assert (panel[cols] >= 0).all().all()
    assert (panel[ED_CLASS_COLS].sum(axis=1) == panel["TOTAL_SHEEP"]).all()


def test_2020_is_published_census_unchanged() -> None:
    cfg, panel, _ = _built()
    published = _published(cfg)["TOTAL_SHEEP"]
    known = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")["TOTAL_SHEEP"]
    assert np.array_equal(known.loc[published.index].to_numpy(), published.to_numpy())


def test_unknown_years_close_exactly_to_aaa09_regions_and_classes() -> None:
    cfg, panel, log = _built()
    _, region = _load_workbook(cfg.files["cso_sheep_workbook"])
    classes = log.loc[log["RECORD_TYPE"] == "REGION_CLASSES"].set_index(["YEAR", "Region"])
    for year in YEARS:
        x = panel.loc[panel["YEAR"] == year].groupby("Region")[["TOTAL_SHEEP", *ED_CLASS_COLS]].sum()
        for class_col in ED_CLASS_COLS:
            assert (x[class_col] == classes.loc[year].loc[x.index, f"TARGET_{class_col}"]).all()
        if year == KNOWN_YEAR:
            continue
        target = region.loc[region["Year"] == year].set_index("Region")["Total sheep__HEAD"]
        assert (x["TOTAL_SHEEP"] == target.loc[x.index]).all(), year


def test_published_2020_zero_stays_zero_after_2020() -> None:
    cfg, panel, _ = _built()
    published = _published(cfg)
    zeros = published.index[published["TOTAL_SHEEP"].eq(0)]
    later = panel.loc[(panel["YEAR"] > KNOWN_YEAR) & panel["CSOED"].isin(zeros)]
    assert int(later["TOTAL_SHEEP"].sum()) == 0


def test_post_2020_ed_split_is_published_2020_share_pro_rata() -> None:
    cfg, panel, _ = _built()
    published = _published(cfg)
    pub_county_total = published.groupby("County")["TOTAL_SHEEP"].transform("sum")
    pub_share = published["TOTAL_SHEEP"] / pub_county_total

    for year in (2021, 2025):
        frame = panel.loc[panel["YEAR"] == year].set_index("CSOED")
        county_total = frame.groupby("County")["TOTAL_SHEEP"].transform("sum")
        expected = pub_share.loc[frame.index] * county_total
        gap = (frame["TOTAL_SHEEP"] - expected).abs()
        assert float(gap.max()) < 1.0, year


def test_2020_source_difference_is_logged_only() -> None:
    cfg, panel, log = _built()
    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DIFFERENCE"].set_index("Region")
    assert len(audit) == 7
    observed = panel.loc[panel["YEAR"] == KNOWN_YEAR].groupby("Region")["TOTAL_SHEEP"].sum()
    assert (audit.loc[observed.index, "ED_PUBLISHED_TOTAL"] == observed).all()
    # Model-universe sheep (census State total 5,520,208 less 7,198 sheep
    # filled into suppressed cells outside the model universe) minus the
    # AAA09 rounded regional sum (5,520,200). Before Stage 00 the gap was
    # -259,807 because suppressed sheep cells were stored as zero.
    assert int(audit["DIFFERENCE"].sum()) == -7190
    assert "REFERENCE_SEED" not in log.columns
    assert "SEED_REFERENCE" not in log.columns


def test_dafm_moves_published_2020_county_share_direction_only() -> None:
    _, _, log = _built()
    split = log.loc[log["RECORD_TYPE"] == "COUNTY_SPLIT"]
    assert len(split) == 26 * (len(YEARS) - 1)
    for (_, _), g in split.groupby(["YEAR", "Region"]):
        assert np.isclose(g["COUNTY_SHARE"].sum(), 1.0)
        moved = g["COUNTY_SHARE"] / g["CSO2020_PUBLISHED_COUNTY_SHARE"]
        index = g["DAFM_EWE_INDEX"]
        assert np.allclose(moved / moved.mean(), index / index.mean(), rtol=1e-9)
