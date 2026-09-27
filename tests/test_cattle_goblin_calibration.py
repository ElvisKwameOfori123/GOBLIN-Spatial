"""Tests for the separate national GOBLIN cattle calibration layer."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS, add_cattle_cohorts
from goblin_spatial.cattle.goblin_calibration import (
    CSO_ONLY_YEARS,
    GOBLIN_CALIBRATION_YEARS,
    PROVENANCE_CSO,
    PROVENANCE_GOBLIN,
    build_goblin_calibrated_cattle,
)
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    annual, _ = build_annual_ed_panel(cfg)
    age_sex = build_annual_age_sex_panel(cfg, annual, mode="dafm_log_odds")
    cso_cohorts = add_cattle_cohorts(age_sex, cfg)
    before_csv = cso_cohorts.to_csv(index=False).encode("utf-8")
    calibrated, factors = build_goblin_calibrated_cattle(cfg, cso_cohorts)
    after_csv = cso_cohorts.to_csv(index=False).encode("utf-8")
    return cfg, cso_cohorts, calibrated, factors, before_csv, after_csv


def test_goblin_layer_does_not_modify_cso_source() -> None:
    _, source, calibrated, _, before_csv, after_csv = _built()

    assert before_csv == after_csv
    assert len(source) == len(calibrated) == 31_427
    assert source[["YEAR", "CSOED"]].equals(calibrated[["YEAR", "CSOED"]])


def test_2015_2020_national_cohort_totals_match_targets() -> None:
    _, _, calibrated, factors, _, _ = _built()

    for year in GOBLIN_CALIBRATION_YEARS:
        yearly = calibrated.loc[calibrated["YEAR"] == year]
        year_factors = factors.loc[factors["YEAR"] == year].set_index("COHORT")
        assert year_factors["PROVENANCE"].eq(PROVENANCE_GOBLIN).all()

        for cohort in FINAL_21_COHORTS:
            target = int(year_factors.loc[cohort, "COHORTS_TARGET"])
            assert int(yearly[cohort].sum()) == target


def test_2021_2025_remain_exactly_cso_with_factor_one() -> None:
    _, source, calibrated, factors, _, _ = _built()

    for year in CSO_ONLY_YEARS:
        left = source.loc[
            source["YEAR"] == year, ["CSOED", *FINAL_21_COHORTS]
        ].sort_values("CSOED").reset_index(drop=True)
        right = calibrated.loc[
            calibrated["YEAR"] == year, ["CSOED", *FINAL_21_COHORTS]
        ].sort_values("CSOED").reset_index(drop=True)
        assert left.equals(right)

        f = factors.loc[factors["YEAR"] == year]
        assert f["FACTOR"].eq(1.0).all()
        assert f["COHORTS_TARGET"].isna().all()
        assert f["PROVENANCE"].eq(PROVENANCE_CSO).all()


def test_hamilton_scaling_preserves_ed_shares_within_rounding() -> None:
    _, source, calibrated, factors, _, _ = _built()

    for year in GOBLIN_CALIBRATION_YEARS:
        idx = source["YEAR"].eq(year)
        year_factors = factors.loc[factors["YEAR"] == year].set_index("COHORT")

        for cohort in FINAL_21_COHORTS:
            model = source.loc[idx, cohort].to_numpy(dtype=float)
            observed = calibrated.loc[idx, cohort].to_numpy(dtype=float)
            model_total = float(model.sum())
            target = float(year_factors.loc[cohort, "COHORTS_TARGET"])

            if model_total == 0:
                assert observed.sum() == 0
                continue

            ideal = model * (target / model_total)
            assert np.max(np.abs(observed - ideal)) <= 1.0 + 1e-9


def test_factor_table_is_complete_and_provenance_is_explicit() -> None:
    _, _, calibrated, factors, _, _ = _built()

    assert len(factors) == 11 * len(FINAL_21_COHORTS)
    assert not factors[["YEAR", "COHORT"]].duplicated().any()
    assert set(factors["COHORT"]) == set(FINAL_21_COHORTS)

    expected = {
        year: PROVENANCE_GOBLIN if year in GOBLIN_CALIBRATION_YEARS else PROVENANCE_CSO
        for year in range(2015, 2026)
    }
    for year, provenance in expected.items():
        assert calibrated.loc[
            calibrated["YEAR"] == year, "GOBLIN_CALIBRATION_PROVENANCE"
        ].eq(provenance).all()
