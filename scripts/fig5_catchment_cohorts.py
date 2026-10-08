#!/usr/bin/env python
"""Figure 5 (Section 3.5). Catchment expression and within-catchment heterogeneity.

Map style follows AgriSyn: Ireland (or the catchment) fills the panel, narrow vertical key
beside it, no frames, grids or north arrows.

a  The 46 EPA WFD catchments coloured by the cattle-system type their 2025 aggregate falls into
   (thresholds of Figure 3 applied to catchment totals). The selected catchment is outlined.
b  The selected catchment (default 25C Lower Shannon) at ED resolution: each ED coloured by its
   own type; four contrasting EDs (A-D) marked. EDs count as members when >= 50% of their area
   lies inside the EPA boundary.
c  Complete 21-cohort structure of EDs A-D and of the catchment aggregate.

Writes: reporting/paper1/figures/Fig5_catchment_<ID>.{png,pdf}
        reporting/paper1/tables/S_catchment_<ID>_ed_cohorts_2025.csv
Run from the repository root:
    python scripts/fig5_catchment_cohorts.py              # 25C Lower Shannon
    python scripts/fig5_catchment_cohorts.py --catchment 18
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch, Rectangle

import paper1_style as S
from goblin_spatial.aggregation.catchments import _normalise_wfd_id

OUTSIDE = "#DCDCDC"
INSIDE_SHARE = 0.5        # ED area share inside the catchment to count as a member
PICK_SHARE = 0.8          # stricter share for the four example EDs
PICK_TYPES = ["Suckler, lower-follower", "Suckler, higher-follower",
              "Dairy, lower-follower", "Dairy, higher-follower"]
SMALL = [  # column, title, breaks, colormap, format
    ("FOLLOWER_TO_ADULT_RATIO", "Followers per cow", [1.5, 2.0, 2.5, 3.0, 3.5], "Greys", "{:.2f}"),
    ("UNDER1_SHARE_FOLLOWERS_PCT", "Under-1 share (%)", [38, 41, 44, 47, 50], "Greys", "{:.0f}%"),
    ("DXB_SHARE_FOLLOWERS_PCT", "DxB share (%)", [26, 30, 34, 38, 42], "Blues", "{:.0f}%"),
    ("BXB_SHARE_FOLLOWERS_PCT", "BxB share (%)", [20, 30, 40, 50, 60], "Oranges", "{:.0f}%"),
]
ORIGIN_STYLE = {"DxD": (S.DAIRY, None, "#0072B2"), "DxB": (S.DXB, "////", "#2C7FB8"),
                "BxB": (S.SUCKLER, None, "#B36B00")}
HERD = [("Dairy cows", "dairy_cows", S.DARK_DAIRY, None),
        ("Suckler cows", "suckler_cows", S.DARK_SUCKLER, None),
        ("Bulls", "bulls", S.BULL, None),
        ("DxD followers", "DXD", S.DAIRY, None),
        ("DxB followers", "DXB", S.DXB, "////"),
        ("BxB followers", "BXB", S.SUCKLER, None)]


# ---------------------------------------------------------------- data
def follower_cols():
    out = []
    for o in S.ORIGINS:
        for age, f, m in S.FOLLOWER_KEYS:
            out.append((o, age, f.format(o=o), m.format(o=o)))
    return out


def add_origin_totals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for o in S.ORIGINS:
        df[o.upper()] = sum(df[c] for oo, _, f, m in follower_cols() if oo == o for c in (f, m))
    return df


def load(cid: str):
    w = S.wfd()
    target = w[w.ID == cid]
    if target.empty:
        raise SystemExit(f"catchment {cid} not found; IDs: {sorted(w.ID)}")
    name = str(target.NAME.iloc[0]).title()
    eds = S.model_eds()
    d = S.ed_signatures(S.YEAR)
    d["TYPE"] = S.cattle_type(d)
    g = eds.merge(d, on="CSOED", how="left", validate="one_to_one")
    g["ED_AREA"] = g.geometry.area
    clip = gpd.clip(g, target.geometry.iloc[0])
    clip = clip[clip.geometry.area > 1e4].copy()
    clip["SHARE_IN"] = clip.geometry.area / clip.ED_AREA
    inside = clip[clip.SHARE_IN >= INSIDE_SHARE].copy()
    edge = clip[clip.SHARE_IN < INSIDE_SHARE].copy()
    wy = pd.read_csv(S.H / "wfd_catchment_year.csv", dtype={"WFD_CATCHMENT_ID": str})
    wy = wy[wy.YEAR == S.YEAR].copy()
    wy["ID"] = wy.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    agg = add_origin_totals(wy[wy.ID == cid]).iloc[0]
    return w, target, name, add_origin_totals(inside), edge, agg


def pick_examples(inside: pd.DataFrame) -> pd.DataFrame:
    """One representative ED per type: closest to the type's within-catchment median."""
    keys = ["DAIRY_SHARE_ADULT_PCT", "FOLLOWER_TO_ADULT_RATIO", "UNDER1_SHARE_FOLLOWERS_PCT",
            "BXB_SHARE_FOLLOWERS_PCT"]
    e = inside[inside.ELIGIBLE & (inside.SHARE_IN >= PICK_SHARE)]
    sd = e[keys].std()
    rows = []
    for t in PICK_TYPES:
        c = e[e.TYPE == t]
        big = c[c.TOTAL_CATTLE >= e.TOTAL_CATTLE.median()]
        c = big if len(big) else c
        if c.empty:
            continue
        dist = ((c[keys] - c[keys].median()) / sd).abs().sum(axis=1)
        rows.append(c.loc[dist.idxmin()])
    out = pd.DataFrame(rows)
    out["LETTER"] = list("ABCD")[: len(out)]
    return out


def agg_type(agg: pd.Series) -> str:
    one = pd.DataFrame({"DAIRY_SHARE_ADULT_PCT": [agg.DAIRY_SHARE_ADULT_PCT],
                        "FOLLOWER_TO_ADULT_RATIO": [agg.FOLLOWER_TO_ADULT_RATIO], "ELIGIBLE": [True]})
    return S.cattle_type(one).iloc[0]


# ---------------------------------------------------------------- map helpers
def base(ax, land, w, bounds, grid=True):
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none", zorder=0)
    w.boundary.plot(ax=ax, color="white", linewidth=0.6, zorder=1)
    x0, y0, x1, y1 = bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    if grid:
        step = 20000
        xs = np.arange(np.ceil(x0 / step) * step, x1, step)
        ys = np.arange(np.ceil(y0 / step) * step, y1, step)
        ax.set_xticks(xs)
        ax.set_yticks(ys)
        ax.set_xticklabels([f"{int(v)}" for v in xs], fontsize=5.6)
        ax.set_yticklabels([f"{int(v)}" for v in ys], fontsize=5.6, rotation=90, va="center")
        ax.grid(True, color="black", lw=0.3, alpha=0.5, zorder=5)
        ax.tick_params(length=2, width=0.4, top=True, right=True, labeltop=True, labelright=True)
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_linewidth(0.6)
    else:
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    ax.set_xlabel("")
    ax.set_ylabel("")


def scalebar(ax, km=10):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x1 - (x1 - x0) * 0.05 - km * 1000
    y = y0 + (y1 - y0) * 0.04
    h = (y1 - y0) * 0.012
    for i in range(2):
        ax.add_patch(Rectangle((x + i * km * 500, y), km * 500, h, facecolor="black" if i == 0 else "white",
                               edgecolor="black", lw=0.5, zorder=8))
    for v, xx in ((0, x), (km // 2, x + km * 500), (km, x + km * 1000)):
        ax.text(xx, y + h * 1.6, f"{v}", ha="center", va="bottom", fontsize=5.8, zorder=8)
    ax.text(x + km * 1000 + 700, y + h / 2, "km", va="center", fontsize=5.8, zorder=8)


def north(ax, x, y):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 0.12), xycoords="axes fraction",
                ha="center", va="center", fontsize=8, fontweight="bold", zorder=9,
                arrowprops=dict(facecolor="black", edgecolor="black", width=3, headwidth=9))


# ---------------------------------------------------------------- panels
def panel_main(ax, side, land, w, target, name, cid, inside, edge, picks, agg, bounds):
    base(ax, land, w, bounds, grid=False)
    edge.plot(ax=ax, color=OUTSIDE, edgecolor="white", lw=0.25, zorder=2)
    for t in S.TYPE_ORDER:
        part = inside[inside.TYPE == t]
        if len(part):
            part.plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.25, zorder=2)
    nd = inside[inside.TYPE.isna()]
    if len(nd):
        nd.plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.2, zorder=2)
    target.boundary.plot(ax=ax, color="black", lw=1.1, zorder=3)
    for _, r in picks.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, r.LETTER, ha="center", va="center", fontsize=6.6, fontweight="bold",
                zorder=9, bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec="black", lw=0.6))
    scalebar(ax)
    ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_title(f"a   {cid} {name}: cattle-system type of each ED, {S.YEAR}", loc="left",
                 fontweight="bold", pad=14)

    side.axis("off")
    ins = side.inset_axes([0.0, 0.70, 0.62, 0.32])
    land.plot(ax=ins, color="#D9D9D9", edgecolor="none")
    target.plot(ax=ins, color="black", edgecolor="none")
    ins.add_patch(Rectangle((bounds[0], bounds[1]), bounds[2] - bounds[0], bounds[3] - bounds[1],
                            fill=False, edgecolor="black", lw=0.5))
    ins.set_xticks([]); ins.set_yticks([]); ins.set_aspect("equal")
    ins.set_xlabel(""); ins.set_ylabel("")
    for sp in ins.spines.values():
        sp.set_visible(False)
    counts = inside.TYPE.value_counts()
    hs = [Patch(facecolor=S.TYPE_COLOURS[t], edgecolor="#8C8C8C", lw=0.3,
                label=f"{s}  {t} ({counts.get(t, 0)})") for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)]
    if len(nd):
        hs.append(Patch(facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.3,
                        label=f"Below threshold ({len(nd)})"))
    hs.append(Patch(facecolor=OUTSIDE, edgecolor="#8C8C8C", lw=0.3,
                    label=f"ED mostly outside ({len(edge)})"))
    side.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.0, 0.66), frameon=False,
                fontsize=5.8, handlelength=1.1, title="Type as in Fig. 3a (number of EDs)",
                title_fontsize=6.0, alignment="left")
    at = agg_type(agg)
    side.text(0.0, 0.0,
              f"Catchment aggregate\n{int(agg.TOTAL_CATTLE):,} cattle in {len(inside)} EDs\n"
              f"{agg.DAIRY_SHARE_ADULT_PCT:.0f}% dairy cows, {agg.FOLLOWER_TO_ADULT_RATIO:.2f} followers/cow\n"
              f"reads as one type: {S.TYPE_SHORT[S.TYPE_ORDER.index(at)]}\n"
              f"EDs span {counts.size} types; dairy share\n"
              f"P10–P90 {inside.DAIRY_SHARE_ADULT_PCT.quantile(0.1):.0f}–"
              f"{inside.DAIRY_SHARE_ADULT_PCT.quantile(0.9):.0f}%",
              transform=side.transAxes, va="bottom", fontsize=5.9, linespacing=1.25,
              bbox=dict(fc="white", ec="#BDBDBD", lw=0.4, pad=2.5))


def panel_small(fig, ax, land, w, target, inside, edge, agg, bounds, col, title, breaks, cm, fmt, letter):
    base(ax, land, w, bounds, grid=False)
    basecm = mpl.colormaps[cm]
    cmap = mcolors.ListedColormap([basecm(p) for p in np.linspace(0.18, 0.95, len(breaks) + 1)])
    norm = mcolors.BoundaryNorm(breaks, cmap.N, extend="both")
    edge.plot(ax=ax, color=OUTSIDE, edgecolor="white", lw=0.15, zorder=2)
    el = inside[inside.ELIGIBLE.fillna(False).astype(bool) & inside[col].notna()]
    rest = inside[~inside.index.isin(el.index)]
    if len(rest):
        rest.plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.15, zorder=2)
    el.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=0.15, zorder=2)
    target.boundary.plot(ax=ax, color="black", linewidth=0.7, zorder=3)
    ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_title(f"{letter}   {title}", loc="left", fontweight="bold", fontsize=6.8)
    ax.text(0.03, 0.97, "catchment " + fmt.format(agg[col]), transform=ax.transAxes, va="top",
            fontsize=5.8, zorder=9, bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.2))
    cax = ax.inset_axes([0.06, -0.10, 0.88, 0.05])
    cb = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax, orientation="horizontal",
                      extend="both", ticks=breaks, spacing="uniform")
    cb.ax.set_xticklabels([f"{b:g}" for b in breaks])
    cb.ax.tick_params(labelsize=5.6, length=2, width=0.4, pad=1)
    cb.outline.set_linewidth(0.4)


def cohort_column(fig, spec, row, head, sub, xmax, first):
    g = spec.subgridspec(2, 1, height_ratios=[0.13, 1], hspace=0.12)
    axb = fig.add_subplot(g[0])
    axp = fig.add_subplot(g[1])
    # whole-herd bar: three adult cohorts and followers by origin, % of all cattle
    left = 0.0
    tot = float(sum(row[c] for _, c, _, _ in HERD))
    plt.rcParams["hatch.color"] = "#1F4E79"
    for _, c, colr, h in HERD:
        v = 100 * row[c] / tot
        axb.barh(0, v, left=left, color=colr, hatch=h, edgecolor="white", lw=0.4, height=1)
        left += v
    axb.set_xlim(0, 100); axb.set_ylim(-0.5, 0.5); axb.axis("off")
    axb.set_title(head, fontsize=6.8, fontweight="bold", loc="center", pad=10)
    axb.text(50, 0.62, sub, ha="center", va="bottom", fontsize=5.5, color="#555555")
    # follower pyramid, % of followers
    fols = follower_cols()
    ftot = float(sum(row[f] + row[m] for _, _, f, m in fols))
    ys, labels = [], []
    for i, (o, age, f, m) in enumerate(fols):
        oi, ai = S.ORIGINS.index(o), i % 3
        y = -(oi * 3.7 + ai)
        colr, h, _ = ORIGIN_STYLE[o]
        fv, mv = 100 * row[f] / ftot, 100 * row[m] / ftot
        axp.barh(y, -fv, color=colr, hatch=h, edgecolor="white", lw=0.3, height=0.86)
        axp.barh(y, mv, color=colr, hatch=h, edgecolor="white", lw=0.3, height=0.86, alpha=0.62)
        ys.append(y); labels.append(age.replace("-", "–"))
    axp.axvline(0, color="#333333", lw=0.5)
    axp.set_xlim(-xmax, xmax)
    ticks = [t for t in (-10, -5, 0, 5, 10) if abs(t) <= xmax]
    axp.set_xticks(ticks)
    axp.set_xticklabels([f"{abs(t)}" for t in ticks], fontsize=5.6)
    axp.set_yticks(ys)
    axp.set_yticklabels(labels if first else [], fontsize=5.6)
    axp.tick_params(axis="y", length=0)
    axp.spines["left"].set_visible(False)
    axp.set_ylim(min(ys) - 0.7, 0.7)
    axp.text(-xmax * 0.96, 0.75, "F", fontsize=6, fontweight="bold", color="#555555", va="bottom")
    axp.text(xmax * 0.96, 0.75, "M", fontsize=6, fontweight="bold", color="#555555", va="bottom", ha="right")
    if first:
        for o in S.ORIGINS:
            yc = -(S.ORIGINS.index(o) * 3.7 + 1)
            axp.text(-xmax * 1.62, yc, o, rotation=90, va="center", ha="center", fontsize=6.4,
                     fontweight="bold", color=ORIGIN_STYLE[o][2], clip_on=False)
    return axb, axp


def panel_cohorts(fig, spec, picks, agg, cid):
    cols = [(r, f"{r.LETTER}   {str(r.ED_NAME).title()}",
             f"{S.TYPE_SHORT[S.TYPE_ORDER.index(r.TYPE)]} · {int(r.TOTAL_CATTLE):,} cattle · "
             f"{r.FOLLOWER_TO_ADULT_RATIO:.1f} fol./cow") for _, r in picks.iterrows()]
    cols.append((agg, f"{cid} aggregate",
                 f"{int(agg.TOTAL_CATTLE):,} cattle · {agg.FOLLOWER_TO_ADULT_RATIO:.1f} fol./cow"))
    vmax = 0.0
    for r, _, _ in cols:
        ft = sum(r[f] + r[m] for _, _, f, m in follower_cols())
        vmax = max(vmax, max(max(r[f], r[m]) / ft * 100 for _, _, f, m in follower_cols()))
    xmax = float(np.ceil(vmax / 2.5) * 2.5 + 1)
    sub = spec.subgridspec(1, len(cols), wspace=0.14)
    axes = []
    for k, (r, head, s) in enumerate(cols):
        axes.append(cohort_column(fig, sub[k], r, head, s, xmax, k == 0))
    for k, (axb, axp) in enumerate(axes):
        axp.set_xlabel("% of followers", fontsize=5.8, labelpad=1)
    # aggregate column set apart
    axes[-1][1].set_facecolor("#F5F5F5")
    return axes


# ---------------------------------------------------------------- AgriSyn-style panels
def catchment_types(w: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    wy = pd.read_csv(S.H / "wfd_catchment_year.csv", dtype={"WFD_CATCHMENT_ID": str})
    wy = wy[wy.YEAR == S.YEAR].copy()
    wy["ID"] = wy.WFD_CATCHMENT_ID.map(_normalise_wfd_id)
    wy["ELIGIBLE"] = True
    wy["TYPE"] = S.cattle_type(wy)
    g = w.merge(wy[["ID", "TYPE"]], on="ID", how="left", validate="one_to_one")
    if g.TYPE.isna().any():
        raise ValueError("catchment without aggregate type")
    return g


def panel_national(ax, w, cid):
    _, _, land = S.land_and_counties()
    g = catchment_types(w)
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    for t in S.TYPE_ORDER:
        part = g[g.TYPE == t]
        if len(part):
            part.plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.5)
    g[g.ID == cid].boundary.plot(ax=ax, color="black", lw=1.2)
    S.fit_ireland(ax, right=0.40)
    counts = g.TYPE.value_counts()
    S.vertical_key(ax, [S.TYPE_COLOURS[t] for t in S.TYPE_ORDER][::-1],
                   [f"{s} ({counts.get(t, 0)})" for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)][::-1],
                   title="catchments", where=(0.74, 0.05, 0.05, 0.42))
    p = g[g.ID == cid].geometry.iloc[0].centroid
    ax.annotate(cid, xy=(p.x, p.y), xytext=(p.x - 75000, p.y + 40000), fontsize=6.4, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color="black", lw=0.6), color=S.TEXT)
    return g


def panel_zoom(ax, w, target, inside, edge, picks, agg, cid, name):
    _, _, land = S.land_and_counties()
    tx0, ty0, tx1, ty1 = target.total_bounds
    pad = (tx1 - tx0) * 0.03
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none", zorder=0)
    w.boundary.plot(ax=ax, color="white", lw=0.8, zorder=1)
    edge.plot(ax=ax, color=OUTSIDE, edgecolor="white", lw=0.3, zorder=2)
    for t in S.TYPE_ORDER:
        part = inside[inside.TYPE == t]
        if len(part):
            part.plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.3, zorder=2)
    nd = inside[inside.TYPE.isna()]
    if len(nd):
        nd.plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.2, zorder=2)
    target.boundary.plot(ax=ax, color="black", lw=1.1, zorder=3)
    for _, r in picks.iterrows():
        q = r.geometry.representative_point()
        ax.text(q.x, q.y, r.LETTER, ha="center", va="center", fontsize=6.6, fontweight="bold", zorder=9,
                bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec="black", lw=0.6))
    width = tx1 - tx0
    ax.set_xlim(tx0 - pad, tx1 + pad + width * 0.62)
    ax.set_ylim(ty0 - pad, ty1 + pad)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_xlabel(""); ax.set_ylabel("")
    scalebar(ax)
    counts = inside.TYPE.value_counts()
    S.vertical_key(ax, ([S.TYPE_COLOURS[t] for t in S.TYPE_ORDER] + [OUTSIDE])[::-1],
                   ([f"{s} ({counts.get(t, 0)})" for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)]
                    + ["ED mostly outside"])[::-1], title="EDs", where=(0.66, 0.30, 0.04, 0.56))
    at = agg_type(agg)
    ax.text(0.66, 0.25, f"Catchment aggregate reads as\n{S.TYPE_SHORT[S.TYPE_ORDER.index(at)]}; "
            f"its {len(inside)} EDs span\n{counts.size} types (dairy share\n"
            f"P10–P90 {inside.DAIRY_SHARE_ADULT_PCT.quantile(0.1):.0f}–"
            f"{inside.DAIRY_SHARE_ADULT_PCT.quantile(0.9):.0f}%)",
            transform=ax.transAxes, fontsize=5.8, va="top", ha="left", color=S.TEXT, linespacing=1.25)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catchment", default="25C")
    a = ap.parse_args()
    cid = _normalise_wfd_id(a.catchment)
    S.style()
    w, target, name, inside, edge, agg = load(cid)
    picks = pick_examples(inside)
    ed_year = pd.read_csv(S.H / "ed_year.csv", usecols=["YEAR", "CSOED", "ED"])
    ed_year = ed_year[ed_year.YEAR == S.YEAR].assign(CSOED=lambda x: x.CSOED.astype(str))
    picks = picks.merge(ed_year[["CSOED", "ED"]].rename(columns={"ED": "ED_NAME"}), on="CSOED", how="left")
    picks = gpd.GeoDataFrame(picks, geometry="geometry", crs=inside.crs)
    _, _, land = S.land_and_counties()

    keep = ["CSOED", "ED_NAME", "TYPE", "TOTAL_CATTLE"] + [c for _, _, c in S.cohorts21()]
    tab = picks[["LETTER"] + keep].copy()
    tab.to_csv(S.TAB / f"S_catchment_{cid}_ed_cohorts_2025.csv", index=False)
    print(tab[["LETTER", "ED_NAME", "TYPE", "TOTAL_CATTLE"]].to_string(index=False))

    fig = plt.figure(figsize=(7.4, 7.1))
    top = fig.add_gridspec(1, 2, width_ratios=[0.78, 1.22], wspace=0.04, left=0.005, right=0.99,
                           top=0.955, bottom=0.515)
    panel_national(fig.add_subplot(top[0]), w, cid)
    panel_zoom(fig.add_subplot(top[1]), w, target, inside, edge, picks, agg, cid, name)
    low = fig.add_gridspec(1, 1, left=0.075, right=0.985, top=0.39, bottom=0.10)
    panel_cohorts(fig, low[0], picks, agg, cid)
    fig.text(0.01, 0.985, "a   Catchment aggregates, 2025", fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.40, 0.985, f"b   {cid} {name}: the same catchment by ED", fontsize=8.5,
             fontweight="bold", va="top")
    fig.text(0.01, 0.478, "c   All 21 cohorts in four contrasting EDs and in the catchment aggregate",
             fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.01, 0.456, "Bar: adult cohorts and followers by origin (% of all cattle). Pyramid: 18 "
             "follower cohorts by origin, age and sex (% of followers; female left, male right).",
             fontsize=5.9, color="#555555", va="top")
    hs = [Patch(facecolor=c, edgecolor="white", hatch=h, label=lab) for lab, _, c, h in HERD]
    fig.legend(handles=hs, loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=6, frameon=False,
               fontsize=5.8, handlelength=1.2, columnspacing=1.0)
    S.save(fig, f"Fig5_catchment_{cid}")


if __name__ == "__main__":
    main()
