"""Soil support for GOBLIN-Spatial.

The direct Colm mapped-soil evidence is first resolved to the model ED universe
without deriving G1/G2/G3. The current production 08B agricultural capability
remains separate until a replacement capability crosswalk is scientifically
validated. Neither soil source replaces validated ``ALL_GRASSLAND`` hectares or
changes livestock allocation by itself.
"""

from .agricultural import (
    FOREST_YIELD_CLASSES,
    SOIL_CLASS_TO_GOBLIN_GROUP,
)
from .colm_ed import (
    COLM_ED_SOIL_VERSION,
    COLM_PHYSICAL_AREA_COLUMNS,
    COLM_PHYSICAL_SHARE_COLUMNS,
    build_colm_model_ed_soil_profile,
    colm_ed_soil_diagnostics,
    prepare_colm_ed_soil_source,
    read_colm_ed_soil_source,
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
    "COLM_ED_SOIL_VERSION",
    "COLM_PHYSICAL_AREA_COLUMNS",
    "COLM_PHYSICAL_SHARE_COLUMNS",
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
    "build_colm_model_ed_soil_profile",
    "build_ed_agricultural_soil_profile",
    "canonical_csoed",
    "colm_ed_soil_diagnostics",
    "overlay_soil_associations",
    "prepare_colm_ed_soil_source",
    "read_colm_ed_soil_source",
    "read_ed_agricultural_soil_profile",
    "select_baseline_ed_geometries",
]
