"""Tests for G1 genetics on the revised annual cattle and age-sex chain."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import KNOWN_YEAR, build_annual_ed_panel
from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS, add_cattle_cohorts
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"

YOUNG_CONTAINERS = (
    "CATTLE_MALE_UNDER_1",
    "CATTLE_FEMALE_UNDER_1",
    "CATTLE_MALE_1_2",
    "CATTLE_FEMALE_1_2",
)


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    annual, _ = build_annual_ed_panel(cfg)
    age_sex = build_annual_age_sex_panel(cfg, annual, mode="dafm_log_odds")
    cohorts = add_cattle_cohorts(age_sex, cfg)
    return cfg, annual, age_sex, cohorts


def test_g1_preserves_fixed_cso_controls() -> None:
    _, _, age_sex, cohorts = _built()

    assert len(cohorts) == 31_427
    assert cohorts["CSOED"].nunique() == 2_857
    assert not cohorts[["YEAR", "CSOED"]].duplicated().any()
    assert (cohorts[FINAL_21_COHORTS] >= 0).all().all()

    control_cols = [
        "DAIRY_COW",
        "OTHER_COW",
        "OTHER_CATTLE",
        "TOTAL_CATTLE",
        "BULLS",
        *CONTAINERS.keys(),
    ]
    left = age_sex[["YEAR", "CSOED", *control_cols]].sort_values(
        ["YEAR", "CSOED"]
    ).reset_index(drop=True)
    right = cohorts[["YEAR", "CSOED", *control_cols]].sort_values(
        ["YEAR", "CSOED"]
    ).reset_index(drop=True)
    assert left.equals(right)


def test_each_age_sex_container_closes_to_dxd_dxb_bxb() -> None:
    _, _, _, cohorts = _built()

    for container, mapping in CONTAINERS.items():
        genetic_cols = [mapping[g] for g in ("DxD", "DxB", "BxB")]
        assert (
            cohorts[genetic_cols].sum(axis=1).astype(np.int64)
            == cohorts[container].astype(np.int64)
        ).all()


def test_21_cohorts_close_to_total_cattle_and_2020_census() -> None:
    cfg, _, _, cohorts = _built()

    assert (
        cohorts[FINAL_21_COHORTS].sum(axis=1).astype(np.int64)
        == cohorts["TOTAL_CATTLE"].astype(np.int64)
    ).all()

    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")
    y2020 = cohorts.loc[cohorts["YEAR"] == KNOWN_YEAR].set_index("CSOED")

    for column in ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"):
        assert np.array_equal(
            y2020.loc[published.index, column].to_numpy(dtype=np.int64),
            published[column].to_numpy(dtype=np.int64),
        )


def test_g1_receiver_movement_is_retained_on_new_chain() -> None:
    _, _, _, cohorts = _built()
    y2020 = cohorts.loc[cohorts["YEAR"] == KNOWN_YEAR].copy()

    # all six follower containers (under 1, 1-2 and 2+), as reported
    dxd_young = [CONTAINERS[c]["DxD"] for c in CONTAINERS]
    dxb_young = [CONTAINERS[c]["DxB"] for c in CONTAINERS]

    zero_dairy = y2020["DAIRY_COW"].eq(0)
    suckler_only = zero_dairy & y2020["OTHER_COW"].gt(0)

    dxd_total = float(y2020[dxd_young].to_numpy().sum())
    dxb_total = float(y2020[dxb_young].to_numpy().sum())
    assert dxd_total > 0
    assert dxb_total > 0

    dxd_zero_dairy_share = (
        float(y2020.loc[zero_dairy, dxd_young].to_numpy().sum()) / dxd_total
    )
    dxb_suckler_only_share = (
        float(y2020.loc[suckler_only, dxb_young].to_numpy().sum()) / dxb_total
    )

    # Regression anchors from the revised annual + age-sex chain, with the 2020
    # national genetic margins on the AAA10 cow denominator (v1.1 panel
    # denominator gave 0.261 and 0.249). Stage 00 census preparation lowered
    # the zero-dairy DxD share from 0.0305 because suppressed dairy cells are
    # no longer stored as zero.
    assert np.isclose(dxd_zero_dairy_share, 0.0197, atol=0.003)
    assert np.isclose(dxb_suckler_only_share, 0.0443, atol=0.003)
