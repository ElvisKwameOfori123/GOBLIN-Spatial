"""Spatialise an externally supplied national GOBLIN livestock-land release.

GOBLIN supplies the national released-land total. GOBLIN-Spatial locates that
release across the validated ED livestock geography using cohort-specific
pasture dry-matter pressure change. The independent ED grassland requirement
calculation remains available as a diagnostic and is not used here to redefine
the national GOBLIN total.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.pressure.grassland_release import (
    _pasture_dm_demand,
    _profile_for_year,
)


def _validate_release_targets(
    targets_by_year: Mapping[int, float],
    milestone_years: list[int],
) -> dict[int, float]:
    """Validate cumulative national GOBLIN land-release targets."""

    if not targets_by_year:
        raise ValueError("national GOBLIN land-release targets cannot be empty")
    targets = {int(year): float(value) for year, value in targets_by_year.items()}
    if set(targets) != set(milestone_years):
        raise ValueError(
            "national land-release targets must exactly match scenario milestones; "
            f"scenario={milestone_years}, targets={sorted(targets)}"
        )
    previous = 0.0
    for year in milestone_years:
        value = targets[year]
        if not np.isfinite(value) or value < -1e-12:
            raise ValueError(
                f"national land-release target for {year} must be finite and non-negative"
            )
        value = max(value, 0.0)
        if value + 1e-9 < previous:
            raise ValueError("cumulative national land release cannot fall between milestones")
        targets[year] = value
        previous = value
    return targets


def _weighted_bounded_allocate(
    capacity: np.ndarray,
    weight: np.ndarray,
    target: float,
) -> np.ndarray:
    """Allocate continuous hectares using non-negative weights and hard capacities."""

    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    weight = np.maximum(np.asarray(weight, dtype=float), 0.0)
    target = max(float(target), 0.0)
    allocation = np.zeros(len(capacity), dtype=float)
    if target <= 1e-12:
        return allocation

    eligible = (capacity > 1e-12) & (weight > 1e-12)
    amount = min(target, float(capacity[eligible].sum()))
    remaining = amount
    residual = capacity.copy()

    for _ in range(len(capacity) + 3):
        if remaining <= 1e-10:
            break
        active = (residual > 1e-12) & (weight > 1e-12)
        if not active.any():
            break
        weighted_capacity = np.where(active, residual * weight, 0.0)
        denominator = float(weighted_capacity.sum())
        if denominator <= 1e-15:
            break
        proposal = remaining * weighted_capacity / denominator
        take = np.minimum(proposal, residual)
        allocation += take
        residual -= take
        new_remaining = amount - float(allocation.sum())
        if abs(new_remaining - remaining) <= 1e-12:
            break
        remaining = new_remaining

    if (allocation - capacity > 1e-8).any():
        raise AssertionError("GOBLIN land-release allocation exceeded ED capacity")
    return allocation


def _allocate_with_pressure_fallback(
    capacity: np.ndarray,
    incremental_pressure: np.ndarray,
    cumulative_pressure: np.ndarray,
    target: float,
) -> np.ndarray:
    """Use incremental pressure first, then cumulative pressure for residual hectares."""

    first = _weighted_bounded_allocate(capacity, incremental_pressure, target)
    remaining_target = max(float(target) - float(first.sum()), 0.0)
    if remaining_target <= 1e-8:
        return first

    residual_capacity = np.maximum(np.asarray(capacity, dtype=float) - first, 0.0)
    second = _weighted_bounded_allocate(
        residual_capacity,
        cumulative_pressure,
        remaining_target,
    )
    allocation = first + second
    residual = max(float(target) - float(allocation.sum()), 0.0)
    if residual > 1e-7:
        eligible_capacity = float(
            np.where(
                np.asarray(cumulative_pressure, dtype=float) > 1e-12,
                np.asarray(capacity, dtype=float),
                0.0,
            ).sum()
        )
        raise ValueError(
            "national GOBLIN land release cannot be spatialised within EDs that "
            "show livestock pasture-pressure reduction; "
            f"requested_increment={target:.6f}, eligible_capacity={eligible_capacity:.6f}, "
            f"unallocated={residual:.6f}"
        )
    return allocation


def allocate_national_goblin_land_release(
    livestock_pathway: pd.DataFrame,
    national_release_ha_by_year: Mapping[int, float],
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]],
    *,
    grassland_column: str = "ALL_GRASSLAND",
) -> pd.DataFrame:
    """Allocate cumulative national GOBLIN released land across EDs.

    Only the additional national release at each milestone is allocated.
    Incremental pasture-pressure reduction provides the first spatial weight;
    cumulative pressure reduction is used only as a fallback where the
    incremental pattern lacks enough ED capacity. Previously attributed release
    never moves backwards between milestones.
    """

    required = {
        "CSOED",
        "PATHWAY_BASELINE_YEAR",
        "MILESTONE_YEAR",
        grassland_column,
    }
    missing = sorted(required - set(livestock_pathway.columns))
    if missing:
        raise ValueError(f"GOBLIN land-release allocation missing columns: {missing}")
    if livestock_pathway[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("GOBLIN land-release allocation requires one row per ED and milestone")

    out = livestock_pathway.copy()
    years = sorted(
        pd.to_numeric(out["MILESTONE_YEAR"], errors="raise")
        .astype(int)
        .unique()
        .tolist()
    )
    targets = _validate_release_targets(national_release_ha_by_year, years)

    baseline_years = pd.to_numeric(
        out["PATHWAY_BASELINE_YEAR"], errors="raise"
    ).astype(int).unique()
    if len(baseline_years) != 1:
        raise ValueError("GOBLIN land-release allocation requires one pathway baseline year")
    baseline_year = int(baseline_years[0])
    baseline_profile = _profile_for_year(pasture_dm_t_per_head_by_year, baseline_year)

    first = out.loc[out["MILESTONE_YEAR"].eq(years[0])].copy()
    first = first.sort_values("CSOED", kind="stable").reset_index(drop=True)
    ed_order = first["CSOED"].astype(str).tolist()
    baseline_dm = _pasture_dm_demand(first, state="BASE", profile=baseline_profile)
    previous_dm = baseline_dm.copy()
    cumulative_release = np.zeros(len(first), dtype=float)
    previous_target = 0.0
    rows: list[pd.DataFrame] = []

    for year in years:
        block = out.loc[out["MILESTONE_YEAR"].eq(year)].copy()
        block = block.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if block["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between GOBLIN release milestones")

        grassland = pd.to_numeric(block[grassland_column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(grassland)).any() or (grassland < -1e-12).any():
            raise ValueError(f"{grassland_column} must be finite and non-negative")
        grassland = np.maximum(grassland, 0.0)
        if (cumulative_release - grassland > 1e-7).any():
            raise AssertionError("previous GOBLIN released land exceeds ED grassland capacity")

        profile = _profile_for_year(pasture_dm_t_per_head_by_year, int(year))
        scenario_dm = _pasture_dm_demand(block, state="SCENARIO", profile=profile)
        incremental_pressure = np.maximum(previous_dm - scenario_dm, 0.0)
        cumulative_pressure = np.maximum(baseline_dm - scenario_dm, 0.0)

        target = targets[year]
        incremental_target = max(target - previous_target, 0.0)
        remaining_capacity = np.maximum(grassland - cumulative_release, 0.0)
        incremental_release = _allocate_with_pressure_fallback(
            remaining_capacity,
            incremental_pressure,
            cumulative_pressure,
            incremental_target,
        )
        cumulative_release = cumulative_release + incremental_release

        if (cumulative_release - grassland > 1e-7).any():
            raise AssertionError("GOBLIN released land exceeds ED ALL_GRASSLAND capacity")
        actual = float(cumulative_release.sum())
        difference = actual - target
        if abs(difference) > 1e-6:
            raise AssertionError(
                f"national GOBLIN land-release closure failed for {year}: "
                f"target={target:.6f}, actual={actual:.6f}, difference={difference:.6f}"
            )

        block["GOBLIN_RELEASE_BASELINE_PASTURE_DM_T"] = baseline_dm
        block["GOBLIN_RELEASE_SCENARIO_PASTURE_DM_T"] = scenario_dm
        block["INCREMENTAL_PASTURE_DM_REDUCTION_T"] = incremental_pressure
        block["CUMULATIVE_PASTURE_DM_REDUCTION_T"] = cumulative_pressure
        block["INCREMENTAL_GOBLIN_RELEASED_GRASSLAND_HA"] = incremental_release
        block["GOBLIN_RELEASED_GRASSLAND_HA"] = cumulative_release
        block["GOBLIN_RELEASED_GRASSLAND_SHARE_OF_ED"] = np.divide(
            cumulative_release,
            grassland,
            out=np.zeros(len(block), dtype=float),
            where=grassland > 0,
        )
        block["GOBLIN_NATIONAL_RELEASE_TARGET_HA"] = target
        block["GOBLIN_NATIONAL_RELEASE_ACTUAL_HA"] = actual
        block["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"] = difference
        block["GOBLIN_RELEASE_ACCOUNTING_ROLE"] = "AUTHORITATIVE_NATIONAL_TOTAL_SPATIALISED"
        rows.append(block)

        previous_dm = scenario_dm
        previous_target = target

    result = pd.concat(rows, ignore_index=True)
    return result.sort_values(["MILESTONE_YEAR", "CSOED"], kind="stable").reset_index(drop=True)
