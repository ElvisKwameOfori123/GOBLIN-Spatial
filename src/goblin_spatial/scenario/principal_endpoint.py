"""Principal sourced-endpoint transition runner."""

from __future__ import annotations

from collections.abc import Mapping
import pandas as pd

from goblin_spatial.pressure.category_release import (
    allocate_category_resolved_goblin_land_release,
)
from goblin_spatial.pressure.national_release import allocate_national_goblin_land_release
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.endpoint_allocation import allocate_adult_endpoint
from goblin_spatial.scenario.endpoint_state import add_fixed_sheep_context, build_endpoint_cattle_state
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)
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
    cohort_reference_path: str | None = None,
    cohort_reference_year: int = 2020,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """Run one absolute GOBLIN endpoint while preserving ED cohort signatures.

    National livestock biology and spatial livestock geography are deliberately
    separated. Exact 21-cohort controls are used directly when supplied. If
    only adult endpoints are supplied, an optional national GOBLIN/COHORTS
    reference profile converts those adults into national 21-cohort margins.
    The ED baseline then determines where those margins are represented through
    local, county-receiver and national-orphan relationships.

    When the pathway supplies category-resolved dairy/beef/sheep land-release
    controls, they take precedence over the older aggregate release spatialiser.
    Both routes retain the same authoritative national gross land total.
    """

    milestone = controls.milestone(controls.target_year)

    national_cohort_targets = None
    cohort_target_source = "ED_SIGNATURE_IMPLIED"
    if milestone.cattle_cohorts is not None:
        national_cohort_targets = dict(milestone.cattle_cohorts)
        cohort_target_source = "EXPLICIT_GOBLIN_21_COHORTS"
    elif cohort_reference_path is not None:
        reference = load_goblin_cohort_reference(
            cohort_reference_path,
            reference_year=int(cohort_reference_year),
        )
        national_cohort_targets = derive_national_cohort_targets(
            dairy_cows=int(milestone.dairy_cows),
            suckler_cows=int(milestone.suckler_cows),
            reference_counts=reference,
            total_cattle_target=milestone.total_cattle,
        )
        cohort_target_source = f"GOBLIN_COHORT_RELATIONSHIP_{int(cohort_reference_year)}"
    elif milestone.total_cattle is not None:
        raise ValueError(
            "an exact total_cattle endpoint requires either complete 21-cohort "
            "controls or cohort_reference_path so follower cohorts can be reconciled"
        )

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
        national_cohort_targets=national_cohort_targets,
    )
    livestock = add_fixed_sheep_context(livestock)
    livestock["PATHWAY_NAME"] = controls.scenario_id
    livestock["PATHWAY_BASELINE_YEAR"] = int(controls.baseline_year)
    livestock["MILESTONE_YEAR"] = int(controls.target_year)
    livestock["PATHWAY_ALLOCATION_RULE"] = allocation_rule.value
    livestock["NATIONAL_COHORT_TARGET_SOURCE"] = cohort_target_source

    if include_standard_output:
        livestock = add_pathway_standard_output(
            livestock,
            mapping_path=mapping_path,
            coefficient_path=coefficient_path,
        )

    system_releases = controls.livestock_land_release_by_system_by_year()
    releases = controls.livestock_land_release_by_year()
    if system_releases:
        if pasture_dm_t_per_head_by_year is None:
            raise ValueError(
                "category-resolved GOBLIN land release requires pasture-DM profiles"
            )
        if set(system_releases) != {int(controls.target_year)}:
            raise ValueError(
                "principal category-resolved endpoint requires a system release "
                "for the exact target year only"
            )
        livestock = allocate_category_resolved_goblin_land_release(
            livestock,
            system_releases[int(controls.target_year)],
            pasture_dm_t_per_head_by_year,
        )
    elif releases:
        if pasture_dm_t_per_head_by_year is None:
            raise ValueError("authoritative GOBLIN land release requires pasture-DM profiles")
        livestock = allocate_national_goblin_land_release(
            livestock,
            releases,
            pasture_dm_t_per_head_by_year,
        )
    return livestock
