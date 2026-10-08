#!/usr/bin/env python
"""Figure 4 (Section 3.4). Land and farm-structure context of ED cattle systems.

a-f  Six classed ED maps: cattle and sheep per farmed hectare, cereal share of farmed area and
     Standard Output per farmed hectare (2025), average holding size and average holder age
     (2020 census, the last observed values).
g    Spearman correlation of three cattle-system signatures (dairy share of adult cows,
     followers per adult cow, under-1 share of followers; 2025) with the six context variables.
     Filled: across all eligible EDs. Open: within counties (percentile ranks taken within each
     county, then correlated), which removes the between-county gradient.

Eligible EDs: >= 10 adult cows, >= 20 followers and >= 50 farmed ha.
Writes: reporting/paper1/figures/Fig4_context.{png,pdf}
        reporting/paper1/tables/S_context_correlations_2025.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

import paper1_style as S

MIN_HA = 50
# YlGnBu (ColorBrewer, colour-vision safe), 6 classes
CLASSES6 = ["#FFFFCC", "#C7E9B4", "#7FCDBB", "#41B6C4", "#2C7FB8", "#253494"]
CONTEXT = [  # column, label, year, breaks (inner), unit
    ("CATTLE_PER_FARMED_HA", "Cattle per farmed ha", 2025, [0.5, 1, 1.5, 2, 2.5], ""),
    ("SHEEP_PER_FARMED_HA", "Sheep per farmed ha", 2025, [0.1, 0.5, 1, 2, 4], ""),
    ("CEREAL_SHARE_FARMED_PCT", "Cereal share of farmed area", 2025, [1, 2.5, 5, 10, 25], "%"),
    ("SO_PER_FARMED_HA", "Standard Output per farmed ha", 2025, [1000, 1500, 2000, 2500, 3000], "€ thousand"),
    ("AVERAGE_SIZE_OF_HOLDINGS", "Average holding size", 2020, [20, 30, 40, 50, 65], "ha"),
    ("AVERAGE_AGE_OF_HOLDER", "Average holder age", 2020, [55, 57, 59, 61, 63], "years"),
]
SIGNATURES = [("DAIRY_SHARE_ADULT_PCT", "Dairy share of adult cows"),
              ("FOLLOWER_TO_ADULT_RATIO", "Followers per adult cow"),
              ("UNDER1_SHARE_FOLLOWERS_PCT", "Under-1 share of followers")]
SHORT = {"CATTLE_PER_FARMED_HA": "Cattle / ha", "SHEEP_PER_FARMED_HA": "Sheep / ha",
         "CEREAL_SHARE_FARMED_PCT": "Cereal share", "SO_PER_FARMED_HA": "SO / ha",
         "AVERAGE_SIZE_OF_HOLDINGS": "Holding size", "AVERAGE_AGE_OF_HOLDER": "Holder age"}


def load() -> pd.DataFrame:
    cols = ["YEAR", "CSOED", "County", "AREA_FARMED", "ADULT_COWS", "FOLLOWER_TOTAL"] + \
        [c for c, *_ in CONTEXT] + [c for c, _ in SIGNATURES]
    e = pd.read_csv(S.H / "ed_year.csv", usecols=cols)
    d = e[e.YEAR == 2025].set_index("CSOED")
    d20 = e[e.YEAR == 2020].set_index("CSOED")
    for c, _, y, _, _ in CONTEXT:
        if y == 2020:
            d[c] = d20[c].reindex(d.index)
    d["ELIGIBLE"] = (d.ADULT_COWS >= S.MIN_COWS) & (d.FOLLOWER_TOTAL >= S.MIN_FOLLOWERS) & \
        (d.AREA_FARMED >= MIN_HA)
    d.index = d.index.astype(str)
    return d.reset_index()


def fmt(v, unit):
    if unit == "€ thousand":
        return f"{v / 1000:g}"
    return f"{v:g}"


def map_panel(ax, eds, d, col, label, year, breaks, unit, letter):
    g = eds.merge(d[["CSOED", col, "AREA_FARMED"]], on="CSOED", how="left", validate="one_to_one")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    ok = g[col].notna() & (g.AREA_FARMED >= MIN_HA)
    cls = np.digitize(g.loc[ok, col], breaks)
    g.loc[ok].plot(ax=ax, color=[CLASSES6[i] for i in cls], edgecolor="white", lw=0.04)
    if (~ok).any():
        g.loc[~ok].plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.15)
    county.boundary.plot(ax=ax, color="#4A4A4A", lw=0.3)
    ax.set_axis_off(); ax.set_aspect("equal")
    yr = "2020 census" if year == 2020 else str(year)
    sub = f"{unit}, {yr}" if unit else yr
    ax.set_title(f"{letter}   {label}\n      ({sub})", loc="left", fontsize=7.2,
                 fontweight="bold", linespacing=1.1)
    # classed legend bar
    cax = ax.inset_axes([0.05, -0.04, 0.9, 0.035])
    cax.imshow(np.arange(6)[None, :], cmap=ListedColormap(CLASSES6), aspect="auto",
               extent=(0, 6, 0, 1))
    cax.set_yticks([])
    cax.set_xticks(range(1, 6))
    cax.set_xticklabels([fmt(b, unit) for b in breaks], fontsize=5.6)
    cax.tick_params(length=2, width=0.4, pad=1)
    for s in cax.spines.values():
        s.set_linewidth(0.3)
    share = 100 * pd.Series(cls).value_counts(normalize=True).reindex(range(6), fill_value=0)
    return share


def within_county_rho(d, a, b):
    ra = d.groupby("County")[a].rank(pct=True)
    rb = d.groupby("County")[b].rank(pct=True)
    return ra.corr(rb)


def correlations(d) -> pd.DataFrame:
    e = d[d.ELIGIBLE]
    rows = []
    for s, sl in SIGNATURES:
        for c, cl, *_ in CONTEXT:
            x = e[[s, c, "County"]].dropna()
            rows.append({"signature": sl, "context": cl, "n": len(x),
                         "rho_all": x[s].rank().corr(x[c].rank()),
                         "rho_within_county": within_county_rho(x, s, c)})
    return pd.DataFrame(rows)


def dot_panel(fig, spec, r):
    sub = spec.subgridspec(1, 3, wspace=0.1)
    ctx = [cl for _, cl, *_ in CONTEXT]
    y = np.arange(len(ctx))[::-1]
    axes = []
    for k, (_, sl) in enumerate(SIGNATURES):
        ax = fig.add_subplot(sub[k])
        q = r[r.signature == sl].set_index("context").reindex(ctx)
        ax.axvline(0, color="#9E9E9E", lw=0.6)
        for v in (-0.5, 0.5):
            ax.axvline(v, color="#E0E0E0", lw=0.5, zorder=0)
        ax.hlines(y, q.rho_within_county, q.rho_all, color="#BDBDBD", lw=0.8, zorder=1)
        ax.scatter(q.rho_all, y, s=18, color=S.TEXT, zorder=3)
        ax.scatter(q.rho_within_county, y, s=18, facecolor="white", edgecolor=S.TEXT, lw=0.8, zorder=3)
        ax.set_xlim(-1, 1)
        ax.set_xticks([-0.5, 0, 0.5])
        ax.set_ylim(-0.6, len(ctx) - 0.4)
        ax.set_yticks(y)
        ax.set_yticklabels(ctx if k == 0 else [], fontsize=6.4)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_title(sl, fontsize=7, fontweight="bold", loc="center")
        ax.set_xlabel("Spearman ρ", fontsize=6.6)
        axes.append(ax)
    fig.text(0.01, axes[0].get_position().y1 + 0.04,
             "g   How cattle-system signatures relate to land and farm structure",
             fontsize=8.5, fontweight="bold")
    axes[-1].legend(handles=[plt.Line2D([], [], marker="o", color=S.TEXT, ls="none", ms=4,
                                        label="All eligible EDs"),
                             plt.Line2D([], [], marker="o", mfc="white", mec=S.TEXT, ls="none",
                                        ms=4, label="Within counties")],
                    loc="lower right", bbox_to_anchor=(1.0, 1.13), frameon=False, fontsize=5.9,
                    handletextpad=0.2, ncol=2)


def main():
    S.style()
    d = load()
    r = correlations(d)
    r.round(3).to_csv(S.TAB / "S_context_correlations_2025.csv", index=False)
    print(r.round(2).to_string())
    eds = S.model_eds()
    fig = plt.figure(figsize=(7.4, 8.8))
    top = fig.add_gridspec(2, 3, left=0.01, right=0.99, top=0.965, bottom=0.30, hspace=0.3,
                           wspace=0.04)
    for i, (c, lab, yr, br, unit) in enumerate(CONTEXT):
        ax = fig.add_subplot(top[i // 3, i % 3])
        map_panel(ax, eds, d, c, lab, yr, br, unit, "abcdef"[i])
    bot = fig.add_gridspec(1, 1, left=0.2, right=0.985, top=0.2, bottom=0.075)
    dot_panel(fig, bot[0, 0], r)
    fig.text(0.01, 0.008, "Eligible EDs: ≥ 10 adult cows, ≥ 20 followers, ≥ 50 farmed ha (n = "
             f"{int(d.ELIGIBLE.sum()):,}). Standard Output includes livestock output, so its "
             "association with dairy share is partly by construction.\nHatched: farmed area "
             "< 50 ha. Within-county ρ correlates percentile ranks taken inside each county.",
             fontsize=5.6, color="#555555", va="bottom")
    S.save(fig, "Fig4_context")


if __name__ == "__main__":
    main()
