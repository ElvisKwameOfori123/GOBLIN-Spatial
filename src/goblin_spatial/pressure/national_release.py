"""SC1 spatialisation of authoritative GOBLIN livestock-land release.

Scientific boundary
-------------------
National GOBLIN supplies the pathway-level gross livestock-land release.
GOBLIN-Spatial resolves where that fixed quantity falls across Electoral
Divisions after the livestock endpoint and cohort state have been solved.

SC1 is deliberately independent of mapped soil, LPIS and future-use
suitability. Those downstream evidence layers do not move livestock, do not
determine the national released-land quantity and do not constrain the ED
release vector. Their substantive role begins in SC2.

The ED release geography is driven by the solved livestock/pasture-DM transition
and bounded only by the validated ``ALL_GRASSLAND`` resource. The independent
pasture-DM land balance is retained as a diagnostic and is never rescaled to the
parent GOBLIN land control.

``GOBLIN_RELEASED_GRASSLAND_HA`` = authoritative pathway release spatialised to EDs.
``POTENTIAL_SPARED_GRASSLAND_HA`` = independent positive pasture-DM diagnostic.
``ADDITIONAL_GRASSLAND_REQUIRED_HA`` = independent local additional requirement.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure.grassland_release import (
    _profile_for_year,
    calculate_spared_grassland,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

SYSTEMS = ("DAIRY", "BEEF", "SHEEP")
HA_TOL = 1e-7


def _targets(values: Mapping[int, float], years: list[int]) -> dict[int, float]:
    out = {int(year): float(value) for year, value in values.items()}
    if set(out) != set(years):
        raise ValueError(
            "national land-release targets must exactly match scenario milestones; "
            f"scenario={years}, targets={sorted(out)}"
        )
    previous = 0.0
    for year in years:
        value = out[year]
        if not np.isfinite(value) or value < -1e-12:
            raise ValueError(
                f"national land-release target for {year} must be finite and non-negative"
            )
        value = max(value, 0.0)
        if value + 1e-9 < previous:
            raise ValueError("cumulative national land release cannot fall between milestones")
        out[year] = value
        previous = value
    return out


def _cohort_dm(
    frame: pd.DataFrame,
    state: str,
    cohorts,
    profile: Mapping[str, float],
) -> np.ndarray:
    demand = np.zeros(len(frame), dtype=float)
    for cohort in cohorts:
        column = (
            f"{state}_COHORT_{cohort}"
            if cohort in FINAL_21_COHORTS
            else f"{state}_SHEEP_COHORT_{cohort}"
        )
        if column not in frame.columns:
            raise ValueError(f"SC1 release missing cohort column: {column}")
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(values)).any() or (values < 0).any():
            raise ValueError(f"invalid livestock counts in {column}")
        demand += values * float(profile[cohort])
    return demand


def _system_dm(
    frame: pd.DataFrame,
    state: str,
    profile: Mapping[str, float],
) -> dict[str, np.ndarray]:
    dairy_followers = [
        cohort
        for cohort in FINAL_21_COHORTS
        if cohort.startswith("DxD_") or cohort.startswith("DxB_")
    ]
    beef_followers = [cohort for cohort in FINAL_21_COHORTS if cohort.startswith("BxB_")]

    dairy = _cohort_dm(frame, state, ["dairy_cows", *dairy_followers], profile)
    beef = _cohort_dm(frame, state, ["suckler_cows", *beef_followers], profile)
    sheep = _cohort_dm(frame, state, GOBLIN_SHEEP_10, profile)
    bulls = _cohort_dm(frame, state, ["bulls"], profile)

    dairy_cows = pd.to_numeric(
        frame[f"{state}_COHORT_dairy_cows"], errors="raise"
    ).to_numpy(dtype=float)
    suckler_cows = pd.to_numeric(
        frame[f"{state}_COHORT_suckler_cows"], errors="raise"
    ).to_numpy(dtype=float)
    adults = dairy_cows + suckler_cows
    dairy_share = np.divide(
        dairy_cows,
        adults,
        out=np.zeros(len(frame), dtype=float),
        where=adults > 0,
    )
    beef_share = np.divide(
        suckler_cows,
        adults,
        out=np.zeros(len(frame), dtype=float),
        where=adults > 0,
    )
    dairy += bulls * dairy_share
    beef += bulls * beef_share
    return {"DAIRY": dairy, "BEEF": beef, "SHEEP": sheep}


def _system_land_controls(
    *,
    baseline_grassland_ha: float,
    target_livestock_land_ha: float,
    total_release_ha: float,
    base_system_dm: dict[str, np.ndarray],
    scenario_system_dm: dict[str, np.ndarray],
) -> dict[str, object]:
    """Derive a symmetric dairy/beef/sheep accounting split from actual DM states."""

    base_dm = {system: float(np.sum(base_system_dm[system])) for system in SYSTEMS}
    scenario_dm = {
        system: float(np.sum(scenario_system_dm[system])) for system in SYSTEMS
    }
    base_sum = float(sum(base_dm.values()))
    scenario_sum = float(sum(scenario_dm.values()))
    if base_sum <= 0 or scenario_sum <= 0:
        raise AssertionError("cannot derive system land controls from zero pasture DM")

    base_land = {
        system: baseline_grassland_ha * base_dm[system] / base_sum
        for system in SYSTEMS
    }
    target_land = {
        system: target_livestock_land_ha * scenario_dm[system] / scenario_sum
        for system in SYSTEMS
    }
    positive_release = {
        system: max(0.0, base_land[system] - target_land[system])
        for system in SYSTEMS
    }
    positive_sum = float(sum(positive_release.values()))
    if total_release_ha > HA_TOL and positive_sum <= HA_TOL:
        raise AssertionError("positive GOBLIN release has no positive system land release")

    release = (
        {
            system: total_release_ha * positive_release[system] / positive_sum
            for system in SYSTEMS
        }
        if positive_sum > HA_TOL
        else {system: 0.0 for system in SYSTEMS}
    )
    return {
        "BASE": base_land,
        "TARGET": target_land,
        "RELEASE": release,
        "AUTHORITY": "RUNTIME_GROSS_RELEASE_FROM_SELECTED_BASELINE",
        "SYSTEM_SPLIT_SOURCE": "DERIVED_ACTUAL_DM_WEIGHT_ROUTE_RESCALED_ALL_PATHWAYS",
    }


def _system_release_propensity(
    base_system_dm: dict[str, np.ndarray],
    scenario_system_dm: dict[str, np.ndarray],
    controls: Mapping[str, object],
) -> dict[str, np.ndarray]:
    """Construct ED release propensities from the solved livestock transition only."""

    n_ed = len(next(iter(base_system_dm.values())))
    provisional: dict[str, np.ndarray] = {}
    release_targets = controls["RELEASE"]
    base_land = controls["BASE"]
    target_land = controls["TARGET"]
    assert isinstance(release_targets, dict)
    assert isinstance(base_land, dict)
    assert isinstance(target_land, dict)

    for system in SYSTEMS:
        base = np.maximum(np.asarray(base_system_dm[system], dtype=float), 0.0)
        scenario = np.maximum(np.asarray(scenario_system_dm[system], dtype=float), 0.0)
        base_weights = (
            base / float(base.sum()) if float(base.sum()) > HA_TOL else np.zeros(n_ed)
        )
        scenario_weights = (
            scenario / float(scenario.sum())
            if float(scenario.sum()) > HA_TOL
            else np.zeros(n_ed)
        )
        signed = (
            base_weights * float(base_land[system])
            - scenario_weights * float(target_land[system])
        )
        propensity = np.maximum(signed, 0.0)
        target = float(release_targets[system])
        if target > HA_TOL and float(propensity.sum()) <= HA_TOL:
            propensity = base.copy()
        provisional[system] = (
            propensity * (target / float(propensity.sum()))
            if target > HA_TOL and float(propensity.sum()) > HA_TOL
            else np.zeros(n_ed, dtype=float)
        )
    return provisional


def _bounded_proportional_allocate(
    capacity: np.ndarray,
    primary_weight: np.ndarray,
    fallback_weight: np.ndarray,
    target: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Allocate a fixed national release to EDs without using soil suitability.

    The primary weight is the livestock-derived release propensity. If that
    signal cannot physically absorb the full authoritative national quantity
    because some EDs hit ``ALL_GRASSLAND`` capacity, remaining hectares are
    redistributed across still-available livestock-bearing grassland using the
    baseline pasture-DM distribution. The fallback is explicit in the outputs.
    """

    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    primary = np.maximum(np.asarray(primary_weight, dtype=float), 0.0)
    fallback = np.maximum(np.asarray(fallback_weight, dtype=float), 0.0)
    if capacity.shape != primary.shape or capacity.shape != fallback.shape:
        raise ValueError("SC1 release capacity and weight vectors must have identical shape")
    if (
        (~np.isfinite(capacity)).any()
        or (~np.isfinite(primary)).any()
        or (~np.isfinite(fallback)).any()
        or not np.isfinite(target)
        or target < -HA_TOL
    ):
        raise ValueError("SC1 release allocation inputs must be finite and non-negative")
    target = max(float(target), 0.0)
    if target > float(capacity.sum()) + 1e-6:
        raise ValueError("national livestock-land release exceeds total ALL_GRASSLAND")

    allocation = np.zeros(len(capacity), dtype=float)
    fallback_allocation = np.zeros(len(capacity), dtype=float)
    remaining_capacity = capacity.copy()
    remaining = target

    def distribute(weights: np.ndarray, *, record_fallback: bool) -> None:
        nonlocal remaining
        for _ in range(20000):
            if remaining <= HA_TOL:
                break
            active = (remaining_capacity > HA_TOL) & (weights > HA_TOL)
            if not active.any():
                break
            active_weights = np.where(active, weights, 0.0)
            weight_sum = float(active_weights.sum())
            if weight_sum <= HA_TOL:
                break
            proposal = remaining * active_weights / weight_sum
            take = np.minimum(proposal, remaining_capacity)
            moved = float(take.sum())
            if moved <= 1e-12:
                break
            allocation[:] += take
            if record_fallback:
                fallback_allocation[:] += take
            remaining_capacity[:] = np.maximum(remaining_capacity - take, 0.0)
            remaining = max(remaining - moved, 0.0)

    distribute(primary, record_fallback=False)
    if remaining > HA_TOL:
        distribute(fallback, record_fallback=True)
    if remaining > HA_TOL:
        # Last-resort accounting support is remaining grassland itself. This is
        # kept explicit so scientific review can see whether the livestock signal
        # was insufficient to place the parent GOBLIN control.
        distribute(remaining_capacity, record_fallback=True)

    if remaining > 1e-5:
        raise AssertionError("SC1 soil-independent release allocation failed national closure")
    if (allocation - capacity > 1e-6).any():
        raise AssertionError("SC1 release exceeded ED ALL_GRASSLAND capacity")
    if abs(float(allocation.sum()) - target) > 1e-5:
        raise AssertionError("SC1 ED release does not close to the national GOBLIN control")
    return allocation, fallback_allocation


def _ras_allocate(
    row_totals: np.ndarray,
    column_targets: np.ndarray,
    prior: np.ndarray,
) -> np.ndarray:
    """Attribute the already-spatialised release to systems for accounting only."""

    rows = np.maximum(np.asarray(row_totals, dtype=float), 0.0)
    cols = np.maximum(np.asarray(column_targets, dtype=float), 0.0)
    matrix = np.maximum(np.asarray(prior, dtype=float), 0.0)
    if matrix.shape != (len(rows), len(cols)):
        raise ValueError("SC1 release RAS prior shape disagrees with margins")
    if not np.isclose(rows.sum(), cols.sum(), atol=1e-5):
        raise ValueError("SC1 release RAS margins disagree")
    if rows.sum() <= HA_TOL:
        return np.zeros_like(matrix)

    support = (rows > HA_TOL)[:, None] & (cols > HA_TOL)[None, :]
    matrix = np.where(support, matrix + 1e-15, 0.0)
    for _ in range(10000):
        column_sum = matrix.sum(axis=0)
        for j in range(len(cols)):
            if cols[j] <= HA_TOL:
                matrix[:, j] = 0.0
            elif column_sum[j] > 0:
                matrix[:, j] *= cols[j] / column_sum[j]
        row_sum = matrix.sum(axis=1)
        for i in range(len(rows)):
            if rows[i] <= HA_TOL:
                matrix[i, :] = 0.0
            elif row_sum[i] > 0:
                matrix[i, :] *= rows[i] / row_sum[i]
        if (
            np.max(np.abs(matrix.sum(axis=1) - rows), initial=0.0) <= HA_TOL
            and np.max(np.abs(matrix.sum(axis=0) - cols), initial=0.0) <= HA_TOL
        ):
            break
    else:
        raise AssertionError("SC1 system attribution did not converge")
    return matrix
