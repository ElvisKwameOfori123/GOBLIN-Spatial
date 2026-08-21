"""ED livestock dynamics diagnostics for GOBLIN-Spatial.

This package sits between the validated historical baseline and future scenario
allocation. It does not alter the baseline and it does not determine national
livestock targets. Its first job is to describe the biological and spatial
relationships that a later scenario module must preserve.
"""

from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.dynamics.cattle import build_cattle_dynamics
from goblin_spatial.dynamics.sheep import build_sheep_dynamics

__all__ = [
    "select_baseline_year",
    "build_cattle_dynamics",
    "build_sheep_dynamics",
]
