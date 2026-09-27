"""Regression tests for the modular cattle build."""

from pathlib import Path

import pandas as pd
import pytest

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS
from goblin_spatial.cattle.panel import AGE_SEX_COLS
from goblin_spatial.config import load_config


pytestmark = pytest.mark.full_data

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"

EXPECTED_TOTAL_CATTLE = {
    2015: 6_963_800,
    2016: 7_221_100,
    2017: 7_363_500,
    2018: 7_348_200,
    2019: 7_208_600,
    2020: 7_314_500,
    2021: 7_358_700,
    2022: 7_396_300,
    2023: 7_341_500,
    2024: 7_183_300,
    2025: 6_904_800,
}

EXPECTED_2020 = {
    "DAIRY_COW": 1_567_600,
    "OTHER_COW": 983_500,
    "OTHER_CATTLE": 4_763_400,
    "TOTAL_CATTLE": 7_314_500,
    "BULLS": 52_103,
    "CATTLE_MALE_UNDER_1": 1_013_154,
    "CATTLE_FEMALE_UNDER_1": 1_104_061,
    "CATTLE_MALE_1_2": 789_970,
    "CATTLE_FEMALE_1_2": 1_005_773,
    "CATTLE_MALE_2_PLUS": 409_630,
    "CATTLE_FEMALE_2_PLUS": 388_709,
}

EXPECTED_2020_GENETIC_MARGINS = {
    "CATTLE_MALE_UNDER_1": (258_902, 333_425, 420_827),
    "CATTLE_FEMALE_UNDER_1": (363_324, 327_582, 413_155),
    "CATTLE_FEMALE_1_2": (333_922, 297_054, 374_797),
    "CATTLE_MALE_1_2": (201_418, 260_115, 328_437),
    "CATTLE_FEMALE_2_PLUS": (46_774, 90_335, 251_600),
    "CATTLE_MALE_2_PLUS": (124_361, 152_082, 133_187),
}


def _panel() -> pd.DataFrame:
    return build_cattle_panel(load_config(CONFIG))


def test_cattle_panel_regression() -> None:
    panel = _panel()

    assert len(panel) == 31_427
    assert panel["CSOED"].nunique() == 2_857
    assert set(panel["YEAR"].unique()) == set(range(2015, 2026))
    assert not panel[["YEAR", "CSOED"]].duplicated().any()

    totals = panel.groupby("YEAR")["TOTAL_CATTLE"].sum().to_dict()
    assert totals == EXPECTED_TOTAL_CATTLE

    baseline = panel.loc[panel["YEAR"] == 2020]
    for column, expected in EXPECTED_2020.items():
        assert int(baseline[column].sum()) == expected

    assert (
        panel[AGE_SEX_COLS].sum(axis=1).astype(int)
        == panel["OTHER_CATTLE"].astype(int)
    ).all()
    assert (
        panel["DAIRY_COW"] + panel["OTHER_COW"] + panel["OTHER_CATTLE"]
        == panel["TOTAL_CATTLE"]
    ).all()


def test_cattle_goblin_cohort_regression() -> None:
    config = load_config(CONFIG)
    cattle = add_cattle_cohorts(build_cattle_panel(config), config)

    assert len(cattle) == 31_427
    assert (cattle[FINAL_21_COHORTS] >= 0).all().all()
    assert (
        cattle[FINAL_21_COHORTS].sum(axis=1).astype(int)
        == cattle["TOTAL_CATTLE"].astype(int)
    ).all()
    assert (cattle["dairy_cows"] == cattle["DAIRY_COW"]).all()
    assert (cattle["suckler_cows"] == cattle["OTHER_COW"]).all()
    assert (cattle["bulls"] == cattle["BULLS"]).all()

    for container, mapping in CONTAINERS.items():
        cohort_columns = [mapping[genetic] for genetic in ("DxD", "DxB", "BxB")]
        assert (
            cattle[cohort_columns].sum(axis=1).astype(int)
            == cattle[container].astype(int)
        ).all()

    y2020 = cattle.loc[cattle["YEAR"] == 2020]
    for container, expected in EXPECTED_2020_GENETIC_MARGINS.items():
        mapping = CONTAINERS[container]
        observed = tuple(
            int(y2020[mapping[genetic]].sum())
            for genetic in ("DxD", "DxB", "BxB")
        )
        assert observed == expected


def test_cattle_ed_informed_genetic_support() -> None:
    """The GOBLIN genetic split must remain sparse where adult origins are absent."""

    config = load_config(CONFIG)
    cattle = add_cattle_cohorts(build_cattle_panel(config), config)
    y2020 = cattle.loc[cattle["YEAR"] == 2020].copy()

    dairy_origin_columns = [
        mapping[genetic]
        for mapping in CONTAINERS.values()
        for genetic in ("DxD", "DxB")
    ]
    bxb_columns = [mapping["BxB"] for mapping in CONTAINERS.values()]

    zero_dairy = y2020["DAIRY_COW"].eq(0)

    # Stage A V1b restores dairy support in 970 published-zero EDs identified
    # from the 2010 AVA42 evidence. No suckler-only ED then needs to be admitted
    # as a capacity-driven dairy-origin receiver.
    assert int(zero_dairy.sum()) == 493

    suckler_only = (
        y2020["DAIRY_COW"].eq(0)
        & y2020["OTHER_COW"].gt(0)
    )
    assert y2020.loc[suckler_only, dairy_origin_columns].sum(axis=1).eq(0).all()

    dairy_only = y2020["DAIRY_COW"].gt(0) & y2020["OTHER_COW"].eq(0)
    assert y2020.loc[dairy_only, bxb_columns].sum(axis=1).eq(0).all()

    # EDs with neither adult-cow type but positive residual cattle remain
    # explicit receiver/rearing exceptions and may carry both origins.
    no_adult_receiver = (
        y2020["DAIRY_COW"].eq(0)
        & y2020["OTHER_COW"].eq(0)
        & y2020["OTHER_CATTLE"].gt(0)
    )
    assert y2020.loc[no_adult_receiver, dairy_origin_columns].sum(axis=1).gt(0).all()
    assert y2020.loc[no_adult_receiver, bxb_columns].sum(axis=1).gt(0).all()
