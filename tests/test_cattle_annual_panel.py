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


def test_no_single_ed_absorbs_county_cow_shortfall() -> None:
    _, panel, _ = _built()
    wide = panel.pivot_table(index="CSOED", columns="YEAR", values="DAIRY_COW")
    # Carrigallen East published 201 dairy cows; the unknown years stay near it.
    assert wide.loc["28060"].drop(KNOWN_YEAR).max() < 2 * 201
    # published dairy EDs follow the national trend 2020 -> 2021
    has = wide[KNOWN_YEAR] > 0
    ratio = wide.loc[has, 2021] / wide.loc[has, KNOWN_YEAR]
    assert ratio.max() < 1.5


def test_every_county_year_calibrated_without_fallback() -> None:
    _, _, log = _built()
    calibration = log.loc[log["RECORD_TYPE"] == "CALIBRATION"]
    assert len(calibration) == 26 * (len(YEARS) - 1)
    assert calibration["SUPPORT_FALLBACK_LEVEL"].eq(0).all()


def test_2020_source_discrepancy_is_written_to_log() -> None:
    cfg, panel, log = _built()
    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DISCREPANCY"].copy()
    assert len(audit) == 26

    county = _load_aaa10(cfg.files["cso_cattle_county"])
    target = _county_controls(county, KNOWN_YEAR)
    observed = (
        panel.loc[panel["YEAR"] == KNOWN_YEAR]
        .groupby("County")[list(COLUMNS)]
        .sum()
    )
    for column in COLUMNS:
        expected = observed[column] - target.loc[observed.index, column]
        actual = audit.set_index("County").loc[observed.index, f"DIFF_{column}"]
        assert np.array_equal(actual.to_numpy(), expected.to_numpy())

    assert audit["REFERENCE_SEEDED_TOTAL"].sum() == 0.0
    assert log.attrs["seeded_head_2020_reference"] == 0.0


def test_integerisation_keeps_structural_zeros() -> None:
    fitted = np.array([[1.5, 0.0, 1.5], [0.5, 2.0, 0.5], [0.0, 1.0, 1.0]])
    rows = fitted.sum(axis=1).round().astype(int)
    cols = fitted.sum(axis=0).round().astype(int)
    out = _integerise_keep_zeros(fitted, rows, cols)
    assert np.array_equal(out.sum(axis=1), rows)
    assert np.array_equal(out.sum(axis=0), cols)
    assert out[0, 1] == 0 and out[2, 0] == 0


def test_post_2020_published_component_zeros_remain_zero() -> None:
    cfg, panel, log = _built()
    published = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    post = panel.loc[panel["YEAR"].between(2021, 2025)].copy()

    for component in COMPONENTS:
        zero_eds = set(published.index[published[component].eq(0)])
        if not zero_eds:
            continue
        affected = post.loc[post["CSOED"].isin(zero_eds), component]
        assert affected.eq(0).all(), f"{component}: a published 2020 zero was filled after 2020"

    assert log.attrs["seeded_head_2020_reference"] == 0.0
    assert log.attrs["unseeded_head_2020_reference"] == pytest.approx(
        log.attrs["cow_shortfall_2020"]
    )
