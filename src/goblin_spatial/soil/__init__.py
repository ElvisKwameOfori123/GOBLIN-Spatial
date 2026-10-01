"""Compatibility exports for historical ED geometry helpers.

The implementation lives in ``goblin_spatial.soil.overlay``; this package-level
module re-exports the two helpers used by the historical baseline and catchment
aggregation code.
"""

from .overlay import canonical_csoed, select_baseline_ed_geometries

__all__ = ["canonical_csoed", "select_baseline_ed_geometries"]
