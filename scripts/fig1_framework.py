#!/usr/bin/env python
"""Figure 1. GOBLIN-Spatial: evidence, reconstruction and outputs.

a  Evidence hierarchy and reconstruction stages (schematic).
b  The 21-cohort cattle population represented in every ED.
c  Study geography: 2,857 model Electoral Divisions and the 46 EPA WFD catchments.

Run from the repository root after scripts/build_historical_release.py.
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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch

import paper1_style as S

# Panel a uses colour only to distinguish the *role* of each evidence source.
# These colours do not imply relative importance or data quality.
ROLE = {  # role colour (light fills, colour-blind safe)
    "Spatial anchor": "#CFE3F2",
    "Annual control": "#FCE2B8",
    "Composition signal": "#D5EBDD",
    "Biological / value coefficient": "#E6E0F0",
}
SOURCES = [
    ("CSO Census of Agriculture 2010, 2020 (ED)", "Spatial anchor"),
    ("CSO annual cattle (county), sheep, land (region)", "Annual control"),
    ("DAFM AIM cattle records 2020 (ED)", "Composition signal"),
    ("DAFM Sheep and Goat Census (county)", "Composition signal"),
    ("GOBLIN / COHORTS cohort relationships", "Biological / value coefficient"),
    ("IFS 2020 Standard Output coefficients", "Biological / value coefficient"),
]
STAGES = [
    "Census preparation (suppressed cells filled)",
    "Annual ED populations closed to official controls",
    "Age-sex composition (county margins, AIM age)",
    "Parental origin: 21 cattle and 10 sheep cohorts",
    "Land, farm structure and Standard Output",
]
OUTPUTS = [
    "2,857 EDs × 2015–2025\n(31,427 ED-years)",
    "Livestock-system signatures",
    "County, 46 WFD catchment\nand national views",
]


def box(ax, x, y, w, h, text, fc, fs=6.2, bold=False, ec="#7F7F7F"):
    """Draw one rounded schematic box; presentation helper only."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012",
                                fc=fc, ec=ec, lw=0.5))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=S.TEXT, linespacing=1.15)


def arrow(ax, x0, y0, x1, y1):
    """Draw a directional arrow between reconstruction stages."""
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=7,
                                 lw=0.6, color="#555555", shrinkA=0, shrinkB=0))


def panel_a(ax):
    """Panel a: evidence sources -> reconstruction stages -> reporting outputs."""
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    S.title(ax, "a", "Evidence, reconstruction and outputs")
    cols = [(0.01, 0.30, "Evidence"), (0.36, 0.33, "Reconstruction"), (0.75, 0.235, "Outputs")]
    for x, w, lab in cols:
        ax.text(x + w / 2, 0.97, lab, ha="center", va="bottom", fontsize=6.8, fontweight="bold",
                color="#555555")
    n = len(SOURCES)
    top, bot = 0.95, 0.06
    h = (top - bot) / n * 0.78
    step = (top - bot) / n
    (xs, ws, _), (xm, wm, _), (xo, wo, _) = cols
    for i, (t, role) in enumerate(SOURCES):
        y = top - (i + 1) * step + (step - h) / 2
        box(ax, xs, y, ws, h, t, ROLE[role], fs=5.7)
    ns = len(STAGES)
    hs = (top - bot) / ns * 0.72
    steps = (top - bot) / ns
    ymid = []
    for i, t in enumerate(STAGES):
        y = top - (i + 1) * steps + (steps - hs) / 2
        box(ax, xm, y, wm, hs, f"{i}   {t}", "#FFFFFF", fs=5.7)
        ymid.append(y + hs / 2)
        if i:
            arrow(ax, xm + wm / 2, y + hs + (steps - hs) - 0.002, xm + wm / 2, y + hs + 0.004)
    ax.add_patch(FancyArrowPatch((xs + ws + 0.006, (top + bot) / 2), (xm - 0.008, (top + bot) / 2),
                                 arrowstyle="-|>", mutation_scale=9, lw=1.0, color="#555555"))
    no = len(OUTPUTS)
    ho = (top - bot) / no * 0.6
    stepo = (top - bot) / no
    for i, t in enumerate(OUTPUTS):
        y = top - (i + 1) * stepo + (stepo - ho) / 2
        box(ax, xo, y, wo, ho, t, "#F7F7F7", fs=5.8, bold=(i == 0))
    ax.add_patch(FancyArrowPatch((xm + wm + 0.006, (top + bot) / 2), (xo - 0.008, (top + bot) / 2),
                                 arrowstyle="-|>", mutation_scale=9, lw=1.0, color="#555555"))
    handles = [Patch(facecolor=c, edgecolor="#7F7F7F", lw=0.4, label=r) for r, c in ROLE.items()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=4,
              frameon=False, fontsize=5.8, handlelength=1.0, columnspacing=1.2)


def panel_b(ax):
    """Panel b: schematic of the complete 21-cohort cattle representation."""
    eds = S.model_eds()
    raw, county, land = S.land_and_counties()
    w = S.wfd()
    land.plot(ax=ax, color=S.GREY_LAND, edgecolor="none")
    eds.plot(ax=ax, color="#E3EDF5", edgecolor="#9DB4C7", linewidth=0.08)
    w.boundary.plot(ax=ax, color=S.DAIRY, linewidth=0.55)
    county.boundary.plot(ax=ax, color="#555555", linewidth=0.3, linestyle=(0, (2, 1)))
    for _, r in w.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, r.ID, fontsize=3.6, ha="center", va="center", color="#08306B")
    ax.set_axis_off(); ax.set_aspect("equal")
    S.title(ax, "c", "Study geography")
    handles = [Patch(facecolor="#E3EDF5", edgecolor="#9DB4C7", lw=0.4, label="Model EDs (2,857)"),
               Patch(facecolor=S.GREY_LAND, edgecolor="none", label="Other EDs (mainly urban)"),
               plt.Line2D([], [], color=S.DAIRY, lw=0.9, label="WFD catchments (46)"),
               plt.Line2D([], [], color="#555555", lw=0.6, ls=(0, (2, 1)), label="Counties (26)")]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=5.8,
              bbox_to_anchor=(-0.02, 1.0))


def panel_c(ax):
    """Panel c: study geography, showing model EDs and WFD catchments."""
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    S.title(ax, "b", "21 cattle cohorts in every ED")
    # adults
    ya, ha = 0.80, 0.11
    adults = [("Dairy cows", S.DARK_DAIRY, 0.03), ("Bulls", S.BULL, 0.37), ("Suckler cows", S.DARK_SUCKLER, 0.71)]
    for t, c, x in adults:
        box(ax, x, ya, 0.26, ha, t, c, fs=6.2, bold=True, ec="none")
        ax.texts[-1].set_color("white")
    # follower grid: columns = origin, rows = age, each cell split female|male
    cols = [("DxD", S.DAIRY, 0.03, "white"), ("DxB", S.DXB, 0.37, "black"), ("BxB", S.SUCKLER, 0.71, "black")]
    ages = ["< 1 year", "1–2 years", "2+ years"]
    y0, hh, g = 0.50, 0.11, 0.03
    for name, c, x, tc in cols:
        ax.text(x + 0.13, y0 + hh + 0.075, name, ha="center", fontsize=6.6, fontweight="bold", color=c if name != "DxB" else "#2C7FB8")
        for j, a in enumerate(ages):
            y = y0 - j * (hh + g)
            for k, sx in enumerate(("F", "M")):
                ax.add_patch(FancyBboxPatch((x + k * 0.13, y), 0.125, hh, boxstyle="round,pad=0.003",
                                            fc=c, ec="white", lw=0.6, alpha=1 if k == 0 else 0.7,
                                            hatch="////" if name == "DxB" else None))
                ax.text(x + k * 0.13 + 0.0625, y + hh / 2, sx, ha="center", va="center",
                        fontsize=6, color=tc, fontweight="bold")
    for j, a in enumerate(ages):
        ax.text(-0.005, y0 - j * (hh + g) + hh / 2, a, ha="right", va="center", fontsize=5.6,
                color="#555555")
    arrow(ax, 0.16, ya - 0.005, 0.16, y0 + hh + 0.11)
    arrow(ax, 0.22, ya - 0.005, 0.45, y0 + hh + 0.11)
    arrow(ax, 0.84, ya - 0.005, 0.84, y0 + hh + 0.11)
    ax.text(0.5, 0.0, "3 adult cohorts + 3 origins × 3 ages × 2 sexes = 21\n"
            "DxD: dairy dam × dairy sire · DxB: dairy dam × beef sire · BxB: beef dam × beef sire",
            ha="center", va="bottom", fontsize=5.6, color="#555555")


def main():
    """Assemble and save Figure 1. No model quantities are recalculated here."""
    S.style()
    fig = plt.figure(figsize=(7.4, 7.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.1, 1], height_ratios=[0.62, 1],
                          wspace=0.06, hspace=0.16)
    panel_a(fig.add_subplot(gs[0, :]))
    panel_c(fig.add_subplot(gs[1, 0]))
    panel_b(fig.add_subplot(gs[1, 1]))
    fig.subplots_adjust(left=0.07, right=0.99, top=0.96, bottom=0.02)
    S.save(fig, "Fig1_framework")


if __name__ == "__main__":
    main()
