#!/usr/bin/env python
"""Figure: the 21 cattle cohorts in detail.

a  National cattle pyramid, 2015 vs 2025. Rows are the 21 GOBLIN cohorts:
   three adult cohorts (dairy cows, suckler cows, bulls) and 18 follower
   cohorts (DxD, DxB, BxB x under 1, 1-2, 2+ years x female/male).
   Females extend left, males right. Filled bars = 2025; open outlines = 2015.
b  Cohort composition of EDs grouped into deciles of breeding orientation
   (dairy share of adult cows), 2025: each cell is the share of all cattle in
   that decile held by the cohort. Deciles pool cattle across their EDs.

Inputs (release tables):
    reporting/report_data/historical/national_year.csv
    reporting/report_data/historical/livestock_signature.csv
Run from the repository root.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

H = Path("reporting/report_data/historical")
ORIG = {"DxD": "#0072B2", "DxB": "#56B4E9", "BxB": "#E69F00"}
ADULT = {"Dairy cows": "#004C7A", "Suckler cows": "#8C4A00", "Bulls": "#7F7F7F"}
AGES = [("2+ yr", "{o}_heifers_more_2_yr", "{o}_steers_more_2_yr"),
        ("1-2 yr", "{o}_heifers_less_2_yr", "{o}_steers_less_2_yr"),
        ("<1 yr", "{o}_calves_f", "{o}_calves_m")]


def rows():
    """(label, origin/group, female column, male column) top to bottom."""
    out = [("Dairy cows", "Dairy cows", "dairy_cows", None),
           ("Suckler cows", "Suckler cows", "suckler_cows", None),
           ("Bulls", "Bulls", None, "bulls")]
    for o in ORIG:
        for age, f, m in AGES:
            out.append((f"{o} {age}", o, f.format(o=o), m.format(o=o)))
    return out


def style():
    mpl.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 7.5, "axes.titlesize": 8.5,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.linewidth": 0.6, "pdf.fonttype": 42})


def pyramid(fig, spec, nat: pd.DataFrame):
    R = rows()
    off = np.concatenate([[2.1] * 3, np.repeat([1.4, 0.7, 0.0], 3)])
    y = np.arange(len(R))[::-1].astype(float) + off
    sub = spec.subgridspec(1, 3, width_ratios=[1, 0.55, 1], wspace=0.0)
    axL, axM, axR = (fig.add_subplot(sub[0, i]) for i in range(3))
    v15, v25 = nat.loc[2015], nat.loc[2025]
    lim = 1950
    for ax, side in ((axL, 2), (axR, 3)):
        for yi, r in zip(y, R):
            c = r[side]
            if c is None:
                continue
            grp = r[1]
            col = ADULT.get(grp, ORIG.get(grp))
            ax.barh(yi, v25[c] / 1e3, height=0.78, color=col,
                    hatch="////" if grp == "DxB" else None,
                    edgecolor="white", lw=0.4, zorder=2)
            ax.barh(yi, v15[c] / 1e3, height=0.78, fill=False, edgecolor="black",
                    lw=0.7, ls=(0, (2, 1.2)), zorder=3)
            pct = 100 * (v25[c] / v15[c] - 1)
            ax.text(max(v25[c], v15[c]) / 1e3 + 40, yi, f"{pct:+.0f}%", va="center",
                    ha="left" if side == 3 else "right", fontsize=6.3,
                    color="#B35806" if pct < -5 else ("#08519C" if pct > 5 else "#333333"),
                    fontweight="bold")
        ax.set_xlim(0, lim)
        ax.set_ylim(-0.8, y.max() + 1.0)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xticks([0, 750, 1500])
        ax.set_xticklabels(["0", "750", "1,500"])
    axL.invert_xaxis()
    axL.spines["right"].set_visible(True)
    axL.spines["right"].set_linewidth(0.6)
    axR.spines["left"].set_visible(True)
    axL.set_xlabel("Females (thousand head)")
    axR.set_xlabel("Males (thousand head)")
    axM.set_xlim(0, 1)
    axM.set_ylim(axL.get_ylim())
    axM.axis("off")
    axM.set_zorder(10)
    for yi, r in zip(y, R):
        txt = r[0].split(" ", 1)[1] if r[1] in ORIG else r[0]
        axM.text(0.5, yi, txt, ha="center", va="center", fontsize=6.4)
    for yi, (name, col) in ((y[3] + 0.75, ("Dairy × dairy (DxD)", ORIG["DxD"])),
                            (y[6] + 0.75, ("Dairy × beef (DxB)", "#2C7FB8")),
                            (y[9] + 0.75, ("Beef × beef (BxB)", "#B36B00")),
                            (y[0] + 0.75, ("Adults", "#333333"))):
        axM.text(0.5, yi, name, ha="center", va="center", fontsize=6.6,
                 fontweight="bold", color=col)
    axR.text(lim, -0.6, "filled 2025\ndashed 2015", ha="right",
             va="bottom", fontsize=6.2, color="#333333")
    axL.set_title("a   National cattle by cohort, 2015 and 2025", loc="left",
                  fontweight="bold", x=0.0)


def deciles(ax, fig, sig: pd.DataFrame):
    d = sig[(sig.GEOGRAPHY_TYPE == "ED") & (sig.YEAR == 2025)]
    d = d[(d.ADULT_COWS >= 10) & (d.FOLLOWER_TOTAL >= 20)].copy()
    d["DEC"] = pd.qcut(d.DAIRY_SHARE_ADULT_PCT.rank(method="first"), 10, labels=False)
    R = rows()
    mat = []
    for lab, grp, fcol, mcol in R:
        cols = [c for c in (fcol, mcol) if c]
        mat.append(d.groupby("DEC")[cols].sum().sum(axis=1)
                   / d.groupby("DEC").TOTAL_CATTLE.sum() * 100)
    M = np.vstack(mat)
    im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=30)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=5.6,
                    color="white" if M[i, j] < 17 else "black")
    ax.set_yticks(range(len(R)))
    ax.set_yticklabels([r[0] for r in R], fontsize=6.4)
    med = d.groupby("DEC").DAIRY_SHARE_ADULT_PCT.median()
    ax.set_xticks(range(10))
    ax.set_xticklabels([f"D{k+1}\n{med[k]:.0f}%" for k in range(10)], fontsize=6.2)
    ax.set_xlabel("Decile of EDs by dairy share of adult cows (median shown)\n"
                  "suckler-oriented  →  dairy-oriented")
    for b in (2.5, 5.5, 8.5):
        ax.axhline(b, color="white", lw=1.2)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, extend="max")
    cb.set_label("% of all cattle in decile", fontsize=6.6)
    cb.ax.tick_params(labelsize=6.2)
    ax.set_title("b   Cohort mix by breeding orientation, 2025",
                 loc="left", fontweight="bold")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F_cohort_detail_21"))
    a = ap.parse_args()
    nat = pd.read_csv(H / "national_year.csv").set_index("YEAR")
    sig = pd.read_csv(H / "livestock_signature.csv")
    tot = sum(nat.loc[2025, r[c]] for r in rows() for c in (2, 3) if r[c])
    if abs(tot - nat.loc[2025, "TOTAL_CATTLE"]) > 1:
        raise ValueError("21 cohorts do not sum to total cattle")
    style()
    mpl.rcParams["hatch.linewidth"] = 0.4
    mpl.rcParams["hatch.color"] = "#1F4E79"
    fig = plt.figure(figsize=(7.4, 4.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1], wspace=0.42)
    pyramid(fig, gs[0, 0], nat)
    deciles(fig.add_subplot(gs[0, 1]), fig, sig)
    fig.subplots_adjust(left=0.03, right=0.94, top=0.92, bottom=0.17)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(a.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", a.out)


if __name__ == "__main__":
    main()
