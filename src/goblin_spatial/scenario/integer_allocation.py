"""Small integer-allocation utilities used by the principal scenario engine.

This module exists so the production cohort-response logic does not depend on
the retired generic fractional scenario allocator.
"""

from __future__ import annotations

import numpy as np


def bounded_integer_allocate(
    weights: np.ndarray,
    capacities: np.ndarray,
    target: int,
) -> np.ndarray:
    """Allocate an exact integer total without exceeding per-ED capacity."""

    weights = np.asarray(weights, dtype=float)
    capacities = np.asarray(capacities, dtype=np.int64)
    target = int(target)

    if weights.shape != capacities.shape:
        raise ValueError("weights and capacities must have the same shape")
    if target < 0 or target > int(capacities.sum()):
        raise ValueError("allocation target exceeds available capacity")
    if target == 0:
        return np.zeros(len(capacities), dtype=np.int64)
    if (capacities < 0).any() or (~np.isfinite(weights)).any() or (weights < 0).any():
        raise ValueError("invalid weights or capacities")

    remaining_capacity = capacities.astype(float).copy()
    fractional = np.zeros(len(capacities), dtype=float)
    remaining = float(target)

    for _ in range(len(capacities) + 2):
        if remaining <= 1e-10:
            break
        active = remaining_capacity > 1e-12
        if not active.any():
            break
        active_weights = np.where(active, weights, 0.0)
        if float(active_weights.sum()) <= 0:
            active_weights = np.where(active, remaining_capacity, 0.0)
        proposal = remaining * active_weights / active_weights.sum()
        take = np.minimum(proposal, remaining_capacity)
        fractional += take
        remaining_capacity -= take
        remaining = float(target - fractional.sum())

    if abs(remaining) > 1e-7:
        raise AssertionError("bounded allocation failed to close in fractional space")

    result = np.floor(fractional + 1e-12).astype(np.int64)
    left = target - int(result.sum())
    if left:
        remainder = fractional - result
        eligible = result < capacities
        order = np.argsort(-np.where(eligible, remainder, -1.0), kind="stable")
        for index in order:
            if left == 0:
                break
            if result[index] < capacities[index]:
                result[index] += 1
                left -= 1

    if left != 0 or int(result.sum()) != target:
        raise AssertionError("bounded integer allocation failed exact closure")
    if (result < 0).any() or (result > capacities).any():
        raise AssertionError("bounded integer allocation violated ED capacity")
    return result
