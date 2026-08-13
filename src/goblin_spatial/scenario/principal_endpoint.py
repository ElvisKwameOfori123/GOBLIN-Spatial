"""Principal sourced-endpoint transition runner."""

from __future__ import annotations

from collections.abc import Mapping
import pandas as pd

from goblin_spatial.pressure.national_release import allocate_national_goblin_land_release
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.endpoint_allocation import allocate_adult_endpoint
from goblin_spatial.scenario.endpoint_state import add_fixed_sheep_context, build_endpoint_cattle_state
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from goblin_spatial.standard_output import add_pathway_standard_output


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
    milestone = controls.milestone(controls.target_year)
    if milestone.cattle_cohorts is not None:
        raise ValueError("exact 21-cohort controls require the explicit full-cohort route")

    adult = allocate_adult_endpoint(
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
    livestock = build_endpoint_cattle_state(
        adult,
        total_cattle_target=milestone.total_cattle,
    )
    livestock = add_fixed_sheep_context(livestock)
    livestock["PATHWAY_NAME"] = controls.scenario_id
    livestock["PATHWAY_BASELINE_YEAR"] = int(controls.baseline_year)
    livestock["MILESTONE_YEAR"] = int(controls.target_year)
    livestock["PATHWAY_ALLOCATION_RULE"] = allocation_rule.value

    if include_standard_output:
        livestock = add_pathway_standard_output(
            livestock,
            mapping_path=mapping_path,
            coefficient_path=coefficient_path,
        )

    releases = controls.livestock_land_release_by_year()
    if releases:
        if pasture_dm_t_per_head_by_year is None:
            raise ValueError("authoritative GOBLIN land release requires pasture-DM profiles")
        livestock = allocate_national_goblin_land_release(
            livestock,
            releases,
            pasture_dm_t_per_head_by_year,
        )
    return livestock
