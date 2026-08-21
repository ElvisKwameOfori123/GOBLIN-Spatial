"""Signed national adult-cattle changes from a selected baseline to an endpoint."""

from __future__ import annotations

from goblin_spatial.scenario.goblin_controls import GoblinNationalMilestone


def signed_adult_endpoint_change(
    milestone: GoblinNationalMilestone,
    *,
    baseline_dairy_cows: int,
    baseline_suckler_cows: int,
) -> dict[str, int | float]:
    """Describe category changes and overall adult contraction without assuming signs."""

    bd = int(baseline_dairy_cows)
    bs = int(baseline_suckler_cows)
    if bd < 0 or bs < 0:
        raise ValueError("baseline adult counts must be non-negative")
    td = int(milestone.dairy_cows)
    ts = int(milestone.suckler_cows)
    base_adults = bd + bs
    target_adults = td + ts
    change_dairy = td - bd
    change_suckler = ts - bs
    change_adults = target_adults - base_adults
    return {
        "baseline_dairy_cows": bd,
        "target_dairy_cows": td,
        "change_dairy_cows": change_dairy,
        "baseline_suckler_cows": bs,
        "target_suckler_cows": ts,
        "change_suckler_cows": change_suckler,
        "baseline_adult_cows": base_adults,
        "target_adult_cows": target_adults,
        "change_adult_cows": change_adults,
        "adult_reduction_n": max(0, -change_adults),
        "adult_reduction_fraction": (
            0.0 if base_adults == 0 else max(0, -change_adults) / base_adults
        ),
        "target_dairy_suckler_ratio": (
            float("inf") if ts == 0 and td > 0 else (0.0 if ts == 0 else td / ts)
        ),
    }
