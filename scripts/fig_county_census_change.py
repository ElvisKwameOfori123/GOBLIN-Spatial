#!/usr/bin/env python
"""Figure: observed county restructuring between the 2010 and 2020 Censuses of
Agriculture (census values only; no reconstruction).

a  Dumbbell: dairy share of adult cows in 2010 (open circle) and 2020 (filled),
   counties ordered by 2020 value.
b  Percentage change 2010-2020 in dairy cows and suckler cows ("other cows")
   for the same counties, with the change in total cattle as a black tick.

Input: data/inputs/baseline/00_CSO_Census_County_Livestock_2010_2020.csv
Run from the repository root.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DAIRY, SUCK = "#0072B2", "#E69F00"
SRC = Path("data/inputs/baseline/00_CSO_Census_County_Livestock_2010_2020.csv")


def load():
    d = pd.read_csv(SRC)
    w = d.pivot_table(index="COUNTY", columns="CENSUS_YEAR",
                      values=["TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW"])
    out = pd.DataFrame(index=w.index)
    for y in (2010, 2020):
        out[f"DS{y}"] = 100 * w["DAIRY_COW"][y] / (w["DAIRY_COW"][y] + w["OTHER_COW"][y])
    for c, k in (("DAIRY_COW", "dD"), ("OTHER_COW", "dS"), ("TOTAL_CATTLE", "dT")):
        out[k] = 100 * (w[c][2020] / w[c][2010] - 1)
    nat = w.sum()
    natv = {"DS2010": 100 * nat["DAIRY_COW"][2010] / (nat["DAIRY_COW"][2010] + nat["OTHER_COW"][2010]),
            "DS2020": 100 * nat["DAIRY_COW"][2020] / (nat["DAIRY_COW"][2020] + nat["OTHER_COW"][2020])}
    for c, k in (("DAIRY_COW", "dD"), ("OTHER_COW", "dS"), ("TOTAL_CATTLE", "dT")):
        natv[k] = 100 * (nat[c][2020] / nat[c][2010] - 1)
    if len(out) != 26:
        raise AssertionError(f"expected 26 counties, found {len(out)}")
    return out.sort_values("DS2020"), natv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=Path("reporting/paper1/figures/F_county_census_change_2010_2020"))
    a = ap.parse_args()
    d, nat = load()
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 7.5, "axes.titlesize": 8.5, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.linewidth": 0.6,
                         "pdf.fonttype": 42, "hatch.linewidth": 0.4})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 5.0), sharey=True,
                                 gridspec_kw={"width_ratios": [1, 1.15]})
    y = np.arange(len(d))
    # a dumbbell
    a1.hlines(y, d.DS2010, d.DS2020, color="#9E9E9E", lw=1.2, zorder=1)
    a1.scatter(d.DS2010, y, s=22, facecolor="white", edgecolor=DAIRY, lw=1, zorder=2, label="2010")
    a1.scatter(d.DS2020, y, s=22, color=DAIRY, zorder=3, label="2020")
    a1.axvline(50, color="#BDBDBD", lw=0.6, ls=(0, (3, 2)))
    a1.set_yticks(y)
    a1.set_yticklabels(d.index)
    a1.set_xlim(0, 100)
    a1.set_xlabel("Dairy share of adult cows (%)\n← suckler-oriented        dairy-oriented →")
    a1.set_ylim(-2.6, len(d) - 0.4)
    a1.legend(loc="center right", bbox_to_anchor=(1.0, 0.35), frameon=False, fontsize=6.6, handletextpad=0.2)
    a1.set_title("a   Every county moved towards dairy", loc="left", fontweight="bold")
    a1.text(1, -1.5, f"State: {nat['DS2010']:.0f}% → {nat['DS2020']:.0f}%",
            va="center", fontsize=6.6, fontweight="bold")
    a1.xaxis.grid(True, color="#EEEEEE", lw=0.5)
    a1.set_axisbelow(True)
    # b paired change bars
    h = 0.38
    a2.barh(y + h / 2, d.dD, height=h, color=DAIRY, label="Dairy cows", zorder=2)
    a2.barh(y - h / 2, d.dS, height=h, color=SUCK, hatch="\\\\\\\\", edgecolor="white",
            lw=0, label="Suckler cows", zorder=2)
    a2.scatter(d.dT, y, marker="|", s=60, color="black", lw=1.4, zorder=3,
               label="Total cattle")
    a2.axvline(0, color="black", lw=0.6)
    a2.set_xlabel("Change 2010–2020 (%)")
    a2.xaxis.grid(True, color="#EEEEEE", lw=0.5)
    a2.set_axisbelow(True)
    a2.legend(loc="lower right", bbox_to_anchor=(1.0, 0.0), frameon=False, fontsize=6.4, ncol=3, columnspacing=0.8, handlelength=1.2)
    a2.set_title("b   Dairy herds grew, suckler herds shrank", loc="left", fontweight="bold")
    a2.text(-40, -0.9, f"State: dairy {nat['dD']:+.0f}%, suckler {nat['dS']:+.0f}%, "
            f"cattle {nat['dT']:+.0f}%", va="center", fontsize=6.6, fontweight="bold")
    a2.tick_params(axis="y", length=0)
    fig.text(0.01, 0.005, "Source: CSO Census of Agriculture 2010 and 2020, county "
             "final results (observed values).", fontsize=6.0, color="#555555")
    fig.subplots_adjust(left=0.1, right=0.98, top=0.94, bottom=0.13, wspace=0.08)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(a.out.with_suffix(f".{ext}"), dpi=600 if ext == "png" else None,
                    facecolor="white")
    print("saved", a.out)
    print(d.round(1).to_string()); print({k: round(v, 1) for k, v in nat.items()})


if __name__ == "__main__":
    main()
