"""Soil support for GOBLIN-Spatial.

The principal production-soil layer is an ED-level aggregation of agricultural
use-range classes to the three soil groups used by GOBLIN grass production.
Holding-linked source records are collapsed to area-weighted ED shares before
they enter the model; individual holdings are not modelling units.

The separate SIS overlay remains available as optional spatial validation and
for later land-opportunity refinement. Neither soil layer changes livestock
allocation.
"""

from .agricultural import (
    FOREST_YIELD_CLASSES,
    SOIL_CLASS_TO_GOBLIN_GROUP,
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

__all__ = [
    "FOREST_YIELD_CLASSES",
    "SOIL_CLASS_TO_GOBLIN_GROUP",
    "SoilOverlayDiagnostics",
    "add_ed_agricultural_soil",
    "build_ed_agricultural_soil_profile",
    "canonical_csoed",
    "overlay_soil_associations",
    "read_ed_agricultural_soil_profile",
    "select_baseline_ed_geometries",
]
