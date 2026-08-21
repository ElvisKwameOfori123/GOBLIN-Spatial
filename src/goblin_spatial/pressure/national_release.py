"""Spatialise an externally supplied national GOBLIN livestock-land release."""

from __future__ import annotations

from collections.abc import Mapping
import numpy as np
import pandas as pd

from goblin_spatial.pressure.grassland_release import _pasture_dm_demand, _profile_for_year


def _targets(values: Mapping[int, float], years: list[int]) -> dict[int, float]:
    if not values:
        raise ValueError("national GOBLIN land-release targets cannot be empty")
    out = {int(y): float(v) for y, v in values.items()}
    if set(out) != set(years):
        raise ValueError(
            "national land-release targets must exactly match scenario milestones; "
            f"scenario={years}, targets={sorted(out)}"
        )
    previous = 0.0
    for year in years:
        value = out[year]
        if not np.isfinite(value) or value < -1e-12:
            raise ValueError(f"national land-release target for {year} must be finite and non-negative")
        value = max(value, 0.0)
        if value + 1e-9 < previous:
            raise ValueError("cumulative national land release cannot fall between milestones")
        out[year] = value
        previous = value
    return out


def _allocate(capacity: np.ndarray, weights: np.ndarray, target: float) -> np.ndarray:
    capacity = np.maximum(np.asarray(capacity, float), 0.0)
    weights = np.maximum(np.asarray(weights, float), 0.0)
    target = max(float(target), 0.0)
    result = np.zeros(len(capacity), float)
    if target <= 1e-12:
        return result
    feasible = min(target, float(capacity[weights > 1e-12].sum()))
    remaining = feasible
    residual = capacity.copy()
    for _ in range(len(capacity) + 3):
        active = (residual > 1e-12) & (weights > 1e-12)
        if remaining <= 1e-10 or not active.any():
            break
        w = np.where(active, weights, 0.0)
        proposal = remaining * w / float(w.sum())
        take = np.minimum(proposal, residual)
        result += take
        residual -= take
        new_remaining = feasible - float(result.sum())
        if abs(new_remaining - remaining) <= 1e-12:
            break
        remaining = new_remaining
    return result


def _allocate_increment(
    capacity: np.ndarray,
    incremental_pressure: np.ndarray,
    cumulative_pressure: np.ndarray,
    target: float,
) -> np.ndarray:
    first = _allocate(capacity, incremental_pressure, target)
    left = max(float(target) - float(first.sum()), 0.0)
    if left <= 1e-8:
        return first
    second = _allocate(np.maximum(capacity - first, 0.0), cumulative_pressure, left)
    result = first + second
    left = max(float(target) - float(result.sum()), 0.0)
    if left > 1e-7:
        raise ValueError(
            "national GOBLIN land release cannot be spatialised within EDs showing "
            f"livestock pasture-pressure reduction; unallocated={left:.6f}"
        )
    return result


def allocate_national_goblin_land_release(
    livestock_pathway: pd.DataFrame,
    national_release_ha_by_year: Mapping[int, float],
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]],
    *,
    grassland_column: str = "ALL_GRASSLAND",
) -> pd.DataFrame:
    """Distribute GOBLIN's cumulative national release using ED pressure change.

    GOBLIN controls national hectares. Cohort pasture-DM change controls geography.
    Earlier ED release persists, and no ED can exceed ``ALL_GRASSLAND``.
    """
    required = {"CSOED", "PATHWAY_BASELINE_YEAR", "MILESTONE_YEAR", grassland_column}
    missing = sorted(required - set(livestock_pathway.columns))
    if missing:
        raise ValueError(f"GOBLIN land-release allocation missing columns: {missing}")
    if livestock_pathway[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("GOBLIN land-release allocation requires one row per ED and milestone")

    out = livestock_pathway.copy()
    years = sorted(pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).unique())
    targets = _targets(national_release_ha_by_year, years)
    base_years = pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").astype(int).unique()
    if len(base_years) != 1:
        raise ValueError("GOBLIN land-release allocation requires one pathway baseline year")
    base_year = int(base_years[0])

    first = out.loc[out["MILESTONE_YEAR"].eq(years[0])].sort_values("CSOED", kind="stable").reset_index(drop=True)
    ed_order = first["CSOED"].astype(str).tolist()
    base_dm = _pasture_dm_demand(first, state="BASE", profile=_profile_for_year(pasture_dm_t_per_head_by_year, base_year))
    previous_dm = base_dm.copy()
    cumulative_release = np.zeros(len(first), float)
    previous_target = 0.0
    rows = []

    for year in years:
        block = out.loc[out["MILESTONE_YEAR"].eq(year)].sort_values("CSOED", kind="stable").reset_index(drop=True)
        if block["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between GOBLIN release milestones")
        grass = pd.to_numeric(block[grassland_column], errors="raise").to_numpy(float)
        if (~np.isfinite(grass)).any() or (grass < -1e-12).any():
            raise ValueError(f"{grassland_column} must be finite and non-negative")
        grass = np.maximum(grass, 0.0)
        scenario_dm = _pasture_dm_demand(
            block,
            state="SCENARIO",
            profile=_profile_for_year(pasture_dm_t_per_head_by_year, int(year)),
        )
        incremental_pressure = np.maximum(previous_dm - scenario_dm, 0.0)
        cumulative_pressure = np.maximum(base_dm - scenario_dm, 0.0)
        target = targets[year]
        increment = target - previous_target
        allocation = _allocate_increment(
            np.maximum(grass - cumulative_release, 0.0),
            incremental_pressure,
            cumulative_pressure,
            increment,
        )
        cumulative_release += allocation
        if (cumulative_release - grass > 1e-7).any():
            raise AssertionError("GOBLIN released land exceeds ED grassland capacity")
        actual = float(cumulative_release.sum())
        if abs(actual - target) > 1e-6:
            raise AssertionError(f"national GOBLIN land-release closure failed for {year}")

        block["GOBLIN_RELEASE_BASELINE_PASTURE_DM_T"] = base_dm
        block["GOBLIN_RELEASE_SCENARIO_PASTURE_DM_T"] = scenario_dm
        block["INCREMENTAL_PASTURE_DM_REDUCTION_T"] = incremental_pressure
        block["CUMULATIVE_PASTURE_DM_REDUCTION_T"] = cumulative_pressure
        block["INCREMENTAL_GOBLIN_RELEASED_GRASSLAND_HA"] = allocation
        block["GOBLIN_RELEASED_GRASSLAND_HA"] = cumulative_release
        block["GOBLIN_RELEASED_GRASSLAND_SHARE_OF_ED"] = np.divide(cumulative_release, grass, out=np.zeros(len(block)), where=grass > 0)
        block["GOBLIN_NATIONAL_RELEASE_TARGET_HA"] = target
        block["GOBLIN_NATIONAL_RELEASE_ACTUAL_HA"] = actual
        block["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"] = actual - target
        block["GOBLIN_RELEASE_ACCOUNTING_ROLE"] = "AUTHORITATIVE_NATIONAL_TOTAL_SPATIALISED"
        rows.append(block)
        previous_dm = scenario_dm
        previous_target = target

    return pd.concat(rows, ignore_index=True).sort_values(["MILESTONE_YEAR", "CSOED"], kind="stable").reset_index(drop=True)
