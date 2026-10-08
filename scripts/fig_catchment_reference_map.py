#!/usr/bin/env python
"""Figure: reference map of the 46 EPA Water Framework Directive catchments.

Each catchment is labelled with its WFD ID (callouts on the map) and listed
by name in a key. Fill shows the catchment's breeding orientation in 2025,
classed from the dairy share of adult cows: suckler-oriented (< 40%),
mixed (40-60%) and dairy-oriented (> 60%). The worked-example catchment
(18 Blackwater, Munster) is outlined.

Inputs:
    data/inputs/spatial/WFD_Catchments_Frozen.gpkg
    data/inputs/spatial/ED_Boundaries_Frozen.gpkg   (island outline)
    reporting/report_data/historical/wfd_catchment_year.csv
Run from the repository root.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from goblin_spatial.aggregation.catchments import _normalise_wfd_id

YEAR = 2025
HIGHLIGHT = "18"
CLASSES = [("Suckler-oriented (dairy share < 40%)", "#E08214"),
           ("Mixed (40–60%)", "#E8E3EF"),
           ("Dairy-oriented (> 60%)", "#8073AC")]


def load():
    g = gpd.read_file("data/inputs/spatial/WFD_Catchments_Frozen.gpkg").to_crs(2157)
    g["ID"] = g.CATCHMENTI.map(_normalise_wfd_id)
    g["geometry"] = g.geometry.make_valid()
    g = g.dissolve(by="ID", as_index=False)
    g["geometry"] = g.geometry.simplify(120, preserve_topology=True)
    w = pd.read_csv("reporting/report_data/historical/wfd_catchment_year.csv",
                    dtype={"WFD_CATCHMENT_ID": str})
    w = w[w.YEAR == YEAR].copy()
    w["ID"] = w.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    g = g.merge(w[["ID", "WFD_CATCHMENT", "DAIRY_SHARE_ADULT_PCT"]], on="ID",
                how="inner", validate="one_to_one")
    if len(g) != 46:
        raise AssertionError(f"matched {len(g)} catchments, expected 46")
    ds = g.DAIRY_SHARE_ADULT_PCT
    g["CLASS"] = pd.cut(ds, [-1, 40, 60, 101], labels=[c[0] for c in CLASSES])
    ed = gpd.read_file("data/inputs/spatial/ED_Boundaries_Frozen.gpkg").to_crs(2157)
    land = gpd.GeoSeries([ed.geometry.make_valid().union_all()], crs=2157)
    land = land.simplify(120, preserve_topology=True)
    return g, land


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F_catchment_reference_map"))
    a = ap.parse_args()
    g, land = load()
    mpl.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 7.5, "pdf.fonttype": 42})
    fig = plt.figure(figsize=(7.4, 6.2))
    ax = fig.add_axes([0.0, 0.03, 0.6, 0.94])
    key = fig.add_axes([0.6, 0.03, 0.4, 0.94])
    key.axis("off")

    colours = dict(CLASSES)
    land.plot(ax=ax, color="#F2F2F2", edgecolor="none")
    g.plot(ax=ax, color=g.CLASS.map(colours).astype(str), edgecolor="white",
           linewidth=0.7)
    g[g.ID == HIGHLIGHT].boundary.plot(ax=ax, color="black", linewidth=1.4)
    for _, r in g.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, r.ID, ha="center", va="center", fontsize=5.6,
                fontweight="bold", color="black",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none",
                          alpha=0.8))
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.set_title("a   Water Framework Directive catchments (n = 46)", loc="left",
                 fontweight="bold", fontsize=8.5)
    handles = [Patch(facecolor=c, edgecolor="#9E9E9E", lw=0.4, label=l) for l, c in CLASSES]
    handles.append(Patch(facecolor="none", edgecolor="black", lw=1.4,
                         label="18 Blackwater (worked example)"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=6.4,
              title=f"Breeding orientation, {YEAR}", title_fontsize=6.6,
              alignment="left")

    rows = g.assign(_n=g.ID.str.extract(r"(\d+)")[0].astype(int), _l=g.ID.str.extract(r"\d+([A-Z]?)")[0]).sort_values(["_n", "_l"])
    half = (len(rows) + 1) // 2
    key.set_title("b   Catchment key", loc="left", fontweight="bold", fontsize=8.5)
    for col, chunk in enumerate((rows.iloc[:half], rows.iloc[half:])):
        for i, (_, r) in enumerate(chunk.iterrows()):
            name = r.WFD_CATCHMENT if len(r.WFD_CATCHMENT) <= 21 else r.WFD_CATCHMENT[:20] + "…"
            y = 0.97 - i * (0.94 / half)
            key.add_patch(mpl.patches.Rectangle((col * 0.5, y - 0.011), 0.025, 0.022,
                          transform=key.transAxes, facecolor=colours[r.CLASS],
                          edgecolor="#9E9E9E", lw=0.3))
            key.text(col * 0.5 + 0.035, y, f"{r.ID}", transform=key.transAxes,
                     fontsize=6.0, va="center", fontweight="bold")
            key.text(col * 0.5 + 0.105, y, name, transform=key.transAxes,
                     fontsize=6.0, va="center",
                     fontweight="bold" if r.ID == HIGHLIGHT else "normal")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(a.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", a.out, dict(g.CLASS.value_counts()))


if __name__ == "__main__":
    main()
