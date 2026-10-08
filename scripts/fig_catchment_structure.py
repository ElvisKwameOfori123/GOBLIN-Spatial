#!/usr/bin/env python
"""Figure: cattle population structure at Water Framework Directive catchment scale, 2025.

a-c  Catchment maps (46 EPA WFD catchments) of dairy share of adult cows,
     followers per adult cow and BxB share of followers. Values are the
     fractional ED-to-catchment aggregates in the release (numerators and
     denominators aggregated first, ratio recomputed).
d    Within-catchment heterogeneity: for each catchment, the weighted ED P10-P90
     range (bar), ED median (white dot) and catchment aggregate (diamond) of
     followers per adult cow, ordered by the aggregate and coloured by
     catchment dairy share.

Inputs:
    data/inputs/spatial/WFD_Catchments_Frozen.gpkg
    data/inputs/spatial/ED_Boundaries_Frozen.gpkg   (land and county outline)
    reporting/report_data/historical/wfd_catchment_year.csv
    reporting/report_data/historical/wfd_signature_spread.csv
Run from the repository root.
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

from goblin_spatial.aggregation.catchments import _normalise_wfd_id

YEAR = 2025
H = Path("reporting/report_data/historical")
MAPS = [
    ("DAIRY_SHARE_ADULT_PCT", "a   Dairy share of adult cows",
     [0, 25, 40, 50, 60, 75, 100], "PuOr", "% of adult cows"),
    ("FOLLOWER_TO_ADULT_RATIO", "b   Followers per adult cow",
     [1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0], "viridis_r", "followers per cow"),
    ("BXB_SHARE_FOLLOWERS_PCT", "c   BxB share of followers",
     [10, 20, 30, 40, 50, 60, 70], "Oranges", "% of followers"),
]


def style():
    mpl.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 7.5, "axes.titlesize": 8.5,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.linewidth": 0.6, "pdf.fonttype": 42})


def load():
    w = pd.read_csv(H / "wfd_catchment_year.csv", dtype={"WFD_CATCHMENT_ID": str})
    w = w[w.YEAR == YEAR].copy()
    w["WFD_CATCHMENT_ID"] = w.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    g = gpd.read_file("data/inputs/spatial/WFD_Catchments_Frozen.gpkg").to_crs(2157)
    g["WFD_CATCHMENT_ID"] = g.CATCHMENTI.map(_normalise_wfd_id)
    g["geometry"] = g.geometry.make_valid()
    g = g.dissolve(by="WFD_CATCHMENT_ID", as_index=False)[["WFD_CATCHMENT_ID", "geometry"]]
    g = g.merge(w, on="WFD_CATCHMENT_ID", how="inner", validate="one_to_one")
    if len(g) != 46:
        raise AssertionError(f"matched {len(g)} catchments, expected 46")
    g["geometry"] = g.geometry.simplify(150, preserve_topology=True)
    ed = gpd.read_file("data/inputs/spatial/ED_Boundaries_Frozen.gpkg").to_crs(2157)
    ed["geometry"] = ed.geometry.make_valid()
    county = ed.dissolve(by="COUNTYNAME", as_index=False)
    county["geometry"] = county.geometry.simplify(150, preserve_topology=True)
    s = pd.read_csv(H / "wfd_signature_spread.csv", dtype={"WFD_CATCHMENT_ID": str})
    s = s[(s.YEAR == YEAR) & (s.SIGNATURE == "FOLLOWER_TO_ADULT_RATIO")].copy()
    s["WFD_CATCHMENT_ID"] = s.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    s = s.merge(w[["WFD_CATCHMENT_ID", "DAIRY_SHARE_ADULT_PCT"]], on="WFD_CATCHMENT_ID")
    return g, county, s


def classed(name, breaks):
    base = mpl.colormaps[name]
    if name == "PuOr":
        cmap = mcolors.ListedColormap([base(p) for p in np.linspace(0.05, 0.95, len(breaks) - 1)])
        return cmap, mcolors.BoundaryNorm(breaks, cmap.N), "neither"
    cmap = mcolors.ListedColormap([base(p) for p in np.linspace(0.15, 1.0, len(breaks) + 1)])
    return cmap, mcolors.BoundaryNorm(breaks, cmap.N, extend="both"), "both"


def cmap_panel(ax, fig, g, county, col, title, breaks, name, label):
    cmap, norm, ext = classed(name, breaks)
    g.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=0.5)
    county.boundary.plot(ax=ax, color="#4A4A4A", linewidth=0.25, alpha=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.set_title(title, loc="left", fontweight="bold")
    cax = ax.inset_axes([0.06, -0.05, 0.88, 0.035])
    cb = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax,
                      orientation="horizontal", extend=ext, ticks=breaks,
                      spacing="uniform")
    cb.ax.set_xticklabels([f"{b:g}" for b in breaks])
    cb.ax.tick_params(labelsize=6.2, length=2, width=0.4)
    cb.outline.set_linewidth(0.4)
    cb.set_label(label, fontsize=6.4, labelpad=1.5)
    if name == "PuOr":
        cb.ax.text(0, 1.5, "suckler-oriented", transform=cb.ax.transAxes, ha="left",
                   va="bottom", fontsize=6.2, color="#B35806")
        cb.ax.text(1, 1.5, "dairy-oriented", transform=cb.ax.transAxes, ha="right",
                   va="bottom", fontsize=6.2, color="#542788")


def range_panel(ax, fig, s):
    s = s.sort_values("CATCHMENT_VALUE").reset_index(drop=True)
    x = np.arange(len(s))
    cmap, norm, _ = classed("PuOr", MAPS[0][2])
    cols = cmap(norm(s.DAIRY_SHARE_ADULT_PCT.to_numpy()))
    ax.vlines(x, s.ED_WEIGHTED_P10, s.ED_WEIGHTED_P90, colors="#4A4A4A", lw=5.2,
              zorder=1)
    ax.vlines(x, s.ED_WEIGHTED_P10, s.ED_WEIGHTED_P90, colors=cols, lw=4.0,
              zorder=2)
    ax.scatter(x, s.ED_WEIGHTED_P50, s=9, c="white", edgecolors="black", lw=0.5,
               zorder=3, label="ED median")
    ax.scatter(x, s.CATCHMENT_VALUE, s=16, marker="D", c="black", zorder=4,
               label="Catchment aggregate")
    ax.set_xticks(x)
    ax.set_xticklabels([t if len(t) <= 24 else t[:23] + "…" for t in s.WFD_CATCHMENT_LABEL],
                       rotation=90, fontsize=5.3)
    ax.set_xlim(-0.7, len(s) - 0.3)
    ax.set_ylabel("Followers per adult cow")
    ax.yaxis.grid(True, color="#E5E5E5", lw=0.5)
    ax.set_axisbelow(True)
    ax.set_title("d   ED spread of followers per adult cow within each catchment, 2025",
                 loc="left", fontweight="bold")
    ax.legend(loc="upper left", frameon=False, fontsize=6.5)
    ax.text(0.01, 0.80, "bar = weighted ED P10–P90\nbar colour = catchment dairy share (scale in a)",
            transform=ax.transAxes, fontsize=6.3, va="top", color="#333333")
    bw = s[s.WFD_CATCHMENT_LABEL.str.contains("Blackwater \\(Munster\\)")]
    if len(bw):
        i = bw.index[0]
        ax.annotate("Blackwater (Munster):\naggregate {:.2f}, EDs {:.2f}–{:.2f}".format(
            bw.CATCHMENT_VALUE.iloc[0], bw.ED_WEIGHTED_P10.iloc[0], bw.ED_WEIGHTED_P90.iloc[0]),
            xy=(i, bw.ED_WEIGHTED_P90.iloc[0]), xytext=(i + 6, bw.ED_WEIGHTED_P90.iloc[0] + 0.95),
            fontsize=6.3, arrowprops=dict(arrowstyle="-", lw=0.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F_catchment_structure_2025"))
    a = ap.parse_args()
    g, county, s = load()
    style()
    fig = plt.figure(figsize=(7.4, 7.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.45, 1], hspace=0.38, wspace=0.05)
    for i, spec in enumerate(MAPS):
        cmap_panel(fig.add_subplot(gs[0, i]), fig, g, county, *spec)
    range_panel(fig.add_subplot(gs[1, :]), fig, s)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.96, bottom=0.17)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(a.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", a.out, len(g), "catchments")


if __name__ == "__main__":
    main()
