"""Electoral Division key and geometry helpers used by historical reporting.

The module name is retained for import compatibility. It contains no soil
modelling and no future-scenario logic.
"""

from __future__ import annotations

import re

import pandas as pd

try:
    import geopandas as gpd  # noqa: F401
except ImportError as exc:  # pragma: no cover
    gpd = None
    _GEO_IMPORT_ERROR = exc
else:
    _GEO_IMPORT_ERROR = None


def _require_geo() -> None:
    if gpd is None:
        raise ImportError(
            "Spatial reporting requires optional geospatial dependencies. "
            "Install with: pip install 'goblin-spatial[geo]'"
        ) from _GEO_IMPORT_ERROR


def canonical_csoed(value: object) -> str:
    """Return a compound-aware canonical CSO Electoral Division key."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
        return ""
    parts = [part.strip() for part in re.split(r"[/;,]", text) if part.strip()]
    normalised: list[str] = []
    for part in parts:
        part = re.sub(r"\.0$", "", part)
        if part[:1].upper() == "E" and part[1:].isdigit():
            part = part[1:]
        if part.isdigit():
            part = part.lstrip("0") or "0"
        normalised.append(part)
    return "/".join(normalised)


def _with_canonical_key(
    frame: pd.DataFrame,
    key_col: str,
    out_col: str = "CSOED_CANONICAL",
) -> pd.DataFrame:
    if key_col not in frame.columns:
        raise ValueError(f"missing ED key column: {key_col}")
    out = frame.copy()
    out[out_col] = out[key_col].map(canonical_csoed)
    if out[out_col].eq("").any():
        raise ValueError(f"{key_col} contains blank ED identifiers")
    return out


def select_baseline_ed_geometries(
    baseline: pd.DataFrame,
    ed_geometries,
    *,
    baseline_key: str = "CSOED",
    ed_key: str = "CSOED",
):
    """Select exactly the historical model ED universe from a geometry layer."""
    _require_geo()
    base = _with_canonical_key(baseline[[baseline_key]].drop_duplicates(), baseline_key)
    if base["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("baseline contains duplicate canonical ED identifiers")
    eds = _with_canonical_key(ed_geometries, ed_key)
    if eds["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("geometry contains duplicate canonical ED identifiers")
    selected = eds.loc[
        eds["CSOED_CANONICAL"].isin(set(base["CSOED_CANONICAL"]))
    ].copy()
    missing = sorted(
        set(base["CSOED_CANONICAL"]) - set(selected["CSOED_CANONICAL"])
    )
    if missing:
        raise ValueError(
            f"geometry is missing {len(missing)} model EDs; examples={missing[:10]}"
        )
    return selected


__all__ = ["canonical_csoed", "select_baseline_ed_geometries"]
