"""Principal one-endpoint GOBLIN-to-ED cattle transition.

This route is intentionally narrower than the generic sequential scenario engine.
It is used when the study has an authoritative national endpoint, such as the
2050 SI_SG or BE_SG adult cow totals, but does not yet have sourced intermediate
livestock milestones.

The contract is:

    selected ED baseline
        -> baseline national adults - GOBLIN endpoint
        -> universal-participation ED reduction allocation
        -> adult-driven 21-cattle-cohort response
        -> total-cattle accounting
        -> optional Standard Output
        -> optional authoritative GOBLIN national land-release spatialisation

No 2030/2040 livestock path is invented from a 2050 endpoint.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.pressure.national_release import allocate_national_goblin_land_release
from goblin_spatial.scenario.allocation import allocate_adult_livestock_scenario
from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from goblin_spatial.scenario.livestock_pathway import build_adult_driven_livestock_pathway


_ADULT_COLUMNS = ("DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP")


def _endpoint_definition(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule,
    random_seed: int,
    score_column: str | None,
    productivity_score_column: str | None,
    vulnerability_score_column: str | None,
    protection_strength: float,
    hybrid_weights: tuple[float, float, float, float],
    expected_eds: int | None,
) -> ScenarioDefinition:
    """Convert one absolute adult endpoint into selected-baseline reductions."""

    from goblin_spatial.dynamics.baseline import select_baseline_year

    baseline = select_baseline_year(
        panel,
        controls.baseline_year,
        expected_eds=expected_eds,
    )
    for column in ("DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"):
        if column not in baseline.columns:
            raise ValueError(f"principal endpoint scenario requires {column}")

    dairy = int(pd.to_numeric(baseline["DAIRY_COW"], errors="raise").sum())
    suckler = int(pd.to_numeric(baseline["OTHER_COW"], errors="raise").sum())
    reductions = controls.adult_reductions_from_baseline(
        baseline_dairy_cows=dairy,
        baseline_suckler_cows=suckler,
    )

    return ScenarioDefinition(
        name=controls.scenario_id,
        baseline_year=controls.baseline_year,
        target_year=controls.target_year,
        dairy_reduction=float(reductions["dairy_reduction_fraction"]),
        suckler_reduction=float(reductions["suckler_reduction_fraction"]),
        sheep_reduction=0.0,
        allocation_rule=allocation_rule,
        random_seed=int(random_seed),
        score_column=score_column,
        productivity_score_column=productivity_score_column,
        vulnerability_score_column=vulnerability_score_column,
        protection_strength=float(protection_strength),
        hybrid_weights=hybrid_weights,
    )


def _as_single_milestone_pathway(
    adult_endpoint: pd.DataFrame,
    *,
    controls: GoblinPathwayControls,
) -> pd.DataFrame:
    """Adapt one-step adult allocation to the cumulative pathway column contract."""

    out = adult_endpoint.copy()
    out["PATHWAY_NAME"] = controls.scenario_id
    out["PATHWAY_BASELINE_YEAR"] = int(controls.baseline_year)
    out["MILESTONE_YEAR"] = int(controls.target_year)
    out["PATHWAY_ALLOCATION_RULE"] = out["SCENARIO_ALLOCATION_RULE"]

    for column in _ADULT_COLUMNS:
        base = pd.to_numeric(out[f"BASE_{column}"], errors="raise").astype(np.int64)
        reduction = pd.to_numeric(
            out[f"REDUCTION_{column}"], errors="raise"
        ).astype(np.int64)
        scenario = pd.to_numeric(
            out[f"SCENARIO_{column}"], errors="raise"
        ).astype(np.int64)
        if not np.array_equal(
            base.to_numpy(dtype=np.int64) - reduction.to_numpy(dtype=np.int64),
            scenario.to_numpy(dtype=np.int64),
        ):
            raise AssertionError(f"endpoint identity failed for {column}")

        out[f"PREVIOUS_{column}"] = base
        out[f"INCREMENTAL_REDUCTION_{column}"] = reduction
        out[f"CUMULATIVE_REDUCTION_{column}"] = reduction
        out[f"INCREMENTAL_REDUCTION_PCT_{column}"] = np.divide(
            100.0 * reduction.to_numpy(dtype=float),
            base.to_numpy(dtype=float),
            out=np.zeros(len(out), dtype=float),
            where=base.to_numpy(dtype=float) > 0,
        )
        out[f"CUMULATIVE_REDUCTION_PCT_{column}"] = out[
            f"INCREMENTAL_REDUCTION_PCT_{column}"
        ]

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
    return out


def run_principal_goblin_endpoint(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule = AllocationRule.PRORATA,
    random_seed: int = 42,
    score_column: str | None = None,
    productivity_score_column: str | None = None,
    vulnerability_score_column: str | None = None,
    protection_strength: float = 0.8,
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15),
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """Run one sourced national endpoint through the spatial cattle system.

    All EDs with the relevant adult stock participate in a non-null reduction,
    because the adult allocation uses ``allocate_adult_livestock_scenario``.
    Protection rules alter reduction intensity only. Sheep are fixed context.

    If the same GOBLIN control package also supplies an authoritative national
    livestock-land release, pasture-DM profiles are required and that release is
    spatialised after the complete livestock state has been solved.
    """

    definition = _endpoint_definition(
        panel,
        controls,
        allocation_rule=allocation_rule,
        random_seed=random_seed,
        score_column=score_column,
        productivity_score_column=productivity_score_column,
        vulnerability_score_column=vulnerability_score_column,
        protection_strength=protection_strength,
        hybrid_weights=hybrid_weights,
        expected_eds=expected_eds,
    )
    adult = allocate_adult_livestock_scenario(
        panel,
        definition,
        expected_eds=expected_eds,
    )
    adult_pathway = _as_single_milestone_pathway(adult, controls=controls)

    livestock = build_adult_driven_livestock_pathway(
        adult_pathway,
        include_standard_output=include_standard_output,
        mapping_path=mapping_path,
        coefficient_path=coefficient_path,
        total_cattle_targets_by_year=controls.total_cattle_targets_by_year(),
    )

    milestone = controls.milestone(controls.target_year)
    if milestone.cattle_cohorts is not None:
        raise ValueError(
            "principal adult-driven endpoint runner does not silently replace the "
            "endogenous follower response with exact 21-cohort targets; use the "
            "explicit full-cohort pathway route for that stronger control"
        )

    releases = controls.livestock_land_release_by_year()
    if releases:
        if pasture_dm_t_per_head_by_year is None:
            raise ValueError(
                "authoritative GOBLIN land release requires cohort pasture-DM profiles "
                "to determine the ED spatial weights"
            )
        livestock = allocate_national_goblin_land_release(
            livestock,
            releases,
            pasture_dm_t_per_head_by_year,
        )

    return livestock
