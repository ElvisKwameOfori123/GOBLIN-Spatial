"""Scenario tools built on the validated GOBLIN-Spatial ED baseline."""

from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.allocation import allocate_adult_livestock_scenario
from goblin_spatial.scenario.cohort_response import allocate_cattle_cohort_response

__all__ = [
    "AllocationRule",
    "ScenarioDefinition",
    "allocate_adult_livestock_scenario",
    "allocate_cattle_cohort_response",
]
