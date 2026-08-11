"""Largest-remainder integer allocation used throughout GOBLIN-Spatial."""

from __future__ import annotations

import numpy as np


def hamilton_allocate(weights, target: int, floor_epsilon: float = 1e-12) -> np.ndarray:
    """Allocate an integer target according to non-negative weights exactly.

    The returned array is non-negative, integer-valued and sums exactly to
    ``target``. Stable ordering makes ties reproducible. A tiny positive floor
    epsilon reproduces the validated baseline allocation convention and avoids
    a value that is microscopically below an integer being floored downward.
    """

    weights = np.asarray(weights, dtype=float)
    target = int(target)

    if target < 0:
        raise ValueError("target must be non-negative")
    if floor_epsilon < 0:
        raise ValueError("floor_epsilon must be non-negative")
    if not np.isfinite(weights).all():
        raise ValueError("weights contain non-finite values")
    if (weights < 0).any():
        raise ValueError("weights must be non-negative")
    if target == 0:
        return np.zeros(len(weights), dtype=np.int64)

    total = float(weights.sum())
    if total <= 0:
        raise ValueError("positive target requires positive total weight")

    quota = weights / total * target
    allocation = np.floor(quota + floor_epsilon).astype(np.int64)
    remainder = quota - allocation
    left = target - int(allocation.sum())

    if left < 0:
        raise AssertionError("Hamilton floor exceeded target")
    if left:
        order = np.argsort(-remainder, kind="stable")
        allocation[order[:left]] += 1

    if int(allocation.sum()) != target:
        raise AssertionError("Hamilton allocation failed exact closure")
    if (allocation < 0).any():
        raise AssertionError("Hamilton allocation produced negative values")

    return allocation
