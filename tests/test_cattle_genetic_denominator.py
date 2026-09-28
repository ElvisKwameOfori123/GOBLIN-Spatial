"""The 2020 genetic denominator: AAA10 cows govern the derived genetic margins.

Observed 2020 ED quantities stay as published; the unobserved national
DxD/DxB/BxB margins use AAA10 June cows in every year, 2020 included.
The 2019-2021 BxB sequence is a reported diagnostic, not a hard test.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import KNOWN_YEAR, build_annual_ed_panel
from goblin_spatial.cattle.cohorts import (
    CONTAINERS,
    FINAL_21_COHORTS,
    _goblin_value,
    _load_goblin,
    add_cattle_cohorts,
)
from goblin_spatial.cattle.panel import _load_aaa10
from goblin_spatial.config import load_config
from goblin_spatial.reconciliation import hamilton_allocate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
GENETICS = ("DxD", "DxB", "BxB")


def _with_denominator(cfg, mode: str):
    other = copy.deepcopy(cfg)
    other.raw.setdefault("cattle", {})["genetic_cow_denominator"] = mode
    return other


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    annual, _ = build_annual_ed_panel(cfg)
    age_sex = build_annual_age_sex_panel(cfg, annual, mode="dafm_log_odds")
    production = add_cattle_cohorts(age_sex, _with_denominator(cfg, "aaa10"))
    reference = add_cattle_cohorts(age_sex, _with_denominator(cfg, "panel"))
    return cfg, age_sex, production, reference


def _sorted(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return frame[["YEAR", "CSOED", *columns]].sort_values(["YEAR", "CSOED"]).reset_index(drop=True)


def test_production_default_is_aaa10() -> None:
    cfg = load_config(CONFIG)
    assert cfg.raw["cattle"]["genetic_cow_denominator"] == "aaa10"


def test_published_2020_cattle_unchanged() -> None:
    cfg, _, production, _ = _built()
    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")
    y2020 = production.loc[production["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    for column in ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"):
        assert np.array_equal(
            y2020.loc[published.index, column].to_numpy(dtype=np.int64),
            published[column].to_numpy(dtype=np.int64),
        ), column


def test_2020_age_sex_containers_unchanged() -> None:
    _, age_sex, production, _ = _built()
    columns = ["BULLS", *CONTAINERS.keys()]
    left = _sorted(age_sex.loc[age_sex["YEAR"] == KNOWN_YEAR], columns)
    right = _sorted(production.loc[production["YEAR"] == KNOWN_YEAR], columns)
    assert left.equals(right)


def test_2020_national_margins_use_aaa10_cows_and_cohorts_coefficients() -> None:
    cfg, _, production, _ = _built()
    goblin = _load_goblin(cfg.files["goblin_cohorts"])
    aaa10 = _load_aaa10(cfg.files["cso_cattle_county"])
    y = aaa10.loc[aaa10["Year"] == KNOWN_YEAR]
    dairy = int(y["Dairy cows__HEAD"].sum())
    other = int(y["Other cows__HEAD"].sum())
    assert (dairy, other) == (1_567_600, 983_500)

    g_dairy = _goblin_value(goblin, "dairy_cows", KNOWN_YEAR)
    g_suckler = _goblin_value(goblin, "suckler_cows", KNOWN_YEAR)
    y2020 = production.loc[production["YEAR"] == KNOWN_YEAR]
    for container, mapping in CONTAINERS.items():
        expectation = np.array(
            [
                _goblin_value(goblin, mapping["DxD"], KNOWN_YEAR) / g_dairy * dairy,
                _goblin_value(goblin, mapping["DxB"], KNOWN_YEAR) / g_dairy * dairy,
                _goblin_value(goblin, mapping["BxB"], KNOWN_YEAR) / g_suckler * other,
            ]
        )
        expected = hamilton_allocate(expectation, int(y2020[container].sum()))
        observed = np.array([int(y2020[mapping[g]].sum()) for g in GENETICS])
        assert np.array_equal(observed, expected), container


def test_genetics_close_to_each_fixed_container() -> None:
    _, _, production, _ = _built()
    for container, mapping in CONTAINERS.items():
        genetic = [mapping[g] for g in GENETICS]
        assert (
            production[genetic].sum(axis=1).astype(np.int64)
            == production[container].astype(np.int64)
        ).all(), container
    assert (
        production[FINAL_21_COHORTS].sum(axis=1).astype(np.int64)
        == production["TOTAL_CATTLE"].astype(np.int64)
    ).all()


def test_years_other_than_2020_are_unchanged() -> None:
    _, _, production, reference = _built()
    columns = ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE", *FINAL_21_COHORTS]
    other_years = lambda f: f.loc[f["YEAR"] != KNOWN_YEAR]  # noqa: E731
    assert _sorted(other_years(production), columns).equals(
        _sorted(other_years(reference), columns)
    )


def test_2020_denominator_change_is_live() -> None:
    _, _, production, reference = _built()
    bxb = [CONTAINERS[c]["BxB"] for c in CONTAINERS]
    p = int(production.loc[production["YEAR"] == KNOWN_YEAR, bxb].to_numpy().sum())
    r = int(reference.loc[reference["YEAR"] == KNOWN_YEAR, bxb].to_numpy().sum())
    assert p != r
