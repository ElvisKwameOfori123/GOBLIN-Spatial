#!/usr/bin/env python
"""Single-catchment map of cattle population structure (default: 18 Blackwater, Munster).

Main map: EDs clipped to the WFD catchment boundary, classed by breeding
orientation (dairy share of adult cows, 2025), with the surrounding island in
grey, neighbouring catchment boundaries, an Irish Transverse Mercator
coordinate grid, north arrow, scale bar and an Ireland locator inset.
Lower row: the same clipped EDs for followers per adult cow, DxB share and
BxB share of followers, each with the catchment aggregate value.

Geometry: data/inputs/spatial/WFD_Catchments_Frozen.gpkg and
data/inputs/spatial/ED_Boundaries_Frozen.gpkg (model EDs selected with the
release's own select_baseline_ed_geometries). Values:
reporting/report_data/historical/livestock_signature.csv and wfd_catchment_year.csv.
Run from the repository root:
    python scripts/fig_single_catchment_map.py --catchment 18
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
from matplotlib.patches import FancyArrow, Patch, Rectangle

from goblin_spatial.aggregation.catchments import _normalise_wfd_id
from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries

YEAR = 2025
MIN_COWS, MIN_FOLLOWERS = 10, 20
H = Path("reporting/report_data/historical")
GREY_LAND, SEA = "#A8A8A8", "white"
ORIENT = [  # (label, lower, upper, colour)  PuOr, colour-blind safe
    ("Suckler (< 25% dairy)", -1, 25, "#B35806"),
    ("Suckler-leaning (25–50%)", 25, 50, "#FDB863"),
    ("Dairy-leaning (50–75%)", 50, 75, "#B2ABD2"),
    ("Dairy (≥ 75%)", 75, 101, "#542788"),
]
NODATA = ("< 10 adult cows or < 20 followers", "#E0E0E0")
SMALL = [
    ("FOLLOWER_TO_ADULT_RATIO", "b   Followers per adult cow", [1.0, 1.5, 2.0, 2.5, 3.0], "viridis_r", "{:.2f}"),
    ("DXB_SHARE_FOLLOWERS_PCT", "c   DxB share of followers (%)", [20, 25, 30, 35, 40, 45], "PuBu", "{:.0f}%"),
    ("BXB_SHARE_FOLLOWERS_PCT", "d   BxB share of followers (%)", [10, 20, 30, 40, 50, 60], "Oranges", "{:.0f}%"),
]


def load(cid: str):
    wfd = gpd.read_file("data/inputs/spatial/WFD_Catchments_Frozen.gpkg").to_crs(2157)
    wfd["ID"] = wfd.CATCHMENTI.map(_normalise_wfd_id)
    wfd["geometry"] = wfd.geometry.make_valid()
    wfd = wfd.dissolve(by="ID", as_index=False)
    target = wfd[wfd.ID == cid]
    if target.empty:
        raise SystemExit(f"catchment {cid} not found; IDs: {sorted(wfd.ID)}")
    name = str(target.NAME.iloc[0]).title()

    raw = gpd.read_file("data/inputs/spatial/ED_Boundaries_Frozen.gpkg")
    raw["geometry"] = raw.geometry.make_valid()
    land = gpd.GeoDataFrame(geometry=[raw.to_crs(2157).geometry.union_all()], crs=2157)

    sig = pd.read_csv(H / "livestock_signature.csv")
    sig = sig[(sig.GEOGRAPHY_TYPE == "ED") & (sig.YEAR == YEAR)].copy()
    sig["CSOED_CANONICAL"] = sig.GEOGRAPHY_ID.astype(str).map(canonical_csoed)
    keys = pd.DataFrame({"CSOED": sig.GEOGRAPHY_ID.astype(str).unique()})
    eds = select_baseline_ed_geometries(keys, raw, baseline_key="CSOED", ed_key="CSOED")
    eds = gpd.GeoDataFrame(eds[["CSOED_CANONICAL", "geometry"]], geometry="geometry",
                           crs=raw.crs).dissolve(by="CSOED_CANONICAL", as_index=False)
    eds = eds.merge(sig, on="CSOED_CANONICAL", validate="one_to_one").to_crs(2157)
    eds["ELIGIBLE"] = (eds.ADULT_COWS >= MIN_COWS) & (eds.FOLLOWER_TOTAL >= MIN_FOLLOWERS)
    clip = gpd.clip(eds, target.geometry.iloc[0])
    clip = clip[clip.geometry.area > 1e4]

    w = pd.read_csv(H / "wfd_catchment_year.csv", dtype={"WFD_CATCHMENT_ID": str})
    w = w[w.YEAR == YEAR].copy()
    w["ID"] = w.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    agg = w[w.ID == cid].iloc[0]
    return wfd, target, land, clip, name, agg


def base(ax, land, wfd, target, bounds, grid=True):
    land.plot(ax=ax, color=GREY_LAND, edgecolor="none", zorder=0)
    wfd.boundary.plot(ax=ax, color="white", linewidth=0.5, zorder=1)
    x0, y0, x1, y1 = bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_facecolor(SEA)
    ax.set_aspect("equal")
    if grid:
        step = 20000
        xs = np.arange(np.ceil(x0 / step) * step, x1, step)
        ys = np.arange(np.ceil(y0 / step) * step, y1, step)
        ax.set_xticks(xs)
        ax.set_yticks(ys)
        ax.set_xticklabels([f"{int(v)}" for v in xs], fontsize=5.8)
        ax.set_yticklabels([f"{int(v)}" for v in ys], fontsize=5.8, rotation=90, va="center")
        ax.grid(True, color="black", lw=0.35, alpha=0.6, zorder=5)
        ax.tick_params(length=2, width=0.4, top=True, right=True, labeltop=True,
                       labelright=True)
    else:
        ax.set_xticks([])
        ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for s in ax.spines.values():
        s.set_linewidth(0.6)


def scalebar(ax, km=20):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x1 - (x1 - x0) * 0.04 - km * 1000
    y = y0 + (y1 - y0) * 0.05
    h = (y1 - y0) * 0.012
    for i in range(2):
        ax.add_patch(Rectangle((x + i * km * 500, y), km * 500, h, facecolor="black" if i == 0 else "white",
                               edgecolor="black", lw=0.5, zorder=8))
    for v, xx in ((0, x), (km // 2, x + km * 500), (km, x + km * 1000)):
        ax.text(xx, y + h * 1.6, f"{v}", ha="center", va="bottom", fontsize=6, zorder=8)
    ax.text(x + km * 1000 + 800, y + h / 2, "km", va="center", fontsize=6, zorder=8)


def north(ax, x=0.5, y=0.93):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 0.11), xycoords="axes fraction",
                ha="center", va="center", fontsize=8, fontweight="bold", zorder=9,
                arrowprops=dict(facecolor="black", edgecolor="black", width=3, headwidth=9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catchment", default="18")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    cid = _normalise_wfd_id(a.catchment)
    out = a.out or Path(f"reporting/paper1/figures/F_catchment_{cid}_map")
    wfd, target, land, clip, name, agg = load(cid)

    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 7.5, "axes.titlesize": 8.5, "pdf.fonttype": 42})
    tx0, ty0, tx1, ty1 = target.total_bounds
    pad = max(tx1 - tx0, ty1 - ty0) * 0.12
    bounds = (tx0 - pad, ty0 - pad * 0.9, tx1 + pad, ty1 + pad * 0.9)

    aspect = (bounds[3] - bounds[1]) / (bounds[2] - bounds[0])
    top_h = max(1.3, 2.6 * aspect)
    fig = plt.figure(figsize=(7.4, 3.4 + 2.2 * top_h / 1.3 * 0.75))
    gs = fig.add_gridspec(2, 3, height_ratios=[top_h, 0.85], hspace=0.2, wspace=0.08)
    top = gs[0, :].subgridspec(1, 2, width_ratios=[3.1, 1], wspace=0.05)
    ax = fig.add_subplot(top[0, 0])
    side = fig.add_subplot(top[0, 1])
    side.axis("off")
    base(ax, land, wfd, target, bounds)
    ds = clip.DAIRY_SHARE_ADULT_PCT.where(clip.ELIGIBLE)
    colours = pd.Series(NODATA[1], index=clip.index)
    for lab, lo, hi, c in ORIENT:
        colours[(ds > lo) & (ds <= hi) if lo >= 0 else (ds >= 0) & (ds <= hi)] = c
    clip.plot(ax=ax, color=colours.values, edgecolor="white", linewidth=0.25, zorder=2)
    target.boundary.plot(ax=ax, color="black", linewidth=1.1, zorder=3)
    scalebar(ax)
    ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_title(f"a   {cid} {name}: breeding orientation of EDs, {YEAR}", loc="left",
                 fontweight="bold", pad=16)

    north(side, 0.5, 1.02)
    ins = side.inset_axes([0.08, 0.58, 0.84, 0.32])
    land.plot(ax=ins, color="#D9D9D9", edgecolor="#9E9E9E", linewidth=0.3)
    target.plot(ax=ins, color="#D7301F", edgecolor="none")
    ix0, iy0, ix1, iy1 = land.total_bounds
    ins.add_patch(Rectangle((bounds[0], bounds[1]), bounds[2] - bounds[0], bounds[3] - bounds[1],
                            fill=False, edgecolor="#D7301F", lw=0.7))
    ins.set_xlim(ix0 - 1e4, ix1 + 1e4)
    ins.set_ylim(iy0 - 1e4, iy1 + 1e4)
    ins.set_xticks([]); ins.set_yticks([]); ins.set_aspect("equal")
    ins.set_xlabel(""); ins.set_ylabel("")
    for sp in ins.spines.values():
        sp.set_linewidth(0.5)

    counts = {lab: int(((colours == c)).sum()) for lab, _, _, c in ORIENT}
    handles = [Patch(facecolor=c, edgecolor="#757575", lw=0.4, label=f"{lab} ({counts[lab]})")
               for lab, _, _, c in ORIENT]
    handles.append(Patch(facecolor=NODATA[1], edgecolor="#757575", lw=0.4,
                         label=f"Below threshold ({int((colours == NODATA[1]).sum())})"))
    side.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.56), frameon=False,
                fontsize=6.1, title="Dairy share of adult cows\n(number of EDs)",
                title_fontsize=6.4, alignment="left", handlelength=1.2)
    side.text(0.0, -0.02, f"Catchment aggregate\n{agg.DAIRY_SHARE_ADULT_PCT:.0f}% dairy cows\n"
              f"{agg.FOLLOWER_TO_ADULT_RATIO:.2f} followers per cow\n{int(agg.TOTAL_CATTLE):,} cattle",
              transform=side.transAxes, va="bottom", fontsize=6.2,
              bbox=dict(fc="white", ec="#BDBDBD", lw=0.4, pad=2.5))

    for i, (col, title, breaks, cm, fmt) in enumerate(SMALL):
        axs = fig.add_subplot(gs[1, i])
        base(axs, land, wfd, target, bounds, grid=False)
        basecm = mpl.colormaps[cm]
        cmap = mcolors.ListedColormap([basecm(p) for p in np.linspace(0.15, 1, len(breaks) + 1)])
        norm = mcolors.BoundaryNorm(breaks, cmap.N, extend="both")
        el = clip[clip.ELIGIBLE & clip[col].notna()]
        clip[~clip.index.isin(el.index)].plot(ax=axs, color=NODATA[1], edgecolor="white", lw=0.2, zorder=2)
        el.plot(ax=axs, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=0.2, zorder=2)
        target.boundary.plot(ax=axs, color="black", linewidth=0.8, zorder=3)
        axs.set_title(title, loc="left", fontweight="bold", fontsize=7.6)
        axs.set_xlabel(""); axs.set_ylabel("")
        axs.text(0.02, 0.97, "catchment " + fmt.format(agg[col]), transform=axs.transAxes,
                 va="top", fontsize=6.2, bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.5))
        cax = axs.inset_axes([0.05, -0.09, 0.9, 0.05])
        cb = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax, orientation="horizontal",
                          extend="both", ticks=breaks, spacing="uniform")
        cb.ax.set_xticklabels([f"{b:g}" for b in breaks])
        cb.ax.tick_params(labelsize=6, length=2, width=0.4)
        cb.outline.set_linewidth(0.4)

    fig.text(0.01, 0.005, "EDs clipped to the EPA WFD catchment boundary; values are whole-ED 2025 "
             "GOBLIN-Spatial signatures. Coordinates: Irish Transverse Mercator (EPSG:2157).",
             fontsize=5.8, color="#555555")
    fig.subplots_adjust(left=0.07, right=0.99, top=0.92, bottom=0.08)
    out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None, facecolor="white")
    print("saved", out, "|", len(clip), "ED parts in", cid, name, counts)


if __name__ == "__main__":
    main()
