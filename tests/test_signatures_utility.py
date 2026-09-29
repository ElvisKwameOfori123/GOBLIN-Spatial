"""Parent-follower propagation rule, 10% utility arms and signature algebra."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import parent_follower_multiplier
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.endpoint_multipliers import parent_endpoint_multiplier
from goblin_spatial.synthesis.signatures import build_signature_long
from goblin_spatial.synthesis.utility_perturbation import (
    DXB,
    DXD,
    BXB,
    livestock_unit_schedule,
    perturb_year,
)


def test_baseline_rule_equals_the_scenario_rule() -> None:
    rng = np.random.default_rng(7)
    n = 400
    base = rng.integers(0, 300, n)
    base[rng.random(n) < 0.3] = 0
    new = np.rint(base * rng.uniform(0.3, 1.2, n)).astype(np.int64)
    cohort = rng.integers(0, 200, n)
    counties = rng.choice(["A", "B", "C", "D"], n).astype(object)
    ours, our_roles = parent_follower_multiplier(base, new, cohort, counties)
    theirs, their_roles = parent_endpoint_multiplier(base, new, cohort, counties)
    assert np.allclose(ours, theirs)
    assert (our_roles == their_roles).all()


def test_receiver_followers_scale_with_county_parents_not_their_own_ed() -> None:
    base = np.array([100.0, 0.0, 50.0, 0.0])
    new = np.array([50.0, 0.0, 50.0, 0.0])  # only ED 0 loses parents
    cohort = np.array([10, 40, 5, 0])
    counties = np.array(["X", "X", "X", "X"], dtype=object)
    multiplier, roles = parent_follower_multiplier(base, new, cohort, counties)
    assert roles.tolist() == ["LOCAL_ED", "COUNTY_RECEIVER", "LOCAL_ED", "NONE"]
    assert multiplier[0] == 0.5  # own parents halved
    assert multiplier[2] == 1.0  # own parents unchanged
    assert np.isclose(multiplier[1], 100.0 / 150.0)  # county parents 150 -> 100


def _frame() -> pd.DataFrame:
    rows = []
    for ed, (dairy, suckler, county) in enumerate([(100, 20, "X"), (0, 40, "X"), (60, 0, "Y")]):
        row = {c: 10 for c in FINAL_21_COHORTS}
        row.update({"CSOED": str(ed), "County": county, "dairy_cows": dairy, "suckler_cows": suckler})
        rows.append(row)
    return pd.DataFrame(rows)


def test_parent_arms_change_only_their_cohorts_by_ten_percent() -> None:
    frame = _frame()
    base = frame[FINAL_21_COHORTS].astype(float)
    dairy = perturb_year(frame, "DAIRY_PARENT", -0.10)
    suckler = perturb_year(frame, "SUCKLER_PARENT", -0.10)
    pro_rata = perturb_year(frame, "PRO_RATA", -0.10)

    dairy_set = ["dairy_cows", *DXD, *DXB]
    suckler_set = ["suckler_cows", *BXB]
    assert np.allclose(dairy[dairy_set], 0.9 * base[dairy_set])  # receiver ED 1 included
    assert np.allclose(dairy.drop(columns=dairy_set), base.drop(columns=dairy_set))
    assert np.allclose(suckler[suckler_set], 0.9 * base[suckler_set])  # ED 2 has no suckler cows
    assert np.allclose(suckler.drop(columns=suckler_set), base.drop(columns=suckler_set))
    assert np.allclose(pro_rata, 0.9 * base)
    # dairy + suckler + bulls reproduce the pro-rata change exactly
    total = (dairy - base).sum(axis=1) + (suckler - base).sum(axis=1) - 0.1 * base["bulls"]
    assert np.allclose(total, (pro_rata - base).sum(axis=1))


def test_lu_schedule_covers_every_cattle_cohort() -> None:
    schedule = livestock_unit_schedule()
    assert set(schedule) == set(FINAL_21_COHORTS)
    assert schedule["dairy_cows"] == 1.0 and schedule["DxB_calves_m"] == 0.4


def test_signature_long_carries_exact_numerators_and_undefined_zero_denominators() -> None:
    signature = pd.DataFrame(
        {
            "GEOGRAPHY_TYPE": ["ED", "ED"],
            "GEOGRAPHY_ID": ["1", "2"],
            "GEOGRAPHY_NAME": ["a", "b"],
            "YEAR": [2020, 2020],
            "dairy_cows": [30.0, 0.0],
            "ADULT_COWS": [60.0, 0.0],
            "DXD_FOLLOWERS": [5.0, 1.0],
            "DXB_FOLLOWERS": [5.0, 1.0],
            "BXB_FOLLOWERS": [10.0, 2.0],
            "FOLLOWER_TOTAL": [20.0, 4.0],
            "TOTAL_CATTLE": [80.0, 4.0],
            "AREA_FARMED": [40.0, 10.0],
            "SO_COVERED_TOTAL_2020_EUR": [800.0, 50.0],
            "UPLAND_SHEEP": [0.0, 0.0],
            "TOTAL_SHEEP": [0.0, 0.0],
            "DAIRY_SHARE_ADULT_PCT": [50.0, np.nan],
            "DXD_SHARE_FOLLOWERS_PCT": [25.0, 25.0],
            "DXB_SHARE_FOLLOWERS_PCT": [25.0, 25.0],
            "BXB_SHARE_FOLLOWERS_PCT": [50.0, 50.0],
            "FOLLOWER_TO_ADULT_RATIO": [20.0 / 60.0, np.nan],
            "CATTLE_PER_FARMED_HA": [2.0, 0.4],
            "SO_PER_FARMED_HA": [20.0, 5.0],
            "UPLAND_SHARE_SHEEP_PCT": [np.nan, np.nan],
        }
    )
    long = build_signature_long(signature)
    dairy = long.loc[long["SIGNATURE"] == "DAIRY_SHARE_ADULT_PCT"]
    assert dairy["VALUE"].iloc[0] == 50.0 and np.isnan(dairy["VALUE"].iloc[1])
    assert set(long["SIGNATURE"]) >= {"DXB_SHARE_FOLLOWERS_PCT", "SO_PER_FARMED_HA"}
