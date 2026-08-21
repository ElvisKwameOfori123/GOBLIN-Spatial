"""Principal SC1 sourced-endpoint transition runner.

This is the supported livestock scenario engine. National GOBLIN controls set
the endpoint and gross released land; GOBLIN-Spatial resolves their geography
without introducing a second scenario generator or pathway-specific release
method.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from goblin_spatial.pressure.national_release import allocate_national_goblin_land_release
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.endpoint_allocation import allocate_adult_endpoint
from goblin_spatial.scenario.endpoint_state import add_fixed_sheep_context, build_endpoint_cattle_state
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls
from goblin_spatial.scenario.metrics import add_sc1_ed_metrics
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)
from goblin_spatial.scenario.principal_allocation import PRINCIPAL_PROTECTION_STRENGTH
from goblin_spatial.standard_output import add_pathway_standard_output


def run_principal_goblin_endpoint(
    panel: pd.DataFrame,
    controls: GoblinPathwayControls,
    *,
    allocation_rule: AllocationRule | str = AllocationRule.PRORATA,
    protection_strength: float = PRINCIPAL_PROTECTION_STRENGTH,
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
    cohort_reference_path: str | None = None,
    cohort_reference_year: int = 2020,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """Run one absolute national endpoint while preserving ED cohort signatures.

    Adult dairy and suckler targets are allocated first. The complete cattle
    state is then reconstructed from the ED dependency/signature structure and
    reconciled to exact national 21-cohort or total-cattle controls when those
    are supplied. Sheep are carried unchanged unless a future explicit sheep
    control is introduced.

    National land release is an authoritative pathway control. When supplied,
    it is spatialised through the solved livestock state, pasture-DM pressure
    and frozen 08B capacity. All pathways use the same spatialisation method.
    Pasture-DM independently calculated spared hectares remain diagnostics and
    do not replace the national land control.
    """

    try:
        rule = allocation_rule if isinstance(allocation_rule, AllocationRule) else AllocationRule(str(allocation_rule))
    except (TypeError, ValueError) as exc:
        supported = tuple(item.value for item in AllocationRule)
        raise ValueError(
            f"{allocation_rule!r} is not a validated principal SC1 policy; "
            f"choose one of {supported}"
        ) from exc

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
        allocation_rule=rule,
        protection_strength=protection_strength,
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
    livestock["PATHWAY_ALLOCATION_RULE"] = rule.value
    livestock["NATIONAL_COHORT_TARGET_SOURCE"] = cohort_target_source

    if include_standard_output:
        livestock = add_pathway_standard_output(
            livestock,
            mapping_path=mapping_path,
            coefficient_path=coefficient_path,
        )

    releases = controls.livestock_land_release_by_year()
    if releases:
        if pasture_dm_t_per_head_by_year is None:
            raise ValueError(
                "authoritative GOBLIN land release requires pasture-DM profiles"
            )
        livestock = allocate_national_goblin_land_release(
            livestock,
            releases,
            pasture_dm_t_per_head_by_year,
        )

    return add_sc1_ed_metrics(livestock)
