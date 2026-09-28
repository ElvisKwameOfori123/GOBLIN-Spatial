"""Tests for the 10-cohort sheep layer on the final CSO sheep panel."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.reconciliation import hamilton_allocate
from goblin_spatial.sheep.annual_panel import (
    KNOWN_YEAR,
    build_annual_sheep_panel,
)
from goblin_spatial.sheep.cohorts import (
    BREEDS,
    GOBLIN_SHEEP_10,
    GROUP_SOURCE,
    SHEEP_CONTROLS,
    add_sheep_cohorts,
    build_annual_sheep_composition,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


@lru_cache(maxsize=1)
def _built():
    cfg = load_config(CONFIG)
    panel, _ = build_annual_sheep_panel(cfg)
    cohorts = add_sheep_cohorts(panel, cfg)
    return cfg, panel, cohorts


def test_10_cohort_layer_preserves_cso_sheep_controls() -> None:
    _, panel, cohorts = _built()

    assert len(cohorts) == len(panel) == 31_427
    assert cohorts["CSOED"].nunique() == 2_857
    assert not cohorts[["YEAR", "CSOED"]].duplicated().any()

    left = panel[["YEAR", "CSOED", *SHEEP_CONTROLS]].sort_values(
        ["YEAR", "CSOED"]
    ).reset_index(drop=True)
    right = cohorts[["YEAR", "CSOED", *SHEEP_CONTROLS]].sort_values(
        ["YEAR", "CSOED"]
    ).reset_index(drop=True)

    for column in SHEEP_CONTROLS:
        assert np.array_equal(
            left[column].to_numpy(dtype=np.int64),
            right[column].to_numpy(dtype=np.int64),
        )


def test_10_cohorts_close_exactly_to_total_sheep() -> None:
    _, _, cohorts = _built()

    assert all(np.issubdtype(cohorts[c].dtype, np.integer) for c in GOBLIN_SHEEP_10)
    assert (cohorts[GOBLIN_SHEEP_10] >= 0).all().all()
    assert (
        cohorts[GOBLIN_SHEEP_10].sum(axis=1).astype(np.int64)
        == cohorts["TOTAL_SHEEP"].astype(np.int64)
    ).all()


def test_system_ewe_ram_and_other_blocks_close() -> None:
    _, _, cohorts = _built()

    assert (
        cohorts["Lowland ewes"] + cohorts["Upland ewes"]
        == cohorts["EWES"]
    ).all()
    assert (
        cohorts["Lowland ram"] + cohorts["Upland ram"]
        == cohorts["RAMS"]
    ).all()

    other_10 = [
        "Lowland lamb_less_1_yr",
        "Lowland male_less_1_yr",
        "Lowland lamb_more_1_yr",
        "Upland lamb_less_1_yr",
        "Upland male_less_1_yr",
        "Upland lamb_more_1_yr",
    ]
    assert (
        cohorts[other_10].sum(axis=1).astype(np.int64)
        == cohorts["OTHER_SHEEP"].astype(np.int64)
    ).all()


def test_county_breed_margins_follow_dafm_composition_targets() -> None:
    cfg, panel, cohorts = _built()
    composition = build_annual_sheep_composition(cfg.files["sheep_breed_anchors"])

    county = (
        panel.groupby(["YEAR", "County"], as_index=False)[
            ["EWES", "RAMS", "OTHER_SHEEP"]
        ]
        .sum()
        .merge(composition, on=["YEAR", "County"], validate="one_to_one")
    )

    for group, source_column in GROUP_SOURCE.items():
        actual_cols = [f"{group}_{breed}" for breed in BREEDS]
        actual = cohorts.groupby(["YEAR", "County"])[actual_cols].sum()

        for row in county.itertuples(index=False):
            shares = np.array(
                [getattr(row, f"{group}_{breed}_SHARE") for breed in BREEDS],
                dtype=float,
            )
            target = hamilton_allocate(shares, int(getattr(row, source_column)))
            got = actual.loc[(row.YEAR, row.County)].to_numpy(dtype=np.int64)
            assert np.array_equal(got, target)


def test_2020_total_sheep_is_still_the_published_ed_census() -> None:
    cfg, _, cohorts = _built()
    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")["TOTAL_SHEEP"].astype(np.int64)

    observed = cohorts.loc[
        cohorts["YEAR"] == KNOWN_YEAR
    ].set_index("CSOED")["TOTAL_SHEEP"].astype(np.int64)

    assert np.array_equal(
        observed.loc[published.index].to_numpy(),
        published.to_numpy(),
    )


def test_zero_sheep_eds_remain_zero_across_all_10_cohorts() -> None:
    _, _, cohorts = _built()
    zero = cohorts["TOTAL_SHEEP"].eq(0)
    assert (cohorts.loc[zero, GOBLIN_SHEEP_10].to_numpy() == 0).all()
