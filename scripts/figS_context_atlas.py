#!/usr/bin/env python
"""Supplementary figure. ED context atlas: three context maps and the six types across five contexts (ranges).

a  Three ED context maps (2025): sheep per farmed ha, cereal share of farmed area and
   Standard Output per farmed ha. No further cattle maps (cattle are treated in Figure 3).
b  The six cattle-system types of Figure 3 across five contexts: sheep per farmed ha, cereal
   share, average holding size, Standard Output per farmed ha and average holder age.
   Dot = ED median of the type; line = ED P10-P90. Cereal row: most EDs record no cereal
   area, so the dot (diamond) is the type's pooled cereal share (total cereal ha / total
   farmed ha). Holding size and holder age are 2020 census values (the last observed).

Eligible EDs: >= 10 adult cows, >= 20 followers and >= 50 farmed ha.
Writes: reporting/paper1/figures/FigS_context_atlas.{png,pdf}
        reporting/paper1/tables/S_context_by_type_2025.csv
        reporting/paper1/tables/S_context_correlations_2025.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

import paper1_style as S

MIN_HA = 50
MAPS = [  # column, title, inner breaks, 6 colours, unit label for the key
    ("SHEEP_PER_FARMED_HA", "Sheep per farmed ha", [0.1, 0.5, 1, 2, 4],
     ["#F7FCF5", "#D3EECD", "#A1D99B", "#5DB96B", "#238B45", "#00592A"], ""),
    ("CEREAL_SHARE_FARMED_PCT", "Cereal share of farmed area", [1, 2.5, 5, 10, 25],
     ["#FBF8EF", "#EFE3C2", "#DCC48C", "#C2A15A", "#9C7A2F", "#6B5214"], "%"),
    ("SO_PER_FARMED_HA", "Standard Output per farmed ha", [1000, 1500, 2000, 2500, 3000],
     ["#F7F7F7", "#D9D9D9", "#BDBDBD", "#969696", "#636363", "#303030"], "€ thousand"),
]
ROWS = [  # column, label, unit, statistic
    ("SHEEP_PER_FARMED_HA", "Sheep per ha", "head per farmed ha", "median"),
    ("CEREAL_SHARE_FARMED_PCT", "Cereal share", "% of farmed area", "pooled"),
    ("AVERAGE_SIZE_OF_HOLDINGS", "Holding size (2020)", "ha", "median"),
    ("SO_PER_FARMED_HA", "Standard Output", "€ per farmed ha", "median"),
    ("AVERAGE_AGE_OF_HOLDER", "Holder age (2020)", "years", "median"),
]


def load() -> pd.DataFrame:
    e = pd.read_csv(S.H / "ed_year.csv", low_memory=False)
    d = e[e.YEAR == S.YEAR].set_index("CSOED").copy()
    d20 = e[e.YEAR == 2020].set_index("CSOED")
    for c in ("AVERAGE_SIZE_OF_HOLDINGS", "AVERAGE_AGE_OF_HOLDER"):
        d[c] = d20[c].reindex(d.index)
    d = d.reset_index()
    d["CSOED"] = d.CSOED.astype(str)
    d["ELIGIBLE"] = (d.ADULT_COWS >= S.MIN_COWS) & (d.FOLLOWER_TOTAL >= S.MIN_FOLLOWERS)
    d["TYPE"] = S.cattle_type(d)
    d.loc[d.AREA_FARMED < MIN_HA, "TYPE"] = np.nan
    return d


def fmt(v, unit):
    return f"{v / 1000:g}" if unit == "€ thousand" else f"{v:g}"


def map_panel(ax, eds, d, col, title, breaks, colours, unit):
    g = eds.merge(d[["CSOED", col, "AREA_FARMED"]], on="CSOED", how="left", validate="one_to_one")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    ok = g[col].notna() & (g.AREA_FARMED >= MIN_HA)
    cls = np.digitize(g.loc[ok, col], breaks)
    g.loc[ok].plot(ax=ax, color=[colours[i] for i in cls], edgecolor="none")
    county.boundary.plot(ax=ax, color="#9E9E9E", lw=0.25)
    ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_title(title, fontsize=7.0, loc="left", pad=3, color=S.TEXT)
    cax = ax.inset_axes([0.08, -0.05, 0.84, 0.035])
    cax.imshow(np.arange(6)[None, :], cmap=ListedColormap(colours), aspect="auto", extent=(0, 6, 0, 1))
    cax.set_yticks([]); cax.set_xticks(range(1, 6))
    cax.set_xticklabels([fmt(b, unit) for b in breaks], fontsize=5.6)
    cax.tick_params(length=1.5, width=0.4, pad=1)
    for s in cax.spines.values():
        s.set_linewidth(0.3)
    if unit:
        cax.text(1.02, 0.5, unit, transform=cax.transAxes, fontsize=5.4, va="center", color="#555555")


def type_stats(d: pd.DataFrame) -> pd.DataFrame:
    e = d[d.TYPE.notna()]
    rows = []
    for col, lab, unit, stat in ROWS:
        for t, x in e.groupby("TYPE"):
            v = x[col].dropna()
            centre = (100 * x.TOTAL_CEREALS.sum() / x.AREA_FARMED.sum()) if stat == "pooled" else v.median()
            rows.append({"variable": lab, "unit": unit, "type": t, "statistic": stat, "centre": centre,
                         "p10": v.quantile(0.1), "p90": v.quantile(0.9), "EDs": len(v),
                         "EDs_zero_pct": 100 * (v == 0).mean()})
    return pd.DataFrame(rows)


def dot_panel(fig, spec, st):
    sub = spec.subgridspec(1, len(ROWS), wspace=0.16)
    y = np.arange(len(S.TYPE_ORDER))[::-1]
    for k, (col, lab, unit, stat) in enumerate(ROWS):
        ax = fig.add_subplot(sub[k])
        q = st[st.variable == lab].set_index("type").reindex(S.TYPE_ORDER)
        for yi, t in zip(y, S.TYPE_ORDER):
            c = S.TYPE_COLOURS[t]
            ax.plot([q.loc[t, "p10"], q.loc[t, "p90"]], [yi, yi], color=c, lw=1.6, solid_capstyle="round",
                    alpha=0.85)
            ax.plot(q.loc[t, "centre"], yi, marker="D" if stat == "pooled" else "o", ms=4.4,
                    mfc=c, mec=S.TEXT, mew=0.5, ls="none", zorder=3)
        ax.set_ylim(-0.6, len(y) - 0.4)
        ax.set_yticks(y)
        ax.set_yticklabels(S.TYPE_SHORT if k == 0 else [], fontsize=6.4)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=5.6, length=1.5, pad=1)
        ax.spines["left"].set_visible(False)
        ax.xaxis.grid(True, color="#EEEEEE", lw=0.4)
        ax.set_axisbelow(True)
        ax.set_title(lab, fontsize=6.4, loc="left", pad=3, color=S.TEXT)
        ax.set_xlabel(unit, fontsize=5.8, labelpad=1)
        lo = min(q.p10.min(), q.centre.min())
        hi = max(q.p90.max(), q.centre.max())
        pad = 0.06 * (hi - lo)
        ax.set_xlim(max(0, lo - pad) if lo >= 0 else lo - pad, hi + pad)
        if k == 0:
            for yi, t in zip(y, S.TYPE_ORDER):
                ax.annotate("", xy=(0, yi))
        if col == "SO_PER_FARMED_HA":
            ax.set_xticks([0, 1000, 2000, 3000])
            ax.set_xticklabels(["0", "1k", "2k", "3k"])


def correlations(d: pd.DataFrame) -> pd.DataFrame:
    e = d[d.TYPE.notna()]
    sig = ["DAIRY_SHARE_ADULT_PCT", "FOLLOWER_TO_ADULT_RATIO", "UNDER1_SHARE_FOLLOWERS_PCT",
           "CATTLE_PER_FARMED_HA"]
    ctx = [c for c, *_ in ROWS]
    out = []
    for a in sig + ctx:
        for b in ctx:
            if a == b:
                continue
            x = e[[a, b, "County"]].dropna()
            ra, rb = x.groupby("County")[a].rank(pct=True), x.groupby("County")[b].rank(pct=True)
            out.append({"a": a, "b": b, "n": len(x), "rho": x[a].rank().corr(x[b].rank()),
                        "rho_within_county": ra.corr(rb)})
    return pd.DataFrame(out)


def main():
    S.style()
    d = load()
    st = type_stats(d)
    st.round(2).to_csv(S.TAB / "S_context_by_type_2025.csv", index=False)
    correlations(d).round(3).to_csv(S.TAB / "S_context_correlations_2025.csv", index=False)
    print(st.pivot(index="type", columns="variable", values="centre").reindex(S.TYPE_ORDER).round(2).to_string())
    eds = S.model_eds()

    fig = plt.figure(figsize=(7.4, 5.9))
    top = fig.add_gridspec(1, 3, wspace=0.02, left=0.0, right=0.97, top=0.90, bottom=0.42)
    for i, (col, title, br, colours, unit) in enumerate(MAPS):
        map_panel(fig.add_subplot(top[i]), eds, d, col, title, br, colours, unit)
    low = fig.add_gridspec(1, 1, left=0.055, right=0.985, top=0.27, bottom=0.075)
    dot_panel(fig, low[0], st)
    fig.text(0.01, 0.985, "a   Agricultural geography, 2025", fontsize=8.5, fontweight="bold", va="top")
    fig.text(0.01, 0.345, "b   Contexts occupied by the six cattle-system types", fontsize=8.5,
             fontweight="bold", va="top")
    fig.text(0.01, 0.322, "Dot: ED median (diamond: pooled share of the type); line: ED P10–P90.",
             fontsize=5.9, color="#555555", va="top")
    S.save(fig, "FigS_context_atlas")


if __name__ == "__main__":
    main()
