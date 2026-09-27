"""Tests for the CSO-controlled annual ED sheep panel (2020 unchanged)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import LSU_COEFFICIENTS, build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.config import load_config
from goblin_spatial.sheep import add_sheep_cohorts
from goblin_spatial.sheep.annual_panel import (
    ED_CLASS_COLS,
    KNOWN_YEAR,
    YEARS,
    build_annual_sheep_panel,
)
from goblin_spatial.sheep.panel import _load_workbook

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    panel, log = build_annual_sheep_panel(cfg)
    return cfg, panel, log


@lru_cache(maxsize=1)
def _unseeded():
    return build_annual_sheep_panel(load_config(CONFIG), seed_reference=False)


def _published(cfg) -> pd.DataFrame:
    e = pd.read_csv(cfg.files["cso_ed_2020"])
    e["CSOED"] = e["CSOED"].astype(str)
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
    assert (known.loc[published.index].to_numpy() == published.to_numpy()).all()


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


def test_zero_in_both_censuses_stays_zero() -> None:
    cfg, panel, _ = _built()
    e10 = pd.read_csv(cfg.files["cso_ed_2010"], dtype=str, keep_default_na=False)
    from goblin_spatial.cattle.ed_keys import canonical_ed_key

    zero10 = set(e10.loc[e10["TOTAL_SHEEP"].str.strip().eq("0"), "CSOED"].map(canonical_ed_key))
    e20 = _published(cfg)
    keys = e20.index.map(canonical_ed_key)
    both = e20.index[(e20["TOTAL_SHEEP"].eq(0)) & keys.isin(zero10)]
    assert len(both) > 150
    assert int(panel.loc[panel["CSOED"].isin(both), "TOTAL_SHEEP"].sum()) == 0


def test_2020_discrepancy_logged_and_fully_seeded() -> None:
    cfg, panel, log = _built()
    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DISCREPANCY"].set_index("Region")
    assert len(audit) == 7
    observed = panel.loc[panel["YEAR"] == KNOWN_YEAR].groupby("Region")["TOTAL_SHEEP"].sum()
    assert (audit.loc[observed.index, "ED_PUBLISHED_TOTAL"] == observed).all()
    assert int(audit["DIFFERENCE"].sum()) == -259807
    assert np.isclose(audit["REFERENCE_SEEDED_TOTAL"].sum(), 259807)
    assert np.allclose(audit["UNSEEDED_RESIDUAL"], 0.0)
    ref = log.loc[log["RECORD_TYPE"] == "REFERENCE_2020"]
    assert (ref["ED_PUBLISHED_TOTAL"] == 0).all()


def test_seeding_is_not_concentrated() -> None:
    # diagnostic bound, not a production cap: no ED takes a tenth of its region's gap
    _, _, log = _built()
    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DISCREPANCY"]
    assert (audit["MAX_SEED_SHARE_OF_GAP"] < 0.10).all()


def test_seeding_keeps_published_eds_on_regional_trend() -> None:
    def spread(panel: pd.DataFrame) -> float:
        w = panel.pivot_table(index="CSOED", columns="YEAR", values="TOTAL_SHEEP")
        pos = w[KNOWN_YEAR] > 0
        return float((w.loc[pos, 2021] / w.loc[pos, KNOWN_YEAR]).quantile(0.95))

    _, seeded, _ = _built()
    unseeded, _ = _unseeded()
    assert spread(seeded) < 1.10
    # without the reference distribution the whole 2020 gap lands on published-sheep EDs
    assert spread(unseeded) > 1.30


def test_dafm_moves_county_direction_only() -> None:
    _, _, log = _built()
    split = log.loc[log["RECORD_TYPE"] == "COUNTY_SPLIT"]
    assert len(split) == 26 * (len(YEARS) - 1)
    for (year, reg), g in split.groupby(["YEAR", "Region"]):
        assert np.isclose(g["COUNTY_SHARE"].sum(), 1.0)
        moved = g["COUNTY_SHARE"] / g["CSO2020_REFERENCE_COUNTY_SHARE"]
        index = g["DAFM_EWE_INDEX"]
        # direction of each county's relative move follows the DAFM ewe index
        assert np.allclose(moved / moved.mean(), index / index.mean(), rtol=1e-9)


def test_held_out_lsu_supports_reference_distribution() -> None:
    cfg, _, log = _built()
    base, _ = build_annual_ed_panel(cfg)
    age = build_annual_age_sex_panel(cfg, base)
    x = age.loc[age["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    e = _published(cfg)
    cattle_lsu = sum(x[c] * w for c, w in LSU_COEFFICIENTS.items()).reindex(e.index)
    residual = (e["LSU"] - cattle_lsu - 0.1 * e["TOTAL_SHEEP"]) / e["ALL_GRASSLAND"] * 100
    seed = log.loc[log["RECORD_TYPE"] == "REFERENCE_2020"].set_index("CSOED")["REFERENCE_SEED"]
    seeded = e.index.isin(seed.index)
    with_sheep = e["TOTAL_SHEEP"] > 0
    before = residual[seeded].median()
    after = (residual[seeded] - 0.1 * seed.reindex(e.index[seeded]) / e.loc[seeded, "ALL_GRASSLAND"] * 100).median()
    baseline = residual[with_sheep].median()
    assert before > 2 * baseline
    assert abs(after - baseline) < abs(before - baseline) / 2


def test_existing_sheep_cohorts_run_unchanged() -> None:
    cfg, panel, _ = _built()
    cohorts = add_sheep_cohorts(panel, cfg)
    assert (cohorts["GOBLIN_10_SHEEP_COHORT_TOTAL"] == cohorts["TOTAL_SHEEP"]).all()
