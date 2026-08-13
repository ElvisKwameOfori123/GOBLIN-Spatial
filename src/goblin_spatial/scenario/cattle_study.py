"""Study-facing cattle-only scenario helpers.

The principal GOBLIN-Spatial study changes dairy and/or suckler cows only. Sheep
remain fixed at the selected 2020 or 2025 baseline and continue to contribute to
grassland demand as unchanged context.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.sequential import SequentialScenarioDefinition


def make_cattle_scenario(
    *,
    name: str,
    baseline_year: int,
    target_year: int,
    dairy_reduction: float = 0.0,
    suckler_reduction: float = 0.0,
    allocation_rule: AllocationRule = AllocationRule.PRORATA,
    random_seed: int = 42,
    milestone_years: Sequence[int] | None = None,
    milestone_reductions: Mapping[int, Mapping[str, float]] | None = None,
) -> SequentialScenarioDefinition:
    """Return a sequential cattle scenario with sheep fixed at baseline."""

    expanded = None
    if milestone_reductions is not None:
        expanded = {}
        for year, values in milestone_reductions.items():
            missing = {"dairy_reduction", "suckler_reduction"} - set(values)
            if missing:
                raise ValueError(
                    f"cattle milestone {year} reductions missing keys: {sorted(missing)}"
                )
            if "sheep_reduction" in values and float(values["sheep_reduction"]) != 0.0:
                raise ValueError("cattle study scenarios must keep sheep unchanged")
            expanded[int(year)] = {
                "dairy_reduction": float(values["dairy_reduction"]),
                "suckler_reduction": float(values["suckler_reduction"]),
                "sheep_reduction": 0.0,
            }

    return SequentialScenarioDefinition(
        name=name,
        baseline_year=int(baseline_year),
        target_year=int(target_year),
        dairy_reduction=float(dairy_reduction),
        suckler_reduction=float(suckler_reduction),
        sheep_reduction=0.0,
        allocation_rule=allocation_rule,
        random_seed=int(random_seed),
        milestone_years=(
            None if milestone_years is None else tuple(int(y) for y in milestone_years)
        ),
        milestone_reductions=expanded,
    )


def cattle_reduction_suite(
    *,
    reduction: float = 0.30,
    baseline_year: int = 2020,
    target_year: int = 2050,
    random_seed: int = 42,
) -> dict[str, SequentialScenarioDefinition]:
    """Return the principal cattle experiments for the current study.

    The suite contains baseline, dairy-only, suckler-only, combined dairy +
    suckler, and a reproducible randomised spatial-incidence sensitivity for the
    same combined national endpoint. Sheep are unchanged in every case.
    """

    r = float(reduction)
    if not 0.0 <= r <= 1.0:
        raise ValueError("reduction must lie in [0, 1]")
    pct = int(round(100.0 * r))

    return {
        "BASELINE": make_cattle_scenario(
            name="BASELINE",
            baseline_year=baseline_year,
            target_year=target_year,
        ),
        f"DAIRY_{pct}": make_cattle_scenario(
            name=f"DAIRY_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
        ),
        f"SUCKLER_{pct}": make_cattle_scenario(
            name=f"SUCKLER_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            suckler_reduction=r,
        ),
        f"BOTH_{pct}": make_cattle_scenario(
            name=f"BOTH_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
            suckler_reduction=r,
        ),
        f"BOTH_{pct}_RANDOMISED": make_cattle_scenario(
            name=f"BOTH_{pct}_RANDOMISED",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
            suckler_reduction=r,
            allocation_rule=AllocationRule.RANDOMISED,
            random_seed=random_seed,
        ),
    }
