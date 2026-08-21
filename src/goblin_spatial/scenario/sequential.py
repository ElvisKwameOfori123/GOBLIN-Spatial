"""High-level sequential GOBLIN-Spatial transition scenario.

This is the principal orchestration layer for the study. It keeps three stages
separate but runs them as one scenario:

1. **Livestock transition** - user supplies dairy, suckler and sheep endpoint
   reductions; the engine derives national milestone populations and allocates
   only the additional reduction at each milestone across EDs.
2. **Grassland release** - the solved 31-cohort herd is passed to the GOBLIN
   pasture-DM/grassland accounting to obtain required and potentially spared
   grassland.
3. **Alternative land use** - newly spared hectares are screened with ED soil
   opportunity indicators and allocated cumulatively according to user/policy
   land-use shares.

Standard Output is valued after the physical livestock state and reports both
cumulative and incremental production-value exposure at every ED/milestone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import (
    SUPPORTED_SCENARIO_BASE_YEARS,
    select_baseline_year,
)
from goblin_spatial.land.opportunity import (
    LAND_USES,
    LandUseAllocationDefinition,
    add_ed_land_opportunity_scores,
    allocate_spared_land_sequentially,
)
from goblin_spatial.pressure import calculate_spared_grassland
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.livestock_pathway import (
    build_adult_driven_livestock_pathway,
)
from goblin_spatial.scenario.pathway import (
    NationalMilestone,
    TransitionPathwayDefinition,
    build_transition_pathway,
)


REDUCTION_KEYS = ("dairy_reduction", "suckler_reduction", "sheep_reduction")


@dataclass(frozen=True)
class SequentialScenarioDefinition:
    """One endpoint plus its sequential ED transition rule.

    If ``milestone_reductions`` is omitted, reductions are interpolated linearly
    from zero at the baseline to the supplied endpoint. If direct milestone
    reductions are supplied, those values take precedence and must end exactly
    at the endpoint reductions.
    """

    name: str
    baseline_year: int
    target_year: int
    dairy_reduction: float
    suckler_reduction: float
    sheep_reduction: float
    allocation_rule: AllocationRule = AllocationRule.PRORATA
    random_seed: int = 42
    milestone_years: tuple[int, ...] | None = None
    milestone_reductions: Mapping[int, Mapping[str, float]] | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("sequential scenario name cannot be empty")
        if self.baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
            raise ValueError(
                f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}"
            )
        if int(self.target_year) <= int(self.baseline_year):
            raise ValueError("target_year must follow baseline_year")
        for key in REDUCTION_KEYS:
            value = float(getattr(self, key))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{key} must lie in [0, 1]")
        if not isinstance(self.random_seed, int):
            raise ValueError("random_seed must be an integer")


def _default_milestone_years(baseline_year: int, target_year: int) -> tuple[int, ...]:
    """Return decadal milestones after baseline, always ending at target year."""

    first_decade = ((int(baseline_year) // 10) + 1) * 10
    years = [
        year
        for year in range(first_decade, int(target_year), 10)
        if year > int(baseline_year)
    ]
    years.append(int(target_year))
    return tuple(dict.fromkeys(years))


def reduction_schedule(
    definition: SequentialScenarioDefinition,
) -> pd.DataFrame:
    """Return the exact reduction fractions used at each milestone."""

    endpoint = {
        key: float(getattr(definition, key)) for key in REDUCTION_KEYS
    }

    if definition.milestone_reductions is not None:
        years = sorted(int(year) for year in definition.milestone_reductions)
        if not years or years[0] <= definition.baseline_year:
            raise ValueError("milestone reductions must follow the baseline year")
        if years[-1] != definition.target_year:
            raise ValueError("direct milestone reductions must end at target_year")
        rows: list[dict[str, float | int]] = []
        previous = {key: 0.0 for key in REDUCTION_KEYS}
        for year in years:
            supplied = definition.milestone_reductions[year]
            missing = sorted(set(REDUCTION_KEYS) - set(supplied))
            if missing:
                raise ValueError(
                    f"milestone {year} reductions missing keys: {missing}"
                )
            row: dict[str, float | int] = {"MILESTONE_YEAR": year}
            for key in REDUCTION_KEYS:
                value = float(supplied[key])
                if not 0.0 <= value <= 1.0:
                    raise ValueError(
                        f"{year} {key} must lie between zero and one"
                    )
                if value + 1e-12 < previous[key]:
                    raise ValueError(
                        f"{key} reduction cannot fall between milestones"
                    )
                row[key] = value
                previous[key] = value
            rows.append(row)

        for key in REDUCTION_KEYS:
            if abs(float(rows[-1][key]) - endpoint[key]) > 1e-12:
                raise ValueError(
                    f"target-year {key} does not equal the scenario endpoint"
                )
        return pd.DataFrame(rows)

    years = (
        tuple(int(year) for year in definition.milestone_years)
        if definition.milestone_years is not None
        else _default_milestone_years(
            definition.baseline_year, definition.target_year
        )
    )
    if not years or years != tuple(sorted(set(years))):
        raise ValueError("milestone_years must be unique and ascending")
    if years[0] <= definition.baseline_year or years[-1] != definition.target_year:
        raise ValueError(
            "milestone years must follow baseline and end at target_year"
        )

    span = float(definition.target_year - definition.baseline_year)
    rows = []
    for year in years:
        progress = (float(year) - definition.baseline_year) / span
        row = {"MILESTONE_YEAR": int(year)}
        for key in REDUCTION_KEYS:
            row[key] = endpoint[key] * progress
        rows.append(row)
    return pd.DataFrame(rows)


def _national_milestones(
    panel: pd.DataFrame,
    definition: SequentialScenarioDefinition,
    *,
    expected_eds: int | None,
) -> tuple[NationalMilestone, ...]:
    baseline = select_baseline_year(
        panel, definition.baseline_year, expected_eds=expected_eds
    )
    totals = {
        "dairy_reduction": int(
            pd.to_numeric(baseline["DAIRY_COW"], errors="raise").sum()
        ),
        "suckler_reduction": int(
            pd.to_numeric(baseline["OTHER_COW"], errors="raise").sum()
        ),
        "sheep_reduction": int(
            pd.to_numeric(baseline["TOTAL_SHEEP"], errors="raise").sum()
        ),
    }
    schedule = reduction_schedule(definition)
    milestones: list[NationalMilestone] = []
    for _, row in schedule.iterrows():
        milestones.append(
            NationalMilestone(
                year=int(row["MILESTONE_YEAR"]),
                dairy_cows=int(
                    round(
                        totals["dairy_reduction"]
                        * (1.0 - float(row["dairy_reduction"]))
                    )
                ),
                suckler_cows=int(
                    round(
                        totals["suckler_reduction"]
                        * (1.0 - float(row["suckler_reduction"]))
                    )
                ),
                sheep=int(
                    round(
                        totals["sheep_reduction"]
                        * (1.0 - float(row["sheep_reduction"]))
                    )
                ),
            )
        )
    return tuple(milestones)


def _national_summary(ed: pd.DataFrame) -> pd.DataFrame:
    """Collapse the ED pathway to a compact milestone dashboard."""

    sum_columns = [
        column
        for column in (
            "BASE_DAIRY_COW",
            "SCENARIO_DAIRY_COW",
            "CUMULATIVE_REDUCTION_DAIRY_COW",
            "BASE_OTHER_COW",
            "SCENARIO_OTHER_COW",
            "CUMULATIVE_REDUCTION_OTHER_COW",
            "BASE_TOTAL_SHEEP",
            "SCENARIO_TOTAL_SHEEP",
            "CUMULATIVE_REDUCTION_TOTAL_SHEEP",
            "BASE_GOBLIN_31_LIVESTOCK_TOTAL",
            "SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL",
            "CUMULATIVE_REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL",
            "BASE_SO_LIVESTOCK_2020_EUR",
            "SCENARIO_SO_LIVESTOCK_2020_EUR",
            "SO_LIVESTOCK_EXPOSURE_2020_EUR",
            "INCREMENTAL_SO_LIVESTOCK_EXPOSURE_2020_EUR",
            "POTENTIAL_SPARED_GRASSLAND_HA",
            "ADDITIONAL_GRASSLAND_REQUIRED_HA",
            "INCREMENTAL_SPARED_GRASSLAND_HA",
            *(f"INCREMENTAL_{land_use}_HA" for land_use in LAND_USES),
            *(f"CUMULATIVE_{land_use}_HA" for land_use in LAND_USES),
            "INCREMENTAL_RETAINED_GRASSLAND_HA",
            "CUMULATIVE_RETAINED_GRASSLAND_HA",
        )
        if column in ed.columns
    ]
    summary = (
        ed.groupby("MILESTONE_YEAR", as_index=False)[sum_columns]
        .sum()
        .sort_values("MILESTONE_YEAR", kind="stable")
        .reset_index(drop=True)
    )

    first_columns = [
        column
        for column in ed.columns
        if column.startswith("NATIONAL_TARGET_")
        or column.startswith("NATIONAL_UNMET_")
    ]
    if first_columns:
        diagnostics = (
            ed.groupby("MILESTONE_YEAR", as_index=False)[first_columns]
            .first()
        )
        summary = summary.merge(
            diagnostics,
            on="MILESTONE_YEAR",
            how="left",
            validate="one_to_one",
        )

    affected = []
    for year, block in ed.groupby("MILESTONE_YEAR", sort=True):
        row = {"MILESTONE_YEAR": int(year)}
        for label, column in (
            ("DAIRY", "CUMULATIVE_REDUCTION_DAIRY_COW"),
            ("SUCKLER", "CUMULATIVE_REDUCTION_OTHER_COW"),
            ("SHEEP", "CUMULATIVE_REDUCTION_TOTAL_SHEEP"),
        ):
            if column in block.columns:
                row[f"EDS_WITH_{label}_REDUCTION"] = int(
                    (pd.to_numeric(block[column], errors="raise") > 0).sum()
                )
        if "POTENTIAL_SPARED_GRASSLAND_HA" in block.columns:
            row["EDS_WITH_SPARED_GRASSLAND"] = int(
                (
                    pd.to_numeric(
                        block["POTENTIAL_SPARED_GRASSLAND_HA"],
                        errors="raise",
                    )
                    > 1e-9
                ).sum()
            )
        affected.append(row)
    if affected:
        summary = summary.merge(
            pd.DataFrame(affected),
            on="MILESTONE_YEAR",
            how="left",
            validate="one_to_one",
        )
    return summary


@dataclass
class SequentialScenarioResult:
    """ED-detail, national summary and reduction schedule for one scenario."""

    ed: pd.DataFrame
    national: pd.DataFrame
    schedule: pd.DataFrame


def run_sequential_scenario(
    panel: pd.DataFrame,
    definition: SequentialScenarioDefinition,
    *,
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
    pasture_dm_t_per_head_by_year: Mapping[
        int, Mapping[str, float]
    ] | None = None,
    supply_multiplier_by_year: float | Mapping[int, float] = 1.0,
    land_use: LandUseAllocationDefinition | None = None,
) -> SequentialScenarioResult:
    """Run livestock -> SO -> spared grassland -> land-use allocation in order.

    ``pasture_dm_t_per_head_by_year`` is optional because livestock/SO scenarios
    can be inspected before the upstream GOBLIN feed controls are supplied. A
    land-use allocation, however, requires a completed spared-grassland stage.
    """

    milestones = _national_milestones(
        panel, definition, expected_eds=expected_eds
    )
    adult_definition = TransitionPathwayDefinition(
        name=definition.name,
        baseline_year=definition.baseline_year,
        milestones=milestones,
        allocation_rule=definition.allocation_rule,
        random_seed=definition.random_seed,
    )
    adult = build_transition_pathway(
        panel, adult_definition, expected_eds=expected_eds
    )
    ed = build_adult_driven_livestock_pathway(
        adult,
        include_standard_output=include_standard_output,
        mapping_path=mapping_path,
        coefficient_path=coefficient_path,
    )

    if pasture_dm_t_per_head_by_year is not None:
        ed = calculate_spared_grassland(
            ed,
            pasture_dm_t_per_head_by_year,
            supply_multiplier_by_year=supply_multiplier_by_year,
        )

    if land_use is not None:
        if "POTENTIAL_SPARED_GRASSLAND_HA" not in ed.columns:
            raise ValueError(
                "land-use allocation requires the GOBLIN grassland-release stage"
            )
        ed = add_ed_land_opportunity_scores(ed)
        ed = allocate_spared_land_sequentially(ed, land_use)

    return SequentialScenarioResult(
        ed=ed,
        national=_national_summary(ed),
        schedule=reduction_schedule(definition),
    )


def standard_reduction_suite(
    *,
    reduction: float = 0.30,
    baseline_year: int = 2020,
    target_year: int = 2050,
    random_seed: int = 42,
) -> dict[str, SequentialScenarioDefinition]:
    """Return the core experiments discussed for the GOBLIN-Spatial study."""

    r = float(reduction)
    if not 0.0 <= r <= 1.0:
        raise ValueError("reduction must lie in [0, 1]")
    pct = int(round(100 * r))
    return {
        "BASELINE": SequentialScenarioDefinition(
            name="BASELINE",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=0.0,
            suckler_reduction=0.0,
            sheep_reduction=0.0,
        ),
        f"DAIRY_{pct}": SequentialScenarioDefinition(
            name=f"DAIRY_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
            suckler_reduction=0.0,
            sheep_reduction=0.0,
        ),
        f"SUCKLER_{pct}": SequentialScenarioDefinition(
            name=f"SUCKLER_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=0.0,
            suckler_reduction=r,
            sheep_reduction=0.0,
        ),
        f"SHEEP_{pct}": SequentialScenarioDefinition(
            name=f"SHEEP_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=0.0,
            suckler_reduction=0.0,
            sheep_reduction=r,
        ),
        f"ALL_{pct}": SequentialScenarioDefinition(
            name=f"ALL_{pct}",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
            suckler_reduction=r,
            sheep_reduction=r,
        ),
        f"ALL_{pct}_RANDOMISED": SequentialScenarioDefinition(
            name=f"ALL_{pct}_RANDOMISED",
            baseline_year=baseline_year,
            target_year=target_year,
            dairy_reduction=r,
            suckler_reduction=r,
            sheep_reduction=r,
            allocation_rule=AllocationRule.RANDOMISED,
            random_seed=random_seed,
        ),
    }
