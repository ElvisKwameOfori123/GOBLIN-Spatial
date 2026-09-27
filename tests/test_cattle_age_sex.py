"""Full-data tests for Step 3 DAFM-informed cattle age-sex allocation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.age_sex import build_dafm_age_signal
from goblin_spatial.cattle.panel import (
    AGE_SEX_COLS,
    _build_2020_baseline,
    _load_aaa10,
    build_cattle_panel,
)
from goblin_spatial.config import load_config


pytestmark = pytest.mark.full_data

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"

FOLDS = {
    1: ["Clare", "Cork", "Longford", "Louth", "Wicklow"],
    2: ["Donegal", "Galway", "Laois", "Monaghan", "Waterford"],
    3: ["Carlow", "Limerick", "Meath", "Sligo", "Westmeath"],
    4: ["Dublin", "Kerry", "Mayo", "Offaly", "Tipperary"],
    5: ["Cavan", "Kildare", "Kilkenny", "Leitrim", "Roscommon", "Wexford"],
}


def _config_with_age_mode(mode: str):
    cfg = load_config(CONFIG)
    raw = deepcopy(cfg.raw)
    raw.setdefault("cattle", {})["age_sex_prior"] = mode
    return replace(cfg, raw=raw)


def _anchor(mode: str) -> pd.DataFrame:
    cfg = _config_with_age_mode(mode)
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    return _build_2020_baseline(
        cfg.files["cso_ed_2020"],
        county,
        cfg.expected_eds,
        age_sex_mode=mode,
        dafm_path=cfg.files["dafm_aim_ed_cattle_profile_2020"],
        logit_epsilon=float(cfg.raw["cattle"].get("dafm_logit_epsilon", 1e-6)),
        dairy_anchor_mode=str(
            cfg.raw.get("cattle", {}).get(
                "dairy_anchor_prior", "positive_proportional"
            )
        ),
        ed_2010_path=cfg.files["cso_ed_2010"],
    )


def _eligible(frame: pd.DataFrame) -> pd.Series:
    lsu_max = (
        frame["DAIRY_COW"]
        + 0.8 * frame["OTHER_COW"]
        + frame["OTHER_CATTLE"]
        + 0.1 * frame["TOTAL_SHEEP"]
    )
    return (
        (frame["TOTAL_CATTLE"] > 0)
        & (frame["LSU"] > 0)
        & (frame["LSU"] <= lsu_max + 1.0)
    )


def _lsu_residual(frame: pd.DataFrame) -> pd.Series:
    modelled = (
        frame["DAIRY_COW"]
        + 0.8 * frame["OTHER_COW"]
        + frame["BULLS"]
        + 0.4
        * (frame["CATTLE_MALE_UNDER_1"] + frame["CATTLE_FEMALE_UNDER_1"])
        + 0.7 * (frame["CATTLE_MALE_1_2"] + frame["CATTLE_FEMALE_1_2"])
        + frame["CATTLE_MALE_2_PLUS"]
        + 0.8 * frame["CATTLE_FEMALE_2_PLUS"]
        + 0.1 * frame["TOTAL_SHEEP"]
    )
    return frame["LSU"] - modelled


def test_dafm_age_signal_has_high_coverage_without_forcing_unmatched_eds() -> None:
    cfg = _config_with_age_mode("dafm_log_odds")
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    flat = _build_2020_baseline(
        cfg.files["cso_ed_2020"],
        county,
        cfg.expected_eds,
        dafm_path=cfg.files["dafm_aim_ed_cattle_profile_2020"],
        dairy_anchor_mode=str(
            cfg.raw.get("cattle", {}).get(
                "dairy_anchor_prior", "positive_proportional"
            )
        ),
    )
    signal = build_dafm_age_signal(
        flat, cfg.files["dafm_aim_ed_cattle_profile_2020"]
    )

    assert int(signal["DAFM_MATCHED"].sum()) == 2577
    cattle_coverage = float(
        flat.loc[signal["DAFM_MATCHED"], "OTHER_CATTLE"].sum()
        / flat["OTHER_CATTLE"].sum()
    )
    assert cattle_coverage > 0.93

    unmatched = ~signal["DAFM_MATCHED"]
    assert np.allclose(
        signal.loc[unmatched, "DAFM_Q_LOCAL"],
        signal.loc[unmatched, "DAFM_Q_COUNTY"],
        atol=0.0,
        rtol=0.0,
    )


def test_dafm_log_odds_preserves_exact_ed_rows_and_county_columns() -> None:
    a0 = _anchor("flat_county")
    a1 = _anchor("dafm_log_odds")

    assert np.array_equal(
        a1[AGE_SEX_COLS].sum(axis=1).to_numpy(),
        a1["OTHER_CATTLE"].to_numpy(),
    )

    a0_county = a0.groupby("County")[AGE_SEX_COLS].sum().sort_index()
    a1_county = a1.groupby("County")[AGE_SEX_COLS].sum().sort_index()
    pd.testing.assert_frame_equal(a1_county, a0_county)

    assert int((a1[AGE_SEX_COLS] != a0[AGE_SEX_COLS]).to_numpy().sum()) > 0


def test_dafm_log_odds_passes_prespecified_lsu_gate_and_improves_diagnostic() -> None:
    a0 = _anchor("flat_county")
    a1 = _anchor("dafm_log_odds")

    eligible0 = _eligible(a0)
    eligible1 = _eligible(a1)
    diagnostic0 = (a0["TOTAL_CATTLE"] > 0) & (a0["LSU"] > 0)
    diagnostic1 = (a1["TOTAL_CATTLE"] > 0) & (a1["LSU"] > 0)

    rate0 = float(eligible0.sum() / diagnostic0.sum())
    rate1 = float(eligible1.sum() / diagnostic1.sum())
    assert rate1 >= rate0 - 0.01

    pooled0 = _lsu_residual(a0.loc[eligible0]).abs().median()
    pooled1 = _lsu_residual(a1.loc[eligible1]).abs().median()
    assert float(pooled1) < float(pooled0)

    for counties in FOLDS.values():
        f0 = a0["County"].isin(counties) & eligible0
        f1 = a1["County"].isin(counties) & eligible1
        median0 = _lsu_residual(a0.loc[f0]).abs().median()
        median1 = _lsu_residual(a1.loc[f1]).abs().median()
        assert float(median1) < float(median0)


def test_production_panel_uses_dafm_log_odds_and_closes_all_years() -> None:
    cfg = _config_with_age_mode("dafm_log_odds")
    panel = build_cattle_panel(cfg)

    assert len(panel) == cfg.expected_eds * 11
    assert (
        panel[AGE_SEX_COLS].sum(axis=1).to_numpy()
        == panel["OTHER_CATTLE"].to_numpy()
    ).all()

    flat = build_cattle_panel(_config_with_age_mode("flat_county"))
    p2020 = panel.loc[panel["YEAR"] == 2020, ["CSOED", *AGE_SEX_COLS]]
    f2020 = flat.loc[flat["YEAR"] == 2020, ["CSOED", *AGE_SEX_COLS]]
    merged = p2020.merge(f2020, on="CSOED", suffixes=("_A1", "_A0"))
    differences = [
        (merged[f"{column}_A1"] != merged[f"{column}_A0"]).any()
        for column in AGE_SEX_COLS
    ]
    assert any(differences)
