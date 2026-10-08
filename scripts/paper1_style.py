"""Shared style, palette and geometry helpers for the Paper 1 figures.

Colours follow the Okabe-Ito colour-vision-safe palette. Geometry comes only
from the repository's frozen spatial inputs:
    data/inputs/spatial/ED_Boundaries_Frozen.gpkg   (3,409 CSO EDs)
    data/inputs/spatial/WFD_Catchments_Frozen.gpkg  (46 EPA WFD catchments)
Model EDs (2,857) are matched with the release's own selector.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import numpy as np
import pandas as pd
import shapely

H = Path("reporting/report_data/historical")
FIG = Path("reporting/paper1/figures")
TAB = Path("reporting/paper1/tables")
CRS = 2157
YEAR = 2025
MIN_COWS, MIN_FOLLOWERS = 10, 20

# Okabe-Ito
DAIRY = "#0072B2"      # dairy cows, DxD
DXB = "#56B4E9"        # dairy dam x beef sire
SUCKLER = "#E69F00"    # suckler cows, BxB
SHEEP = "#009E73"
BULL = "#999999"
DARK_DAIRY = "#004C7A"
DARK_SUCKLER = "#8C4A00"
GREY_LAND = "#F2F2F2"
NODATA = "#FFFFFF"        # drawn with NODATA_HATCH so it differs from non-model land
NODATA_HATCH = "xxxxx"
TEXT = "#333333"

ORIGINS = ("DxD", "DxB", "BxB")
FOLLOWER_KEYS = [  # (age label, female column, male column)
    ("<1 yr", "{o}_calves_f", "{o}_calves_m"),
    ("1-2 yr", "{o}_heifers_less_2_yr", "{o}_steers_less_2_yr"),
    ("2+ yr", "{o}_heifers_more_2_yr", "{o}_steers_more_2_yr"),
]


def cohorts21() -> list[tuple[str, str, str]]:
    """(label, group, column) for the 21 cattle cohorts in display order."""
    rows = [("Dairy cows", "Adults", "dairy_cows"),
            ("Suckler cows", "Adults", "suckler_cows"),
            ("Bulls", "Adults", "bulls")]
    for o in ORIGINS:
        for age, f, m in FOLLOWER_KEYS:
            rows.append((f"{o} female {age}", o, f.format(o=o)))
            rows.append((f"{o} male {age}", o, m.format(o=o)))
    return rows


def style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 7.5, "axes.titlesize": 8.5, "axes.labelsize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "hatch.linewidth": 0.4, "pdf.fonttype": 42, "svg.fonttype": "none",
    })


def title(ax, letter: str, text: str, **kw) -> None:
    ax.set_title(f"{letter}   {text}", loc="left", fontweight="bold", **kw)


def save(fig, name: str, out: Path | None = None) -> Path:
    path = (out or FIG / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", path.with_suffix(".png"))
    return path


def _simplify(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if hasattr(shapely, "coverage_simplify"):
        out["geometry"] = shapely.coverage_simplify(out.geometry.values, tol)
    else:
        out["geometry"] = out.geometry.simplify(tol, preserve_topology=True)
    out["geometry"] = out.geometry.make_valid()
    return out


@lru_cache(maxsize=1)
def _raw_eds() -> gpd.GeoDataFrame:
    raw = gpd.read_file("data/inputs/spatial/ED_Boundaries_Frozen.gpkg")
    raw["geometry"] = raw.geometry.make_valid()
    return raw


@lru_cache(maxsize=1)
def model_eds(simplify_m: float = 60) -> gpd.GeoDataFrame:
    """2,857 model ED polygons keyed by CSOED (as in the release tables)."""
    from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries
    keys = pd.read_csv(H / "ed_year.csv", usecols=["CSOED"]).drop_duplicates()
    keys["CSOED"] = keys.CSOED.astype(str)
    raw = _raw_eds()
    sel = select_baseline_ed_geometries(keys, raw, baseline_key="CSOED", ed_key="CSOED")
    sel = gpd.GeoDataFrame(sel[["CSOED_CANONICAL", "geometry"]], geometry="geometry",
                           crs=raw.crs).dissolve(by="CSOED_CANONICAL", as_index=False)
    keys["CSOED_CANONICAL"] = keys.CSOED.map(canonical_csoed)
    sel = sel.merge(keys, on="CSOED_CANONICAL", how="inner", validate="one_to_one")
    if len(sel) != 2857:
        raise AssertionError(f"matched {len(sel)} model EDs, expected 2,857")
    return _simplify(sel.to_crs(CRS), simplify_m)


@lru_cache(maxsize=1)
def land_and_counties(simplify_m: float = 60):
    raw = _raw_eds()[["COUNTYNAME", "geometry"]].to_crs(CRS)
    raw = _simplify(raw, simplify_m)
    county = raw.dissolve(by="COUNTYNAME", as_index=False)
    land = gpd.GeoDataFrame(geometry=[raw.geometry.union_all()], crs=CRS)
    return raw, county, land


@lru_cache(maxsize=1)
def wfd(simplify_m: float = 120) -> gpd.GeoDataFrame:
    from goblin_spatial.aggregation.catchments import _normalise_wfd_id
    g = gpd.read_file("data/inputs/spatial/WFD_Catchments_Frozen.gpkg").to_crs(CRS)
    g["ID"] = g.CATCHMENTI.map(_normalise_wfd_id)
    g["geometry"] = g.geometry.make_valid()
    g = g.dissolve(by="ID", as_index=False)
    if len(g) != 46:
        raise AssertionError(f"expected 46 WFD catchments, found {len(g)}")
    g["geometry"] = g.geometry.simplify(simplify_m, preserve_topology=True)
    return g


def ed_signatures(year: int = YEAR) -> pd.DataFrame:
    s = pd.read_csv(H / "livestock_signature.csv")
    s = s[(s.GEOGRAPHY_TYPE == "ED") & (s.YEAR == year)].copy()
    s["CSOED"] = s.GEOGRAPHY_ID.astype(str)
    s["ELIGIBLE"] = (s.ADULT_COWS >= MIN_COWS) & (s.FOLLOWER_TOTAL >= MIN_FOLLOWERS)
    return s


# ---- cattle-system typology (fixed thresholds) --------------------------------
DAIRY_CUTS = (40.0, 60.0)
FOLLOWER_CUT = 1.9
TYPE_ORDER = ["Suckler, lower-follower", "Suckler, higher-follower",
              "Mixed, lower-follower", "Mixed, higher-follower",
              "Dairy, lower-follower", "Dairy, higher-follower"]
TYPE_SHORT = ["S-L", "S-H", "M-L", "M-H", "D-L", "D-H"]
TYPE_COLOURS = {  # orange = suckler, lilac = mixed, blue = dairy; min CVD deltaE >= 14
    # (deutan, protan, tritan simulated with colorspacious, incl. hatched white no-data)
    "Suckler, lower-follower": "#F3C77A",   # light = lower-follower, dark = higher
    "Suckler, higher-follower": "#B35806",
    "Mixed, lower-follower": "#B8A2D4",
    "Mixed, higher-follower": "#8A6BB0",
    "Dairy, lower-follower": "#BFDDF0",
    "Dairy, higher-follower": "#08519C",
}


def cattle_type(df: pd.DataFrame) -> pd.Series:
    b = np.select([df.DAIRY_SHARE_ADULT_PCT < DAIRY_CUTS[0],
                   df.DAIRY_SHARE_ADULT_PCT <= DAIRY_CUTS[1]], ["Suckler", "Mixed"], "Dairy")
    f = np.where(df.FOLLOWER_TO_ADULT_RATIO > FOLLOWER_CUT, "higher-follower", "lower-follower")
    t = pd.Series([f"{x}, {y}" for x, y in zip(b, f)], index=df.index)
    return t.where(df.ELIGIBLE)
