#!/usr/bin/env python
"""Figure 3 and Table 4. ED cattle-system types and their 21-cohort composition, 2025.

Typology (fixed thresholds, eligible EDs: >= 10 adult cows and >= 20 followers):
    breeding orientation  Suckler: dairy share of adult cows < 40%
                          Mixed:   40-60%
                          Dairy:   > 60%
    follower intensity    lower:  followers per adult cow <= 1.9
                          higher: > 1.9
a  Map of the six types across EDs.
b  21 x 6 heatmap: share of all cattle in each type held by each cohort
   (cohort head summed over the type's EDs / total cattle of those EDs).

Writes:
    reporting/paper1/figures/Fig3_cattle_system_types.{png,pdf}
    reporting/paper1/tables/T4_cattle_system_types_2025.csv
    reporting/paper1/tables/S_cattle_types_2020_sensitivity.csv
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import paper1_style as S


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
        "Cattle per farmed ha": g.CATTLE_PER_FARMED_HA.median(),
    }).reindex(S.TYPE_ORDER)
    rules = {"Suckler": "< 40%", "Mixed": "40–60%", "Dairy": "> 60%"}
    t.insert(0, "Rule", [f"dairy share {rules[k.split(',')[0]]}; followers/cow "
                         f"{'≤' if 'lower-follower' in k else '>'} {S.FOLLOWER_CUT}" for k in t.index])
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
    g[g.TYPE.isna()].plot(ax=ax, facecolor=S.NODATA, edgecolor="#7F7F7F", hatch=S.NODATA_HATCH, lw=0.2)
    for t in S.TYPE_ORDER:
        g[g.TYPE == t].plot(ax=ax, color=S.TYPE_COLOURS[t], edgecolor="white", lw=0.05)
    county.boundary.plot(ax=ax, color="#4A4A4A", lw=0.35)
    ax.set_axis_off(); ax.set_aspect("equal")
    counts = d.TYPE.value_counts()
    # 3 x 2 legend matrix: rows = breeding orientation, columns = follower intensity
    lg = ax.inset_axes([0.30, -0.215, 0.44, 0.165])
    lg.set_xlim(0, 2); lg.set_ylim(0, 3); lg.axis("off")
    rows = [("Suckler", "< 40% dairy"), ("Mixed", "40–60%"), ("Dairy", "> 60%")]
    for i, (b, rule) in enumerate(rows):
        y = 2 - i
        for j, f in enumerate(("lower-follower", "higher-follower")):
            t = f"{b}, {f}"
            dark = j == 1
            lg.add_patch(plt.Rectangle((j + 0.03, y + 0.06), 0.94, 0.88, color=S.TYPE_COLOURS[t], lw=0))
            lg.text(j + 0.5, y + 0.5, f"{S.TYPE_SHORT[S.TYPE_ORDER.index(t)]}\n{counts.get(t, 0):,} EDs",
                    ha="center", va="center", fontsize=5.3, linespacing=1.05,
                    color="white" if dark else "black", fontweight="bold")
        lg.text(-0.06, y + 0.5, f"{b}  {rule}", ha="right", va="center", fontsize=5.5,
                linespacing=1.1, color=S.TEXT)
    lg.text(0.5, 3.08, f"≤ {S.FOLLOWER_CUT}", ha="center", va="bottom", fontsize=5.5, color=S.TEXT)
    lg.text(1.5, 3.08, f"> {S.FOLLOWER_CUT}", ha="center", va="bottom", fontsize=5.5, color=S.TEXT)
    lg.text(1.0, 3.6, "Followers per adult cow", ha="center", va="bottom", fontsize=5.8,
            fontweight="bold", color=S.TEXT)
    lg.add_patch(plt.Rectangle((2.12, 0.06), 0.22, 0.6, facecolor=S.NODATA, edgecolor="#7F7F7F",
                               hatch=S.NODATA_HATCH, lw=0.3, clip_on=False))
    lg.text(2.42, 0.36, f"Below threshold\n({int(d.TYPE.isna().sum())} EDs)", va="center",
            fontsize=5.6, color="#555555", clip_on=False)


def panel_heat(ax, fig, H, t4):
    labels = [lab for lab, _, _ in S.cohorts21()]
    M = H.to_numpy()
    norm = mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=40)
    im = ax.imshow(M, aspect="auto", cmap="viridis", norm=norm)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.1f}" if v < 10 else f"{v:.0f}", ha="center", va="center",
                    fontsize=5.4, color="white" if norm(v) < 0.62 else "black")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=5.9)
    ax.set_xticks(range(6))
    ax.set_xticklabels([f"{s}\n{int(t4.loc[t, 'EDs'])}\n{t4.loc[t, 'Share of cattle (%)']:.0f}%"
                        for s, t in zip(S.TYPE_SHORT, S.TYPE_ORDER)], fontsize=5.8)
    ax.xaxis.tick_top()
    for t, lab in zip(ax.get_xticklabels(), S.TYPE_ORDER):
        t.set_color(S.TYPE_COLOURS[lab] if "lower-follower" not in lab else "#555555")
        t.set_fontweight("bold")
    for b in (2.5, 8.5, 14.5):
        ax.axhline(b, color="white", lw=1.6)
    for b in (1.5, 3.5):
        ax.axvline(b, color="white", lw=1.6)
    for y, name in ((1, "Adults"), (5.5, "DxD"), (11.5, "DxB"), (17.5, "BxB")):
        ax.text(5.62, y, name, rotation=270, va="center", ha="left", fontsize=6.4, clip_on=False,
                fontweight="bold", color={"Adults": "#555555", "DxD": S.DAIRY,
                                          "DxB": "#2C7FB8", "BxB": "#B36B00"}[name])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cax = ax.inset_axes([0.0, -0.045, 1.0, 0.016])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", ticks=[0, 1, 5, 10, 20, 30, 40])
    cb.set_label("% of all cattle in the type (square-root scale)", fontsize=6.2)
    cb.ax.tick_params(labelsize=5.8, length=2)
    cb.outline.set_linewidth(0.4)
    ax.annotate("Type\nEDs\n% of all cattle", xy=(-0.5, -0.5), xytext=(-4, 3.5),
                textcoords="offset points", ha="right", va="bottom", fontsize=5.8,
                color="#555555", fontweight="bold", annotation_clip=False)


def main():
    S.style()
    d25 = typed(2025)
    t4 = table4(d25)
    H = heat(d25)
    S.TAB.mkdir(parents=True, exist_ok=True)
    t4.round(2).to_csv(S.TAB / "T4_cattle_system_types_2025.csv")
    d20 = typed(2020)
    both = d25[["CSOED", "TYPE"]].merge(d20[["CSOED", "TYPE"]], on="CSOED", suffixes=("_2025", "_2020"))
    both = both.dropna()
    sens = pd.crosstab(both.TYPE_2020, both.TYPE_2025).reindex(index=S.TYPE_ORDER, columns=S.TYPE_ORDER)
    sens.to_csv(S.TAB / "S_cattle_types_2020_2025_crosstab.csv")
    agree = 100 * (both.TYPE_2020 == both.TYPE_2025).mean()
    print(t4.round(1).to_string())
    print(f"same type 2020 and 2025 (fixed thresholds): {agree:.1f}% of {len(both):,} EDs")

    fig = plt.figure(figsize=(7.4, 5.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.05], wspace=0.32)
    panel_map(fig.add_subplot(gs[0, 0]), d25)
    panel_heat(fig.add_subplot(gs[0, 1]), fig, H, t4)
    fig.text(0.01, 0.005, "Below threshold: < 10 adult cows or < 20 followers. All types contain the complete "
             "21-cohort population; sex and 2+ year fractions follow county age-sex margins.",
             fontsize=5.6, color="#555555", va="bottom")
    fig.subplots_adjust(left=0.02, right=0.92, top=0.86, bottom=0.17)
    for x, t in ((0.01, "a   Cattle-system types across EDs, 2025"),
                 (0.47, "b   Complete 21-cohort composition of each type")):
        fig.text(x, 0.975, t, fontsize=8.5, fontweight="bold", va="top")
    S.save(fig, "Fig3_cattle_system_types")


if __name__ == "__main__":
    main()
