#!/usr/bin/env python
"""Supplementary figure. What catchment aggregates show and what they hide (46 catchments).

a  The 46 EPA WFD catchments classed by the catchment aggregate of followers per adult cow, 2025.
b  For each catchment, the aggregate (dot) against the ED-weighted P10-P90 range of the same
   signature across the EDs that intersect it (bar); sorted by aggregate.
c  Blackwater (Munster), catchment 18: EDs clipped to the catchment and coloured by the six
   cattle-system types of Figure 3, with the catchment aggregate and its ED range.

Inputs: reporting/report_data/historical/wfd_signature_spread.csv, wfd_catchment_year.csv,
        livestock_signature.csv; data/inputs/spatial/WFD_Catchments_Frozen.gpkg.
Writes: reporting/paper1/figures/Fig6_catchments.{png,pdf}
        reporting/paper1/tables/S_blackwater_types_2025.csv
"""
from __future__ import annotations

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Rectangle

import paper1_style as S
from goblin_spatial.aggregation.catchments import _normalise_wfd_id

SIG = "FOLLOWER_TO_ADULT_RATIO"
ZOOM = "18"
MARK = {"18": "Blackwater (Munster)", "30": "Corrib"}
BREAKS = [1.5, 1.75, 2.0, 2.25, 2.5]
# viridis, 6 classes (colour-vision safe, light = high so labels stay readable)
CLASSES = ["#440154", "#414487", "#2A788E", "#22A884", "#7AD151", "#FDE725"]


def cls(v):
    return CLASSES[int(np.digitize(v, BREAKS))]


def spread() -> pd.DataFrame:
    s = pd.read_csv(S.H / "wfd_signature_spread.csv", dtype={"WFD_CATCHMENT_ID": str})
    s = s[(s.YEAR == S.YEAR) & (s.SIGNATURE == SIG)].copy()
    s["ID"] = s.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    if len(s) != 46:
        raise ValueError(f"expected 46 catchments, found {len(s)}")
    return s.set_index("ID")


def aggregate(cid: str) -> pd.Series:
    w = pd.read_csv(S.H / "wfd_catchment_year.csv", dtype={"WFD_CATCHMENT_ID": str})
    w = w[w.YEAR == S.YEAR].copy()
    w["ID"] = w.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    return w[w.ID == cid].iloc[0]


def panel_a(ax, w, sp):
    _, county, land = S.land_and_counties()
    g = w.merge(sp[["CATCHMENT_VALUE"]], left_on="ID", right_index=True, validate="one_to_one")
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    g.plot(ax=ax, color=[cls(v) for v in g.CATCHMENT_VALUE], edgecolor="white", lw=0.5)
    for cid in MARK:
        g[g.ID == cid].boundary.plot(ax=ax, color="black", lw=1.1)
    for _, r in g.iterrows():
        p = r.geometry.representative_point()
        dark = np.digitize(r.CATCHMENT_VALUE, BREAKS) <= 2
        ax.text(p.x, p.y, r.ID, fontsize=3.8, ha="center", va="center",
                color="white" if dark else "black")
    ax.set_axis_off(); ax.set_aspect("equal")
    S.title(ax, "a", "Catchment aggregate, followers per cow")
    cax = ax.inset_axes([0.08, -0.02, 0.84, 0.03])
    cax.imshow(np.arange(6)[None, :], cmap=ListedColormap(CLASSES), aspect="auto", extent=(0, 6, 0, 1))
    cax.set_yticks([]); cax.set_xticks(range(1, 6))
    cax.set_xticklabels([f"{b:g}" for b in BREAKS], fontsize=5.8)
    cax.tick_params(length=2, width=0.4, pad=1)
    for s in cax.spines.values():
        s.set_linewidth(0.3)
    cax.set_title(f"Followers per adult cow, {S.YEAR}", fontsize=6, pad=2)


def panel_b(ax, sp):
    d = sp.sort_values("CATCHMENT_VALUE")
    y = np.arange(len(d))
    ax.hlines(y, d.ED_WEIGHTED_P10, d.ED_WEIGHTED_P90, color="#BDBDBD", lw=2.4, zorder=1)
    ax.scatter(d.CATCHMENT_VALUE, y, s=14, c=[cls(v) for v in d.CATCHMENT_VALUE],
               edgecolor="#333333", lw=0.4, zorder=3)
    labels = [f"{i}  {str(n).replace(' (Munster)', '')}" for i, n in zip(d.index, d.WFD_CATCHMENT)]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=4.9)
    for t, cid in zip(ax.get_yticklabels(), d.index):
        if cid in MARK:
            t.set_fontweight("bold")
            t.set_color("black")
        else:
            t.set_color("#555555")
    ax.set_ylim(-0.8, len(d) - 0.2)
    ax.set_xlim(0.6, 4.7)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True, color="#EEEEEE", lw=0.5)
    ax.set_axisbelow(True)
    ax.set_xlabel("Followers per adult cow")
    width = d.ED_WEIGHTED_P90 - d.ED_WEIGHTED_P10
    between = d.CATCHMENT_VALUE.max() - d.CATCHMENT_VALUE.min()
    ax.text(4.65, 1, f"Range of aggregates across\n46 catchments: {between:.2f}\n"
            f"Median ED P10–P90 width\ninside a catchment: {width.median():.2f}",
            ha="right", va="bottom", fontsize=5.8, color="#555555")
    ax.legend(handles=[plt.Line2D([], [], marker="o", color="#333333", mfc="white", ls="none",
                                  ms=3.5, label="Catchment aggregate"),
                       plt.Line2D([], [], color="#BDBDBD", lw=2.4, label="ED P10–P90 (weighted)")],
              loc="lower right", bbox_to_anchor=(1.0, 0.17), frameon=False, fontsize=5.8)
    S.title(ax, "b", "Aggregates hide the ED range")


def panel_c(ax, w, sp, agg):
    target = w[w.ID == ZOOM]
    _, county, land = S.land_and_counties()
    eds = S.model_eds()
    d = S.ed_signatures(S.YEAR)
    d["TYPE"] = S.cattle_type(d)
    g = eds.merge(d[["CSOED", "TYPE"]], on="CSOED", how="left", validate="one_to_one")
    g["ED_AREA"] = g.geometry.area
    clip = gpd.clip(g, target.geometry.iloc[0])
    clip = clip[clip.geometry.area > 1e4]
    # an ED is counted in the catchment when at least half of its area lies inside it
    inside = clip[clip.geometry.area >= 0.5 * clip.ED_AREA]
    tx0, ty0, tx1, ty1 = target.total_bounds
    pad = (tx1 - tx0) * 0.05
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none", zorder=0)
    w.boundary.plot(ax=ax, color="white", lw=0.6, zorder=1)
    OUTSIDE = "#DCDCDC"
    edge = clip[~clip.index.isin(inside.index)]
    edge.plot(ax=ax, color=OUTSIDE, edgecolor="white", lw=0.2, zorder=2)
    for t in S.TYPE_ORDER:
        part = inside[inside.TYPE == t]
        if len(part):
            part.plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.2, zorder=2)
    nd = inside[inside.TYPE.isna()]
    if len(nd):
        nd.plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.2, zorder=2)
    target.boundary.plot(ax=ax, color="black", lw=1.0, zorder=3)
    ax.set_xlim(tx0 - pad, tx1 + pad)
    ax.set_ylim(ty0 - pad, ty1 + pad * 2.6)
    ax.set_axis_off(); ax.set_aspect("equal")
    # scale bar, 20 km
    x0, x1 = ax.get_xlim(); y0, _ = ax.get_ylim()
    xs, ys, h = x1 - 24000, y0 + 2500, 900
    for i in range(2):
        ax.add_patch(Rectangle((xs + i * 10000, ys), 10000, h, facecolor="black" if i == 0 else "white",
                               edgecolor="black", lw=0.4, zorder=6))
    ax.text(xs + 10000, ys + h * 1.8, "0     10     20 km", ha="center", va="bottom", fontsize=5.4, zorder=6)
    # locator
    ins = ax.inset_axes([0.0, 0.70, 0.17, 0.30])
    land.plot(ax=ins, color="#D9D9D9", edgecolor="none")
    target.plot(ax=ins, color="black", edgecolor="none")
    ins.set_axis_off(); ins.set_aspect("equal")
    # counts by type (ED parts, whole-ED type)
    counts = inside.TYPE.value_counts()
    hs = [Patch(facecolor=S.TYPE_COLOURS[t], edgecolor="#8C8C8C", lw=0.3,
                label=f"{s} {t} ({counts.get(t, 0)})") for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)
          if counts.get(t, 0)]
    if len(nd):
        hs.append(Patch(facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.3,
                        label=f"Below threshold ({len(nd)})"))
    hs.append(Patch(facecolor=OUTSIDE, edgecolor="#8C8C8C", lw=0.3,
                    label=f"ED mostly outside the catchment ({len(edge)})"))
    ax.legend(handles=hs, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=len(hs), frameon=False,
              fontsize=5.8, handlelength=1.0, columnspacing=0.8,
              title="Cattle-system type of EDs with ≥ 50% of their area in the catchment (types as in Fig. 3)", title_fontsize=6)
    agg_type = S.cattle_type(pd.DataFrame({"DAIRY_SHARE_ADULT_PCT": [agg.DAIRY_SHARE_ADULT_PCT],
                                           "FOLLOWER_TO_ADULT_RATIO": [agg.FOLLOWER_TO_ADULT_RATIO],
                                           "ELIGIBLE": [True]})).iloc[0]
    r = sp.loc[ZOOM]
    ax.text(0.995, 0.995,
            f"Catchment aggregate\n{agg.DAIRY_SHARE_ADULT_PCT:.0f}% dairy cows, "
            f"{agg.FOLLOWER_TO_ADULT_RATIO:.2f} followers per cow\n"
            f"reads as one type: {S.TYPE_SHORT[S.TYPE_ORDER.index(agg_type)]}\n"
            f"ED P10–P90: {r.ED_WEIGHTED_P10:.2f}–{r.ED_WEIGHTED_P90:.2f} followers per cow\n"
            f"{100 * counts.get('Dairy, lower-follower', 0) / len(inside):.0f}% of {len(inside)} EDs D-L, "
            f"{100 * counts.get('Dairy, higher-follower', 0) / len(inside):.0f}% D-H",
            transform=ax.transAxes, ha="right", va="top", fontsize=5.9, linespacing=1.25,
            bbox=dict(fc="white", ec="#BDBDBD", lw=0.4, pad=2.5), zorder=7)
    S.title(ax, "c", f"{ZOOM} Blackwater (Munster): dairy throughout, follower intensity varies")
    out = inside.TYPE.value_counts().reindex(S.TYPE_ORDER).fillna(0).astype(int).rename("EDs").to_frame()
    out.to_csv(S.TAB / "S_blackwater_types_2025.csv")
    print(out.to_string(), "| aggregate type:", agg_type)


def main():
    S.style()
    sp = spread()
    w = S.wfd()
    agg = aggregate(ZOOM)
    fig = plt.figure(figsize=(7.4, 7.4))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.25, 1], height_ratios=[1.05, 1],
                          wspace=0.42, hspace=0.2)
    panel_a(fig.add_subplot(gs[0, 0]), w, sp)
    panel_b(fig.add_subplot(gs[0, 1]), sp)
    panel_c(fig.add_subplot(gs[1, :]), w, sp, agg)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.965, bottom=0.07)
    fig.text(0.01, 0.005, "EDs clipped to the EPA WFD catchment boundaries (WFD_Catchments_Frozen.gpkg); "
             "ED values are whole-ED 2025 signatures. P10–P90 weighted by followers.",
             fontsize=5.6, color="#555555", va="bottom")
    S.save(fig, "FigS_catchment_ranges")


if __name__ == "__main__":
    main()
