#!/usr/bin/env python
"""Figure 4. How ED cattle systems changed.

a  Observed, 2010-2020: ED change in total cattle against change in the dairy share of adult
   cows, using only census cells published in both censuses (>= 10 adult cows in both years).
   The grey band marks a stable herd (|cattle change| <= 5%); highlighted points are stable-herd
   EDs whose dairy share moved by >= 10 percentage points.
b  Reconstructed, 2015-2025: distribution across eligible EDs of the change in the DxD, DxB
   and BxB shares of followers (percentage points), with the national change marked.

Inputs: reporting/paper1/tables/S5_observed_restructuring_ed.csv (paper1_figures_final.py)
        reporting/report_data/historical/ed_year.csv, national_year.csv
Writes: reporting/paper1/figures/Fig4_ed_change.{png,pdf}
        reporting/paper1/tables/S_ed_follower_origin_change_2015_2025.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import paper1_style as S

STABLE_PCT, SHIFT_PP = 5.0, 10.0
HIGHLIGHT = "#D55E00"  # Okabe-Ito vermillion
START, END = 2015, 2025
ORIGIN = [("DxD", "DXD_SHARE_FOLLOWERS_PCT", "DXD_FOLLOWERS", S.DAIRY, None),
          ("DxB", "DXB_SHARE_FOLLOWERS_PCT", "DXB_FOLLOWERS", S.DXB, "////"),
          ("BxB", "BXB_SHARE_FOLLOWERS_PCT", "BXB_FOLLOWERS", S.SUCKLER, None)]


def spearman(x, y) -> float:
    return pd.Series(x).rank().corr(pd.Series(y).rank())


def panel_a(ax):
    p = pd.read_csv(S.TAB / "S5_observed_restructuring_ed.csv")
    stable = p.CATTLE_CHANGE_PCT.abs() <= STABLE_PCT
    hl = stable & (p.DS_CHANGE_PP.abs() >= SHIFT_PP)
    if hl.sum() != p.STABLE_HERD_SHIFTED_SYSTEM.sum():
        raise ValueError("highlight rule disagrees with S5 table")
    q = p[~p.ZERO_DAIRY_BOTH]
    rho = spearman(q.CATTLE_CHANGE_PCT, q.DS_CHANGE_PP)
    x = p.CATTLE_CHANGE_PCT.clip(-60, 100)
    ax.axvspan(-STABLE_PCT, STABLE_PCT, color="#E8E8E8", lw=0, zorder=0)
    ax.axhline(0, color="#9E9E9E", lw=0.6, zorder=1)
    ax.axvline(0, color="#9E9E9E", lw=0.6, zorder=1)
    for v in (-SHIFT_PP, SHIFT_PP):
        ax.axhline(v, color="#9E9E9E", lw=0.5, ls=(0, (3, 2)), zorder=1)
    z = p.ZERO_DAIRY_BOTH
    ax.scatter(x[~hl & ~z], p.DS_CHANGE_PP[~hl & ~z], s=4, color="#7F7F7F", alpha=0.45, lw=0, zorder=2)
    ax.scatter(x[z], p.DS_CHANGE_PP[z], s=4, marker="|", color="#BDBDBD", lw=0.4, zorder=2)
    ax.text(98, -2, f"no dairy cows in\neither census ({z.sum()})", fontsize=5.6, color="#7F7F7F",
            ha="right", va="top")
    ax.scatter(x[hl], p.DS_CHANGE_PP[hl], s=7, color=HIGHLIGHT, lw=0, zorder=3)
    st = p[stable]
    ax.annotate(f"Stable herd (±{STABLE_PCT:.0f}%): {len(st):,} EDs\n"
                f"median |change| {st.DS_CHANGE_PP.abs().median():.1f} pp\n"
                f"{hl.sum()} EDs ({100 * hl.sum() / len(st):.0f}%) moved ≥ {SHIFT_PP:.0f} pp",
                xy=(STABLE_PCT, -10), xytext=(16, -24), fontsize=6.2, color=HIGHLIGHT, va="top",
                arrowprops=dict(arrowstyle="-", color=HIGHLIGHT, lw=0.5))
    ax.text(98, 54, f"n = {len(p):,} EDs\nSpearman ρ = {rho:.2f}\n(EDs with dairy cows, n = {len(q):,})",
            ha="right", va="top",
            fontsize=6.2, color="#555555")
    ax.set_xlim(-62, 102)
    ax.set_ylim(-56, 56)
    ax.set_xlabel("Change in total cattle, 2010–2020 (%)")
    ax.set_ylabel("Change in dairy share of adult cows (pp)")
    S.title(ax, "a", "Observed: systems shifted where herds did not")
    return p, hl


def change_table() -> tuple[pd.DataFrame, dict]:
    cols = ["CSOED", "YEAR", "ADULT_COWS", "FOLLOWER_TOTAL"] + [c for _, c, _, _, _ in ORIGIN]
    e = pd.read_csv(S.H / "ed_year.csv", usecols=cols)
    e = e[e.YEAR.isin([START, END])]
    e["OK"] = (e.ADULT_COWS >= S.MIN_COWS) & (e.FOLLOWER_TOTAL >= S.MIN_FOLLOWERS)
    w = e.pivot(index="CSOED", columns="YEAR")
    ok = w["OK"][START] & w["OK"][END]
    out = pd.DataFrame(index=w.index[ok])
    for name, c, _, _, _ in ORIGIN:
        out[f"{name}_CHANGE_PP"] = (w[c][END] - w[c][START])[ok]
    n = pd.read_csv(S.H / "national_year.csv").set_index("YEAR")
    nat = {}
    for name, _, num, _, _ in ORIGIN:
        sh = 100 * n[num] / n[["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]].sum(axis=1)
        nat[name] = sh[END] - sh[START]
    return out, nat


def panel_b(fig, spec, ch, nat):
    sub = spec.subgridspec(3, 1, hspace=0.15)
    bins = np.arange(-40, 40.5, 1.5)
    axes = []
    for i, (name, _, _, c, h) in enumerate(ORIGIN):
        ax = fig.add_subplot(sub[i])
        v = ch[f"{name}_CHANGE_PP"].dropna()
        ax.hist(v.clip(-39.9, 39.9), bins=bins, color=c, hatch=h, edgecolor="white", lw=0.3)
        p10, med, p90 = v.quantile([0.1, 0.5, 0.9])
        top = ax.get_ylim()[1]
        ax.axvline(0, color="#555555", lw=0.6)
        ax.plot([p10, p90], [top * 1.02] * 2, color=S.TEXT, lw=1.0, solid_capstyle="butt",
                clip_on=False)
        ax.plot(med, top * 1.02, "o", ms=3.2, color=S.TEXT, clip_on=False)
        ax.plot(nat[name], top * 1.02, marker="v", ms=4.2, color="white", mec=S.TEXT, mew=0.7,
                clip_on=False, ls="none")
        ax.text(-39, top * 0.55, name, fontsize=7.4, fontweight="bold",
                color={"DxB": "#2C7FB8", "BxB": "#B36B00"}.get(name, c), va="center")
        ax.text(39, top * 0.55, f"median {med:+.1f} pp\nP10–P90 {p10:+.1f} to {p90:+.1f}",
                fontsize=5.9, ha="right", va="center", color="#555555")
        ax.set_ylim(0, top * 1.08)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlim(-40, 40)
        if i < 2:
            ax.tick_params(axis="x", labelbottom=False)
        axes.append(ax)
    axes[-1].set_xlabel(f"Change in share of followers, {START}–{END} (pp)")
    S.title(axes[0], "b", "Reconstructed: shifts in almost every ED")
    axes[0].legend(handles=[plt.Line2D([], [], color=S.TEXT, marker="o", ms=3, lw=1,
                                       label="ED median and P10–P90"),
                            plt.Line2D([], [], color="white", marker="v", ms=4, mec=S.TEXT,
                                       ls="none", label="National change")],
                   loc="upper left", bbox_to_anchor=(0.0, 0.98), frameon=False, fontsize=5.8,
                   handlelength=1.4, borderaxespad=0.2)
    axes[-1].text(0.0, -0.75, f"{len(ch):,} EDs eligible in both years (≥ {S.MIN_COWS} adult cows, "
                  f"≥ {S.MIN_FOLLOWERS} followers).", transform=axes[-1].transAxes, fontsize=5.6,
                  color="#555555")


def main():
    S.style()
    plt.rcParams["hatch.color"] = "#1F4E79"
    ch, nat = change_table()
    q = ch.quantile([0.1, 0.5, 0.9]).T.round(2)
    q["national_pp"] = [round(nat[n], 2) for n, *_ in ORIGIN]
    q["EDs_falling_pct"] = (100 * (ch < 0).mean()).round(1).to_numpy()
    q["EDs_rising_pct"] = (100 * (ch > 0).mean()).round(1).to_numpy()
    q.to_csv(S.TAB / "S_ed_follower_origin_change_2015_2025.csv")
    print(q.to_string())
    fig = plt.figure(figsize=(7.4, 3.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.05], wspace=0.22)
    panel_a(fig.add_subplot(gs[0, 0]))
    panel_b(fig, gs[0, 1], ch, nat)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.88, bottom=0.17)
    S.save(fig, "Fig4_ed_change")


if __name__ == "__main__":
    main()
