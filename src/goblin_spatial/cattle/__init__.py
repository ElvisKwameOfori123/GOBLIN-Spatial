"""Cattle spatialisation and GOBLIN cattle cohort modules."""

from .panel import build_cattle_panel
from .cohorts import add_cattle_cohorts

__all__ = ["build_cattle_panel", "add_cattle_cohorts"]
