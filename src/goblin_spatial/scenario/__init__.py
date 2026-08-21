"""Scenario tools built on the validated GOBLIN-Spatial ED baseline."""

from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.allocation import allocate_adult_livestock_scenario
from goblin_spatial.scenario.cohort_response import (
    allocate_cattle_cohort_response,
    build_ed_cohort_dependency_profile,
)
from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
    load_adult_endpoint_controls,
)
from goblin_spatial.scenario.control_table import (
    ScenarioControlSelection,
    active_scenario_ids,
    load_scenario_controls,
    read_scenario_control_table,
)
from goblin_spatial.scenario.metrics import (
    add_sc1_ed_metrics,
    build_sc1_county_summary,
    build_sc1_national_metrics,
    gini,
)
from goblin_spatial.scenario.comparison import (
    add_sc1_comparison_intensity,
    build_sc1_robust_exposure,
    compare_sc1_to_prorata,
    summarise_sc1_redistribution,
)
from goblin_spatial.scenario.styles_pathway_controls import (
    load_styles_split_gas_pathway_controls,
)
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)
from goblin_spatial.scenario.endpoint_change import signed_adult_endpoint_change
from goblin_spatial.scenario.reconciliation import build_goblin_reconciliation
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.scenario.net_zero import (
    NetZeroScenarioDefinition,
    build_net_zero_livestock_scenario,
    run_net_zero_scenario,
)
from goblin_spatial.scenario.pathway import (
    NationalMilestone,
    TransitionPathwayDefinition,
    build_transition_pathway,
    linear_milestones_from_endpoint,
)
from goblin_spatial.scenario.cattle_pathway import build_cattle_cohort_pathway
from goblin_spatial.scenario.sheep_pathway import build_sheep_cohort_pathway
from goblin_spatial.scenario.livestock_pathway import (
    build_adult_driven_livestock_pathway,
    build_full_livestock_pathway,
)
from goblin_spatial.scenario.sequential import (
    SequentialScenarioDefinition,
    SequentialScenarioResult,
    reduction_schedule,
    run_sequential_scenario,
    standard_reduction_suite,
)
from goblin_spatial.scenario.cattle_study import (
    make_cattle_scenario,
    cattle_reduction_suite,
)
from goblin_spatial.scenario.study_workflow import (
    PRE_ADULT_CATTLE_COHORTS,
    CattleStudyRun,
    build_18_cohort_dependency_audit,
    build_scenario_cohort_audit,
    load_pasture_dm_profiles,
    write_cattle_study_outputs,
    run_cattle_study,
    build_and_run_cattle_study,
)

__all__ = [
    "NetZeroScenarioDefinition",
    "build_net_zero_livestock_scenario",
    "run_net_zero_scenario",
    "AllocationRule",
    "ScenarioDefinition",
    "GoblinNationalMilestone",
    "GoblinPathwayControls",
    "load_adult_endpoint_controls",
    "ScenarioControlSelection",
    "active_scenario_ids",
    "load_scenario_controls",
    "read_scenario_control_table",
    "gini",
    "add_sc1_ed_metrics",
    "build_sc1_national_metrics",
    "build_sc1_county_summary",
    "add_sc1_comparison_intensity",
    "compare_sc1_to_prorata",
    "build_sc1_robust_exposure",
    "summarise_sc1_redistribution",
    "load_styles_split_gas_pathway_controls",
    "derive_national_cohort_targets",
    "load_goblin_cohort_reference",
    "signed_adult_endpoint_change",
    "build_goblin_reconciliation",
    "run_principal_goblin_endpoint",
    "allocate_adult_livestock_scenario",
    "allocate_cattle_cohort_response",
    "build_ed_cohort_dependency_profile",
    "NationalMilestone",
    "TransitionPathwayDefinition",
    "build_transition_pathway",
    "linear_milestones_from_endpoint",
    "build_cattle_cohort_pathway",
    "build_sheep_cohort_pathway",
    "build_adult_driven_livestock_pathway",
    "build_full_livestock_pathway",
    "SequentialScenarioDefinition",
    "SequentialScenarioResult",
    "reduction_schedule",
    "run_sequential_scenario",
    "standard_reduction_suite",
    "make_cattle_scenario",
    "cattle_reduction_suite",
    "PRE_ADULT_CATTLE_COHORTS",
    "CattleStudyRun",
    "build_18_cohort_dependency_audit",
    "build_scenario_cohort_audit",
    "load_pasture_dm_profiles",
    "write_cattle_study_outputs",
    "run_cattle_study",
    "build_and_run_cattle_study",
]
