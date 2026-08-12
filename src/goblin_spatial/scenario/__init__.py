"""Scenario tools built on the validated GOBLIN-Spatial ED baseline."""

from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.allocation import allocate_adult_livestock_scenario
from goblin_spatial.scenario.cohort_response import allocate_cattle_cohort_response
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
from goblin_spatial.scenario.livestock_pathway import build_full_livestock_pathway

__all__ = [
    "NetZeroScenarioDefinition",
    "build_net_zero_livestock_scenario",
    "run_net_zero_scenario",
    "AllocationRule",
    "ScenarioDefinition",
    "allocate_adult_livestock_scenario",
    "allocate_cattle_cohort_response",
    "NationalMilestone",
    "TransitionPathwayDefinition",
    "build_transition_pathway",
    "linear_milestones_from_endpoint",
    "build_cattle_cohort_pathway",
    "build_sheep_cohort_pathway",
    "build_full_livestock_pathway",
]
