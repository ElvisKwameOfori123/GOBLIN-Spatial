#!/usr/bin/env python
"""Figure 4 (Section 3.4). The agricultural context of local cattle systems.

a  Three compact ED maps (AgriSyn map style), 2025: sheep per farmed ha, cereal share of farmed
   area and Standard Output per farmed ha.
b  Context profile of the six cattle-system types of Figure 3. For each context the type's
   pooled value (ratio of type totals) is expressed relative to the same pooled value for all
   eligible EDs (= 100), on a logarithmic axis:
       sheep per farmed ha        total sheep / total farmed ha                (2025)
       cereal share               total cereal ha / total farmed ha            (2025)
       average holding size       total farmed ha / total holdings             (2020 census)
       Standard Output per ha     total Standard Output / total farmed ha      (2025)
       average holder age         holdings-weighted mean holder age            (2020 census)
   Pooled values are used because most EDs record no cereal area (ED median 0).

Eligible EDs: >= 10 adult cows, >= 20 followers and >= 50 farmed ha.
Supplement: figS_context_atlas.py (sheep and cereal maps, ED medians and P10-P90).
Writes: reporting/paper1/figures/Fig4_context.{png,pdf}
        reporting/paper1/tables/S_context_index_by_type_2025.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FixedLocator, NullLocator

import paper1_style as S

MIN_HA = 50
MAPS = [  # column, title, inner breaks, colours (low to high), label format, key title
    ("SHEEP_PER_FARMED_HA", "Sheep per farmed ha", [0.1, 0.5, 1, 2, 4],
     ["#F7FCF5", "#D3EECD", "#A1D99B", "#5DB96B", "#238B45", "#00592A"], "{:g}", "head/ha"),
    ("CEREAL_SHARE_FARMED_PCT", "Cereal share of farmed area", [1, 2.5, 5, 10, 25],
     ["#FBF8EF", "#EFE3C2", "#DCC48C", "#C2A15A", "#9C7A2F", "#6B5214"], "{:g}", "%"),
    ("SO_PER_FARMED_HA", "Standard Output per farmed ha", [1000, 1500, 2000, 2500, 3000],
     ["#F7F7F7", "#D9D9D9", "#BDBDBD", "#969696", "#636363", "#303030"], "k", "€ per ha"),
]
ROWS = ["Sheep per farmed ha", "Cereal share of farmed area", "Average holding size (2020)",
        "Standard Output per farmed ha", "Average holder age (2020)"]


def load() -> pd.DataFrame:
    e = pd.read_csv(S.H / "ed_year.csv", low_memory=False)
    d = e[e.YEAR == S.YEAR].set_index("CSOED").copy()
    d20 = e[e.YEAR == 2020].set_index("CSOED")
    for c in ("AVERAGE_AGE_OF_HOLDER", "AGRICULTURAL_HOLDINGS", "AREA_FARMED"):
        d[c + "_2020"] = d20[c].reindex(d.index)
    d = d.reset_index()
    d["CSOED"] = d.CSOED.astype(str)
    d["ELIGIBLE"] = (d.ADULT_COWS >= S.MIN_COWS) & (d.FOLLOWER_TOTAL >= S.MIN_FOLLOWERS)
    d["TYPE"] = S.cattle_type(d)
    d.loc[d.AREA_FARMED < MIN_HA, "TYPE"] = np.nan
    return d


def pooled(x: pd.DataFrame) -> pd.Series:
    h = x.AGRICULTURAL_HOLDINGS_2020
    return pd.Series({
        ROWS[0]: x.TOTAL_SHEEP.sum() / x.AREA_FARMED.sum(),
        ROWS[1]: 100 * x.TOTAL_CEREALS.sum() / x.AREA_FARMED.sum(),
        ROWS[2]: x.AREA_FARMED_2020.sum() / h.sum(),
        ROWS[3]: x.SO_COVERED_TOTAL_2020_EUR.sum() / x.AREA_FARMED.sum(),
        ROWS[4]: (x.AVERAGE_AGE_OF_HOLDER_2020 * h).sum() / h[x.AVERAGE_AGE_OF_HOLDER_2020.notna()].sum(),
    })


def index_table(d: pd.DataFrame) -> pd.DataFrame:
    e = d[d.TYPE.notna()]
    ref = pooled(e)
    vals = pd.DataFrame({t: pooled(x) for t, x in e.groupby("TYPE")})[S.TYPE_ORDER]
    idx = 100 * vals.div(ref, axis=0)
    out = vals.add_suffix(" value").join(idx.add_suffix(" index"))
    out.insert(0, "All eligible EDs value", ref)
    return out, idx


def panel_map(ax, eds, d, col, title, breaks, colours, fmt, key_title):
    g = eds.merge(d[["CSOED", col, "AREA_FARMED"]], on="CSOED", how="left", validate="one_to_one")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    ok = g[col].notna() & (g.AREA_FARMED >= MIN_HA)
    cls = np.digitize(g.loc[ok, col], breaks)
    g.loc[ok].plot(ax=ax, color=[colours[i] for i in cls], edgecolor="none")
    county.boundary.plot(ax=ax, color="#A6A6A6", lw=0.25)
    S.fit_ireland(ax, right=0.42)
    ax.set_title(title, fontsize=7.0, loc="left", pad=2, color=S.TEXT)
    f = (lambda v: f"{v / 1000:g}k") if fmt == "k" else (lambda v: f"{v:g}")
    S.vertical_key(ax, colours, S.class_labels(breaks, f), title=key_title,
                   where=(0.74, 0.05, 0.05, 0.40))


def panel_profile(ax, idx: pd.DataFrame):
    n = len(ROWS)
    offsets = np.linspace(0.27, -0.27, len(S.TYPE_ORDER))
    for i, row in enumerate(ROWS):
        y0 = n - 1 - i
        ax.axhspan(y0 - 0.42, y0 + 0.42, color="#F7F7F7" if i % 2 == 0 else "white", lw=0, zorder=0)
        v = idx.loc[row]
        ax.plot([v.min(), v.max()], [y0, y0], color="#D0D0D0", lw=0.8, zorder=1)
        for off, t in zip(offsets, S.TYPE_ORDER):
            ax.plot(v[t], y0 + off, "o", ms=5.2, mfc=S.TYPE_COLOURS[t], mec=S.TEXT, mew=0.45, zorder=3)
    ax.axvline(100, color="#555555", lw=0.7, zorder=2)
    ax.set_xscale("log", base=2)
    ticks = [6.25, 12.5, 25, 50, 100, 200]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.set_xlim(min(10, idx.values.min() * 0.85), max(240, idx.values.max() * 1.15))
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_yticks(range(n))
    ax.set_yticklabels(ROWS[::-1], fontsize=6.6)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=6.2)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Relative to all eligible EDs (= 100), log scale", fontsize=6.6)
    ax.text(100, n - 0.38, "all EDs", ha="center", va="bottom", fontsize=5.8, color="#555555")
    hs = [plt.Line2D([], [], marker="o", ls="none", ms=5, mfc=S.TYPE_COLOURS[t], mec=S.TEXT, mew=0.45,
                     label=s) for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)]
    ax.legend(handles=hs, loc="lower center", bbox_to_anchor=(0.5, 1.03), ncol=6, frameon=False,
              fontsize=6.2, handletextpad=0.2, columnspacing=0.9)


def main():
    S.style()
    d = load()
    table, idx = index_table(d)
    table.round(2).to_csv(S.TAB / "S_context_index_by_type_2025.csv")
    print(table.round(2).to_string())
    eds = S.model_eds()
    fig = plt.figure(figsize=(7.4, 6.0))
    top = fig.add_gridspec(1, 3, wspace=0.02, left=0.005, right=0.99, top=0.955, bottom=0.45)
    for i, (col, title, br, colours, fmt, kt) in enumerate(MAPS):
        panel_map(fig.add_subplot(top[i]), eds, d, col, title, br, colours, fmt, kt)
    low = fig.add_gridspec(1, 1, left=0.26, right=0.975, top=0.33, bottom=0.085)
    panel_profile(fig.add_subplot(low[0]), idx)
    fig.text(0.01, 0.985, "a   Agricultural geography, 2025", fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.01, 0.415, "b   Contexts of the six cattle-system types", fontsize=8.5, fontweight="bold",
             va="top")
    S.save(fig, "Fig4_context")


if __name__ == "__main__":
    main()
