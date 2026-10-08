#!/usr/bin/env python
"""Figure 2. National restructuring of Irish livestock systems, 2015-2025.

a  Total cattle, dairy cows, suckler cows and sheep, indexed to 2015 = 100.
b  Composition of the whole cattle population in 2015, 2020 and 2025 (100% bars):
   dairy cows, suckler cows, bulls, and DxD, DxB and BxB followers.

Input: reporting/report_data/historical/national_year.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

import paper1_style as S

START, CENSUS, END = 2015, 2020, 2025


def load() -> pd.DataFrame:
    n = pd.read_csv(S.H / "national_year.csv").set_index("YEAR").loc[START:END]
    parts = n[["dairy_cows", "suckler_cows", "bulls", "DXD_FOLLOWERS", "DXB_FOLLOWERS",
               "BXB_FOLLOWERS"]].sum(axis=1)
    if (parts - n.TOTAL_CATTLE).abs().max() > 1:
        raise ValueError("cattle groups do not sum to TOTAL_CATTLE")
    return n


def panel_a(ax, n):
    series = [("TOTAL_CATTLE", "Total cattle", "black", "-", "o"),
              ("DAIRY_COW", "Dairy cows", S.DAIRY, "-", "s"),
              ("OTHER_COW", "Suckler cows", S.SUCKLER, "-", "^"),
              ("TOTAL_SHEEP", "Sheep", S.SHEEP, "--", "D")]
    yrs = n.index.to_numpy()
    ax.axvline(CENSUS, color="#9E9E9E", lw=0.7, ls=(0, (3, 2)), zorder=0)
    ax.axhline(100, color="#D0D0D0", lw=0.6, zorder=0)
    ends = []
    for col, lab, c, ls, mk in series:
        idx = 100 * n[col] / n.loc[START, col]
        ax.plot(yrs, idx, color=c, ls=ls, lw=1.6, marker=mk, ms=3.2, mec="white", mew=0.5)
        ends.append((idx.iloc[-1], lab, c))
    ends.sort()
    placed = []
    for y, lab, c in ends:
        yy = y if not placed else max(y, placed[-1] + 7.5)
        placed.append(yy)
        ax.annotate(f"{lab}\n{y - 100:+.1f}%", xy=(END, y), xytext=(END + 0.35, yy), va="center",
                    fontsize=6.6, color=c, fontweight="bold", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=c, lw=0.5) if abs(yy - y) > 0.5 else None)
    ax.text(CENSUS + 0.12, 71, "Census\nyear", fontsize=6.2, color="#7F7F7F", va="bottom")
    ax.set_xlim(START - 0.3, END + 0.3)
    ax.set_ylim(70, 130)
    ax.set_xticks(range(START, END + 1, 2))
    ax.set_ylabel("Index (2015 = 100)")
    ax.yaxis.grid(True, color="#EEEEEE", lw=0.5)
    ax.set_axisbelow(True)
    S.title(ax, "a", "Stable totals, diverging breeding herds")


def panel_b(ax, n):
    groups = [("Dairy cows", "dairy_cows", S.DARK_DAIRY, None, "white"),
              ("DxD followers", "DXD_FOLLOWERS", S.DAIRY, None, "white"),
              ("DxB followers", "DXB_FOLLOWERS", S.DXB, "////", "black"),
              ("BxB followers", "BXB_FOLLOWERS", S.SUCKLER, None, "black"),
              ("Suckler cows", "suckler_cows", S.DARK_SUCKLER, None, "white"),
              ("Bulls", "bulls", S.BULL, None, "black")]
    years = [START, CENSUS, END]
    x = range(len(years))
    plt.rcParams["hatch.color"] = "#1F4E79"
    base = [0.0] * 3
    for lab, col, c, h, tc in groups:
        v = [100 * n.loc[y, col] / n.loc[y, "TOTAL_CATTLE"] for y in years]
        ax.bar(x, v, bottom=base, width=0.62, color=c, hatch=h, edgecolor="white", lw=0.6, label=lab)
        for i in x:
            if v[i] >= 3.5:
                ax.text(i, base[i] + v[i] / 2, f"{v[i]:.0f}%", ha="center", va="center",
                        fontsize=6.3, color=tc, fontweight="bold")
        # label groups at the right of the last bar
        ax.text(2.36, base[2] + v[2] / 2, lab, va="center", fontsize=6.4, color=S.TEXT)
        base = [b + vi for b, vi in zip(base, v)]
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{y}\n{n.loc[y, 'TOTAL_CATTLE'] / 1e6:.2f} m cattle" for y in years])
    ax.set_xlim(-0.45, 3.3)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of all cattle (%)")
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    S.title(ax, "b", "Same herd size, different composition")


def main():
    n = load()
    S.style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.4), gridspec_kw={"width_ratios": [1.05, 1]})
    panel_a(a, n)
    panel_b(b, n)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.17, wspace=0.42)
    S.save(fig, "Fig2_national_restructuring")


if __name__ == "__main__":
    main()
