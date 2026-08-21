"""Exact dairy/suckler composition within existing ED category footprints."""

from __future__ import annotations

import numpy as np

from goblin_spatial.scenario.allocation import _bounded_integer_allocate


def reconcile_endpoint_composition(
    base_dairy: np.ndarray,
    base_suckler: np.ndarray,
    preferred_retained: np.ndarray,
    *,
    target_dairy: int,
    target_suckler: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Allocate exact adult targets subject to universal ED contraction."""

    d = np.asarray(base_dairy, dtype=np.int64)
    s = np.asarray(base_suckler, dtype=np.int64)
    preferred = np.asarray(preferred_retained, dtype=np.int64)
    adults = d + s
    if target_dairy + target_suckler != int(preferred.sum()):
        raise AssertionError("preferred retained adults do not equal endpoint adult total")

    active = adults > 0
    maximum = np.where(active, np.maximum(adults - 1, 0), 0).astype(np.int64)
    if int(maximum.sum()) < target_dairy + target_suckler:
        raise ValueError("universal ED contraction leaves insufficient adult capacity")

    dairy_only = (d > 0) & (s == 0)
    suckler_only = (d == 0) & (s > 0)
    mixed = (d > 0) & (s > 0)
    dairy_capacity = int(maximum[dairy_only].sum() + maximum[mixed].sum())
    suckler_capacity = int(maximum[suckler_only].sum() + maximum[mixed].sum())
    if target_dairy > dairy_capacity or target_suckler > suckler_capacity:
        raise ValueError("endpoint composition is infeasible within existing category footprints")

    base_share_s = np.divide(
        s.astype(float), adults.astype(float), out=np.zeros(len(adults)), where=adults > 0
    )
    preferred_s = preferred.astype(float) * base_share_s
    single_s_capacity = int(maximum[suckler_only].sum())
    mixed_capacity = int(maximum[mixed].sum())
    dairy_only_capacity = int(maximum[dairy_only].sum())
    max_suckler_in_mixed = min(
        mixed_capacity,
        max(dairy_only_capacity + mixed_capacity - target_dairy, 0),
    )
    min_suckler_single = max(target_suckler - max_suckler_in_mixed, 0)
    max_suckler_single = min(target_suckler, single_s_capacity)
    if min_suckler_single > max_suckler_single:
        raise ValueError("cannot reconcile suckler endpoint with dairy capacity")

    preferred_single = float(preferred_s[suckler_only].sum())
    preferred_total = float(preferred_s[(suckler_only | mixed)].sum())
    desired_single = (
        int(round(target_suckler * preferred_single / preferred_total))
        if preferred_total > 0 else min_suckler_single
    )
    suckler_single_target = min(max(desired_single, min_suckler_single), max_suckler_single)
    suckler_mixed_target = target_suckler - suckler_single_target

    scenario_s = np.zeros(len(adults), dtype=np.int64)
    if suckler_only.any():
        scenario_s[suckler_only] = _bounded_integer_allocate(
            np.maximum(preferred_s[suckler_only], 1e-12), maximum[suckler_only], suckler_single_target
        )
    if mixed.any():
        scenario_s[mixed] = _bounded_integer_allocate(
            np.maximum(preferred_s[mixed], 1e-12), maximum[mixed], suckler_mixed_target
        )

    remaining = maximum - scenario_s
    dairy_eligible = d > 0
    base_share_d = np.divide(
        d.astype(float), adults.astype(float), out=np.zeros(len(adults)), where=adults > 0
    )
    preferred_d = preferred.astype(float) * base_share_d
    scenario_d = np.zeros(len(adults), dtype=np.int64)
    scenario_d[dairy_eligible] = _bounded_integer_allocate(
        np.maximum(preferred_d[dairy_eligible], 1e-12),
        remaining[dairy_eligible],
        target_dairy,
    )

    if int(scenario_d.sum()) != target_dairy or int(scenario_s.sum()) != target_suckler:
        raise AssertionError("adult endpoint composition failed national closure")
    if ((d == 0) & (scenario_d > 0)).any() or ((s == 0) & (scenario_s > 0)).any():
        raise AssertionError("adult endpoint seeded a category into a zero footprint")
    if ((scenario_d + scenario_s)[active] >= adults[active]).any():
        raise AssertionError("an adult-cattle ED did not contract")
    return scenario_d, scenario_s
