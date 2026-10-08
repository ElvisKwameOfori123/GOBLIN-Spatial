#!/usr/bin/env python
"""Figure 4 (Section 3.4). The agricultural context of local cattle systems.

a  Standard Output per farmed ha across EDs, 2025 (single context map).
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
SO_BREAKS = [1000, 1500, 2000, 2500, 3000]
SO_COLOURS = ["#F7F7F7", "#D9D9D9", "#BDBDBD", "#969696", "#636363", "#303030"]
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


def panel_map(ax, d):
    eds = S.model_eds()
    g = eds.merge(d[["CSOED", "SO_PER_FARMED_HA", "AREA_FARMED"]], on="CSOED", how="left",
                  validate="one_to_one")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    ok = g.SO_PER_FARMED_HA.notna() & (g.AREA_FARMED >= MIN_HA)
    cls = np.digitize(g.loc[ok, "SO_PER_FARMED_HA"], SO_BREAKS)
    g.loc[ok].plot(ax=ax, color=[SO_COLOURS[i] for i in cls], edgecolor="none")
    county.boundary.plot(ax=ax, color="#9E9E9E", lw=0.25)
    ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlabel(""); ax.set_ylabel("")
    cax = ax.inset_axes([0.12, -0.03, 0.76, 0.03])
    cax.imshow(np.arange(6)[None, :], cmap=ListedColormap(SO_COLOURS), aspect="auto", extent=(0, 6, 0, 1))
    cax.set_yticks([]); cax.set_xticks(range(1, 6))
    cax.set_xticklabels([f"{b / 1000:g}" for b in SO_BREAKS], fontsize=5.8)
    cax.tick_params(length=1.5, width=0.4, pad=1)
    for s in cax.spines.values():
        s.set_linewidth(0.3)
    cax.set_xlabel("€ thousand per farmed ha", fontsize=5.9, labelpad=1.5)


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
    fig = plt.figure(figsize=(7.4, 3.9))
    gs = fig.add_gridspec(1, 2, width_ratios=[0.78, 1.22], wspace=0.06, left=0.0, right=0.975,
                          top=0.86, bottom=0.14)
    panel_map(fig.add_subplot(gs[0]), d)
    axp = fig.add_subplot(gs[1])
    panel_profile(axp, idx)
    pos = axp.get_position()
    axp.set_position([pos.x0 + 0.17, pos.y0, pos.width - 0.17, pos.height])
    fig.text(0.01, 0.975, "a   Agricultural production context, 2025", fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.42, 0.975, "b   Contexts of the six cattle-system types", fontsize=8.5, fontweight="bold",
             va="top")
    S.save(fig, "Fig4_context")


if __name__ == "__main__":
    main()
