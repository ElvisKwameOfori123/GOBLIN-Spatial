"""Allocate sourced Styles SI_SG / BE_SG released-land targets across EDs.

This module is deliberately downstream of livestock, authoritative national land
release, soil and LPIS context. It does not decide how much land Ireland
releases. It places only the incremental land uses supplied by the same Styles
pathway package and leaves the remainder as Available land.

The Table S3 released-land accounting used here is:

    gross livestock-land release
        = allocated incremental uses + Available residual

Organic-soil rewetting and restored wetland are not included in this released-
land pool because the Table S3 arithmetic already closes without them.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from .opportunity_v2 import add_ed_land_opportunity_scores_v2


STYLES_RELEASED_LAND_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
)

DEFAULT_STYLES_PRIORITY = STYLES_RELEASED_LAND_USES


def _weighted_allocate(capacity: np.ndarray, score: np.ndarray, target: float) -> np.ndarray:
    """Allocate continuous hectares by score without exceeding ED capacity."""

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
        total_weight = float(weights.sum())
        if total_weight <= 1e-15:
            break
        proposal = remaining * weights / total_weight
        take = np.minimum(proposal, residual)
        allocation += take
        residual -= take
        new_remaining = feasible - float(allocation.sum())
        if abs(new_remaining - remaining) <= 1e-12:
            break
        remaining = new_remaining

    if (allocation - capacity > 1e-8).any():
        raise AssertionError("Styles land allocation exceeded ED released-land capacity")
    return allocation


def _validate_priority(priority: Sequence[str]) -> tuple[str, ...]:
    resolved = tuple(str(value).strip().upper() for value in priority)
    if len(resolved) != len(STYLES_RELEASED_LAND_USES) or set(resolved) != set(
        STYLES_RELEASED_LAND_USES
    ):
        raise ValueError(
            "priority must contain each Styles released-land use exactly once"
        )
    return resolved


def _styles_scores(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return transparent first-stage ED scores for the five released-land uses.

    Biorefinery grass uses the same productive grass-clover screen as AD grass.
    Additional tillage uses the production-soil score, reduced where matched LPIS
    identifies sensitive grass context. These are opportunity-screen weights,
    not parcel-level crop suitability claims.
    """

    required = {
        "FORESTRY_OPPORTUNITY_SCORE",
        "AD_GRASS_OPPORTUNITY_SCORE",
        "WILLOW_OPPORTUNITY_SCORE",
        "GOBLIN_SOIL_PRODUCTIVITY_SCORE",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Styles land allocation missing opportunity scores: {missing}")

    def values(column: str) -> np.ndarray:
        out = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(out)).any():
            raise ValueError(f"{column} must be finite")
        return np.clip(out, 0.0, 1.0)

    productivity = values("GOBLIN_SOIL_PRODUCTIVITY_SCORE")
    if "LPIS_PRODUCTIVE_GRASS_CONTEXT_SHARE" in frame.columns:
        context = pd.to_numeric(
            frame["LPIS_PRODUCTIVE_GRASS_CONTEXT_SHARE"], errors="coerce"
        ).to_numpy(dtype=float)
        context = np.where(np.isfinite(context), np.clip(context, 0.0, 1.0), 1.0)
    else:
        context = np.ones(len(frame), dtype=float)

    return {
        "AD_GRASS": values("AD_GRASS_OPPORTUNITY_SCORE"),
        "BIOREFINERY_GRASS": values("AD_GRASS_OPPORTUNITY_SCORE"),
        "WILLOW": values("WILLOW_OPPORTUNITY_SCORE"),
        "ADDITIONAL_TILLAGE": np.clip(productivity * context, 0.0, 1.0),
        "FOREST": values("FORESTRY_OPPORTUNITY_SCORE"),
    }


def allocate_styles_released_land_targets(
    frame: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    released_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
    priority: Sequence[str] = DEFAULT_STYLES_PRIORITY,
    attach_scores: bool = True,
) -> pd.DataFrame:
    """Place one Styles pathway's explicit 2050 released-land targets across EDs.

    National released hectares and land-use targets remain hard pathway controls.
    Opportunity evidence affects geography only. If an opportunity screen cannot
    accommodate a target, the unmet amount is reported and remains in the ED
    Available-land residual rather than being forced into unsuitable locations.
    """

    milestone = controls.milestone(controls.target_year)
    if milestone.livestock_land_release_ha is None:
        raise ValueError(
            "Styles land allocation requires an authoritative livestock-land release"
        )
    if milestone.available_land_residual_ha is None:
        raise ValueError("Styles land allocation requires the sourced Available residual")

    supplied_targets = dict(milestone.land_use_targets_ha)
    missing_targets = sorted(set(STYLES_RELEASED_LAND_USES) - set(supplied_targets))
    extra_targets = sorted(set(supplied_targets) - set(STYLES_RELEASED_LAND_USES))
    if missing_targets or extra_targets:
        raise ValueError(
            "Styles land-use controls must contain exactly the released-land uses; "
            f"missing={missing_targets}, extra={extra_targets}"
        )

    expected_release = float(milestone.livestock_land_release_ha)
    expected_residual = float(milestone.available_land_residual_ha)
    target_sum = float(sum(float(v) for v in supplied_targets.values()))
    if abs(target_sum + expected_residual - expected_release) > 1e-6:
        raise AssertionError("Styles national released-land accounting does not close")

    required = {"CSOED", "MILESTONE_YEAR", released_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Styles land allocation missing columns: {missing}")

    out = frame.copy()
    years = pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).unique()
    if len(years) != 1 or int(years[0]) != int(controls.target_year):
        raise ValueError(
            "Styles land allocation currently requires the single sourced target year"
        )
    if out["CSOED"].duplicated().any():
        raise ValueError("Styles land allocation requires one row per ED")

    if attach_scores:
        needed = {
            "FORESTRY_OPPORTUNITY_SCORE",
            "AD_GRASS_OPPORTUNITY_SCORE",
            "WILLOW_OPPORTUNITY_SCORE",
            "GOBLIN_SOIL_PRODUCTIVITY_SCORE",
        }
        if not needed.issubset(out.columns):
            out = add_ed_land_opportunity_scores_v2(out)

    scores = _styles_scores(out)
    release = pd.to_numeric(out[released_column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(release)).any() or (release < -1e-10).any():
        raise ValueError("released land must be finite and non-negative")
    release = np.maximum(release, 0.0)
    if abs(float(release.sum()) - expected_release) > 1e-6:
        raise AssertionError(
            "ED released-land sum does not match the authoritative Styles pathway total"
        )

    remaining = release.copy()
    priority_order = _validate_priority(priority)
    total_unmet = 0.0

    for land_use in priority_order:
        target = float(supplied_targets[land_use])
        allocation = _weighted_allocate(remaining, scores[land_use], target)
        remaining = np.maximum(remaining - allocation, 0.0)
        allocated = float(allocation.sum())
        unmet = max(target - allocated, 0.0)
        total_unmet += unmet

        out[f"STYLES_ALLOCATED_{land_use}_HA"] = allocation
        out[f"STYLES_{land_use}_OPPORTUNITY_SCORE"] = scores[land_use]
        out[f"STYLES_NATIONAL_TARGET_{land_use}_HA"] = target
        out[f"STYLES_NATIONAL_ALLOCATED_{land_use}_HA"] = allocated
        out[f"STYLES_NATIONAL_UNMET_{land_use}_HA"] = unmet

    out["STYLES_AVAILABLE_RESIDUAL_HA"] = remaining
    actual_residual = float(remaining.sum())
    expected_with_unmet = expected_residual + total_unmet
    if abs(actual_residual - expected_with_unmet) > 1e-6:
        raise AssertionError(
            "Styles Available residual does not reconcile with unmet land-use targets"
        )

    allocated_columns = [
        f"STYLES_ALLOCATED_{land_use}_HA" for land_use in STYLES_RELEASED_LAND_USES
    ]
    out["STYLES_ALLOCATED_RELEASED_LAND_HA"] = out[allocated_columns].sum(axis=1)
    out["STYLES_LAND_ACCOUNTING_CLOSURE_HA"] = (
        out["STYLES_ALLOCATED_RELEASED_LAND_HA"]
        + out["STYLES_AVAILABLE_RESIDUAL_HA"]
        - release
    )
    if not np.allclose(
        out["STYLES_ALLOCATED_RELEASED_LAND_HA"].to_numpy(dtype=float)
        + out["STYLES_AVAILABLE_RESIDUAL_HA"].to_numpy(dtype=float),
        release,
        atol=1e-7,
    ):
        raise AssertionError("ED Styles land allocation does not close to released land")

    out["STYLES_EXPECTED_AVAILABLE_RESIDUAL_HA"] = expected_residual
    out["STYLES_ACTUAL_AVAILABLE_RESIDUAL_HA"] = actual_residual
    out["STYLES_TOTAL_UNMET_LAND_TARGET_HA"] = total_unmet
    out["STYLES_LAND_TARGET_ACCOUNTING_ROLE"] = (
        "SAME_PATHWAY_EXPLICIT_TARGETS_SPATIALISED"
    )
    return out


def _report_hectares(value: float) -> float:
    """Normalise sub-microhectare floating noise at the reporting boundary."""

    return float(np.round(float(value), 6))


def summarise_styles_released_land_targets(
    frame: pd.DataFrame,
    *,
    released_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Return one-row national reconciliation for a Styles land allocation.

    Continuous ED allocation retains full floating precision. National hectare
    reporting is rounded to 1e-6 ha so binary floating representation cannot
    turn an exact sourced control such as 803000 ha into 802999.9999999999 ha.
    """

    required = {
        "MILESTONE_YEAR",
        released_column,
        "STYLES_AVAILABLE_RESIDUAL_HA",
        "STYLES_EXPECTED_AVAILABLE_RESIDUAL_HA",
        "STYLES_ACTUAL_AVAILABLE_RESIDUAL_HA",
        "STYLES_TOTAL_UNMET_LAND_TARGET_HA",
    }
    for land_use in STYLES_RELEASED_LAND_USES:
        required.update(
            {
                f"STYLES_ALLOCATED_{land_use}_HA",
                f"STYLES_NATIONAL_TARGET_{land_use}_HA",
                f"STYLES_NATIONAL_ALLOCATED_{land_use}_HA",
                f"STYLES_NATIONAL_UNMET_{land_use}_HA",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Styles land summary missing columns: {missing}")

    years = pd.to_numeric(frame["MILESTONE_YEAR"], errors="raise").astype(int).unique()
    if len(years) != 1:
        raise ValueError("Styles land summary requires one milestone year")

    row: dict[str, float | int] = {
        "MILESTONE_YEAR": int(years[0]),
        "GOBLIN_RELEASED_GRASSLAND_HA": _report_hectares(
            pd.to_numeric(frame[released_column], errors="raise").sum()
        ),
        "STYLES_AVAILABLE_RESIDUAL_HA": _report_hectares(
            pd.to_numeric(frame["STYLES_AVAILABLE_RESIDUAL_HA"], errors="raise").sum()
        ),
        "STYLES_EXPECTED_AVAILABLE_RESIDUAL_HA": _report_hectares(
            pd.to_numeric(frame["STYLES_EXPECTED_AVAILABLE_RESIDUAL_HA"], errors="raise").iloc[0]
        ),
        "STYLES_ACTUAL_AVAILABLE_RESIDUAL_HA": _report_hectares(
            pd.to_numeric(frame["STYLES_ACTUAL_AVAILABLE_RESIDUAL_HA"], errors="raise").iloc[0]
        ),
        "STYLES_TOTAL_UNMET_LAND_TARGET_HA": _report_hectares(
            pd.to_numeric(frame["STYLES_TOTAL_UNMET_LAND_TARGET_HA"], errors="raise").iloc[0]
        ),
    }
    for land_use in STYLES_RELEASED_LAND_USES:
        row[f"TARGET_{land_use}_HA"] = _report_hectares(
            pd.to_numeric(frame[f"STYLES_NATIONAL_TARGET_{land_use}_HA"], errors="raise").iloc[0]
        )
        row[f"ALLOCATED_{land_use}_HA"] = _report_hectares(
            pd.to_numeric(frame[f"STYLES_ALLOCATED_{land_use}_HA"], errors="raise").sum()
        )
        row[f"UNMET_{land_use}_HA"] = _report_hectares(
            pd.to_numeric(frame[f"STYLES_NATIONAL_UNMET_{land_use}_HA"], errors="raise").iloc[0]
        )
    return pd.DataFrame([row])
