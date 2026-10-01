"""Legacy import shim for historical ED geometry helpers.

New code should import these helpers from ``goblin_spatial.aggregation.spatial_keys``.
This compatibility module contains no soil modelling or scenario logic.
"""

from goblin_spatial.aggregation.spatial_keys import (
    canonical_csoed,
    select_baseline_ed_geometries,
)

__all__ = ["canonical_csoed", "select_baseline_ed_geometries"]
