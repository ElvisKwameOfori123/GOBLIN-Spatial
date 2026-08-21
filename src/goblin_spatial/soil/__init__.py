"""Soil support for GOBLIN-Spatial.

08B agricultural capability is precomputed once to a compact ED control and is
attached before principal SC1 land-release spatialisation. 08C mapped physical
soil is a separate downstream context layer. Neither source replaces the
validated ``ALL_GRASSLAND`` hectares or changes the livestock allocation.
"""

from .agricultural import (
    FOREST_YIELD_CLASSES,
    SOIL_CLASS_TO_GOBLIN_GROUP,
)
from .context_v2 import (
    add_ed_agricultural_soil,
    build_ed_agricultural_soil_profile,
    read_ed_agricultural_soil_profile,
)
from .overlay import (
    SoilOverlayDiagnostics,
    canonical_csoed,
    overlay_soil_associations,
    select_baseline_ed_geometries,
)
from .principal_context import (
    CLASS_SHARE_COLUMNS,
    GROUP_SHARE_COLUMNS,
    MAP_SG_SHARE_COLUMNS,
    PHYSICAL_AREA_COLUMNS,
    PHYSICAL_SHARE_COLUMNS,
    add_principal_08b_context,
    add_principal_08c_context,
)

__all__ = [
    "CLASS_SHARE_COLUMNS",
    "FOREST_YIELD_CLASSES",
    "GROUP_SHARE_COLUMNS",
    "MAP_SG_SHARE_COLUMNS",
    "PHYSICAL_AREA_COLUMNS",
    "PHYSICAL_SHARE_COLUMNS",
    "SOIL_CLASS_TO_GOBLIN_GROUP",
    "SoilOverlayDiagnostics",
    "add_ed_agricultural_soil",
    "add_principal_08b_context",
    "add_principal_08c_context",
    "build_ed_agricultural_soil_profile",
    "canonical_csoed",
    "overlay_soil_associations",
    "read_ed_agricultural_soil_profile",
    "select_baseline_ed_geometries",
]
