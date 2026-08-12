"""Scenario allocation tools built on the validated GOBLIN-Spatial ED baseline."""

from goblin_spatial.scenario.definition import AllocationRule, ScenarioDefinition
from goblin_spatial.scenario.allocation import allocate_adult_livestock_scenario

__all__ = [
    "AllocationRule",
    "ScenarioDefinition",
    "allocate_adult_livestock_scenario",
]
