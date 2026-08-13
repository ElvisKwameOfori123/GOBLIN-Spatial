"""Tests for national-biological / ED-spatial cattle cohort response."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario import allocate_cattle_cohort_response
from goblin_spatial.scenario.cohort_response import (
    _reduction_signal,
    build_ed_cohort_dependency_profile,
)


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

    assert signal[0] == pytest.approx(0.50)
    assert signal[2] == pytest.approx(0.10)
    assert source[0] == "LOCAL_ED"
    assert source[2] == "LOCAL_ED"

    assert signal[1] == pytest.approx(0.50)
    assert signal[3] == pytest.approx(0.10)
    assert source[1] == "COUNTY_RECEIVER"
    assert source[3] == "COUNTY_RECEIVER"

    assert signal[4] == pytest.approx(0.30)
    assert source[4] == "NATIONAL_ORPHAN"


def test_mixed_ed_blends_local_and_county_rearing_dependence_without_fixed_factor():
    # National coefficient is 100 cohort / 200 adults = 0.5 cohort per adult.
    # ED A has 100 adults and 80 cohort head: 50 are locally supportable and 30
    # are inferred receiver/rearing stock. Hence local share=0.625 and county
    # dependence share=0.375. Local adult reduction is 20%, while the county
    # reduction is 40%; the effective cohort signal is therefore 27.5%.
    signal, source = _reduction_signal(
        base_adults=np.array([100, 100]),
        adult_reductions=np.array([20, 60]),
        cohort_base=np.array([80, 20]),
        counties=np.array(["X", "X"], dtype=object),
    )

    expected = 0.625 * 0.20 + 0.375 * 0.40
    assert source[0] == "MIXED_ED_COUNTY"
    assert signal[0] == pytest.approx(expected)
    assert source[1] == "LOCAL_ED"
    assert signal[1] == pytest.approx(0.60)


def test_dependency_profile_exposes_ed_cohort_roles_for_paper_and_audit():
    frame = pd.DataFrame(
        {
            "YEAR": [2020, 2020, 2020],
            "CSOED": ["A", "B", "C"],
            "County": ["X", "X", "X"],
            "DAIRY_COW": [100, 100, 0],
            "OTHER_COW": [50, 50, 0],
        }
    )
    for cohort in FINAL_21_COHORTS:
        if cohort == "dairy_cows":
            frame[cohort] = frame["DAIRY_COW"]
        elif cohort == "suckler_cows":
            frame[cohort] = frame["OTHER_COW"]
        elif cohort == "bulls":
            frame[cohort] = [5, 5, 2]
        elif cohort.startswith("DxD_") or cohort.startswith("DxB_"):
            frame[cohort] = [80, 20, 20]
        else:
            frame[cohort] = [20, 20, 10]

    profile = build_ed_cohort_dependency_profile(frame)
    assert set(profile["YEAR"]) == {2020}
    assert len(profile) == 3 * (len(FINAL_21_COHORTS) - 2)
    assert {
        "COHORT_PER_ADULT_COEFFICIENT",
        "LOCAL_SUPPORT_SHARE",
        "COUNTY_DEPENDENCY_SHARE",
        "COHORT_SPATIAL_ROLE",
    }.issubset(profile.columns)

    dxb_a = profile.loc[
        (profile["CSOED"] == "A") & (profile["COHORT"] == "DxB_calves_m")
    ].iloc[0]
    dxb_c = profile.loc[
        (profile["CSOED"] == "C") & (profile["COHORT"] == "DxB_calves_m")
    ].iloc[0]
    assert dxb_a["COHORT_SPATIAL_ROLE"] == "MIXED_ED_COUNTY"
    assert 0 < dxb_a["COUNTY_DEPENDENCY_SHARE"] < 1
    assert dxb_c["COHORT_SPATIAL_ROLE"] == "COUNTY_RECEIVER"
    assert dxb_c["COUNTY_DEPENDENCY_SHARE"] == pytest.approx(1.0)


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
