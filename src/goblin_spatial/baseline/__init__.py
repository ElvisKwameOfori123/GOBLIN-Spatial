"""Unified historical-baseline interface for GOBLIN-Spatial v1.

This package is a staged compatibility layer around the validated cattle,
sheep, land, farm-structure and Standard Output implementations. Scientific
mathematics remains in the validated modules while their public interfaces are
migrated into the final v1 architecture.
"""

from .cattle import build_cattle_baseline
from .sheep import build_sheep_baseline
from .merge import merge_livestock
from .land_farm_structure import add_land_farm_structure
from .standard_output import add_standard_output

__all__ = [
    "build_cattle_baseline",
    "build_sheep_baseline",
    "merge_livestock",
    "add_land_farm_structure",
    "add_standard_output",
]
