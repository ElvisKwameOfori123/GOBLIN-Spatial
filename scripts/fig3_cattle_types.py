#!/usr/bin/env python
"""Figure 3 and Table 4. Cattle-system types: where they are and what they contain (2025).

Typology (fixed thresholds; eligible EDs have >= 10 adult cows and >= 20 followers):
    breeding orientation  Suckler: dairy share of adult cows < 40%; Mixed: 40-60%; Dairy: > 60%
    follower intensity    lower: <= 1.9 followers per adult cow; higher: > 1.9

a  WHERE: the six types across EDs, with a compact key (rows: orientation; light/dark:
   follower intensity).
b  BROAD COMPOSITION: whole-herd composition of each type as 100% bars (dairy cows, suckler
   cows, bulls, DxD, DxB and BxB followers).
c  FULL BIOLOGY: the complete 21-cohort profile of each type in a 3 x 2 grid (rows: suckler,
   mixed, dairy; columns: lower, higher follower intensity). Shared x-axis (% of all cattle in
   the type) capped at 14%; bars beyond the cap carry a break mark and their value.

Values are cohort head summed over the type's EDs divided by total cattle of those EDs.
Writes:
    reporting/paper1/figures/Fig3_cattle_system_types.{png,pdf}
    reporting/paper1/tables/T4_cattle_system_types_2025.csv
    reporting/paper1/tables/S_cattle_type_cohort_shares_2025.csv  (all 126 profile values)
    reporting/paper1/tables/S_cattle_types_2020_2025_crosstab.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch, Rectangle

import paper1_style as S

XCAP = 14.0
GROUPS = [  # (label, column or origin, colour, hatch, text colour on bar)
    ("Dairy cows", "dairy_cows", S.DARK_DAIRY, None, "white"),
    ("Suckler cows", "suckler_cows", S.DARK_SUCKLER, None, "white"),
    ("Bulls", "bulls", S.BULL, None, "black"),
    ("DxD followers", "DxD", S.DAIRY, None, "white"),
    ("DxB followers", "DxB", S.DXB, "////", "black"),
    ("BxB followers", "BxB", S.SUCKLER, None, "black"),
]
ORIGIN_COLOUR = {"DxD": (S.DAIRY, None), "DxB": (S.DXB, "////"), "BxB": (S.SUCKLER, None)}
ADULT_COLOUR = {"dairy_cows": S.DARK_DAIRY, "suckler_cows": S.DARK_SUCKLER, "bulls": S.BULL}
SHORT_LABEL = {"Dairy cows": "Dairy cows", "Suckler cows": "Suckler cows", "Bulls": "Bulls"}


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


def profiles(d: pd.DataFrame) -> pd.DataFrame:
    """Rows = 21 cohorts (display order), columns = six types, values = % of the type's cattle."""
    e = d[d.TYPE.notna()]
    cols = [c for _, _, c in S.cohorts21()]
    tot = e.groupby("TYPE")[cols].sum()
    share = 100 * tot.div(e.groupby("TYPE").TOTAL_CATTLE.sum(), axis=0)
    if (share.sum(axis=1) - 100).abs().max() > 0.01:
        raise ValueError("cohort shares do not close to 100%")
    return share.reindex(S.TYPE_ORDER).T


def herd_groups(P: pd.DataFrame) -> pd.DataFrame:
    """Six broad groups (% of cattle) from the 21-cohort profile."""
    out = {}
    for lab, key, *_ in GROUPS:
        if key in ADULT_COLOUR:
            out[lab] = P.loc[key]
        else:
            rows = [c for _, grp, c in S.cohorts21() if grp == key]
            out[lab] = P.loc[rows].sum()
    return pd.DataFrame(out)  # index = types


# ------------------------------------------------------------------ panels
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
    lg = ax.inset_axes([-0.02, 0.72, 0.32, 0.2])
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


def panel_bars(ax, G):
    plt.rcParams["hatch.color"] = "#1F4E79"
    y = np.arange(len(S.TYPE_ORDER))[::-1]
    left = np.zeros(len(y))
    for lab, _, colr, h, tc in GROUPS:
        v = G[lab].reindex(S.TYPE_ORDER).to_numpy()
        ax.barh(y, v, left=left, color=colr, hatch=h, edgecolor="white", lw=0.5, height=0.72)
        for yi, li, vi in zip(y, left, v):
            if vi >= 9:
                ax.text(li + vi / 2, yi, f"{vi:.0f}", ha="center", va="center", fontsize=5.6, color=tc)
        left += v
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(y) - 0.4)
    ax.set_yticks(y)
    ax.set_yticklabels(S.TYPE_SHORT, fontsize=6.4)
    ax.tick_params(axis="y", length=0, pad=9)
    for yi, t in zip(y, S.TYPE_ORDER):  # type colour chip beside each label
        ax.add_patch(Rectangle((-3.2, yi - 0.3), 2.2, 0.6, color=S.TYPE_COLOURS[t], lw=0,
                               clip_on=False))
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=5.8, length=2)
    ax.set_xlabel("% of all cattle in the type", fontsize=6.0, labelpad=1)
    ax.spines["left"].set_visible(False)
    hs = [Patch(facecolor=c, hatch=h, edgecolor="white", label=lab) for lab, _, c, h, _ in GROUPS]
    ax.legend(handles=hs, loc="upper center", bbox_to_anchor=(0.45, -0.27), ncol=3, frameon=False,
              fontsize=5.8, handlelength=1.0, columnspacing=0.9, borderaxespad=0.0)


def profile_layout():
    """y position of each of the 21 cohorts: F/M pairs touch, ages and origins are separated."""
    pos, y, prev_grp, prev_age = [], 0.0, None, None
    for lab, grp, col in S.cohorts21():
        age = lab.split()[-2] if grp != "Adults" else lab
        if prev_grp is not None:
            if grp != prev_grp:
                y += 1.4
            elif grp == "Adults" or age != prev_age:
                y += 0.35
        pos.append(-y)
        y += 1.0
        prev_grp, prev_age = grp, age
    return np.array(pos)


def mini_profile(ax, values: pd.Series, title: str, colour: str, labels: bool):
    rows = S.cohorts21()
    ypos = profile_layout()
    for (lab, grp, col), yy in zip(rows, ypos):
        v = float(values[col])
        if grp == "Adults":
            colr, h, alpha = ADULT_COLOUR[col], None, 1.0
        else:
            colr, h = ORIGIN_COLOUR[grp]
            alpha = 1.0 if " female " in lab else 0.55
        ax.barh(yy, min(v, XCAP), color=colr, hatch=h, alpha=alpha, edgecolor="white", lw=0.15,
                height=1.0)
        if v > XCAP:
            ax.plot([XCAP - 1.0, XCAP - 0.6], [yy - 0.5, yy + 0.5], color="white", lw=1.3,
                    solid_capstyle="butt")
            ax.text(XCAP + 0.3, yy, f"{v:.0f}", va="center", ha="left", fontsize=5.4, color=S.TEXT)
    ax.set_xlim(0, XCAP)
    ax.set_ylim(ypos.min() - 0.8, 0.8)
    ax.set_yticks([])
    ax.set_xticks([0, 5, 10])
    ax.tick_params(axis="x", labelsize=5.4, length=1.5, pad=1)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True, color="#EAEAEA", lw=0.4)
    ax.set_axisbelow(True)
    ax.text(0.0, 1.03, "■", transform=ax.transAxes, color=colour, fontsize=8, va="bottom", ha="left")
    ax.text(0.07, 1.03, title, transform=ax.transAxes, fontsize=6.3, va="bottom", ha="left",
            color=S.TEXT)
    if labels:
        tr = ax.get_yaxis_transform()
        for (lab, grp, col), yy in zip(rows, ypos):
            if grp == "Adults":
                ax.text(-0.02, yy, {"dairy_cows": "Dairy cows", "suckler_cows": "Suckler cows",
                                    "bulls": "Bulls"}[col],
                        transform=tr, ha="right", va="center", fontsize=5.3, color=S.TEXT)
            elif " female " in lab:  # one age label per F/M pair
                age = lab.split()[-2].replace("-", "–")
                ax.text(-0.02, yy - 0.5, f"{age} yr", transform=tr, ha="right", va="center",
                        fontsize=5.3, color=S.TEXT)
        for grp in S.ORIGINS:
            ys = [yy for (lab, g, _), yy in zip(rows, ypos) if g == grp]
            ax.plot([-0.30, -0.30], [min(ys) - 0.4, max(ys) + 0.4], transform=tr, color="#9E9E9E",
                    lw=0.6, clip_on=False)
            ax.text(-0.34, np.mean(ys), grp, transform=tr, ha="right", va="center", fontsize=5.8,
                    fontweight="bold", color={"DxD": S.DAIRY, "DxB": "#2C7FB8", "BxB": "#B36B00"}[grp])


def panel_profiles(fig, spec, P):
    sub = spec.subgridspec(3, 2, hspace=0.24, wspace=0.10)
    axes = []
    for i, b in enumerate(("Suckler", "Mixed", "Dairy")):
        for j, f in enumerate(("lower-follower", "higher-follower")):
            t = f"{b}, {f}"
            ax = fig.add_subplot(sub[i, j])
            mini_profile(ax, P[t], f"{S.TYPE_SHORT[S.TYPE_ORDER.index(t)]}  {t}",
                         S.TYPE_COLOURS[t], labels=(j == 0))
            if i < 2:
                ax.tick_params(axis="x", labelbottom=False)
            axes.append(ax)
    for ax in axes[-2:]:
        ax.set_xlabel("% of all cattle in the type", fontsize=5.9, labelpad=1)
    return axes


def main():
    S.style()
    d25 = typed(2025)
    t4 = table4(d25)
    P = profiles(d25)
    G = herd_groups(P)
    if (G.sum(axis=1) - 100).abs().max() > 0.01:
        raise ValueError("broad groups do not close to 100%")
    S.TAB.mkdir(parents=True, exist_ok=True)
    t4.round(1).to_csv(S.TAB / "T4_cattle_system_types_2025.csv")
    P.round(2).set_axis([lab for lab, _, _ in S.cohorts21()], axis=0).to_csv(
        S.TAB / "S_cattle_type_cohort_shares_2025.csv")
    d20 = typed(2020)
    both = d25[["CSOED", "TYPE"]].merge(d20[["CSOED", "TYPE"]], on="CSOED", suffixes=("_2025", "_2020"))
    both = both.dropna()
    pd.crosstab(both.TYPE_2020, both.TYPE_2025).reindex(index=S.TYPE_ORDER, columns=S.TYPE_ORDER).to_csv(
        S.TAB / "S_cattle_types_2020_2025_crosstab.csv")
    print(t4.round(1).to_string())
    print(G.round(1).to_string())

    fig = plt.figure(figsize=(7.4, 7.6))
    left = fig.add_gridspec(2, 1, height_ratios=[1, 0.34], hspace=0.17, left=0.055, right=0.44,
                            top=0.955, bottom=0.13)
    right = fig.add_gridspec(1, 1, left=0.575, right=0.965, top=0.915, bottom=0.05)
    axm = fig.add_subplot(left[0])
    panel_map(axm, d25)
    axm.set_anchor("N")
    axb = fig.add_subplot(left[1])
    panel_bars(axb, G)
    axes = panel_profiles(fig, right[0], P)
    fig.text(0.01, 0.985, "a   Six cattle-system types across EDs", fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.01, axb.get_position().y1 + 0.035, "b   Whole-herd composition", fontsize=8.5,
             fontweight="bold", va="bottom")
    fig.text(0.49, 0.985, "c   Complete 21-cohort profile of each type", fontsize=8.5,
             fontweight="bold", va="top")
    fig.text(0.49, 0.962, "solid = female, light = male; bars beyond 14% are broken and labelled",
             fontsize=5.8, color="#555555", va="top")
    S.save(fig, "Fig3_cattle_system_types")


if __name__ == "__main__":
    main()
