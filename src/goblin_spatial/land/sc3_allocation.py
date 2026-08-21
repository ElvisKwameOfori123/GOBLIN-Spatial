"""SC3 constrained allocation of explicit national land-use targets.

SC3 consumes a completed SC2 opportunity/capacity table.  It does not derive
eligibility itself and it does not invent a national land-use pathway.  Every
national target is supplied explicitly, normally from the editable scenario
control row.

Five Stage-A uses compete for the same frozen SC1 released-land pool and are
therefore mutually exclusive:

    AD_GRASS
    BIOREFINERY_GRASS
    WILLOW
    ADDITIONAL_TILLAGE
    FOREST

Rewetting is handled second, against the Stage-A remainder and an independently
supplied organic-soil capacity.  This preserves the source accounting distinction
while preventing physical double allocation.

SC2 must supply, for every use, both a physical capacity column and an explicit
ranking/score column.  There are deliberately no built-in 0.85/0.80/0.70 or other
scientific suitability weights in this allocator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


STAGE_A_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
)
REWETTING_USE = "REWETTING"
SC3_USES = (*STAGE_A_USES, REWETTING_USE)
DEFAULT_STAGE_A_PRIORITY = STAGE_A_USES


def _validate_targets(targets: Mapping[str, float]) -> dict[str, float]:
    supplied = {str(key).strip().upper(): float(value) for key, value in dict(targets).items()}
    missing = sorted(set(SC3_USES) - set(supplied))
    extra = sorted(set(supplied) - set(SC3_USES))
    if missing or extra:
        raise ValueError(
            "SC3 targets must contain exactly the six supported land uses; "
            f"missing={missing}, extra={extra}"
        )
    if any((not np.isfinite(value)) or value < 0 for value in supplied.values()):
        raise ValueError("SC3 national targets must be finite and non-negative")
    return supplied


def _validate_use_columns(
    mapping: Mapping[str, str],
    *,
    label: str,
) -> dict[str, str]:
    supplied = {str(key).strip().upper(): str(value).strip() for key, value in dict(mapping).items()}
    missing = sorted(set(SC3_USES) - set(supplied))
    extra = sorted(set(supplied) - set(SC3_USES))
    if missing or extra:
        raise ValueError(
            f"{label} must contain exactly the six SC3 land uses; "
            f"missing={missing}, extra={extra}"
        )
    if any(not column for column in supplied.values()):
        raise ValueError(f"{label} contains an empty column name")
    return supplied


def _validate_priority(priority: Sequence[str]) -> tuple[str, ...]:
    resolved = tuple(str(value).strip().upper() for value in priority)
    if len(resolved) != len(STAGE_A_USES) or set(resolved) != set(STAGE_A_USES):
        raise ValueError("SC3 Stage-A priority must contain each Stage-A use exactly once")
    return resolved


def _values(frame: pd.DataFrame, column: str, *, bounded_score: bool = False) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC3 input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    if bounded_score:
        if ((values < -1e-12) | (values > 1.0 + 1e-12)).any():
            raise ValueError(f"{column} must lie in [0, 1]")
        return np.clip(values, 0.0, 1.0)
    if (values < -1e-10).any():
        raise ValueError(f"{column} must be non-negative")
    return np.maximum(values, 0.0)


def _weighted_allocate(capacity: np.ndarray, score: np.ndarray, target: float) -> np.ndarray:
    """Allocate continuous hectares by explicit score without exceeding capacity."""

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
        raise AssertionError("SC3 allocation exceeded supplied SC2 capacity")
    if float(allocation.sum()) - target > 1e-7:
        raise AssertionError("SC3 allocation exceeded national target")
    return allocation


def allocate_sc3_targets(
    frame: pd.DataFrame,
    targets: Mapping[str, float],
    *,
    capacity_columns: Mapping[str, str],
    score_columns: Mapping[str, str],
    release_column: str = "SC2_POTENTIAL_RELEASE_HA",
    stage_a_priority: Sequence[str] = DEFAULT_STAGE_A_PRIORITY,
) -> pd.DataFrame:
    """Allocate explicit national targets within SC2 capacity and frozen release.

    SC2 capacity columns are broad maximum feasible hectares for each use.  The
    score columns provide the study's explicitly validated ordering within that
    capacity.  Eligibility may overlap in SC2; realised hectares are mutually
    exclusive here.
    """

    if "CSOED" not in frame.columns:
        raise ValueError("SC3 allocation requires CSOED")
    if frame["CSOED"].duplicated().any():
        raise ValueError("SC3 endpoint allocation requires one row per ED")

    target_map = _validate_targets(targets)
    capacity_map = _validate_use_columns(capacity_columns, label="capacity_columns")
    score_map = _validate_use_columns(score_columns, label="score_columns")
    priority = _validate_priority(stage_a_priority)

    out = frame.copy()
    release = _values(out, release_column)
    remaining = release.copy()

    target_results: dict[str, tuple[float, float]] = {}
    for use in priority:
        raw_capacity = _values(out, capacity_map[use])
        score = _values(out, score_map[use], bounded_score=True)
        capacity = np.minimum(raw_capacity, remaining)
        allocation = _weighted_allocate(capacity, score, target_map[use])
        remaining = np.maximum(remaining - allocation, 0.0)
        allocated = float(allocation.sum())
        unmet = max(target_map[use] - allocated, 0.0)
        target_results[use] = (allocated, unmet)

        out[f"SC3_REALIZED_{use}_HA"] = allocation
        out[f"SC3_AVAILABLE_BEFORE_{use}_HA"] = remaining + allocation
        out[f"SC3_NATIONAL_TARGET_{use}_HA"] = target_map[use]
        out[f"SC3_NATIONAL_REALIZED_{use}_HA"] = allocated
        out[f"SC3_NATIONAL_UNMET_{use}_HA"] = unmet

    out["SC3_STAGE_A_AVAILABLE_HA"] = remaining.copy()
    stage_a_remaining_national = float(remaining.sum())

    # Rewetting is deliberately second and can only consume the Stage-A remainder.
    rewet_capacity_raw = _values(out, capacity_map[REWETTING_USE])
    rewet_score = _values(out, score_map[REWETTING_USE], bounded_score=True)
    rewet_capacity = np.minimum(rewet_capacity_raw, remaining)
    rewetting = _weighted_allocate(
        rewet_capacity,
        rewet_score,
        target_map[REWETTING_USE],
    )
    remaining = np.maximum(remaining - rewetting, 0.0)
    rewet_realised = float(rewetting.sum())
    rewet_unmet = max(target_map[REWETTING_USE] - rewet_realised, 0.0)
    target_results[REWETTING_USE] = (rewet_realised, rewet_unmet)

    out[f"SC3_REALIZED_{REWETTING_USE}_HA"] = rewetting
    out[f"SC3_NATIONAL_TARGET_{REWETTING_USE}_HA"] = target_map[REWETTING_USE]
    out[f"SC3_NATIONAL_REALIZED_{REWETTING_USE}_HA"] = rewet_realised
    out[f"SC3_NATIONAL_UNMET_{REWETTING_USE}_HA"] = rewet_unmet
    out["SC3_RESIDUAL_AVAILABLE_LAND_HA"] = remaining

    realised_columns = [f"SC3_REALIZED_{use}_HA" for use in SC3_USES]
    out["SC3_REALISED_CONVERSION_HA"] = out[realised_columns].sum(axis=1)
    out["SC3_ACCOUNTING_CLOSURE_HA"] = (
        out["SC3_REALISED_CONVERSION_HA"]
        + out["SC3_RESIDUAL_AVAILABLE_LAND_HA"]
        - release
    )
    if not np.allclose(
        out["SC3_REALISED_CONVERSION_HA"].to_numpy(dtype=float)
        + out["SC3_RESIDUAL_AVAILABLE_LAND_HA"].to_numpy(dtype=float),
        release,
        atol=1e-7,
    ):
        raise AssertionError("SC3 realised conversion + residual does not close to SC1 release")

    out["SC3_NATIONAL_STAGE_A_AVAILABLE_HA"] = stage_a_remaining_national
    out["SC3_NATIONAL_RESIDUAL_AVAILABLE_LAND_HA"] = float(remaining.sum())
    out["SC3_TOTAL_UNMET_TARGET_HA"] = float(sum(unmet for _, unmet in target_results.values()))
    out["SC3_ALLOCATION_VERSION"] = "1.0"
    return out


def summarise_sc3_allocation(
    frame: pd.DataFrame,
    *,
    release_column: str = "SC2_POTENTIAL_RELEASE_HA",
) -> pd.DataFrame:
    """Return a one-row national SC3 reconciliation summary."""

    required = {
        release_column,
        "SC3_STAGE_A_AVAILABLE_HA",
        "SC3_RESIDUAL_AVAILABLE_LAND_HA",
        "SC3_REALISED_CONVERSION_HA",
    }
    for use in SC3_USES:
        required.update(
            {
                f"SC3_REALIZED_{use}_HA",
                f"SC3_NATIONAL_TARGET_{use}_HA",
                f"SC3_NATIONAL_REALIZED_{use}_HA",
                f"SC3_NATIONAL_UNMET_{use}_HA",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SC3 summary missing columns: {missing}")

    row: dict[str, float] = {
        "POTENTIAL_RELEASE_HA": float(pd.to_numeric(frame[release_column], errors="raise").sum()),
        "STAGE_A_AVAILABLE_HA": float(pd.to_numeric(frame["SC3_STAGE_A_AVAILABLE_HA"], errors="raise").sum()),
        "REALISED_CONVERSION_HA": float(pd.to_numeric(frame["SC3_REALISED_CONVERSION_HA"], errors="raise").sum()),
        "RESIDUAL_AVAILABLE_LAND_HA": float(pd.to_numeric(frame["SC3_RESIDUAL_AVAILABLE_LAND_HA"], errors="raise").sum()),
    }
    total_unmet = 0.0
    for use in SC3_USES:
        target = float(pd.to_numeric(frame[f"SC3_NATIONAL_TARGET_{use}_HA"], errors="raise").iloc[0])
        realised = float(pd.to_numeric(frame[f"SC3_REALIZED_{use}_HA"], errors="raise").sum())
        unmet = float(pd.to_numeric(frame[f"SC3_NATIONAL_UNMET_{use}_HA"], errors="raise").iloc[0])
        row[f"TARGET_{use}_HA"] = target
        row[f"REALISED_{use}_HA"] = realised
        row[f"UNMET_{use}_HA"] = unmet
        total_unmet += unmet
    row["TOTAL_UNMET_TARGET_HA"] = total_unmet
    row["ACCOUNTING_CLOSURE_HA"] = (
        row["REALISED_CONVERSION_HA"]
        + row["RESIDUAL_AVAILABLE_LAND_HA"]
        - row["POTENTIAL_RELEASE_HA"]
    )
    return pd.DataFrame([row])
