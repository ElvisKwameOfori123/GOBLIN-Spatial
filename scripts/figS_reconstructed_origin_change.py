#!/usr/bin/env python
"""Supplementary figure. Reconstructed change in follower origin across EDs, 2015-2025.

Distribution across eligible EDs (>= 10 adult cows and >= 20 followers in both years) of the
change in the DxD, DxB and BxB shares of followers (percentage points), with the ED median,
P10-P90 and the national change marked. Reconstructed values, not census observations.

Inputs: reporting/report_data/historical/ed_year.csv, national_year.csv
Writes: reporting/paper1/figures/FigS_reconstructed_origin_change.{png,pdf}
        reporting/paper1/tables/S_ed_follower_origin_change_2015_2025.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import paper1_style as S

START, END = 2015, 2025
ORIGIN = [("DxD", "DXD_SHARE_FOLLOWERS_PCT", "DXD_FOLLOWERS", S.DAIRY, None),
          ("DxB", "DXB_SHARE_FOLLOWERS_PCT", "DXB_FOLLOWERS", S.DXB, "////"),
          ("BxB", "BXB_SHARE_FOLLOWERS_PCT", "BXB_FOLLOWERS", S.SUCKLER, None)]


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
    axes[0].set_title(f"Change in follower origin across EDs, {START}–{END} (reconstructed)",
                      loc="left", fontweight="bold", fontsize=7.6, pad=10)
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
    fig = plt.figure(figsize=(4.2, 3.6))
    gs = fig.add_gridspec(1, 1)
    panel_b(fig, gs[0, 0], ch, nat)
    fig.subplots_adjust(left=0.05, right=0.97, top=0.88, bottom=0.2)
    S.save(fig, "FigS_reconstructed_origin_change")


if __name__ == "__main__":
    main()
