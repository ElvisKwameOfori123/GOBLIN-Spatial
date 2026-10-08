#!/usr/bin/env python
"""Figure 3. Spatial differentiation of cattle population structure across
Electoral Divisions, 2025.

a  Dairy share of adult cows (suckler-oriented <-> dairy-oriented)
b  Followers per adult cow
c  Under-1 share of followers
d  DxD share of followers (dairy dam x dairy sire)
e  DxB share of followers (dairy dam x beef sire)
f  BxB share of followers (beef dam x beef sire)

Geometry: the repository's frozen CSO ED boundaries
(data/inputs/spatial/ED_Boundaries_Frozen.gpkg, 3,409 census EDs). The 2,857
model EDs are selected and merged with the same function the release uses
(goblin_spatial.soil.overlay.select_baseline_ed_geometries); the remaining
census EDs, outside the model universe, are drawn in pale grey so the island
is complete. County outlines are dissolved from the full boundary file.

Data: reporting/report_data/historical/livestock_signature.csv (2025, ED rows).
EDs with < 10 adult cows or < 20 followers are shown in a labelled grey class.

Style follows the AGRISYN curated maps: Irish Transverse Mercator (EPSG:2157),
white ED edges, dark-grey county outlines, classed colour scales with a capped
top class, explicit no-data classes, the exact metric in each title.
Palettes are colour-vision-deficiency safe and vary in lightness.

Run from the repository root after scripts/build_historical_release.py:
    python scripts/fig3_cattle_structure_maps.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.patches import Patch

from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries

YEAR = 2025
MIN_COWS, MIN_FOLLOWERS = 10, 20
CRS = 2157
SIMPLIFY_M = 60

OUTSIDE = "#F2F2F2"     # census EDs outside the 2,857-ED model universe
BELOW = "#C8C8C8"       # model EDs below the eligibility rule
ED_EDGE, ED_LW = "white", 0.05
CTY_EDGE, CTY_LW = "#4A4A4A", 0.4

# column, title, class breaks, colormap, legend label
PANELS = [
    ("DAIRY_SHARE_ADULT_PCT", "a   Dairy share of adult cows",
     [0, 10, 25, 40, 50, 60, 75, 90, 100], "PuOr", "% of adult cows"),
    ("FOLLOWER_TO_ADULT_RATIO", "b   Followers per adult cow",
     [0, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0], "viridis_r", "followers per cow"),
    ("UNDER1_SHARE_FOLLOWERS_PCT", "c   Under-1 share of followers",
     [0, 36, 40, 44, 48, 52, 56], "cividis_r", "% of followers"),
    ("DXD_SHARE_FOLLOWERS_PCT", "d   DxD share of followers",
     [0, 10, 20, 30, 40, 50, 60], "Blues", "% of followers"),
    ("DXB_SHARE_FOLLOWERS_PCT", "e   DxB share of followers",
     [0, 20, 25, 30, 35, 40, 45], "PuBu", "% of followers"),
    ("BXB_SHARE_FOLLOWERS_PCT", "f   BxB share of followers",
     [0, 15, 30, 45, 60, 75], "Oranges", "% of followers"),
]


def simplify(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if hasattr(shapely, "coverage_simplify"):
        out["geometry"] = shapely.coverage_simplify(out.geometry.values, tol)
    else:
        out["geometry"] = out.geometry.simplify(tol, preserve_topology=True)
    out["geometry"] = out.geometry.make_valid()
    return out


def load(root: Path):
    sig = pd.read_csv(root / "reporting/report_data/historical/livestock_signature.csv")
    sig = sig[(sig.GEOGRAPHY_TYPE == "ED") & (sig.YEAR == YEAR)].copy()
    sig["CSOED_CANONICAL"] = sig.GEOGRAPHY_ID.astype(str).map(canonical_csoed)

    raw = gpd.read_file(root / "data/inputs/spatial/ED_Boundaries_Frozen.gpkg")
    raw["geometry"] = raw.geometry.make_valid()

    keys = pd.DataFrame({"CSOED": sig.GEOGRAPHY_ID.astype(str).unique()})
    model = select_baseline_ed_geometries(keys, raw, baseline_key="CSOED", ed_key="CSOED")
    model = gpd.GeoDataFrame(model[["CSOED_CANONICAL", "geometry"]], geometry="geometry",
                             crs=raw.crs).dissolve(by="CSOED_CANONICAL", as_index=False)
    model = model.merge(sig, on="CSOED_CANONICAL", how="inner", validate="one_to_one")
    if len(model) != 2857:
        raise AssertionError(f"matched {len(model)} model ED polygons, expected 2,857")
    model["ELIGIBLE"] = (model.ADULT_COWS >= MIN_COWS) & (model.FOLLOWER_TOTAL >= MIN_FOLLOWERS)

    full = raw[["COUNTYNAME", "geometry"]].to_crs(CRS)
    model = simplify(model.to_crs(CRS), SIMPLIFY_M)
    land = simplify(full, SIMPLIFY_M)
    county = land.dissolve(by="COUNTYNAME", as_index=False)
    return model, land, county


def style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 7.5, "axes.titlesize": 8.5, "pdf.fonttype": 42,
    })


def classed(name: str, breaks: list[float]):
    base = mpl.colormaps[name]
    if name == "PuOr":   # diverging: both ends saturated, light centre at 50%
        cols = [base(p) for p in np.linspace(0.04, 0.96, len(breaks) - 1)]
        cmap = mcolors.ListedColormap(cols)
        return cmap, mcolors.BoundaryNorm(breaks, cmap.N), "neither"
    cols = [base(p) for p in np.linspace(0.15, 1.0, len(breaks))]
    cmap = mcolors.ListedColormap(cols)
    return cmap, mcolors.BoundaryNorm(breaks, cmap.N, extend="max"), "max"


def draw(ax, fig, model, land, county, col, title, breaks, cmap_name, label):
    cmap, norm, extend = classed(cmap_name, breaks)
    land.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    below = model[~model.ELIGIBLE | model[col].isna()]
    shown = model[model.ELIGIBLE & model[col].notna()]
    below.plot(ax=ax, color=BELOW, edgecolor=ED_EDGE, linewidth=ED_LW)
    shown.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor=ED_EDGE,
               linewidth=ED_LW)
    county.boundary.plot(ax=ax, color=CTY_EDGE, linewidth=CTY_LW)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_axis_off()
    ax.set_aspect("equal")

    q = shown[col].quantile([0.1, 0.5, 0.9]).to_numpy()
    fmt = "{:.2f}" if col == "FOLLOWER_TO_ADULT_RATIO" else "{:.0f}%"
    ax.text(0.02, 0.97, "P10 " + fmt.format(q[0]) + "\nmedian " + fmt.format(q[1])
            + "\nP90 " + fmt.format(q[2]), transform=ax.transAxes, fontsize=6.2,
            va="top", ha="left", color="#333333")

    cax = ax.inset_axes([0.06, -0.05, 0.88, 0.032])
    cb = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax,
                      orientation="horizontal", extend=extend, ticks=breaks,
                      spacing="uniform")
    cb.ax.set_xticklabels([f"{b:g}" for b in breaks])
    cb.ax.tick_params(labelsize=6.2, length=2, width=0.4)
    cb.outline.set_linewidth(0.4)
    cb.set_label(label, fontsize=6.4, labelpad=1.5)
    if cmap_name == "PuOr":
        cb.ax.text(0, 1.5, "suckler-oriented", transform=cb.ax.transAxes,
                   ha="left", va="bottom", fontsize=6.2, color="#B35806")
        cb.ax.text(1, 1.5, "dairy-oriented", transform=cb.ax.transAxes,
                   ha="right", va="bottom", fontsize=6.2, color="#542788")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F3_cattle_structure_maps_2025"))
    a = ap.parse_args()

    model, land, county = load(a.root)
    style()
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 7.9))
    for ax, spec in zip(axes.ravel(), PANELS):
        draw(ax, fig, model, land, county, *spec)
    n_below = int((~model.ELIGIBLE).sum())
    fig.legend(handles=[
        Patch(facecolor=BELOW, edgecolor="#9E9E9E", lw=0.4,
              label=f"< {MIN_COWS} adult cows or < {MIN_FOLLOWERS} followers ({n_below} EDs)"),
        Patch(facecolor=OUTSIDE, edgecolor="#9E9E9E", lw=0.4,
              label="Outside model universe (mainly urban EDs)")],
        loc="lower center", ncol=2, frameon=False, fontsize=6.6,
        bbox_to_anchor=(0.5, 0.0), handlelength=1.2)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.965, bottom=0.085,
                        wspace=0.04, hspace=0.3)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(a.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print(f"Saved {a.out.with_suffix('.png')}: {int(model.ELIGIBLE.sum()):,} eligible EDs")


if __name__ == "__main__":
    main()
