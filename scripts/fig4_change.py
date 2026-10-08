#!/usr/bin/env python
"""Figure 4. Stable cattle numbers do not imply a stable cattle system (observed, 2010-2020).

Uses only census cells published in both the 2010 and 2020 Censuses of Agriculture, for EDs
with >= 10 adult cows in both years (S5_observed_restructuring_ed.csv). No reconstructed
values are used.

a  ED change in total cattle against change in the dairy share of adult cows. The shaded
   band marks a stable herd (|cattle change| <= 5%). Stable-herd EDs whose dairy share moved
   by >= 10 percentage points are coloured by direction.
b  Where those stable-herd EDs are: shift toward dairy (>= +10 pp), shift toward suckler
   (<= -10 pp) or limited change; all other EDs form the grey background.
   Cattle change above 100% is drawn at 100%. Methodological detail belongs in the caption.

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
TO_DAIRY, TO_SUCKLER, LIMITED = S.DAIRY, S.SUCKLER, "#8C8C8C"
BACKGROUND = "#EBEBEB"


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
    ax.axvspan(-STABLE_PCT, STABLE_PCT, color="#EDEDED", lw=0, zorder=0)
    ax.axhline(0, color="#BDBDBD", lw=0.5, zorder=1)
    base = p.CLASS.isin(["changed", "limited"])
    ax.scatter(x[base], p.DS_CHANGE_PP[base], s=4, color="#BDBDBD", alpha=0.6, lw=0, zorder=2)
    for cls, c in (("to_dairy", TO_DAIRY), ("to_suckler", TO_SUCKLER)):
        m = p.CLASS == cls
        ax.scatter(x[m], p.DS_CHANGE_PP[m], s=9, color=c, lw=0, zorder=3)
    st = p[p.STABLE]
    n_sh = int(p.CLASS.isin(["to_dairy", "to_suckler"]).sum())
    ax.text(9, 52, f"{n_sh} of {len(st)} stable-herd EDs changed ≥ {SHIFT_PP:.0f} pp", fontsize=6.4,
            fontweight="bold", color=S.TEXT, va="top")
    ax.text(9, 46, f"{int((p.CLASS == 'to_dairy').sum())} toward dairy", fontsize=6.4, color=TO_DAIRY,
            fontweight="bold", va="top")
    ax.text(9, -28, f"{int((p.CLASS == 'to_suckler').sum())} toward suckler", fontsize=6.4,
            color="#B36B00", fontweight="bold", va="center")
    ax.text(99, -52, f"ρ = {rho_all:.2f}\nρ = {rho_dairy:.2f} excluding zero-dairy EDs", ha="right",
            va="bottom", fontsize=5.9, color="#7F7F7F")
    ax.text(0, -56, f"±{STABLE_PCT:.0f}%", ha="center", va="bottom", fontsize=5.6, color="#7F7F7F")
    ax.set_xlim(-62, 102)
    ax.set_ylim(-57, 56)
    ax.set_xlabel("Change in total cattle, 2010–2020 (%)")
    ax.set_ylabel("Change in dairy share of adult cows (pp)")
    S.title(ax, "a", "Stable herds, shifting systems")
    return rho_all, rho_dairy


def panel_b(ax, p):
    eds = S.model_eds().copy()
    eds["KEY_C"] = eds.CSOED.map(ed_key)
    g = eds.merge(p[["KEY_C", "CLASS"]].drop_duplicates("KEY_C"), on="KEY_C", how="left")
    _, county, land = S.land_and_counties()
    land.plot(ax=ax, color=BACKGROUND, edgecolor="none")
    county.boundary.plot(ax=ax, color="#BDBDBD", lw=0.3)
    for cls, c in (("limited", LIMITED), ("to_suckler", TO_SUCKLER), ("to_dairy", TO_DAIRY)):
        part = g[g.CLASS == cls]
        part.plot(ax=ax, color=c, edgecolor=c, lw=0.3, zorder=3)
    ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlabel(""); ax.set_ylabel("")
    S.title(ax, "b", "Where stable-herd EDs changed")
    n = g.CLASS.value_counts()
    hs = [Patch(facecolor=TO_DAIRY, label=f"Toward dairy ({n.get('to_dairy', 0)})"),
          Patch(facecolor=TO_SUCKLER, label=f"Toward suckler ({n.get('to_suckler', 0)})"),
          Patch(facecolor=LIMITED, label=f"Change < {SHIFT_PP:.0f} pp ({n.get('limited', 0)})"),
          Patch(facecolor=BACKGROUND, label="All other EDs")]
    ax.legend(handles=hs, loc="upper left", bbox_to_anchor=(-0.02, 0.98), frameon=False,
              fontsize=6.2, handlelength=1.0, title=f"Stable-herd EDs (±{STABLE_PCT:.0f}%)",
              title_fontsize=6.4, alignment="left")
    return g


def main():
    S.style()
    p = load()
    fig = plt.figure(figsize=(7.4, 3.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1], wspace=0.08)
    ra, rd = panel_a(fig.add_subplot(gs[0, 0]), p)
    g = panel_b(fig.add_subplot(gs[0, 1]), p)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.92, bottom=0.12)
    S.save(fig, "Fig4_observed_restructuring")
    out = p.loc[p.STABLE, ["KEY", "County", "ED_NAME", "CATTLE_CHANGE_PCT", "DS10", "DS20",
                           "DS_CHANGE_PP", "CLASS"]].sort_values("DS_CHANGE_PP", ascending=False)
    out.round(2).to_csv(S.TAB / "S_stable_herd_eds_2010_2020.csv", index=False)
    print(out.CLASS.value_counts().to_string(), f"\nrho all {ra:.3f}, rho excl zero-dairy {rd:.3f}")
    print("mapped classes:", g.CLASS.value_counts().to_dict())


if __name__ == "__main__":
    main()
