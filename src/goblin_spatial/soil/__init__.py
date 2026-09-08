"""Neutral source-level spatial utilities.

Production SC2 reads the frozen physical-soil control through
``goblin_spatial.land.colm_lpis_context``. This package only exposes the shared
Electoral Division key and geometry selection helpers used by optional spatial
preprocessing utilities.
"""

from .overlay import canonical_csoed, select_baseline_ed_geometries

__all__ = ["canonical_csoed", "select_baseline_ed_geometries"]
