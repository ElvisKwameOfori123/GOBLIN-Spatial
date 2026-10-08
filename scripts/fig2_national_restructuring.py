#!/usr/bin/env python
"""Figure 2. National restructuring of Irish livestock systems, 2015-2025.

Panel a: total cattle, dairy cows, suckler cows and sheep, indexed to 2015 = 100.
Panel b: followers by parental origin (DxD, DxB, BxB), million head, every year.

Reads the released national table only:
    reporting/report_data/historical/national_year.csv

Colours follow the Okabe-Ito colour-blind-safe palette; lines also differ by
marker and line style so the figure reads in greyscale.

Usage:
    python fig2_national_restructuring.py \
        --national reporting/report_data/historical/national_year.csv \
        --out reporting/paper1/figures/F2_national_restructuring
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

# Okabe-Ito
BLACK = "#000000"
BLUE = "#0072B2"      # dairy cows, DxD
SKY = "#56B4E9"       # DxB (dairy dam, beef sire)
ORANGE = "#E69F00"    # suckler cows, BxB
GREEN = "#009E73"     # sheep
GREY = "#7F7F7F"

CENSUS_YEAR = 2020
START, END = 2015, 2025

REQUIRED = ["YEAR", "TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP",
            "DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS", "FOLLOWER_TOTAL"]


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise KeyError(f"national table lacks columns: {missing}")
    df = df[REQUIRED].sort_values("YEAR").set_index("YEAR").loc[START:END]
    if list(df.index) != list(range(START, END + 1)):
        raise ValueError("national table must contain every year 2015-2025")
    origin_sum = df[["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]].sum(axis=1)
    if (origin_sum - df["FOLLOWER_TOTAL"]).abs().max() > 0.5:
        raise ValueError("DxD + DxB + BxB does not equal FOLLOWER_TOTAL")
    return df


def style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })


def panel_a(ax, df: pd.DataFrame) -> None:
    series = [
        ("TOTAL_CATTLE", "Total cattle", BLACK, "-", "o"),
        ("DAIRY_COW", "Dairy cows", BLUE, "-", "s"),
        ("OTHER_COW", "Suckler cows", ORANGE, "-", "^"),
        ("TOTAL_SHEEP", "Sheep", GREEN, "--", "D"),
    ]
    years = df.index.to_numpy()
    ax.axvline(CENSUS_YEAR, color=GREY, lw=0.7, ls=(0, (3, 2)), zorder=0)
    ax.axhline(100, color="#BDBDBD", lw=0.6, zorder=0)
    ends = []
    for col, label, colour, ls, mk in series:
        idx = 100 * df[col] / df.loc[START, col]
        ax.plot(years, idx, color=colour, ls=ls, lw=1.6, marker=mk, ms=3.2,
                mec="white", mew=0.5, zorder=3)
        ends.append((idx.iloc[-1], label, colour))

    # direct labels at line ends, nudged apart so they never overlap
    ends.sort()
    placed = []
    for y, label, colour in ends:
        yy = y if not placed else max(y, placed[-1] + 7.5)
        placed.append(yy)
        change = y - 100
        ax.annotate(f"{label}\n{change:+.1f}%", xy=(END, y), xytext=(END + 0.35, yy),
                    va="center", ha="left", fontsize=7, color=colour,
                    fontweight="bold", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=colour, lw=0.5)
                    if abs(yy - y) > 0.5 else None)

    ax.text(CENSUS_YEAR + 0.12, 70.8, "Census\nyear", fontsize=6.5, color=GREY,
            va="bottom", ha="left")
    ax.set_xlim(START - 0.3, END + 0.3)
    ax.set_ylim(70, 130)
    ax.set_xticks(range(START, END + 1, 2))
    ax.set_ylabel("Index (2015 = 100)")
    ax.set_title("a   Stable totals, diverging breeding herds", loc="left",
                 fontweight="bold")


def panel_b(ax, df: pd.DataFrame) -> None:
    years = df.index.to_numpy()
    # DxB and BxB have near-identical luminance (0.405 vs 0.416), so in
    # greyscale they would merge; a light hatch on DxB keeps them distinct.
    parts = [
        ("BXB_FOLLOWERS", "BxB", ORANGE, None),
        ("DXB_FOLLOWERS", "DxB", SKY, "////"),
        ("DXD_FOLLOWERS", "DxD", BLUE, None),
    ]
    bottom = pd.Series(0.0, index=df.index)
    mpl.rcParams["hatch.color"] = "#1F4E79"
    mpl.rcParams["hatch.linewidth"] = 0.45
    for col, label, colour, hatch in parts:
        vals = df[col] / 1e6
        ax.bar(years, vals, bottom=bottom, width=0.72, color=colour,
               hatch=hatch, edgecolor="white", linewidth=0.6, label=label,
               zorder=2)
        for yr, dx, ha in ((START, -0.45, "right"), (END, 0.45, "left")):
            share = 100 * df.loc[yr, col] / df.loc[yr, "FOLLOWER_TOTAL"]
            ax.text(yr + dx, bottom[yr] + vals[yr] / 2, f"{share:.0f}%",
                    ha=ha, va="center", fontsize=6.8, color=colour,
                    fontweight="bold", zorder=4)
        bottom = bottom + vals

    for yr in (START, CENSUS_YEAR, END):
        ax.text(yr, bottom[yr] + 0.06, f"{bottom[yr]:.2f}", ha="center",
                va="bottom", fontsize=6.5, color="#4D4D4D")
    ax.annotate("Census year", xy=(CENSUS_YEAR, bottom[CENSUS_YEAR] + 0.36),
                ha="center", va="bottom", fontsize=6.5, color=GREY)

    ax.set_xlim(START - 1.6, END + 1.6)
    ax.set_ylim(0, 5.6)
    ax.set_xticks(range(START, END + 1, 2))
    ax.set_ylabel("Followers (million head)")
    ax.set_title("b   Same follower total, new origin", loc="left",
                 fontweight="bold")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper center",
              bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False, fontsize=7,
              handlelength=1.2, columnspacing=1.4)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--national", type=Path,
                    default=Path("reporting/report_data/historical/national_year.csv"))
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F2_national_restructuring"))
    args = ap.parse_args()

    df = load(args.national)
    style()
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(7.4, 3.2), gridspec_kw={"width_ratios": [1.08, 1]})
    panel_a(ax_a, df)
    panel_b(ax_b, df)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.9, bottom=0.17, wspace=0.5)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(args.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print(f"Saved {args.out.with_suffix('.png')} and .pdf")


if __name__ == "__main__":
    main()
