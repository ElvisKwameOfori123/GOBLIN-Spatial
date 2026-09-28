"""Tests for the CSO-controlled annual ED sheep panel (2020 unchanged)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import LSU_COEFFICIENTS, build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.config import load_config
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
    # diagnostic, not a production cap: no region's gap is absorbed by a few EDs
    _, _, log = _built()
    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DISCREPANCY"]
    assert (audit["N_EDS_FOR_50PCT"] >= 5).all()


def test_dafm_interpolation_beats_frozen_2020_on_held_out_years() -> None:
    from goblin_spatial.sheep.annual_panel import _dafm_ewe_shares

    cfg, _, _ = _built()
    crosswalk, _ = _load_workbook(cfg.files["cso_sheep_workbook"])
    shares = _dafm_ewe_shares(
        cfg.files["dafm_sheep_county_pattern"], cfg.files["sheep_breed_anchors"], crosswalk
    )
    for held, lo, hi in ((2016, 2015, 2020), (2022, 2020, 2025)):
        w = (held - lo) / (hi - lo)
        interp = (1 - w) * shares[lo] + w * shares[hi]
        assert (interp - shares[held]).abs().mean() < (shares[KNOWN_YEAR] - shares[held]).abs().mean()


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


def test_county_base_is_2020_reference_and_closer_to_dafm_2020_levels() -> None:
    """County base = published county sheep + reference sheep of its EDs.

    DAFM 2020 county levels never enter production (only ratios to 2020 do),
    so they are an independent check of the 2020 county base.
    """

    from goblin_spatial.sheep.panel import _normalise_county

    cfg, _, log = _built()
    split = log.loc[(log["RECORD_TYPE"] == "COUNTY_SPLIT") & (log["YEAR"] == 2021)].set_index("County")
    ref = log.loc[log["RECORD_TYPE"] == "REFERENCE_2020"].groupby("County")["REFERENCE_SEED"].sum()
    e = pd.read_csv(cfg.files["cso_ed_2020"])
    e["County"] = e["County"].map(_normalise_county)
    county = e.groupby("County")["TOTAL_SHEEP"].sum().astype(float).add(ref, fill_value=0.0)
    region = split["Region"]
    expected = county.loc[split.index] / county.loc[split.index].groupby(region).transform("sum")
    assert np.allclose(split["CSO2020_REFERENCE_COUNTY_SHARE"], expected, atol=1e-12)

    dafm = pd.read_csv(cfg.files["dafm_sheep_county_pattern"])
    dafm["County"] = dafm["County"].map(_normalise_county)
    ewes = dafm.loc[dafm["YEAR"] == KNOWN_YEAR].set_index("County").loc[split.index, "EWES"]
    ewes = ewes / ewes.groupby(region).transform("sum")
    err_ref = (split["CSO2020_REFERENCE_COUNTY_SHARE"] - ewes).abs().mean()
    err_pub = (split["CSO2020_PUBLISHED_COUNTY_SHARE"] - ewes).abs().mean()
    assert err_ref < err_pub


def test_published_eds_follow_regional_trend_in_every_county() -> None:
    cfg, panel, _ = _built()
    _, region = _load_workbook(cfg.files["cso_sheep_workbook"])
    t = region.set_index(["Region", "Year"])["Total sheep__HEAD"]
    w = panel.pivot_table(index=["Region", "County", "CSOED"], columns="YEAR", values="TOTAL_SHEEP")
    pos = w[KNOWN_YEAR] > 0
    ratio = (w.loc[pos, 2021] / w.loc[pos, KNOWN_YEAR]).groupby(level=["Region", "County"]).median()
    for (reg, county), value in ratio.items():
        regional = t[(reg, 2021)] / t[(reg, KNOWN_YEAR)]
        assert abs(value / regional - 1) < 0.10, county


def test_held_out_lsu_supports_reference_distribution() -> None:
    """Published 2020 LSU is never used to place sheep; it checks the placement.

    For both candidate types (2010-positive, 2010-blank) the median residual
    LSU per 100 ha moves at least halfway to that of EDs with published sheep.
    """

    from goblin_spatial.cattle.ed_keys import canonical_ed_key

    cfg, _, log = _built()
    base, _ = build_annual_ed_panel(cfg)
    age = build_annual_age_sex_panel(cfg, base)
    x = age.loc[age["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    e = _published(cfg)
    cattle_lsu = sum(x[c] * w for c, w in LSU_COEFFICIENTS.items()).reindex(e.index)
    residual = (e["LSU"] - cattle_lsu - 0.1 * e["TOTAL_SHEEP"]) / e["ALL_GRASSLAND"] * 100
    seed = (
        log.loc[log["RECORD_TYPE"] == "REFERENCE_2020"].set_index("CSOED")["REFERENCE_SEED"]
        .reindex(e.index).fillna(0.0)
    )
    after = residual - 0.1 * seed / e["ALL_GRASSLAND"] * 100
    baseline = residual[e["TOTAL_SHEEP"] > 0].median()

    e10 = pd.read_csv(cfg.files["cso_ed_2010"], dtype=str, keep_default_na=False)
    text = e10.set_index(e10["CSOED"].map(canonical_ed_key))["TOTAL_SHEEP"].str.strip()
    s10 = e.index.map(canonical_ed_key).map(pd.to_numeric(text.mask(text.eq(""))))
    s10 = pd.Series(np.asarray(s10, dtype=float), index=e.index)
    for group in (seed.gt(0) & s10.gt(0), seed.gt(0) & s10.isna()):
        assert group.sum() > 100
        before_gap = residual[group].median() - baseline
        after_gap = after[group].median() - baseline
        assert before_gap > 1.0
        assert abs(after_gap) < before_gap / 2
