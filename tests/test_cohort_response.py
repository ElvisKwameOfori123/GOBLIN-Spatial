"""Tests for national-biological / ED-spatial cattle cohort response."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario import allocate_cattle_cohort_response
from goblin_spatial.scenario.cohort_response import _reduction_signal


def _adult_scenario() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "CSOED": ["A", "B", "C"],
            "County": ["Test", "Test", "Test"],
            "BASE_DAIRY_COW": [100, 20, 0],
            "BASE_OTHER_COW": [10, 80, 0],
            "BASE_ADULT_COWS": [110, 100, 0],
            "REDUCTION_DAIRY_COW": [10, 10, 0],
            "REDUCTION_OTHER_COW": [5, 25, 0],
            "REDUCTION_ADULT_COWS": [15, 35, 0],
            "SCENARIO_DAIRY_COW": [90, 10, 0],
            "SCENARIO_OTHER_COW": [5, 55, 0],
        }
    )

    frame["dairy_cows"] = [100, 20, 0]
    frame["suckler_cows"] = [10, 80, 0]
    frame["bulls"] = [3, 5, 2]

    for cohort in FINAL_21_COHORTS:
        if cohort in {"dairy_cows", "suckler_cows", "bulls"}:
            continue
        if cohort.startswith("DxD_"):
            frame[cohort] = [10, 2, 3]
        elif cohort.startswith("DxB_"):
            frame[cohort] = [8, 2, 5]
        elif cohort.startswith("BxB_"):
            frame[cohort] = [2, 10, 3]
        else:
            raise AssertionError(cohort)

    return frame


def _targets(frame: pd.DataFrame) -> dict[str, int]:
    targets: dict[str, int] = {}
    for cohort in FINAL_21_COHORTS:
        baseline = int(frame[cohort].sum())
        if cohort == "dairy_cows":
            targets[cohort] = 100
        elif cohort == "suckler_cows":
            targets[cohort] = 60
        elif cohort == "bulls":
            targets[cohort] = 8
        else:
            targets[cohort] = baseline - 3
    return targets


def test_cohort_response_subtracts_from_existing_ed_cohorts_and_closes_nationally():
    frame = _adult_scenario()
    targets = _targets(frame)
    out = allocate_cattle_cohort_response(frame, targets)

    for cohort in FINAL_21_COHORTS:
        base = out[f"BASE_COHORT_{cohort}"]
        reduction = out[f"REDUCTION_COHORT_{cohort}"]
        scenario = out[f"SCENARIO_COHORT_{cohort}"]

        assert (reduction >= 0).all()
        assert (reduction <= base).all()
        assert (base - reduction == scenario).all()
        assert int(scenario.sum()) == targets[cohort]

    assert int(out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].sum()) == sum(targets.values())


def test_receiver_rearing_ed_uses_same_county_reduction_signal():
    frame = _adult_scenario()
    targets = _targets(frame)
    out = allocate_cattle_cohort_response(frame, targets)

    # C has no dairy cows but contains dairy-origin animals. It therefore uses
    # the dairy reduction rate of its own county rather than being excluded or
    # automatically inheriting a national receiver rate.
    c = out.loc[out["CSOED"] == "C"].iloc[0]
    expected_county_rate = 20 / 120

    assert c["BASE_DAIRY_COW"] == 0
    assert c["DxB_calves_m"] > 0
    assert c["REDUCTION_SIGNAL_SOURCE_DxB_calves_m"] == "COUNTY_RECEIVER"
    assert c["REDUCTION_SIGNAL_DxB_calves_m"] == pytest.approx(expected_county_rate)


def test_reduction_signal_is_ed_first_county_second_and_orphan_last():
    signal, source = _reduction_signal(
        base_adults=np.array([100, 0, 100, 0, 0]),
        adult_reductions=np.array([50, 0, 10, 0, 0]),
        cohort_base=np.array([10, 10, 10, 10, 5]),
        counties=np.array(["X", "X", "Y", "Y", "Z"], dtype=object),
    )

    # Breeding EDs use their own local adult reduction rates.
    assert signal[0] == pytest.approx(0.50)
    assert signal[2] == pytest.approx(0.10)
    assert source[0] == "LOCAL_ED"
    assert source[2] == "LOCAL_ED"

    # Receiver EDs inherit only their own county's breeding reduction rate.
    assert signal[1] == pytest.approx(0.50)
    assert signal[3] == pytest.approx(0.10)
    assert source[1] == "COUNTY_RECEIVER"
    assert source[3] == "COUNTY_RECEIVER"

    # County Z has a cohort but no corresponding breeding adults: only this
    # sparse orphan case uses the national fallback rate (60 / 200 = 0.30).
    assert signal[4] == pytest.approx(0.30)
    assert source[4] == "NATIONAL_ORPHAN"


def test_cohort_response_rejects_adult_target_inconsistent_with_adult_allocation():
    frame = _adult_scenario()
    targets = _targets(frame)
    targets["dairy_cows"] = 99

    with pytest.raises(AssertionError, match="does not match the adult scenario target"):
        allocate_cattle_cohort_response(frame, targets)


def test_cohort_response_is_reduction_only_for_now():
    frame = _adult_scenario()
    targets = _targets(frame)
    targets["DxD_calves_m"] = int(frame["DxD_calves_m"].sum()) + 1

    with pytest.raises(ValueError, match="cannot expand"):
        allocate_cattle_cohort_response(frame, targets)
