#!/usr/bin/env python
"""Figure 4. Stable cattle numbers do not imply a stable cattle system (observed, 2010-2020).

Uses only census cells published in both the 2010 and 2020 Censuses of Agriculture, for EDs
with >= 10 adult cows in both years (S5_observed_restructuring_ed.csv). No reconstructed
values are used.

a  ED change in total cattle against change in the dairy share of adult cows. The shaded
   band marks a stable herd (|cattle change| <= 5%). Stable-herd EDs whose dairy share moved
   by >= 10 percentage points are coloured by direction.
b  Where those stable-herd EDs are: shift toward dairy (>= +10 pp), shift toward suckler
   (<= -10 pp) or limited change; all other EDs are faded.

Writes: reporting/paper1/figures/Fig4_observed_restructuring.{png,pdf}
        reporting/paper1/tables/S_stable_herd_eds_2010_2020.csv
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import paper1_style as S
from goblin_spatial.soil.overlay import canonical_csoed

STABLE_PCT, SHIFT_PP = 5.0, 10.0
TO_DAIRY, TO_SUCKLER, LIMITED = S.DAIRY, S.SUCKLER, "#6E6E6E"
CHANGED, NOT_COMPARABLE = "#D9D9D9", S.GREY_LAND


def ed_key(k: str) -> str:
    """Canonical ED key; merged EDs ("a/b") are order-independent."""
    return "/".join(sorted(str(canonical_csoed(k)).split("/")))


def spearman(x, y) -> float:
    return pd.Series(x).rank().corr(pd.Series(y).rank())


def load() -> pd.DataFrame:
    p = pd.read_csv(S.TAB / "S5_observed_restructuring_ed.csv", dtype={"KEY": str})
    p["STABLE"] = p.CATTLE_CHANGE_PCT.abs() <= STABLE_PCT
    p["CLASS"] = np.select(
        [p.STABLE & (p.DS_CHANGE_PP >= SHIFT_PP), p.STABLE & (p.DS_CHANGE_PP <= -SHIFT_PP), p.STABLE],
        ["to_dairy", "to_suckler", "limited"], "changed")
    shifted = p.CLASS.isin(["to_dairy", "to_suckler"])
    if shifted.sum() != p.STABLE_HERD_SHIFTED_SYSTEM.sum():
        raise ValueError("shift rule disagrees with S5 table")
    p["KEY_C"] = p.KEY.map(ed_key)
    return p


def panel_a(ax, p):
    rho_all = spearman(p.CATTLE_CHANGE_PCT, p.DS_CHANGE_PP)
    q = p[~p.ZERO_DAIRY_BOTH]
    rho_dairy = spearman(q.CATTLE_CHANGE_PCT, q.DS_CHANGE_PP)
    x = p.CATTLE_CHANGE_PCT.clip(-60, 100)
    ax.axvspan(-STABLE_PCT, STABLE_PCT, color="#E8E8E8", lw=0, zorder=0)
    ax.axhline(0, color="#9E9E9E", lw=0.6, zorder=1)
    for v in (-SHIFT_PP, SHIFT_PP):
        ax.axhline(v, color="#BDBDBD", lw=0.5, ls=(0, (3, 2)), zorder=1)
    base = p.CLASS.isin(["changed", "limited"])
    ax.scatter(x[base], p.DS_CHANGE_PP[base], s=4, color="#A6A6A6", alpha=0.5, lw=0, zorder=2)
    for cls, c in (("to_dairy", TO_DAIRY), ("to_suckler", TO_SUCKLER)):
        m = p.CLASS == cls
        ax.scatter(x[m], p.DS_CHANGE_PP[m], s=9, color=c, edgecolor="white", lw=0.2, zorder=3)
    st = p[p.STABLE]
    n_sh = int(p.CLASS.isin(["to_dairy", "to_suckler"]).sum())
    ax.annotate(f"{len(st):,} EDs within ±{STABLE_PCT:.0f}% cattle change\n"
                f"{n_sh} ({100 * n_sh / len(st):.0f}%) shifted ≥ {SHIFT_PP:.0f} pp in breeding orientation\n"
                f"{int((p.CLASS == 'to_dairy').sum())} toward dairy, "
                f"{int((p.CLASS == 'to_suckler').sum())} toward suckler",
                xy=(STABLE_PCT, 30), xytext=(14, 50), fontsize=6.1, color=S.TEXT, va="top",
                arrowprops=dict(arrowstyle="-", color="#555555", lw=0.5))
    ax.text(98, -54, f"n = {len(p):,} EDs\nSpearman ρ = {rho_all:.2f}\n"
            f"ρ = {rho_dairy:.2f} excluding {int(p.ZERO_DAIRY_BOTH.sum())} EDs\nwith no dairy cows in either census",
            ha="right", va="bottom", fontsize=5.9, color="#555555")
    ax.set_xlim(-62, 102)
    ax.set_ylim(-56, 56)
    ax.set_xlabel("Change in total cattle, 2010–2020 (%)")
    ax.set_ylabel("Change in dairy share of adult cows, 2010–2020 (pp)")
    ax.yaxis.grid(False)
    S.title(ax, "a", "Stable herds, shifting systems")
    return rho_all, rho_dairy


def panel_b(ax, lax, p):
    eds = S.model_eds().copy()
    eds["KEY_C"] = eds.CSOED.map(ed_key)
    g = eds.merge(p[["KEY_C", "CLASS"]].drop_duplicates("KEY_C"), on="KEY_C", how="left")
    g["CLASS"] = g.CLASS.fillna("not_comparable")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=NOT_COMPARABLE, edgecolor="none")
    colours = {"not_comparable": NOT_COMPARABLE, "changed": CHANGED, "limited": LIMITED,
               "to_suckler": TO_SUCKLER, "to_dairy": TO_DAIRY}
    for cls in ["not_comparable", "changed", "limited", "to_suckler", "to_dairy"]:
        part = g[g.CLASS == cls]
        if len(part):
            if cls in ("to_suckler", "to_dairy"):  # outline so small EDs stay visible
                part.plot(ax=ax, color=colours[cls], edgecolor=S.TEXT, lw=0.35, zorder=4)
            else:
                part.plot(ax=ax, color=colours[cls], edgecolor="white",
                          lw=0.05 if cls in ("not_comparable", "changed") else 0.15)
    county.boundary.plot(ax=ax, color="#4A4A4A", lw=0.3)
    ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlabel(""); ax.set_ylabel("")
    S.title(ax, "b", f"Where stable-herd EDs shifted")
    n = g.CLASS.value_counts()
    hs = [Patch(facecolor=TO_DAIRY, edgecolor=S.TEXT, lw=0.35, label=f"Toward dairy\n≥ +{SHIFT_PP:.0f} pp ({n.get('to_dairy', 0)})"),
          Patch(facecolor=TO_SUCKLER, edgecolor=S.TEXT, lw=0.35, label=f"Toward suckler\n≤ −{SHIFT_PP:.0f} pp ({n.get('to_suckler', 0)})"),
          Patch(facecolor=LIMITED, label=f"Limited change\n< {SHIFT_PP:.0f} pp ({n.get('limited', 0)})"),
          Patch(facecolor=CHANGED, label=f"Cattle changed\n> {STABLE_PCT:.0f}% ({n.get('changed', 0):,})"),
          Patch(facecolor=NOT_COMPARABLE, edgecolor="#BDBDBD", lw=0.3,
                label=f"Not comparable\n({n.get('not_comparable', 0):,})")]
    lax.axis("off")
    lax.legend(handles=hs[:3], loc="upper left", bbox_to_anchor=(0.0, 0.80), frameon=False,
               fontsize=5.8, handlelength=1.1, alignment="left",
               title=f"Stable cattle\nnumbers (±{STABLE_PCT:.0f}%)", title_fontsize=6.1, labelspacing=0.7)
    lax.add_artist(lax.get_legend())
    lax.legend(handles=hs[3:], loc="upper left", bbox_to_anchor=(0.0, 0.36), frameon=False,
               fontsize=5.8, handlelength=1.1, alignment="left", title="Other EDs", title_fontsize=6.1, labelspacing=0.7)
    return g


def main():
    S.style()
    p = load()
    fig = plt.figure(figsize=(7.4, 3.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 0.9, 0.36], wspace=0.1)
    ra, rd = panel_a(fig.add_subplot(gs[0, 0]), p)
    g = panel_b(fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2]), p)
    fig.text(0.01, 0.005, "Census cells published in both the 2010 and 2020 Censuses of Agriculture; "
             "EDs with ≥ 10 adult cows in both years.\nNot comparable: suppressed in either census or < 10 adult cows. "
             "Cattle change above 100% drawn at 100%.",
             fontsize=5.6, color="#555555", va="bottom")
    fig.subplots_adjust(left=0.075, right=0.99, top=0.91, bottom=0.15)
    S.save(fig, "Fig4_observed_restructuring")
    out = p.loc[p.STABLE, ["KEY", "County", "ED_NAME", "CATTLE_CHANGE_PCT", "DS10", "DS20",
                           "DS_CHANGE_PP", "CLASS"]].sort_values("DS_CHANGE_PP", ascending=False)
    out.round(2).to_csv(S.TAB / "S_stable_herd_eds_2010_2020.csv", index=False)
    print(out.CLASS.value_counts().to_string(), f"\nrho all {ra:.3f}, rho excl zero-dairy {rd:.3f}")
    print("mapped classes:", g.CLASS.value_counts().to_dict())


if __name__ == "__main__":
    main()
