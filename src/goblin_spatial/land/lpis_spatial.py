"""Safe spatial wrapper for the LPIS-to-ED overlay.

GeoPandas spatial joins return the right-hand dataframe index labels.  The
underlying LPIS builder uses those values positionally for vectorised geometry
intersection, so the selected ED geography is reset here before delegation.
"""
from __future__ import annotations

from goblin_spatial.soil.overlay import select_baseline_ed_geometries
from .lpis import build_ed_lpis_profile as _build_ed_lpis_profile


def build_ed_lpis_profile(lpis, ed_gdf, baseline, **kwargs):
    """Build the LPIS ED profile after forcing a contiguous model-ED index."""
    baseline_key_col = kwargs.get("baseline_key_col", "CSOED")
    ed_key_col = kwargs.get("ed_key_col", "CSOED")
    _, selected = select_baseline_ed_geometries(
        baseline.drop_duplicates(subset=[baseline_key_col]),
        ed_gdf,
        baseline_key_col=baseline_key_col,
        ed_key_col=ed_key_col,
    )
    selected = selected.reset_index(drop=True)
    return _build_ed_lpis_profile(lpis, selected, baseline, **kwargs)
