"""Tests for the optional public-GOBLIN pasture-DM adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure.goblin_adapter import (
    canonical_goblin_spatial_cohort,
    pasture_dm_profile_from_goblin_animals,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


class _FakeFeed:
    def dry_matter_from_grass(self, animal):
        # kg DM/head/day; uses an upstream-style animal attribute so weighted
        # duplicate rows can be tested without optional dependencies installed.
        return float(animal.weight) / 100.0


def _row(cohort, *, pop=10.0, weight=200.0, grazing="pasture"):
    return {
        "year": 2050,
        "Scenarios": 7,
        "cohort": cohort,
        "pop": pop,
        "weight": weight,
        "daily_milk": 0.0,
        "forage": "irish_grass",
        "grazing": grazing,
        "con_type": "concentrate",
        "con_amount": 0.0,
    }


def _upstream_31_rows():
    rows = [_row(cohort) for cohort in FINAL_21_COHORTS]
    generic = {
        "ewes": "ewes",
        "lamb_less_1_yr": "lamb_less_1_yr",
        "male_less_1_yr": "male_less_1_yr",
        "lamb_more_1_yr": "lamb_more_1_yr",
        "ram": "ram",
    }
    for system, grazing in (("Lowland", "flat_pasture"), ("Upland", "hilly_pasture")):
        for suffix, upstream in generic.items():
            rows.append(_row(upstream, grazing=grazing))
    return rows


def _upstream_reference_scenario_dataframe() -> pd.DataFrame:
    """Return the public livestock_generation reference fixture.

    The values are copied from the upstream package's ``tests/animal_data_test.py``
    fixture.  They are used only to exercise the public AnimalData -> cattle_lca /
    sheep_lca feed path and derive an auditable per-head pasture-DM profile; they
    are not GOBLIN-Spatial livestock-population assumptions.
    """

    columns = [
        "Scenarios",
        "Cattle systems",
        "Manure management",
        "Dairy pop",
        "Beef pop",
        "Dairy prod",
        "Beef prod",
        "mm_storage",
        "Cattle EF",
        "AD prod",
        "Forest area",
        "Conifer proportion",
        "Conifer harvest",
        "Conifer thinned",
        "Broadleaf harvest",
        "Bioenergy area",
        "Crop area",
        "Wetland area",
        "Land rewetting",
        "Grass management",
        "Upland sheep pop",
        "Upland sheep prod",
        "Lowland sheep pop",
        "Lowland sheep prod",
        "Dairy Pasture fertilisation",
        "Beef Pasture fertilisation",
        "Broadleaf proportion",
        "Afforest Year",
    ]
    common = [
        0.0879077282507005,
        0.500607270596862,
        0,
        0,
        0,
        0.801458098547012,
        0.36840211684271,
        0.0555663357895664,
        0.126070113756632,
        0,
        0,
        0.0784928061838073,
        0.120049095269181,
        0,
        0.0879200186051467,
    ]
    tail = [136.870524806694, 105.00171069052, 0.591628596827221, 2080]
    data = [
        [0, "Dairy", "tank solid", 0, 0, *common[:2], *common[2:], 0, 0, 0, 0, *tail],
        [0, "Dairy", "tank liquid", 172390.09063152, 0, 0.8, 0.500607270596862, *common[2:], 0, 0, 0, 0, *tail],
        [0, "Beef", "tank solid", 0, 0, *common[:2], *common[2:], 0, 0, 0, 0, *tail],
        [0, "Beef", "tank liquid", 0, 27807.487070967, *common[:2], *common[2:], 0, 0, 0, 0, *tail],
        [0, "Lowland sheep", "tank liquid", 0, 0, *common[:2], *common[2:], 0, 0, 37812, 0, *tail],
        [0, "Upland sheep", "tank liquid", 0, 0, *common[:2], *common[2:], 9453, 0, 0, 0, *tail],
    ]
    # The explicit shape assertion protects us from silently shifting fixture
    # values relative to the upstream 28-column scenario contract.
    if any(len(row) != len(columns) for row in data):
        raise AssertionError("upstream reference fixture shape changed")
    return pd.DataFrame(data, columns=columns)


def test_public_goblin_cohort_contract_matches_spatial_31():
    profile = pasture_dm_profile_from_goblin_animals(
        pd.DataFrame(_upstream_31_rows()),
        year=2050,
        scenario=7,
        cattle_feed=_FakeFeed(),
        sheep_feed=_FakeFeed(),
    )

    assert set(profile) == set(FINAL_21_COHORTS) | set(GOBLIN_SHEEP_10)
    # 200 kg / 100 = 2 kg DM/day = 0.73 t DM/head/year.
    assert profile["dairy_cows"] == pytest.approx(0.73)
    assert profile["Lowland ewes"] == pytest.approx(0.73)
    assert profile["Upland ram"] == pytest.approx(0.73)


def test_upstream_sheep_grazing_preserves_lowland_upland_identity():
    assert canonical_goblin_spatial_cohort(
        {"cohort": "ewes", "grazing": "flat_pasture"}
    ) == "Lowland ewes"
    assert canonical_goblin_spatial_cohort(
        {"cohort": "ewes", "grazing": "hilly_pasture"}
    ) == "Upland ewes"


def test_duplicate_upstream_rows_are_population_weighted():
    rows = _upstream_31_rows()
    # Replace the dairy row with two management/productivity rows.  Per-head DM
    # is 1 and 3 kg/day with populations 1 and 3 -> weighted mean 2.5 kg/day.
    rows = [row for row in rows if row["cohort"] != "dairy_cows"]
    rows.extend(
        [
            _row("dairy_cows", pop=1.0, weight=100.0),
            _row("dairy_cows", pop=3.0, weight=300.0),
        ]
    )
    profile = pasture_dm_profile_from_goblin_animals(
        pd.DataFrame(rows),
        cattle_feed=_FakeFeed(),
        sheep_feed=_FakeFeed(),
    )
    assert profile["dairy_cows"] == pytest.approx(2.5 * 365.0e-3)


def test_zero_population_row_still_defines_future_per_head_control():
    rows = _upstream_31_rows()
    for row in rows:
        if row["cohort"] == "bulls":
            row["pop"] = 0.0
            row["weight"] = 400.0
    profile = pasture_dm_profile_from_goblin_animals(
        pd.DataFrame(rows),
        cattle_feed=_FakeFeed(),
        sheep_feed=_FakeFeed(),
    )
    assert profile["bulls"] == pytest.approx(4.0 * 365.0e-3)


def test_real_upstream_goblin_2020_pasture_profile_contract():
    """Exercise the real public GOBLIN animal/feed stack, not injected fakes."""

    pytest.importorskip("livestock_generation")
    pytest.importorskip("cattle_lca")
    pytest.importorskip("sheep_lca")
    from livestock_generation.livestock import AnimalData

    animal_class = AnimalData(
        "ireland",
        2020,
        2050,
        _upstream_reference_scenario_dataframe(),
    )
    animals = animal_class.create_baseline_animal_dataframe()
    profile = pasture_dm_profile_from_goblin_animals(animals)

    expected = set(FINAL_21_COHORTS) | set(GOBLIN_SHEEP_10)
    assert set(profile) == expected
    assert len(profile) == 31
    assert all(value >= 0 for value in profile.values())
    assert profile["dairy_cows"] > 0
    assert profile["suckler_cows"] > 0
    assert profile["Lowland ewes"] > 0
    assert profile["Upland ewes"] > 0

    print("\nUPSTREAM_GOBLIN_PASTURE_DM_2020_T_PER_HEAD_YEAR")
    for cohort in [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]:
        print(f"{cohort},{profile[cohort]:.12f}")
