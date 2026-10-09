#!/usr/bin/env python
"""Figure 2. National restructuring of Irish livestock systems, 2015-2025.

a  Total cattle, dairy cows, suckler cows and sheep, indexed to 2015 = 100.
b  Composition of the whole cattle population in 2015, 2020 and 2025 (100% bars):
   dairy cows, suckler cows, bulls, and DxD, DxB and BxB followers.

c  Observed change in the dairy share of adult cows by county, 2010-2020 Censuses of
   Agriculture (sequential scale anchored at 0 pp; every county increased).

Input: reporting/report_data/historical/national_year.csv
       data/inputs/baseline/00_CSO_Census_County_Livestock_2010_2020.csv
"""
from __future__ import annotations

# -----------------------------------------------------------------------------
# PAPER 1 REPORTING CODE
# This script is a reporting/visualisation layer only. It does not modify the
# GOBLIN-Spatial reconstruction or any frozen model inputs. All quantities are
# read from the release tables and are transformed only for plotting or tabular
# reporting. Comments below distinguish observed/control data from reconstructed
# quantities where that distinction matters for interpretation.
# -----------------------------------------------------------------------------

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import paper1_style as S

# 2020 is shown as the census anchor, but the figure tells the full 2015-2025 story.
START, CENSUS, END = 2015, 2020, 2025


def load() -> pd.DataFrame:
    """Load national annual release data and assert whole-herd accounting closure."""
    n = pd.read_csv(S.H / "national_year.csv").set_index("YEAR").loc[START:END]
    parts = n[["dairy_cows", "suckler_cows", "bulls", "DXD_FOLLOWERS", "DXB_FOLLOWERS",
               "BXB_FOLLOWERS"]].sum(axis=1)
    if (parts - n.TOTAL_CATTLE).abs().max() > 1:
        raise ValueError("cattle groups do not sum to TOTAL_CATTLE")
    return n


def panel_a(ax, n):
    """Panel a: official annual livestock controls indexed to 2015 = 100.

    Indexing makes divergent trajectories directly comparable without implying
    that species have similar absolute population sizes.
    """
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
    S.title(ax, "a", "Stable totals, diverging herds")


def panel_b(ax, n):
    """Panel b: whole-cattle composition in 2015, 2020 and 2025.

    Adult cow and bull totals close to the national account; DxD/DxB/BxB follower
    origin is the reconstructed component. Each annual bar sums to 100%.
    """
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
        ax.text(2.36, base[2] + v[2] / 2, lab, va="center", fontsize=6.4, color=S.TEXT)
        base = [b + vi for b, vi in zip(base, v)]
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{y}\n{n.loc[y, 'TOTAL_CATTLE'] / 1e6:.2f} m" for y in years], fontsize=6.4)
    ax.set_xlim(-0.45, 3.3)
    ax.set_ylim(0, 100)
    ax.set_ylabel("")
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=6.4)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    S.title(ax, "b", "Same size, new composition")


CTY_BREAKS = [5, 10, 15]
CTY_COLOURS = ["#DEEBF7", "#9ECAE1", "#4292C6", "#08519C"]


def county_change() -> pd.DataFrame:
    """Return *observed* county change in dairy share between the two censuses."""
    c = pd.read_csv("data/inputs/baseline/00_CSO_Census_County_Livestock_2010_2020.csv")
    c["DS"] = 100 * c.DAIRY_COW / (c.DAIRY_COW + c.OTHER_COW)
    p = c.pivot(index="COUNTY", columns="CENSUS_YEAR", values="DS")
    p["CHANGE_PP"] = p[2020] - p[2010]
    if len(p) != 26 or not (p.CHANGE_PP > 0).all():
        raise ValueError("expected 26 counties, all with a positive change")
    p.round(2).to_csv(S.TAB / "S_county_dairy_share_change_2010_2020.csv")
    return p


def census_county(name: str) -> str:
    """Normalise county names so census data join cleanly to frozen geometry."""
    n = name.replace(" County", "").replace(" City", "")
    if n in ("Dún Laoghaire-Rathdown", "Fingal", "South Dublin", "Dublin"):
        return "Dublin"
    if "Tipperary" in n:
        return "Tipperary"
    return n


def panel_c(ax, p):
    """Panel c: map observed county restructuring, not reconstructed ED change."""
    raw, _, land = S.land_and_counties()
    g = raw.copy()
    g["COUNTY"] = g.COUNTYNAME.map(census_county)
    g = g.dissolve(by="COUNTY", as_index=False).merge(p[["CHANGE_PP"]], left_on="COUNTY",
                                                      right_index=True, how="left", validate="one_to_one")
    if g.CHANGE_PP.isna().any():
        raise ValueError(f"unmatched counties: {g.COUNTY[g.CHANGE_PP.isna()].tolist()}")
    cls = np.digitize(g.CHANGE_PP, CTY_BREAKS)
    g.plot(ax=ax, color=[CTY_COLOURS[i] for i in cls], edgecolor="white", lw=0.6)
    S.fit_ireland(ax, right=0.30)
    S.vertical_key(ax, CTY_COLOURS, ["0–5", "5–10", "10–15", "≥ 15"], title="pp",
                   where=(0.80, 0.04, 0.055, 0.28), fontsize=6.0)
    lo, hi = p.CHANGE_PP.idxmin(), p.CHANGE_PP.idxmax()
    for name in (lo, hi):
        r = g[g.COUNTY == name].geometry.iloc[0].representative_point()
        ax.annotate(f"{name} {p.loc[name, 'CHANGE_PP']:+.1f}", xy=(r.x, r.y),
                    xytext=(r.x + (-170000 if name == hi else -190000), r.y + (-170000 if name == hi else 20000)),
                    fontsize=5.9, color=S.TEXT, arrowprops=dict(arrowstyle="-", lw=0.5, color="#555555"),
                    bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))
    S.title(ax, "c", "Dairy share rose\n      in every county")
    ax.text(0.0, -0.02, "Change in dairy share of adult cows,\n2010–2020 censuses (pp)", transform=ax.transAxes,
            fontsize=6.0, color="#555555", va="top")


def main():
    """Assemble Figure 2 and save the county-change data used by panel c."""
    n = load()
    S.style()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(7.4, 3.6), gridspec_kw={"width_ratios": [1.0, 0.95, 1.2]})
    panel_a(a, n)
    panel_b(b, n)
    panel_c(c, county_change())
    fig.subplots_adjust(left=0.065, right=0.995, top=0.87, bottom=0.14, wspace=0.56)
    S.save(fig, "Fig2_national_restructuring")


if __name__ == "__main__":
    main()
