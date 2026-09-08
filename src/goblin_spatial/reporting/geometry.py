"""Frozen ED geometry access for publication and GIS reporting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.reporting.validation import validate_ed_table


def _geopandas():
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Spatial reporting requires geopandas. Install with: "
            "pip install 'goblin-spatial[reporting]'"
        ) from exc
    return gpd


def load_frozen_ed_geometry(
    path: str | Path,
    *,
    key: str = "CSOED",
    expected_eds: int = 2857,
):
    """Load the single frozen ED geometry authority and validate its key universe."""

    gpd = _geopandas()
    geometry = gpd.read_file(Path(path))
    validate_ed_table(geometry, key=key, expected_eds=expected_eds)
    if geometry.geometry.isna().any():
        raise ValueError("frozen ED geometry contains missing geometries")
    return geometry


def join_ed_results(
    geometry,
    results: pd.DataFrame,
    *,
    key: str = "CSOED",
    expected_eds: int = 2857,
):
    """Join one complete ED result table to frozen geometry with 1:1 closure."""

    validate_ed_table(geometry, key=key, expected_eds=expected_eds)
    validate_ed_table(results, key=key, expected_eds=expected_eds)

    left = geometry.copy()
    right = results.copy()
    left[key] = left[key].astype(str)
    right[key] = right[key].astype(str)

    missing_in_results = sorted(set(left[key]) - set(right[key]))
    missing_in_geometry = sorted(set(right[key]) - set(left[key]))
    if missing_in_results or missing_in_geometry:
        raise ValueError(
            "ED geometry/result universes differ: "
            f"missing_in_results={missing_in_results[:10]}, "
            f"missing_in_geometry={missing_in_geometry[:10]}"
        )

    joined = left.merge(right, on=key, how="left", validate="one_to_one")
    if len(joined) != expected_eds:
        raise AssertionError("ED geometry join changed the frozen ED universe")
    return joined
