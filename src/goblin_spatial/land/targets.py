"""Allocate potentially spared grassland to explicit cumulative land-use targets.

This module is downstream of the policy-neutral opportunity envelope. It does not
invent a land-use pathway. The user supplies cumulative national hectare targets
for each milestone and land use; the model then places only those requested
hectares across EDs using the transparent opportunity scores.

The accounting boundary remains::

    potential release -> opportunity -> explicit target allocation

A target can remain unmet when there is insufficient spared land or insufficient
eligible ED capacity. Unmet hectares are reported rather than forced into an
ineligible use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .opportunity import LAND_USES, OPPORTUNITY_SCORE_COLUMNS, add_ed_land_opportunity_scores


TARGET_COLUMNS = {land_use: f"{land_use}_HA" for land_use in LAND_USES}
DEFAULT_TARGET_PRIORITY = (
    "REWETTING",
    "FOREST",
    "AD_GRASS",
    "WILLOW",
    "ENERGY_GRASS",
    "NATURE",
)


def read_land_use_targets(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Read and validate cumulative national land-use targets by milestone.

    Required columns are ``MILESTONE_YEAR`` plus one ``<LAND_USE>_HA`` column for
    every land use in :data:`LAND_USES`. Targets are cumulative hectares and must
    be non-negative and non-decreasing through time for each use.
    """

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source))
    required = {"MILESTONE_YEAR", *TARGET_COLUMNS.values()}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"land-use target table missing columns: {missing}")

    out = frame[["MILESTONE_YEAR", *TARGET_COLUMNS.values()]].copy()
    out["MILESTONE_YEAR"] = pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int)
    if out["MILESTONE_YEAR"].duplicated().any():
        raise ValueError("land-use target table contains duplicate milestone years")
    out = out.sort_values("MILESTONE_YEAR", kind="stable").reset_index(drop=True)

    for land_use, column in TARGET_COLUMNS.items():
        values = pd.to_numeric(out[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(values)).any() or (values < -1e-12).any():
            raise ValueError(f"{column} must be finite and non-negative")
        values = np.maximum(values, 0.0)
        if (np.diff(values) < -1e-9).any():
            raise ValueError(f"cumulative {land_use} target cannot fall between milestones")
        out[column] = values

    return out


def _validate_priority(priority: Sequence[str]) -> tuple[str, ...]:
    resolved = tuple(str(value).upper() for value in priority)
    if len(resolved) != len(LAND_USES) or set(resolved) != set(LAND_USES):
        raise ValueError("priority must contain each alternative land use exactly once")
    return resolved


def _weighted_allocate(capacity: np.ndarray, score: np.ndarray, target: float) -> np.ndarray:
    """Allocate continuous hectares without exceeding ED capacity."""

    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    score = np.clip(np.asarray(score, dtype=float), 0.0, 1.0)
    target = max(float(target), 0.0)
    allocation = np.zeros(len(capacity), dtype=float)
    if target <= 1e-12:
        return allocation

    eligible_capacity = np.where(score > 1e-12, capacity, 0.0)
    feasible = min(target, float(eligible_capacity.sum()))
    remaining = feasible
    residual = capacity.copy()

    for _ in range(len(capacity) + 3):
        if remaining <= 1e-10:
            break
        active = (residual > 1e-12) & (score > 1e-12)
        if not active.any():
            break
        weights = np.where(active, residual * score, 0.0)
        weight_sum = float(weights.sum())
        if weight_sum <= 1e-15:
            break
        proposal = remaining * weights / weight_sum
        take = np.minimum(proposal, residual)
        allocation += take
        residual -= take
        new_remaining = feasible - float(allocation.sum())
        if abs(new_remaining - remaining) <= 1e-12:
            break
        remaining = new_remaining

    if (allocation - capacity > 1e-8).any():
        raise AssertionError("target allocation exceeded ED spared-land capacity")
    return allocation


def allocate_spared_land_to_cumulative_targets(
    frame: pd.DataFrame,
    targets: str | Path | pd.DataFrame,
    *,
    spared_column: str = "POTENTIAL_SPARED_GRASSLAND_HA",
    priority: Sequence[str] = DEFAULT_TARGET_PRIORITY,
    attach_scores: bool = True,
) -> pd.DataFrame:
    """Allocate spared grassland to explicit cumulative national hectare targets.

    At every milestone the function tries to reach the supplied cumulative target
    for each land use. Earlier unmet target is therefore carried forward. Existing
    allocations remain allocated, while currently unallocated spared grassland may
    be used at a later milestone. Allocation is mutually exclusive across land uses
    and closes exactly to potential spared grassland within every ED and milestone.
    """

    required = {"CSOED", "MILESTONE_YEAR", spared_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"target allocation missing columns: {missing}")

    ordered = frame.copy()
    if attach_scores and any(
        column not in ordered.columns for column in OPPORTUNITY_SCORE_COLUMNS.values()
    ):
        ordered = add_ed_land_opportunity_scores(ordered)

    missing_scores = sorted(
        column for column in OPPORTUNITY_SCORE_COLUMNS.values() if column not in ordered.columns
    )
    if missing_scores:
        raise ValueError(f"target allocation requires ED opportunity scores: {missing_scores}")

    if ordered[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("target allocation requires one row per ED and milestone")

    ordered["MILESTONE_YEAR"] = pd.to_numeric(
        ordered["MILESTONE_YEAR"], errors="raise"
    ).astype(int)
    years = sorted(ordered["MILESTONE_YEAR"].unique().tolist())
    target_table = read_land_use_targets(targets)
    target_years = target_table["MILESTONE_YEAR"].astype(int).tolist()
    if target_years != years:
        raise ValueError(
            "land-use target milestones must exactly match scenario milestones; "
            f"scenario={years}, targets={target_years}"
        )
    target_lookup = target_table.set_index("MILESTONE_YEAR")
    priority_order = _validate_priority(priority)

    first = ordered.loc[ordered["MILESTONE_YEAR"].eq(years[0])].sort_values(
        "CSOED", kind="stable"
    )
    ed_order = first["CSOED"].astype(str).tolist()
    n_ed = len(ed_order)
    cumulative = {land_use: np.zeros(n_ed, dtype=float) for land_use in LAND_USES}
    rows: list[pd.DataFrame] = []

    for year in years:
        block = ordered.loc[ordered["MILESTONE_YEAR"].eq(year)].copy()
        block = block.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if block["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between target-allocation milestones")

        spared = pd.to_numeric(block[spared_column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(spared)).any() or (spared < -1e-10).any():
            raise ValueError("potential spared grassland must be finite and non-negative")
        spared = np.maximum(spared, 0.0)

        already_allocated = np.zeros(n_ed, dtype=float)
        for land_use in LAND_USES:
            already_allocated += cumulative[land_use]
        if (already_allocated - spared > 1e-7).any():
            raise ValueError(
                "potential spared grassland fell below previously allocated land; "
                "cumulative target allocation cannot silently reverse conversion"
            )
        remaining_capacity = np.maximum(spared - already_allocated, 0.0)

        for land_use in priority_order:
            target = float(target_lookup.loc[year, TARGET_COLUMNS[land_use]])
            allocated_before = float(cumulative[land_use].sum())
            requested_now = max(target - allocated_before, 0.0)
            score = pd.to_numeric(
                block[OPPORTUNITY_SCORE_COLUMNS[land_use]], errors="raise"
            ).to_numpy(dtype=float)
            if (~np.isfinite(score)).any() or ((score < -1e-12) | (score > 1.0 + 1e-12)).any():
                raise ValueError(f"{OPPORTUNITY_SCORE_COLUMNS[land_use]} must lie in [0, 1]")
            allocation = _weighted_allocate(remaining_capacity, score, requested_now)
            cumulative[land_use] += allocation
            remaining_capacity = np.maximum(remaining_capacity - allocation, 0.0)

            cumulative_total = float(cumulative[land_use].sum())
            block[f"INCREMENTAL_{land_use}_HA"] = allocation
            block[f"CUMULATIVE_{land_use}_HA"] = cumulative[land_use]
            block[f"NATIONAL_CUMULATIVE_TARGET_{land_use}_HA"] = target
            block[f"NATIONAL_CUMULATIVE_ALLOCATED_{land_use}_HA"] = cumulative_total
            block[f"NATIONAL_CUMULATIVE_UNMET_{land_use}_TARGET_HA"] = max(
                target - cumulative_total, 0.0
            )

        block["RETAINED_SPARED_GRASSLAND_HA"] = remaining_capacity
        allocation_columns = [f"CUMULATIVE_{land_use}_HA" for land_use in LAND_USES]
        block["CUMULATIVE_ALTERNATIVE_LAND_HA"] = block[allocation_columns].sum(axis=1)
        block["LAND_TARGET_ALLOCATION_CLOSURE_HA"] = (
            block["CUMULATIVE_ALTERNATIVE_LAND_HA"]
            + block["RETAINED_SPARED_GRASSLAND_HA"]
            - spared
        )
        if not np.allclose(
            block["CUMULATIVE_ALTERNATIVE_LAND_HA"].to_numpy(dtype=float)
            + block["RETAINED_SPARED_GRASSLAND_HA"].to_numpy(dtype=float),
            spared,
            atol=1e-7,
        ):
            raise AssertionError("target allocation does not close to potential spared grassland")

        rows.append(block)

    result = pd.concat(rows, ignore_index=True)
    return result.sort_values(["MILESTONE_YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def summarise_land_target_allocation(
    frame: pd.DataFrame,
    *,
    spared_column: str = "POTENTIAL_SPARED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Return national milestone totals for an explicit land-target allocation."""

    required = {"MILESTONE_YEAR", spared_column, "RETAINED_SPARED_GRASSLAND_HA"}
    for land_use in LAND_USES:
        required.update(
            {
                f"INCREMENTAL_{land_use}_HA",
                f"CUMULATIVE_{land_use}_HA",
                f"NATIONAL_CUMULATIVE_TARGET_{land_use}_HA",
                f"NATIONAL_CUMULATIVE_ALLOCATED_{land_use}_HA",
                f"NATIONAL_CUMULATIVE_UNMET_{land_use}_TARGET_HA",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"land-target summary missing columns: {missing}")

    rows: list[dict[str, float | int]] = []
    for year, block in frame.groupby("MILESTONE_YEAR", sort=True):
        row: dict[str, float | int] = {
            "MILESTONE_YEAR": int(year),
            "POTENTIAL_SPARED_GRASSLAND_HA": float(
                pd.to_numeric(block[spared_column], errors="raise").sum()
            ),
            "RETAINED_SPARED_GRASSLAND_HA": float(
                pd.to_numeric(block["RETAINED_SPARED_GRASSLAND_HA"], errors="raise").sum()
            ),
        }
        for land_use in LAND_USES:
            row[f"INCREMENTAL_{land_use}_HA"] = float(
                pd.to_numeric(block[f"INCREMENTAL_{land_use}_HA"], errors="raise").sum()
            )
            row[f"CUMULATIVE_{land_use}_HA"] = float(
                pd.to_numeric(block[f"CUMULATIVE_{land_use}_HA"], errors="raise").sum()
            )
            for prefix in (
                "NATIONAL_CUMULATIVE_TARGET",
                "NATIONAL_CUMULATIVE_ALLOCATED",
                "NATIONAL_CUMULATIVE_UNMET",
            ):
                suffix = (
                    f"{prefix}_{land_use}_TARGET_HA"
                    if prefix == "NATIONAL_CUMULATIVE_UNMET"
                    else f"{prefix}_{land_use}_HA"
                )
                row[suffix] = float(pd.to_numeric(block[suffix], errors="raise").iloc[0])
        rows.append(row)

    return pd.DataFrame(rows).sort_values("MILESTONE_YEAR", kind="stable").reset_index(drop=True)
