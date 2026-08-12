"""Spatial soil support for GOBLIN-Spatial.

The soil package starts from a neutral ED x SIS association overlay.  It does
not infer GOBLIN soil groups or future land uses until separate, documented
crosswalks are supplied.
"""

from .overlay import (
    SoilOverlayDiagnostics,
    canonical_csoed,
    overlay_soil_associations,
    select_baseline_ed_geometries,
)

__all__ = [
    "SoilOverlayDiagnostics",
    "canonical_csoed",
    "overlay_soil_associations",
    "select_baseline_ed_geometries",
]
