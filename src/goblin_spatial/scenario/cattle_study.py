"""Study-facing cattle-only scenario helpers.

The principal GOBLIN-Spatial study changes dairy and/or suckler cows only. Sheep
remain fixed at the selected 2020 or 2025 baseline and continue to contribute to
grassland demand as unchanged context.

For externally supplied GOBLIN pathways, adult values are treated as absolute
national endpoints. GOBLIN-Spatial calculates the remaining adjustment as
``selected baseline - endpoint`` and then allocates that reduction across the
existing ED livestock footprint.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
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


def make_cattle_scenario_from_goblin_endpoint(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule = AllocationRule.PRORATA,
    random_seed: int = 42,
    expected_eds: int | None = None,
    milestone_years: Sequence[int] | None = None,
) -> SequentialScenarioDefinition:
    """Translate an absolute GOBLIN adult endpoint into baseline reductions.

    The selected ED baseline remains the spatial stock. The pathway milestone is
    the national destination. This helper calculates the remaining dairy and
    suckler reductions from the selected baseline and constructs the existing
    reduction-allocation scenario. Sheep remain unchanged.
    """

    baseline = select_baseline_year(
        panel,
        controls.baseline_year,
        expected_eds=expected_eds,
    )
    for column in ("DAIRY_COW", "OTHER_COW"):
        if column not in baseline.columns:
            raise ValueError(f"GOBLIN endpoint scenario requires baseline column {column}")

    baseline_dairy = int(pd.to_numeric(baseline["DAIRY_COW"], errors="raise").sum())
    baseline_suckler = int(pd.to_numeric(baseline["OTHER_COW"], errors="raise").sum())
    reductions = controls.adult_reductions_from_baseline(
        baseline_dairy_cows=baseline_dairy,
        baseline_suckler_cows=baseline_suckler,
    )

    return make_cattle_scenario(
        name=controls.scenario_id,
        baseline_year=controls.baseline_year,
        target_year=controls.target_year,
        dairy_reduction=float(reductions["dairy_reduction_fraction"]),
        suckler_reduction=float(reductions["suckler_reduction_fraction"]),
        allocation_rule=allocation_rule,
        random_seed=random_seed,
        milestone_years=milestone_years,
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
