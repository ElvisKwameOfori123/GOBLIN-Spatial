"""Shared style, palette and geometry helpers for the Paper 1 figures.

Colours follow the Okabe-Ito colour-vision-safe palette. Geometry comes only
from the repository's frozen spatial inputs:
    data/inputs/spatial/ED_Boundaries_Frozen.gpkg   (3,409 CSO EDs)
    data/inputs/spatial/WFD_Catchments_Frozen.gpkg  (46 EPA WFD catchments)
Model EDs (2,857) are matched with the release's own selector.
"""
from __future__ import annotations

# -----------------------------------------------------------------------------
# PAPER 1 REPORTING CODE
# This script is a reporting/visualisation layer only. It does not modify the
# GOBLIN-Spatial reconstruction or any frozen model inputs. All quantities are
# read from the release tables and are transformed only for plotting or tabular
# reporting. Comments below distinguish observed/control data from reconstructed
# quantities where that distinction matters for interpretation.
# -----------------------------------------------------------------------------

from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import numpy as np
import pandas as pd
import shapely

# Repository-relative locations. These helpers assume scripts are run from the
# repository root so the reporting layer remains reproducible and path-stable.
H = Path("reporting/report_data/historical")
FIG = Path("reporting/paper1/figures")
TAB = Path("reporting/paper1/tables")
CRS = 2157
YEAR = 2025
MIN_COWS, MIN_FOLLOWERS = 10, 20

# Okabe-Ito-based semantic palette used consistently across all Paper 1 figures.
# Blue = dairy/DxD, light blue = DxB, orange = suckler/BxB, green = sheep.
# Type colours below preserve breeding orientation by hue and follower intensity
# by lightness.
DAIRY = "#0072B2"
DXB = "#56B4E9"
SUCKLER = "#E69F00"
SHEEP = "#009E73"
BULL = "#999999"
DARK_DAIRY = "#004C7A"
DARK_SUCKLER = "#8C4A00"
GREY_LAND = "#F2F2F2"
NODATA = "#FFFFFF"
NODATA_HATCH = "xxxxx"
TEXT = "#333333"

ORIGINS = ("DxD", "DxB", "BxB")
FOLLOWER_KEYS = [
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
    """Apply one publication style to every Paper 1 figure."""
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 7.5, "axes.titlesize": 8.5, "axes.labelsize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "hatch.linewidth": 0.4, "pdf.fonttype": 42, "svg.fonttype": "none",
    })


def title(ax, letter: str, text: str, **kw) -> None:
    """Apply the shared left-aligned panel-title convention."""
    ax.set_title(f"{letter}   {text}", loc="left", fontweight="bold", **kw)


def save(fig, name: str, out: Path | None = None) -> Path:
    """Save matched high-resolution PNG and vector PDF outputs."""
    path = (out or FIG / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", path.with_suffix(".png"))
    return path


def _simplify(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    """Simplify plotting geometry only; model accounting never uses simplified shapes."""
    out = gdf.copy()
    if hasattr(shapely, "coverage_simplify"):
        out["geometry"] = shapely.coverage_simplify(out.geometry.values, tol)
    else:
        out["geometry"] = out.geometry.simplify(tol, preserve_topology=True)
    out["geometry"] = out.geometry.make_valid()
    return out


@lru_cache(maxsize=1)
def _raw_eds() -> gpd.GeoDataFrame:
    """Read and validate the frozen CSO ED boundary file once per run."""
    raw = gpd.read_file("data/inputs/spatial/ED_Boundaries_Frozen.gpkg")
    raw["geometry"] = raw.geometry.make_valid()
    return raw


@lru_cache(maxsize=1)
def model_eds(simplify_m: float = 60) -> gpd.GeoDataFrame:
    """Return the exact 2,857-ED model universe matched by the release selector."""
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
    """Return plotting layers for national land and county boundaries."""
    raw = _raw_eds()[["COUNTYNAME", "geometry"]].to_crs(CRS)
    raw = _simplify(raw, simplify_m)
    county = raw.dissolve(by="COUNTYNAME", as_index=False)
    land = gpd.GeoDataFrame(geometry=[raw.geometry.union_all()], crs=CRS)
    return raw, county, land


@lru_cache(maxsize=1)
def wfd(simplify_m: float = 120) -> gpd.GeoDataFrame:
    """Return the 46 frozen WFD catchment geometries for plotting."""
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
    """Load ED livestock signatures and attach the common biological eligibility flag."""
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
TYPE_COLOURS = {
    "Suckler, lower-follower": "#F3C77A",
    "Suckler, higher-follower": "#B35806",
    "Mixed, lower-follower": "#B8A2D4",
    "Mixed, higher-follower": "#8A6BB0",
    "Dairy, lower-follower": "#BFDDF0",
    "Dairy, higher-follower": "#08519C",
}


def cattle_type(df: pd.DataFrame) -> pd.Series:
    """Apply the fixed two-dimensional cattle-system classification.

    Breeding orientation: suckler <40%, mixed 40-60%, dairy >60% dairy share
    of adult cows. Follower intensity: lower <=1.9, higher >1.9 followers/cow.
    Ineligible EDs are returned as missing rather than forced into a class.
    """
    b = np.select([df.DAIRY_SHARE_ADULT_PCT < DAIRY_CUTS[0],
                   df.DAIRY_SHARE_ADULT_PCT <= DAIRY_CUTS[1]], ["Suckler", "Mixed"], "Dairy")
    f = np.where(df.FOLLOWER_TO_ADULT_RATIO > FOLLOWER_CUT, "higher-follower", "lower-follower")
    t = pd.Series([f"{x}, {y}" for x, y in zip(b, f)], index=df.index)
    return t.where(df.ELIGIBLE)


# ---- compact map helpers ------------------------------------------------------
def fit_ireland(ax, pad: float = 0.01, right: float = 0.0) -> None:
    """Fit Ireland tightly in a map panel while reserving optional legend space."""
    _, _, land = land_and_counties()
    x0, y0, x1, y1 = land.total_bounds
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    ax.set_xlim(x0 - dx, x1 + dx + (x1 - x0) * right)
    ax.set_ylim(y0 - dy, y1 + dy)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_xlabel("")
    ax.set_ylabel("")


def vertical_key(ax, colours, labels, title: str = "", where=(0.86, 0.06, 0.045, 0.42),
                 fontsize: float = 5.6):
    """Draw a narrow stacked colour key beside a compact map."""
    import matplotlib.pyplot as plt
    k = ax.inset_axes(list(where))
    n = len(colours)
    for i, c in enumerate(colours):
        k.add_patch(plt.Rectangle((0, i), 1, 1, facecolor=c, edgecolor="white", lw=0.4))
        k.text(1.25, i + 0.5, labels[i], va="center", ha="left", fontsize=fontsize, color=TEXT)
    k.set_xlim(0, 1); k.set_ylim(0, n)
    k.axis("off")
    if title:
        k.text(0, n + 0.25, title, va="bottom", ha="left", fontsize=fontsize, color="#555555")
    return k


def class_labels(breaks, fmt=lambda v: f"{v:g}"):
    """Convert numeric class breaks into human-readable interval labels."""
    out = [f"< {fmt(breaks[0])}"]
    out += [f"{fmt(a)}–{fmt(b)}" for a, b in zip(breaks[:-1], breaks[1:])]
    out.append(f"≥ {fmt(breaks[-1])}")
    return out
