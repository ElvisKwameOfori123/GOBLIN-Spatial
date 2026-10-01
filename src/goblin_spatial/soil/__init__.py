"""Legacy compatibility exports for historical ED geometry helpers.

New code should import from ``goblin_spatial.aggregation.spatial_keys``.
"""

from .overlay import canonical_csoed, select_baseline_ed_geometries

__all__ = ["canonical_csoed", "select_baseline_ed_geometries"]
