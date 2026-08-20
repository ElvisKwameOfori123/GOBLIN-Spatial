"""Unified historical-baseline interface for GOBLIN-Spatial v1.

The core historical baseline ends at fixed-2020 Standard Output. Agricultural
soil, mapped physical soil and frozen livestock signatures are subsequent
scenario-ready enrichments and must not alter the reconstructed activities.
"""

from .agricultural_soil import add_agricultural_soil, build_agricultural_soil_profile
from .cattle import build_cattle_baseline
from .land_farm_structure import add_land_farm_structure
from .merge import merge_livestock
from .sheep import build_sheep_baseline
from .signatures import build_signatures
from .standard_output import add_standard_output

__all__ = [
    "build_cattle_baseline",
    "build_sheep_baseline",
    "merge_livestock",
    "add_land_farm_structure",
    "add_standard_output",
    "build_agricultural_soil_profile",
    "add_agricultural_soil",
    "build_signatures",
]
