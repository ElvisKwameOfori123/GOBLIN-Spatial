"""Tests for the CSO-only annual ED cattle panel (known truth unchanged)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.annual_panel import (
    COLUMNS,
    COMPONENTS,
    KNOWN_YEAR,
    YEARS,
    _county_controls,
    _integerise_keep_zeros,
    build_annual_ed_panel,
)
from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.cattle.panel import _load_aaa10
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    panel, log = build_annual_ed_panel(cfg)
    return cfg, panel, log


def test_shape_and_identity() -> None:
    _, panel, _ = _built()
    assert len(panel) == 2857 * len(YEARS)
    assert not panel[["YEAR", "CSOED"]].duplicated().any()
    assert set(panel["YEAR"]) == set(YEARS)
    assert panel.groupby("YEAR")["CSOED"].nunique().eq(2857).all()
    assert all(np.issubdtype(panel[column].dtype, np.integer) for column in COLUMNS)
    assert (panel[list(COLUMNS)] >= 0).all().all()
    assert (panel[list(COMPONENTS)].sum(axis=1) == panel["TOTAL_CATTLE"]).all()


def test_2020_is_published_census_unchanged() -> None:
    cfg, panel, _ = _built()
    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")[list(COLUMNS)]
    known = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")[list(COLUMNS)]
    assert (known.loc[published.index].to_numpy() == published.to_numpy()).all()


def test_unknown_years_close_exactly_to_aaa10() -> None:
    cfg, panel, _ = _built()
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    for year in YEARS:
        if year == KNOWN_YEAR:
            continue
        sums = panel.loc[panel["YEAR"] == year].groupby("County")[list(COLUMNS)].sum()
        target = _county_controls(county, year).loc[sums.index, list(COLUMNS)]
        assert (sums.to_numpy() == target.to_numpy()).all(), year


def test_zero_in_both_censuses_stays_zero() -> None:
    cfg, panel, _ = _built()
    e20 = pd.read_csv(cfg.files["cso_ed_2020"])
    e20["CSOED"] = e20["CSOED"].astype(str)
    e10 = pd.read_csv(cfg.files["cso_ed_2010"], dtype=str, keep_default_na=False)
    e10 = e10.set_index(e10["CSOED"].map(canonical_ed_key))
    keys = e20["CSOED"].map(canonical_ed_key)
    for column in COLUMNS:
        zero_2010 = keys.map(e10[column]).astype(str).str.strip().eq("0")
        both = e20.loc[e20[column].eq(0) & zero_2010, "CSOED"]
        values = panel.loc[panel["CSOED"].isin(both), column]
        assert int(values.sum()) == 0, column


def test_published_2020_zero_stays_zero_after_2020() -> None:
    cfg, panel, _ = _built()
    e20 = pd.read_csv(cfg.files["cso_ed_2020"])
    e20["CSOED"] = e20["CSOED"].astype(str)
    later = panel.loc[panel["YEAR"] > KNOWN_YEAR]
    for column in COLUMNS:
        zero = e20.loc[e20[column].eq(0), "CSOED"]
        assert int(later.loc[later["CSOED"].isin(zero), column].sum()) == 0, column


def test_post_2020_is_published_share_pro_rata() -> None:
    cfg, panel, _ = _built()
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    e20 = pd.read_csv(cfg.files["cso_ed_2020"])
    e20["CSOED"] = e20["CSOED"].astype(str)
    e20 = e20.set_index("CSOED")
    for year in (2021, 2025):
        frame = panel.loc[panel["YEAR"] == year].set_index("CSOED")
        controls = _county_controls(county, year)
        for component in COMPONENTS:
            share = e20[component] / e20.groupby("County")[component].transform("sum")
            expected = share * e20["County"].map(_normalise(controls[component]))
            # Hamilton rounding moves each ED by less than one head
            gap = (frame.loc[e20.index, component] - expected).abs()
            assert float(gap.max()) < 1.0, (year, component)


def _normalise(series: pd.Series) -> pd.Series:
    from goblin_spatial.cattle.panel import _normalise_county

    return series.rename(index=_normalise_county)


def test_2020_source_difference_is_written_to_log() -> None:
    cfg, panel, log = _built()
    assert len(log) == 26
    assert (log["RECORD_TYPE"] == "2020_SOURCE_DIFFERENCE").all()

    county = _load_aaa10(cfg.files["cso_cattle_county"])
    target = _county_controls(county, KNOWN_YEAR)
    observed = (
        panel.loc[panel["YEAR"] == KNOWN_YEAR]
        .groupby("County")[list(COLUMNS)]
        .sum()
    )
    for column in COLUMNS:
        expected = observed[column] - target.loc[observed.index, column]
        actual = log.set_index("County").loc[observed.index, f"DIFF_{column}"]
        assert np.array_equal(actual.to_numpy(), expected.to_numpy())
    assert int(log["DIFF_DAIRY_COW"].sum()) == 0


def test_integerisation_keeps_structural_zeros() -> None:
    fitted = np.array([[1.5, 0.0, 1.5], [0.5, 2.0, 0.5], [0.0, 1.0, 1.0]])
    rows = fitted.sum(axis=1).round().astype(int)
    cols = fitted.sum(axis=0).round().astype(int)
    out = _integerise_keep_zeros(fitted, rows, cols)
    assert np.array_equal(out.sum(axis=1), rows)
    assert np.array_equal(out.sum(axis=0), cols)
    assert out[0, 1] == 0 and out[2, 0] == 0
