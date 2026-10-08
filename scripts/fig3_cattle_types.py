#!/usr/bin/env python
"""Figure 3 and Table 4. Where the cattle systems are, and what they contain (2025).

Typology (fixed thresholds; eligible EDs have >= 10 adult cows and >= 20 followers):
    breeding orientation  Suckler: dairy share of adult cows < 40%; Mixed: 40-60%; Dairy: > 60%
    follower intensity    lower: <= 1.9 followers per adult cow; higher: > 1.9

a  The six types across EDs, with a compact legend (rows: orientation; light/dark: follower
   intensity).
b  21-cohort fingerprint: share of all cattle in each type held by each cohort (cohort head
   summed over the type's EDs / total cattle of those EDs). Linear grey scale capped at 12%;
   values are printed only for cells >= 10% (the adult cow cohorts).

Writes:
    reporting/paper1/figures/Fig3_cattle_system_types.{png,pdf}
    reporting/paper1/tables/T4_cattle_system_types_2025.csv
    reporting/paper1/tables/S_cattle_types_2020_2025_crosstab.csv
    reporting/paper1/tables/S_cattle_type_cohort_shares_2025.csv  (all 126 heatmap values)
"""
from __future__ import annotations

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

import paper1_style as S

VMAX, LABEL_MIN = 12.0, 10.0
HEAT_CMAP = mcolors.LinearSegmentedColormap.from_list("grey", ["#FFFFFF", "#252525"])


def typed(year: int) -> pd.DataFrame:
    d = S.ed_signatures(year)
    d["TYPE"] = S.cattle_type(d)
    return d


def table4(d: pd.DataFrame) -> pd.DataFrame:
    e = d[d.TYPE.notna()]
    g = e.groupby("TYPE")
    t = pd.DataFrame({
        "EDs": g.size(),
        "Share of cattle (%)": 100 * g.TOTAL_CATTLE.sum() / e.TOTAL_CATTLE.sum(),
        "Dairy share of adult cows (%)": g.DAIRY_SHARE_ADULT_PCT.median(),
        "Followers per adult cow": g.FOLLOWER_TO_ADULT_RATIO.median(),
        "Under-1 share of followers (%)": g.UNDER1_SHARE_FOLLOWERS_PCT.median(),
        "DxD share (%)": g.DXD_SHARE_FOLLOWERS_PCT.median(),
        "DxB share (%)": g.DXB_SHARE_FOLLOWERS_PCT.median(),
        "BxB share (%)": g.BXB_SHARE_FOLLOWERS_PCT.median(),
    }).reindex(S.TYPE_ORDER)
    t.index.name = "Type"
    return t


def heat(d: pd.DataFrame) -> pd.DataFrame:
    e = d[d.TYPE.notna()]
    cols = [c for _, _, c in S.cohorts21()]
    tot = e.groupby("TYPE")[cols].sum()
    share = 100 * tot.div(e.groupby("TYPE").TOTAL_CATTLE.sum(), axis=0)
    if (share.sum(axis=1) - 100).abs().max() > 0.01:
        raise ValueError("cohort shares do not close to 100%")
    return share.reindex(S.TYPE_ORDER).T


def panel_map(ax, d):
    eds = S.model_eds()
    _, county, land = S.land_and_counties()
    g = eds.merge(d[["CSOED", "TYPE"]], on="CSOED", how="left", validate="one_to_one")
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    g[g.TYPE.isna()].plot(ax=ax, facecolor=S.NODATA, edgecolor="#9E9E9E", hatch=S.NODATA_HATCH, lw=0.2)
    for t in S.TYPE_ORDER:
        g[g.TYPE == t].plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.05)
    county.boundary.plot(ax=ax, color="#8C8C8C", lw=0.3)
    ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlabel(""); ax.set_ylabel("")
    # compact legend in the Atlantic, north-west of the island
    lg = ax.inset_axes([0.0, 0.70, 0.30, 0.20])
    lg.set_xlim(0, 3.6); lg.set_ylim(0, 3.9); lg.axis("off")
    for i, b in enumerate(("Suckler", "Mixed", "Dairy")):
        y = 2 - i
        lg.text(1.0, y + 0.45, b, ha="right", va="center", fontsize=6.2, color=S.TEXT)
        for j, f in enumerate(("lower-follower", "higher-follower")):
            lg.add_patch(Rectangle((1.2 + j * 1.15, y + 0.08), 1.05, 0.78, lw=0,
                                   color=S.TYPE_COLOURS[f"{b}, {f}"]))
    lg.text(1.725, 3.05, "lower", ha="center", va="bottom", fontsize=5.8, color="#555555")
    lg.text(2.875, 3.05, "higher", ha="center", va="bottom", fontsize=5.8, color="#555555")
    lg.text(2.3, 3.55, "followers per cow", ha="center", va="bottom", fontsize=5.8, color="#555555")


def panel_heat(ax, fig, H):
    labels = [lab for lab, _, _ in S.cohorts21()]
    M = H.to_numpy()
    im = ax.imshow(M, aspect="auto", cmap=HEAT_CMAP, vmin=0, vmax=VMAX, interpolation="nearest")
    for i, j in zip(*np.where(M >= LABEL_MIN)):
        ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=6.0, color="white")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=6.0)
    ax.set_xticks(range(6))
    ax.set_xticklabels(S.TYPE_SHORT, fontsize=6.6)
    ax.xaxis.tick_top()
    ax.tick_params(length=0, pad=9)
    # type colour chips between the column labels and the matrix
    for j, t in enumerate(S.TYPE_ORDER):
        ax.add_patch(Rectangle((j - 0.42, -1.05), 0.84, 0.38, color=S.TYPE_COLOURS[t], lw=0,
                               clip_on=False))
    for b in (2.5, 8.5, 14.5):
        ax.axhline(b, color="white", lw=2.2)
    for y, name in ((1, "Adults"), (5.5, "DxD"), (11.5, "DxB"), (17.5, "BxB")):
        ax.text(5.65, y, name, rotation=270, va="center", ha="left", fontsize=6.2, clip_on=False,
                color="#555555")
    for s in ax.spines.values():
        s.set_visible(False)
    cax = ax.inset_axes([0.0, -0.05, 0.6, 0.016])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend="max", ticks=[0, 4, 8, 12])
    cb.set_label("% of all cattle in the type", fontsize=6.0, labelpad=2)
    cb.ax.tick_params(labelsize=5.8, length=2)
    cb.outline.set_linewidth(0.3)


def main():
    S.style()
    d25 = typed(2025)
    t4 = table4(d25)
    H = heat(d25)
    S.TAB.mkdir(parents=True, exist_ok=True)
    t4.round(1).to_csv(S.TAB / "T4_cattle_system_types_2025.csv")
    H.round(2).set_axis([lab for lab, _, _ in S.cohorts21()], axis=0).to_csv(
        S.TAB / "S_cattle_type_cohort_shares_2025.csv")
    d20 = typed(2020)
    both = d25[["CSOED", "TYPE"]].merge(d20[["CSOED", "TYPE"]], on="CSOED", suffixes=("_2025", "_2020"))
    both = both.dropna()
    pd.crosstab(both.TYPE_2020, both.TYPE_2025).reindex(index=S.TYPE_ORDER, columns=S.TYPE_ORDER).to_csv(
        S.TAB / "S_cattle_types_2020_2025_crosstab.csv")
    print(t4.round(1).to_string())
    print(f"same type 2020 and 2025: {100 * (both.TYPE_2020 == both.TYPE_2025).mean():.1f}% of {len(both):,} EDs")

    fig = plt.figure(figsize=(7.4, 5.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.95], wspace=0.30)
    panel_map(fig.add_subplot(gs[0, 0]), d25)
    panel_heat(fig.add_subplot(gs[0, 1]), fig, H)
    fig.subplots_adjust(left=0.01, right=0.94, top=0.88, bottom=0.10)
    for x, t in ((0.01, "a   Six cattle-system types across EDs"),
                 (0.45, "b   21-cohort fingerprint of each type")):
        fig.text(x, 0.985, t, fontsize=8.5, fontweight="bold", va="top")
    S.save(fig, "Fig3_cattle_system_types")


if __name__ == "__main__":
    main()
