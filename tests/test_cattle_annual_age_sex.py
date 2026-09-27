"""Tests for the age-sex split on the CSO annual ED panel."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from goblin_spatial.cattle.annual_age_sex import (
    build_annual_age_sex_panel,
    county_age_sex_targets,
    lsu_check_2020,
)
from goblin_spatial.cattle.annual_panel import KNOWN_YEAR, build_annual_ed_panel
from goblin_spatial.cattle.panel import AGE_SEX_COLS, _load_aaa10
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    base, _ = build_annual_ed_panel(cfg)
    a1 = build_annual_age_sex_panel(cfg, base, "dafm_log_odds")
    a0 = build_annual_age_sex_panel(cfg, base, "flat_county")
    return cfg, base, a1, a0


def test_annual_panel_is_not_changed() -> None:
    _, base, a1, _ = _built()
    cols = ["YEAR", "CSOED", "DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]
    left = base[cols].sort_values(["YEAR", "CSOED"]).reset_index(drop=True)
    right = a1[cols].sort_values(["YEAR", "CSOED"]).reset_index(drop=True)
    assert left.equals(right)


def test_rows_close_to_other_cattle() -> None:
    _, _, a1, a0 = _built()
    for panel in (a1, a0):
        assert not panel[["YEAR", "CSOED"]].duplicated().any()
        assert all(np.issubdtype(panel[column].dtype, np.integer) for column in AGE_SEX_COLS)
        assert (panel[AGE_SEX_COLS] >= 0).all().all()
        assert (panel[AGE_SEX_COLS].sum(axis=1) == panel["OTHER_CATTLE"]).all()


def test_dafm_signal_is_retained_for_audit() -> None:
    _, _, a1, a0 = _built()

    assert a1["AGE_SEX_DAFM_Q_LOCAL"].notna().all()
    assert a1["AGE_SEX_DAFM_Q_COUNTY"].notna().all()
    assert a1["AGE_SEX_AIM_MATCHED"].dtype == bool

    unmatched = ~a1["AGE_SEX_AIM_MATCHED"]
    assert np.allclose(
        a1.loc[unmatched, "AGE_SEX_DAFM_Q_LOCAL"],
        a1.loc[unmatched, "AGE_SEX_DAFM_Q_COUNTY"],
    )

    assert not a0["AGE_SEX_AIM_MATCHED"].any()
    assert a0["AGE_SEX_DAFM_Q_LOCAL"].isna().all()
    assert a0["AGE_SEX_DAFM_Q_COUNTY"].isna().all()


def test_county_columns_match_cso() -> None:
    cfg, _, a1, _ = _built()
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    for (year, name), group in a1.groupby(["YEAR", "County"]):
        target = county_age_sex_targets(county, year, name, int(group["OTHER_CATTLE"].sum()))
        assert np.array_equal(group[AGE_SEX_COLS].sum().to_numpy(), target), (year, name)


def test_2020_uses_published_other_cattle() -> None:
    cfg, _, a1, _ = _built()
    import pandas as pd

    published = pd.read_csv(cfg.files["cso_ed_2020"])
    x = a1.loc[a1["YEAR"] == KNOWN_YEAR]
    assert int(x[AGE_SEX_COLS].sum().sum()) == int(published["OTHER_CATTLE"].sum())


def test_dafm_prior_improves_held_out_lsu() -> None:
    cfg, _, a1, a0 = _built()
    flat = lsu_check_2020(cfg, a0)
    dafm = lsu_check_2020(cfg, a1)
    assert dafm["eligible_eds"] == flat["eligible_eds"]
    assert dafm["median_abs_residual"] < flat["median_abs_residual"]
