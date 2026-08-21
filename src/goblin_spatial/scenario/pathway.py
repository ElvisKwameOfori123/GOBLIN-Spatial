"""Cumulative national-to-ED livestock transition pathways.

This module converts a sequence of national GOBLIN milestone targets into a
spatially consistent ED pathway. It never reallocates a milestone from scratch.
Instead, each milestone removes only the additional animals required from the
previous ED state.

For livestock category k and milestone t::

    incremental national reduction = national state[t-1] - GOBLIN target[t]
    ED state[t] = ED state[t-1] - incremental ED reduction[t]

The selected 2020 or 2025 ED baseline remains immutable. Protection/randomised
scores are evaluated from that selected baseline, so a trajectory uses one
consistent spatial rule rather than redrawing the country at every milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from goblin_spatial.dynamics.baseline import (
    SUPPORTED_SCENARIO_BASE_YEARS,
    select_baseline_year,
)
from goblin_spatial.scenario.allocation import (
    CATEGORY_COLUMNS,
    _bounded_integer_allocate,
    _rule_cut_weights,
)
from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition


TARGET_KEYS = {
    "DAIRY_COW": "dairy_cows",
    "OTHER_COW": "suckler_cows",
    "TOTAL_SHEEP": "sheep",
}


@dataclass(frozen=True)
class NationalMilestone:
    """Absolute national livestock totals for one pathway milestone."""

    year: int
    dairy_cows: int
    suckler_cows: int
    sheep: int

    def __post_init__(self) -> None:
        if int(self.year) <= 0:
            raise ValueError("milestone year must be positive")
        for label, value in (
            ("dairy_cows", self.dairy_cows),
            ("suckler_cows", self.suckler_cows),
            ("sheep", self.sheep),
        ):
            if int(value) < 0:
                raise ValueError(f"{label} cannot be negative")


@dataclass(frozen=True)
class TransitionPathwayDefinition:
    """National GOBLIN pathway plus a spatial allocation rule.

    The milestones contain absolute national totals. Direct GOBLIN milestone
    values should be supplied whenever available. Interpolated milestones are
    permitted only when they are created explicitly, for example with
    :func:`linear_milestones_from_endpoint`.
    """

    name: str
    baseline_year: int
    milestones: tuple[NationalMilestone, ...]
    allocation_rule: AllocationRule = AllocationRule.PRORATA
    random_seed: int = 42
    score_column: str | None = None
    productivity_score_column: str | None = None
    vulnerability_score_column: str | None = None
    protection_strength: float = 0.8
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("pathway name cannot be empty")
        if self.baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
            raise ValueError(
                f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}"
            )
        if not self.milestones:
            raise ValueError("pathway requires at least one milestone")

        years = [int(m.year) for m in self.milestones]
        if years != sorted(years) or len(set(years)) != len(years):
            raise ValueError("milestones must have unique years in ascending order")
        if years[0] <= self.baseline_year:
            raise ValueError("first milestone must follow the baseline year")

        ScenarioDefinition(
            name=f"{self.name}__allocation_template",
            baseline_year=self.baseline_year,
            target_year=years[-1],
            allocation_rule=self.allocation_rule,
            random_seed=self.random_seed,
            score_column=self.score_column,
            productivity_score_column=self.productivity_score_column,
            vulnerability_score_column=self.vulnerability_score_column,
            protection_strength=self.protection_strength,
            hybrid_weights=self.hybrid_weights,
        )


def _rule_template(
    pathway: TransitionPathwayDefinition, target_year: int
) -> ScenarioDefinition:
    return ScenarioDefinition(
        name=f"{pathway.name}__{target_year}",
        baseline_year=pathway.baseline_year,
        target_year=target_year,
        allocation_rule=pathway.allocation_rule,
        random_seed=pathway.random_seed,
        score_column=pathway.score_column,
        productivity_score_column=pathway.productivity_score_column,
        vulnerability_score_column=pathway.vulnerability_score_column,
        protection_strength=pathway.protection_strength,
        hybrid_weights=pathway.hybrid_weights,
    )


def _integer_column(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def build_transition_pathway(
    panel: pd.DataFrame,
    pathway: TransitionPathwayDefinition,
    *,
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Spatialise a cumulative contraction pathway across EDs."""

    baseline = select_baseline_year(
        panel, pathway.baseline_year, expected_eds=expected_eds
    )
    missing = [column for column in CATEGORY_COLUMNS if column not in baseline.columns]
    if missing:
        raise ValueError(f"transition pathway missing required columns: {missing}")

    base_arrays = {
        column: _integer_column(baseline, column) for column in CATEGORY_COLUMNS
    }
    current_arrays = {
        column: values.copy() for column, values in base_arrays.items()
    }
    base_totals = {
        column: int(values.sum()) for column, values in base_arrays.items()
    }

    previous_totals = base_totals.copy()
    for milestone in pathway.milestones:
        for column, target_key in TARGET_KEYS.items():
            target = int(getattr(milestone, target_key))
            if target > previous_totals[column]:
                raise ValueError(
                    f"{pathway.name} {milestone.year} target for {column} "
                    "exceeds the previous national state; contraction pathways "
                    "must be non-increasing"
                )
            previous_totals[column] = target

    rows: list[pd.DataFrame] = []
    for milestone in pathway.milestones:
        out = baseline.copy()
        out.insert(0, "PATHWAY_NAME", pathway.name)
        out.insert(1, "PATHWAY_BASELINE_YEAR", pathway.baseline_year)
        out.insert(2, "MILESTONE_YEAR", int(milestone.year))
        out.insert(3, "PATHWAY_ALLOCATION_RULE", pathway.allocation_rule.value)
        out.insert(4, "PATHWAY_RANDOM_SEED", int(pathway.random_seed))

        rule_template = _rule_template(pathway, int(milestone.year))

        for column, target_key in TARGET_KEYS.items():
            base = base_arrays[column]
            previous = current_arrays[column]
            target_total = int(getattr(milestone, target_key))
            previous_total = int(previous.sum())
            incremental_total = previous_total - target_total

            if incremental_total < 0:
                raise AssertionError(
                    "validated contraction pathway became expansive"
                )

            cut_weights, protection_score = _rule_cut_weights(
                baseline, previous, rule_template
            )
            incremental = _bounded_integer_allocate(
                cut_weights, previous, incremental_total
            )
            scenario_values = previous - incremental
            cumulative = base - scenario_values

            if int(incremental.sum()) != incremental_total:
                raise AssertionError(
                    f"incremental reduction failed for {column}"
                )
            if int(scenario_values.sum()) != target_total:
                raise AssertionError(
                    f"national milestone target failed for {column}"
                )
            if not np.array_equal(previous - incremental, scenario_values):
                raise AssertionError(
                    f"previous-minus-increment identity failed for {column}"
                )
            if not np.array_equal(base - scenario_values, cumulative):
                raise AssertionError(
                    f"cumulative reduction identity failed for {column}"
                )
            if (scenario_values < 0).any() or (scenario_values > previous).any():
                raise AssertionError(
                    f"non-monotonic ED pathway for {column}"
                )
            if ((base == 0) & (scenario_values > 0)).any():
                raise AssertionError(
                    f"pathway seeded {column} into a zero-baseline ED"
                )

            out[f"BASE_{column}"] = base
            out[f"PREVIOUS_{column}"] = previous
            out[f"INCREMENTAL_REDUCTION_{column}"] = incremental
            out[f"CUMULATIVE_REDUCTION_{column}"] = cumulative
            out[f"SCENARIO_{column}"] = scenario_values
            out[f"INCREMENTAL_REDUCTION_PCT_{column}"] = np.where(
                previous > 0, 100.0 * incremental / previous, 0.0
            )
            out[f"CUMULATIVE_REDUCTION_PCT_{column}"] = np.where(
                base > 0, 100.0 * cumulative / base, 0.0
            )
            out[f"CUT_WEIGHT_{column}"] = cut_weights
            if protection_score is not None:
                out[f"PROTECTION_SCORE_{column}"] = protection_score

            current_arrays[column] = scenario_values.astype(np.int64)

        out["BASE_ADULT_COWS"] = (
            out["BASE_DAIRY_COW"] + out["BASE_OTHER_COW"]
        )
        out["PREVIOUS_ADULT_COWS"] = (
            out["PREVIOUS_DAIRY_COW"] + out["PREVIOUS_OTHER_COW"]
        )
        out["INCREMENTAL_REDUCTION_ADULT_COWS"] = (
            out["INCREMENTAL_REDUCTION_DAIRY_COW"]
            + out["INCREMENTAL_REDUCTION_OTHER_COW"]
        )
        out["CUMULATIVE_REDUCTION_ADULT_COWS"] = (
            out["CUMULATIVE_REDUCTION_DAIRY_COW"]
            + out["CUMULATIVE_REDUCTION_OTHER_COW"]
        )
        out["SCENARIO_ADULT_COWS"] = (
            out["SCENARIO_DAIRY_COW"] + out["SCENARIO_OTHER_COW"]
        )
        rows.append(out)

    result = pd.concat(rows, ignore_index=True)
    ordered = result.sort_values(
        ["CSOED", "MILESTONE_YEAR"], kind="stable"
    )
    for column in CATEGORY_COLUMNS:
        diffs = ordered.groupby("CSOED", sort=False)[
            f"SCENARIO_{column}"
        ].diff()
        if (diffs.dropna() > 0).any():
            raise AssertionError(
                f"ED pathway increases {column} between milestones"
            )

    return result


def linear_milestones_from_endpoint(
    baseline_totals: Mapping[str, int],
    *,
    baseline_year: int,
    endpoint: NationalMilestone,
    milestone_years: Sequence[int] = (2030, 2040, 2050),
) -> tuple[NationalMilestone, ...]:
    """Create explicitly linear national milestones from one endpoint."""

    required = {"dairy_cows", "suckler_cows", "sheep"}
    missing = required - set(baseline_totals)
    if missing:
        raise ValueError(f"baseline_totals missing keys: {sorted(missing)}")
    if endpoint.year <= baseline_year:
        raise ValueError("endpoint year must follow baseline year")

    years = tuple(int(year) for year in milestone_years)
    if not years or years != tuple(sorted(set(years))):
        raise ValueError("milestone_years must be unique and ascending")
    if years[0] <= baseline_year or years[-1] != int(endpoint.year):
        raise ValueError(
            "milestone years must follow baseline and end at endpoint year"
        )

    endpoint_values = {
        "dairy_cows": int(endpoint.dairy_cows),
        "suckler_cows": int(endpoint.suckler_cows),
        "sheep": int(endpoint.sheep),
    }
    for key in required:
        if endpoint_values[key] > int(baseline_totals[key]):
            raise ValueError(
                "linear contraction endpoint cannot exceed baseline total"
            )

    output: list[NationalMilestone] = []
    span = int(endpoint.year) - int(baseline_year)
    for year in years:
        share = (year - int(baseline_year)) / span
        values = {
            key: int(
                round(
                    int(baseline_totals[key])
                    + share
                    * (
                        endpoint_values[key]
                        - int(baseline_totals[key])
                    )
                )
            )
            for key in required
        }
        output.append(
            NationalMilestone(
                year=year,
                dairy_cows=values["dairy_cows"],
                suckler_cows=values["suckler_cows"],
                sheep=values["sheep"],
            )
        )

    output[-1] = endpoint
    return tuple(output)
