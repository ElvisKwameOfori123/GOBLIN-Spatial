"""Publication-facing graphs for the final GOBLIN-Spatial study.

This module is strictly downstream of the validated final-results SQLite database.
It does not recompute SC1, SC2 or SC3 science. The graph suite is organised around
six manuscript claims rather than around model modules:

1. national bioeconomy transition and competing land claims;
2. concentration of territorial transition exposure relative to the baseline;
3. distributional trade-offs of place-based protection;
4. persistent versus policy-contingent exposure;
5. released land as a contested transition resource;
6. territorial feasibility of competing land-use claims.

All graphics are generated reproducibly from frozen tables and written as PNG,
SVG and PDF.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


PAPER_FIGURE_VERSION = "2.0"
MAIN_SCENARIOS = ("BE_SG", "ALL_GAS_NZ")
PRINCIPAL_SCENARIOS = ("SI_SG", "BE_SG", "ALL_GAS_NZ")
PRINCIPAL_RULES = (
    "PRORATA",
    "DAIRY_PROTECTION",
    "ECONOMIC_CAPACITY_PROTECTION",
    "SOCIAL_VULNERABILITY_PROTECTION",
)
SC3_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
    "REWETTING",
)

SCENARIO_LABELS = {
    "SI_SG": "SI–SG",
    "BE_SG": "BE–SG",
    "ALL_GAS_NZ": "All-gas NZ",
}
RULE_LABELS = {
    "PRORATA": "Proportional",
    "DAIRY_PROTECTION": "Dairy dependence",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic vulnerability",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social vulnerability",
}
RULE_LABELS_SHORT = {
    "DAIRY_PROTECTION": "Dairy",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social",
}
USE_LABELS = {
    "AD_GRASS": "AD grass",
    "BIOREFINERY_GRASS": "Biorefinery grass",
    "WILLOW": "Willow",
    "ADDITIONAL_TILLAGE": "Tillage",
    "FOREST": "Forestry",
    "REWETTING": "Rewetting",
}

# Okabe–Ito inspired palette: stable, print-friendly and colour-blind considerate.
COLORS = {
    "SI_SG": "#7F7F7F",
    "BE_SG": "#0072B2",
    "ALL_GAS_NZ": "#D55E00",
    "DAIRY": "#0072B2",
    "SUCKLER": "#E69F00",
    "FOLLOWER": "#009E73",
    "RELIEF": "#0072B2",
    "BURDEN": "#D55E00",
    "BASELINE": "#333333",
    "TARGET": "#666666",
    "REALIZED": "#0072B2",
    "UNMET": "#D55E00",
    "G1": "#0072B2",
    "G2": "#E69F00",
    "G3": "#009E73",
}


REQUIRED_TABLES = {
    "national_results",
    "lorenz_data",
    "redistribution",
    "robust_exposure",
    "persistence_histogram",
    "land_release_summary",
    "transition_conditions",
    "opportunity_mobilisation",
    "shared_pool_summary",
}


def _read_tables(path: Path) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(f"final results database not found: {path}")
    with sqlite3.connect(path) as con:
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(REQUIRED_TABLES - names)
        if missing:
            raise ValueError(f"final results database missing paper-figure tables: {missing}")
        return {name: pd.read_sql_query(f'SELECT * FROM "{name}"', con) for name in REQUIRED_TABLES}


def _setup_matplotlib():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "axes.titleweight": "bold",
            "axes.titlesize": 11.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.frameon": False,
            "legend.fontsize": 8.0,
            "font.size": 9.0,
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    return plt


def _save(fig, base: Path) -> list[Path]:
    paths: list[Path] = []
    for suffix in (".png", ".svg", ".pdf"):
        path = base.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight", "pad_inches": 0.08}
        if suffix == ".png":
            kwargs["dpi"] = 600
        fig.savefig(path, **kwargs)
        paths.append(path)
    return paths


def _panel_title(ax, letter: str, title: str) -> None:
    ax.set_title(f"{letter}. {title}", loc="left", pad=9)


def _grid(ax, axis: str = "y") -> None:
    ax.grid(axis=axis, color="#B0B0B0", alpha=0.20, linewidth=0.7)
    ax.set_axisbelow(True)


def _prorata(frame: pd.DataFrame, rule_col: str) -> pd.DataFrame:
    return frame.loc[frame[rule_col].astype(str).eq("PRORATA")].copy()


def _scenario_order(frame: pd.DataFrame, scenario_col: str) -> pd.DataFrame:
    order = {scenario: i for i, scenario in enumerate(PRINCIPAL_SCENARIOS)}
    out = frame.copy()
    out["_ORDER"] = out[scenario_col].astype(str).map(order).fillna(999)
    return out.sort_values("_ORDER", kind="stable").drop(columns="_ORDER")


def _main_scenario(frame: pd.DataFrame, scenario_col: str) -> pd.DataFrame:
    return frame.loc[frame[scenario_col].astype(str).isin(MAIN_SCENARIOS)].copy()


def _friendly_use(use: str) -> str:
    return USE_LABELS.get(use, use.replace("_", " ").title())


def _lorenz_curve(values: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    v = pd.to_numeric(pd.Series(values), errors="coerce").fillna(0.0).clip(lower=0.0).to_numpy(float)
    if not len(v) or float(v.sum()) <= 0:
        return np.array([0.0, 100.0]), np.array([0.0, 100.0])
    v = np.sort(v)
    y = np.concatenate([[0.0], np.cumsum(v) / v.sum() * 100.0])
    x = np.linspace(0.0, 100.0, len(y))
    return x, y


def _eds_for_share(values: pd.Series | np.ndarray, share: float = 0.5) -> int:
    v = pd.to_numeric(pd.Series(values), errors="coerce").fillna(0.0).clip(lower=0.0).to_numpy(float)
    total = float(v.sum())
    if total <= 0:
        return 0
    ordered = np.sort(v)[::-1]
    return int(np.searchsorted(np.cumsum(ordered) / total, share, side="left") + 1)


def _manifest_row(fig_id: str, title: str, question: str, files: list[Path], note: str = "") -> dict[str, object]:
    by_suffix = {p.suffix.lower(): str(p) for p in files}
    return {
        "FIGURE_ID": fig_id,
        "TITLE": title,
        "SCIENTIFIC_QUESTION": question,
        "PNG": by_suffix.get(".png", ""),
        "SVG": by_suffix.get(".svg", ""),
        "PDF": by_suffix.get(".pdf", ""),
        "NOTE": note,
        "PAPER_FIGURE_VERSION": PAPER_FIGURE_VERSION,
    }


def _cross_protection_matrix(conditions: pd.DataFrame, scenario: str = "ALL_GAS_NZ") -> pd.DataFrame:
    """Signed SO-exposure change in high-tercile territorial groups, EUR million.

    Groups are defined once from the PRORATA baseline scores. Positive values mean
    extra exposure relative to PRORATA; negative values mean relief.
    """
    score_cols = {
        "Dairy dependence": "DAIRY_STRENGTH_SCORE",
        "Economic vulnerability": "ECONOMIC_VULNERABILITY_SCORE",
        "Social vulnerability": "SOCIAL_VULNERABILITY_SCORE",
    }
    base = conditions.loc[
        conditions["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
        & conditions["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ].copy()
    memberships: dict[str, set[str]] = {}
    for label, col in score_cols.items():
        scores = pd.to_numeric(base[col], errors="coerce")
        cutoff = float(scores.quantile(2.0 / 3.0))
        memberships[label] = set(base.loc[scores.ge(cutoff), "CSOED"].astype(str))

    rows: list[dict[str, object]] = []
    for rule in PRINCIPAL_RULES[1:]:
        b = conditions.loc[
            conditions["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & conditions["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ].copy()
        b["CSOED"] = b["CSOED"].astype(str)
        signed = pd.to_numeric(
            b["SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR"], errors="coerce"
        ).fillna(0.0)
        row: dict[str, object] = {"RULE": rule}
        for label, ids in memberships.items():
            row[label] = float(signed.loc[b["CSOED"].isin(ids)].sum() / 1e6)
        rows.append(row)
    return pd.DataFrame(rows).set_index("RULE")


def _baseline_transition_block(conditions: pd.DataFrame) -> pd.DataFrame:
    return conditions.loc[
        conditions["STUDY_SCENARIO_ID"].astype(str).eq("BE_SG")
        & conditions["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ].copy()


def generate_paper_figures(database: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Generate six reproducible, claim-led manuscript graph figures."""
    db = Path(database).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tables = _read_tables(db)
    plt = _setup_matplotlib()
    from matplotlib.lines import Line2D
    manifest: list[dict[str, object]] = []

    # ------------------------------------------------------------------
    # P01. National bioeconomy transition and competing land claims.
    # ------------------------------------------------------------------
    national = _scenario_order(_prorata(tables["national_results"], "ALLOCATION_POLICY"), "SCENARIO_ID")
    labels = [SCENARIO_LABELS.get(str(s), str(s)) for s in national["SCENARIO_ID"]]
    x = np.arange(len(national))

    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.7), constrained_layout=True)

    dairy = pd.to_numeric(national["SCENARIO_DAIRY_COWS"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    suckler = pd.to_numeric(national["SCENARIO_SUCKLER_COWS"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    total = pd.to_numeric(national["SCENARIO_TOTAL_CATTLE"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    followers = np.maximum(total - dairy - suckler, 0.0)
    axes[0].bar(x, dairy, color=COLORS["DAIRY"], label="Dairy cows")
    axes[0].bar(x, suckler, bottom=dairy, color=COLORS["SUCKLER"], label="Suckler cows")
    axes[0].bar(x, followers, bottom=dairy + suckler, color=COLORS["FOLLOWER"], label="Follower/other cattle")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Cattle (thousand head)")
    _panel_title(axes[0], "A", "National cattle endpoint")
    _grid(axes[0])
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1)

    base_dairy = float(pd.to_numeric(national["BASE_DAIRY_COWS"], errors="coerce").dropna().iloc[0])
    base_suck = float(pd.to_numeric(national["BASE_SUCKLER_COWS"], errors="coerce").dropna().iloc[0])
    base_total = float(pd.to_numeric(national["BASE_TOTAL_CATTLE"], errors="coerce").dropna().iloc[0])
    pct = pd.DataFrame(
        {
            "Dairy": 100.0 * (pd.to_numeric(national["SCENARIO_DAIRY_COWS"], errors="coerce").to_numpy(float) - base_dairy) / base_dairy,
            "Suckler": 100.0 * (pd.to_numeric(national["SCENARIO_SUCKLER_COWS"], errors="coerce").to_numpy(float) - base_suck) / base_suck,
            "Total cattle": 100.0 * (pd.to_numeric(national["SCENARIO_TOTAL_CATTLE"], errors="coerce").to_numpy(float) - base_total) / base_total,
        }
    )
    markers = {"Dairy": "o", "Suckler": "s", "Total cattle": "D"}
    metric_colors = {"Dairy": COLORS["DAIRY"], "Suckler": COLORS["SUCKLER"], "Total cattle": COLORS["BASELINE"]}
    offsets = {"Dairy": -0.18, "Suckler": 0.0, "Total cattle": 0.18}
    for metric in ("Dairy", "Suckler", "Total cattle"):
        axes[1].scatter(x + offsets[metric], pct[metric], s=42, marker=markers[metric], color=metric_colors[metric], label=metric, zorder=3)
        for xx, yy in zip(x + offsets[metric], pct[metric]):
            axes[1].vlines(xx, 0.0, yy, color=metric_colors[metric], alpha=0.35, linewidth=1.2)
    axes[1].axhline(0.0, color="#555555", linewidth=0.9)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Change from 2020 baseline (%)")
    _panel_title(axes[1], "B", "Composition of livestock restructuring")
    _grid(axes[1])
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1)

    release = pd.to_numeric(national["RUN_GROSS_RELEASE_HA"], errors="coerce").to_numpy(float) / 1000.0
    claims = (
        pd.to_numeric(national["STAGE_A_TARGET_HA"], errors="coerce").fillna(0.0).to_numpy(float)
        + pd.to_numeric(national["REWETTING_TARGET_HA"], errors="coerce").fillna(0.0).to_numpy(float)
    ) / 1000.0
    width = 0.34
    axes[2].bar(x - width / 2, release, width, color="#8C8C8C", label="Gross released land")
    axes[2].bar(x + width / 2, claims, width, color="#56B4E9", label="Downstream land claims")
    for xx, rel, cl in zip(x, release, claims):
        share = 100.0 * cl / rel if rel > 0 else np.nan
        axes[2].text(xx + width / 2, cl + max(claims) * 0.025, f"{share:.0f}% of release", ha="center", va="bottom", fontsize=7.8)
    axes[2].set_xticks(x, labels)
    axes[2].set_ylabel("Area (kha)")
    _panel_title(axes[2], "C", "Released land and downstream claims")
    _grid(axes[2])
    axes[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1)

    files = _save(fig, out / "paper_fig01_national_transition")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P01",
            "National transition and competing land claims",
            "How do alternative bioeconomy futures differ in livestock restructuring, released land and downstream land demand?",
            files,
            note="Downstream claims = Stage-A land-use targets plus rewetting target; opportunity envelopes are not summed here.",
        )
    )

    # ------------------------------------------------------------------
    # P02. Transition concentration relative to the baseline production geography.
    # ------------------------------------------------------------------
    lorenz = _prorata(tables["lorenz_data"], "STUDY_ALLOCATION_POLICY")
    base_block = _baseline_transition_block(tables["transition_conditions"])
    base_x, base_y = _lorenz_curve(base_block["BASE_SO_LIVESTOCK_2020_EUR"])
    baseline_eds50 = _eds_for_share(base_block["BASE_SO_LIVESTOCK_2020_EUR"], 0.5)
    base_gini = float(pd.to_numeric(national["GINI_BASE_SO_LIVESTOCK"], errors="coerce").dropna().iloc[0])

    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.7), constrained_layout=True)
    ax = axes[0]
    ax.plot([0, 100], [0, 100], linestyle="--", color="#A0A0A0", linewidth=1.0, label="Equal distribution")
    ax.plot(base_x, base_y, color=COLORS["BASELINE"], linewidth=2.2, label="Baseline livestock SO")
    for scenario in PRINCIPAL_SCENARIOS:
        block = lorenz.loc[
            lorenz["METRIC"].astype(str).eq("Standard Output gross loss")
            & lorenz["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
        ].sort_values("CUMULATIVE_ED_SHARE_PCT")
        if not block.empty:
            ax.plot(
                block["CUMULATIVE_ED_SHARE_PCT"],
                block["CUMULATIVE_EXPOSURE_SHARE_PCT"],
                linewidth=1.9,
                color=COLORS[scenario],
                label=SCENARIO_LABELS[scenario],
            )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Cumulative share of EDs (%)")
    ax.set_ylabel("Cumulative share of livestock SO / exposure (%)")
    _panel_title(ax, "A", "Baseline production versus transition exposure")
    _grid(ax, "both")
    ax.legend(loc="upper left")

    gini_values = [base_gini] + [
        float(pd.to_numeric(national.loc[national["SCENARIO_ID"].astype(str).eq(s), "GINI_SO_LOSS"], errors="coerce").iloc[0])
        for s in PRINCIPAL_SCENARIOS
    ]
    gini_labels = ["Baseline SO"] + [SCENARIO_LABELS[s] for s in PRINCIPAL_SCENARIOS]
    gini_colors = [COLORS["BASELINE"]] + [COLORS[s] for s in PRINCIPAL_SCENARIOS]
    yy = np.arange(len(gini_values))
    axes[1].scatter(gini_values, yy, s=55, color=gini_colors, zorder=3)
    for i, value in enumerate(gini_values):
        axes[1].hlines(i, 0.0, value, color=gini_colors[i], linewidth=2.2, alpha=0.55)
        axes[1].text(value + 0.008, i, f"{value:.3f}", va="center", fontsize=8)
    axes[1].set_yticks(yy, gini_labels)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, max(gini_values) + 0.10)
    axes[1].set_xlabel("Gini coefficient")
    _panel_title(axes[1], "B", "Concentration relative to baseline")
    _grid(axes[1], "x")

    eds50_values = [baseline_eds50] + [
        int(pd.to_numeric(national.loc[national["SCENARIO_ID"].astype(str).eq(s), "EDS_FOR_50PCT_SO_LOSS"], errors="coerce").iloc[0])
        for s in PRINCIPAL_SCENARIOS
    ]
    axes[2].barh(yy, eds50_values, color=gini_colors)
    for i, value in enumerate(eds50_values):
        axes[2].text(value + 16, i, f"{value:,}", va="center", fontsize=8)
    axes[2].set_yticks(yy, gini_labels)
    axes[2].invert_yaxis()
    axes[2].set_xlabel("EDs accounting for 50% of SO / exposure")
    _panel_title(axes[2], "C", "How many EDs carry half of the total?")
    _grid(axes[2], "x")

    files = _save(fig, out / "paper_fig02_transition_concentration")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P02",
            "Transition concentration relative to baseline production",
            "Does transition exposure amplify, reproduce or disperse the pre-existing geography of livestock production?",
            files,
            note="Baseline concentration is derived from the 2020 livestock Standard Output distribution across the modelled ED universe.",
        )
    )

    # ------------------------------------------------------------------
    # P03. Distributional trade-offs of place-based protection.
    # ------------------------------------------------------------------
    redistribution = tables["redistribution"].copy()
    national_all = tables["national_results"].copy()
    main_red = redistribution.loc[
        redistribution["PATHWAY_NAME"].astype(str).isin(MAIN_SCENARIOS)
        & ~redistribution["PATHWAY_ALLOCATION_RULE"].astype(str).eq("PRORATA")
    ].copy()
    main_red["_S"] = main_red["PATHWAY_NAME"].map({"BE_SG": 0, "ALL_GAS_NZ": 1})
    main_red["_R"] = main_red["PATHWAY_ALLOCATION_RULE"].map(
        {"DAIRY_PROTECTION": 0, "ECONOMIC_CAPACITY_PROTECTION": 1, "SOCIAL_VULNERABILITY_PROTECTION": 2}
    )
    main_red = main_red.sort_values(["_S", "_R"], kind="stable")
    row_labels = [
        f"{SCENARIO_LABELS[str(s)]} | {RULE_LABELS_SHORT[str(r)]}"
        for s, r in zip(main_red["PATHWAY_NAME"], main_red["PATHWAY_ALLOCATION_RULE"])
    ]
    y = np.arange(len(main_red))

    fig = plt.figure(figsize=(13.8, 8.4), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=(1.0, 1.05), width_ratios=(1.15, 1.0))
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    relief = -pd.to_numeric(main_red["TOTAL_PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_2020_EUR"], errors="coerce").fillna(0.0).to_numpy(float) / 1e6
    burden = pd.to_numeric(main_red["TOTAL_DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_2020_EUR"], errors="coerce").fillna(0.0).to_numpy(float) / 1e6
    ax_a.barh(y, relief, color=COLORS["RELIEF"], label="Relief")
    ax_a.barh(y, burden, color=COLORS["BURDEN"], label="Transferred burden")
    ax_a.axvline(0.0, color="#555555", linewidth=0.9)
    ax_a.set_yticks(y, row_labels)
    ax_a.invert_yaxis()
    ax_a.set_xlabel("Change in gross SO exposure relative to PRORATA (€ million)")
    _panel_title(ax_a, "A", "Relief and transferred exposure")
    _grid(ax_a, "x")
    ax_a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)

    gini_rows: list[dict[str, object]] = []
    for scenario in MAIN_SCENARIOS:
        b = national_all.loc[national_all["SCENARIO_ID"].astype(str).eq(scenario)].copy()
        g_pr = float(pd.to_numeric(b.loc[b["ALLOCATION_POLICY"].astype(str).eq("PRORATA"), "GINI_SO_LOSS"], errors="coerce").iloc[0])
        for rule in PRINCIPAL_RULES[1:]:
            g = float(pd.to_numeric(b.loc[b["ALLOCATION_POLICY"].astype(str).eq(rule), "GINI_SO_LOSS"], errors="coerce").iloc[0])
            gini_rows.append({"SCENARIO": scenario, "RULE": rule, "DELTA": g - g_pr})
    gini_df = pd.DataFrame(gini_rows)
    xx = np.arange(3)
    width = 0.32
    for j, scenario in enumerate(MAIN_SCENARIOS):
        b = gini_df.loc[gini_df["SCENARIO"].eq(scenario)].set_index("RULE").reindex(PRINCIPAL_RULES[1:])
        vals = b["DELTA"].to_numpy(float)
        ax_b.bar(xx + (j - 0.5) * width, vals, width, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
    ax_b.axhline(0.0, color="#555555", linewidth=0.9)
    ax_b.set_xticks(xx, [RULE_LABELS_SHORT[r] for r in PRINCIPAL_RULES[1:]])
    ax_b.set_ylabel("Δ Gini relative to PRORATA")
    _panel_title(ax_b, "B", "Pathway-dependent concentration effect")
    _grid(ax_b)
    ax_b.legend(loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)

    # Coupling bridge: how much released land is geographically relocated by protection.
    reloc_rows: list[dict[str, object]] = []
    for scenario in MAIN_SCENARIOS:
        release_total = float(
            pd.to_numeric(
                tables["land_release_summary"].loc[
                    tables["land_release_summary"]["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
                    & tables["land_release_summary"]["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA"),
                    "GROSS_RELEASE_HA",
                ],
                errors="coerce",
            ).iloc[0]
        )
        for rule in PRINCIPAL_RULES[1:]:
            r = main_red.loc[
                main_red["PATHWAY_NAME"].astype(str).eq(scenario)
                & main_red["PATHWAY_ALLOCATION_RULE"].astype(str).eq(rule)
            ].iloc[0]
            relocated = float(r["TOTAL_DISPLACED_BURDEN_GOBLIN_RELEASED_GRASSLAND_HA"])
            reloc_rows.append({"SCENARIO": scenario, "RULE": rule, "SHARE": 100.0 * relocated / release_total})
    reloc = pd.DataFrame(reloc_rows)
    for j, scenario in enumerate(MAIN_SCENARIOS):
        b = reloc.loc[reloc["SCENARIO"].eq(scenario)].set_index("RULE").reindex(PRINCIPAL_RULES[1:])
        vals = b["SHARE"].to_numpy(float)
        ax_c.bar(xx + (j - 0.5) * width, vals, width, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
    ax_c.set_xticks(xx, [RULE_LABELS_SHORT[r] for r in PRINCIPAL_RULES[1:]])
    ax_c.set_ylabel("Released-land relocation (% of total release)")
    _panel_title(ax_c, "C", "Implementation also relocates transition land")
    _grid(ax_c)

    matrix = _cross_protection_matrix(tables["transition_conditions"], "ALL_GAS_NZ")
    col_order = ["Dairy dependence", "Economic vulnerability", "Social vulnerability"]
    matrix = matrix.reindex(index=PRINCIPAL_RULES[1:], columns=col_order)
    values = matrix.to_numpy(float)
    vmax = max(abs(float(np.nanmin(values))), abs(float(np.nanmax(values))), 1.0)
    im = ax_d.imshow(values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax_d.set_xticks(np.arange(len(col_order)), ["High dairy\ndependence", "High economic\nvulnerability", "High social\nvulnerability"])
    ax_d.set_yticks(np.arange(3), [RULE_LABELS_SHORT[r] + " protection" for r in PRINCIPAL_RULES[1:]])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            val = values[i, j]
            ax_d.text(j, i, f"{val:+.0f}", ha="center", va="center", fontsize=8.3, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax_d, fraction=0.046, pad=0.03)
    cbar.set_label("Change in gross SO exposure (€ million)")
    _panel_title(ax_d, "D", "Cross-protection trade-offs under All-gas NZ")
    ax_d.spines.top.set_visible(True)
    ax_d.spines.right.set_visible(True)

    files = _save(fig, out / "paper_fig03_protection_tradeoffs")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P03",
            "Distributional trade-offs of place-based protection",
            "How does place-based protection redistribute exposure, concentration and the geography of released land?",
            files,
            note="Cross-protection groups are high-tercile baseline score groups. Positive matrix values denote extra exposure relative to PRORATA.",
        )
    )

    # ------------------------------------------------------------------
    # P04. Persistence and pathway-vs-allocation sensitivity.
    # ------------------------------------------------------------------
    hist = tables["persistence_histogram"].copy()
    robust = tables["robust_exposure"].copy()
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), constrained_layout=True)

    h = hist.loc[hist["METRIC"].astype(str).eq("SO exposure")].sort_values("FREQUENCY")
    axes[0].bar(h["FREQUENCY"], h["ED_COUNT"], color="#7A7A7A")
    persistent = int(h.loc[h["FREQUENCY"].eq(int(h["FREQUENCY"].max())), "ED_COUNT"].sum())
    axes[0].text(
        0.98,
        0.94,
        f"{persistent} EDs appear in the top exposure decile\nin every tested configuration",
        transform=axes[0].transAxes,
        ha="right",
        va="top",
        fontsize=8.3,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#B0B0B0"},
    )
    axes[0].set_xlabel("Top-decile appearances across 12 configurations")
    axes[0].set_ylabel("ED count")
    _panel_title(axes[0], "A", "Frequency of high-exposure classification")
    _grid(axes[0])

    xv = pd.to_numeric(robust["PATHWAY_SENSITIVITY_SO_LOSS_PCT"], errors="coerce").to_numpy(float)
    yv = pd.to_numeric(robust["ALLOCATION_SENSITIVITY_SO_LOSS_PCT"], errors="coerce").to_numpy(float)
    finite = np.isfinite(xv) & np.isfinite(yv)
    axes[1].scatter(xv[finite], yv[finite], s=13, alpha=0.40, color="#4C78A8", edgecolors="none")
    high = max(float(np.nanmax(xv[finite])), float(np.nanmax(yv[finite]))) if finite.any() else 1.0
    axes[1].plot([0, high], [0, high], linestyle="--", linewidth=1.0, color="#555555")
    allocation_dominated = int(np.sum(yv[finite] > xv[finite]))
    pathway_dominated = int(np.sum(xv[finite] > yv[finite]))
    axes[1].text(
        0.03,
        0.97,
        f"Pathway-dominated: {pathway_dominated:,} EDs\nAllocation-dominated: {allocation_dominated:,} EDs",
        transform=axes[1].transAxes,
        ha="left",
        va="top",
        fontsize=8.3,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#B0B0B0"},
    )
    axes[1].set_xlabel("Pathway sensitivity in SO exposure (percentage points)")
    axes[1].set_ylabel("Allocation sensitivity in SO exposure (percentage points)")
    _panel_title(axes[1], "B", "Pathway versus implementation sensitivity")
    _grid(axes[1], "both")

    files = _save(fig, out / "paper_fig04_persistence_sensitivity")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P04",
            "Persistent and policy-contingent exposure",
            "Which places remain highly exposed across tested futures, and where does implementation choice matter more than pathway choice?",
            files,
            note="This figure reports the central protection-strength experiment; protection-strength sensitivity should be reported separately when available.",
        )
    )

    # ------------------------------------------------------------------
    # P05. Released land as a contested transition resource.
    # ------------------------------------------------------------------
    release = tables["land_release_summary"].copy()
    release_main = _main_scenario(release, "STUDY_SCENARIO_ID")
    release_pr = _prorata(release_main, "STUDY_ALLOCATION_POLICY")
    release_pr = release_pr.set_index("STUDY_SCENARIO_ID").reindex(MAIN_SCENARIOS).reset_index()
    mobilisation = _prorata(tables["opportunity_mobilisation"], "STUDY_ALLOCATION_POLICY")

    fig = plt.figure(figsize=(13.8, 8.3), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    xx = np.arange(2)
    origin_cols = [("DAIRY_RELEASE_HA", "Dairy", COLORS["DAIRY"]), ("BEEF_RELEASE_HA", "Beef", COLORS["SUCKLER"]), ("SHEEP_RELEASE_HA", "Sheep", COLORS["FOLLOWER"])]
    bottom = np.zeros(2)
    total_release = pd.to_numeric(release_pr["GROSS_RELEASE_HA"], errors="coerce").to_numpy(float)
    for col, label, color in origin_cols:
        vals = pd.to_numeric(release_pr[col], errors="coerce").fillna(0.0).to_numpy(float)
        shares = np.divide(vals, total_release, out=np.zeros_like(vals), where=total_release > 0) * 100.0
        ax_a.bar(xx, shares, bottom=bottom, label=label, color=color)
        for j, share in enumerate(shares):
            if share >= 7:
                ax_a.text(j, bottom[j] + share / 2, f"{share:.0f}%", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        bottom += shares
    ax_a.set_xticks(xx, [SCENARIO_LABELS[s] for s in MAIN_SCENARIOS])
    ax_a.set_ylim(0, 100)
    ax_a.set_ylabel("Share of released land (%)")
    _panel_title(ax_a, "A", "Livestock-system origin of released land")
    _grid(ax_a)
    ax_a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3)

    # Capability composition with min–max range across all four allocation rules.
    cap_cols = [("G1_RELEASE_SHARE_PCT", "G1", COLORS["G1"]), ("G2_RELEASE_SHARE_PCT", "G2", COLORS["G2"]), ("G3_RELEASE_SHARE_PCT", "G3", COLORS["G3"])]
    offsets = np.array([-0.18, 0.0, 0.18])
    for k, (col, label, color) in enumerate(cap_cols):
        means = []
        mins = []
        maxs = []
        for scenario in MAIN_SCENARIOS:
            b = release_main.loc[release_main["STUDY_SCENARIO_ID"].astype(str).eq(scenario)]
            vals = pd.to_numeric(b[col], errors="coerce").dropna().to_numpy(float)
            means.append(float(np.mean(vals)))
            mins.append(float(np.min(vals)))
            maxs.append(float(np.max(vals)))
        means_arr = np.array(means)
        yerr = np.vstack([means_arr - np.array(mins), np.array(maxs) - means_arr])
        ax_b.errorbar(xx + offsets[k], means_arr, yerr=yerr, fmt="o", capsize=3, color=color, label=label, markersize=6)
    ax_b.set_xticks(xx, [SCENARIO_LABELS[s] for s in MAIN_SCENARIOS])
    ax_b.set_ylabel("Released-land capability share (%)")
    _panel_title(ax_b, "B", "Capability composition is stable across implementation rules")
    _grid(ax_b)
    ax_b.legend(loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    ax_b.text(0.98, 0.04, "Whiskers = min–max across 4 implementation rules", transform=ax_b.transAxes, ha="right", va="bottom", fontsize=7.7, color="#555555")

    # Competing opportunity envelopes: eligible capacity vs target, main pathways only.
    use_order = list(SC3_USES)
    yy = np.arange(len(use_order))
    scenario_offsets = {"BE_SG": -0.14, "ALL_GAS_NZ": 0.14}
    for scenario in MAIN_SCENARIOS:
        b = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
        eligible = pd.to_numeric(b["ELIGIBLE_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        target = pd.to_numeric(b["TARGET_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        ypos = yy + scenario_offsets[scenario]
        for i in range(len(use_order)):
            ax_c.hlines(ypos[i], target[i], eligible[i], color=COLORS[scenario], alpha=0.45, linewidth=2.0)
        ax_c.scatter(eligible, ypos, s=45, facecolors="white", edgecolors=COLORS[scenario], linewidths=1.5, label=f"{SCENARIO_LABELS[scenario]} eligible")
        ax_c.scatter(target, ypos, s=34, color=COLORS[scenario], marker="|", linewidths=2.4, label=f"{SCENARIO_LABELS[scenario]} target")
    ax_c.set_yticks(yy, [_friendly_use(u) for u in use_order])
    ax_c.invert_yaxis()
    ax_c.set_xlabel("Area (kha)")
    _panel_title(ax_c, "C", "Competing opportunity envelopes")
    _grid(ax_c, "x")
    opportunity_handles = [
        Line2D([0], [0], color=COLORS["BE_SG"], lw=2, label="BE–SG"),
        Line2D([0], [0], color=COLORS["ALL_GAS_NZ"], lw=2, label="All-gas NZ"),
        Line2D([0], [0], marker="o", markerfacecolor="white", markeredgecolor="#555555", linestyle="None", label="Eligible capacity"),
        Line2D([0], [0], marker="|", color="#555555", linestyle="None", markersize=10, markeredgewidth=2, label="National target"),
    ]
    ax_c.legend(handles=opportunity_handles, loc="upper right", fontsize=7.5, ncol=2)
    ax_c.text(
        0.98,
        0.04,
        "Eligibility envelopes overlap\nand are not additive",
        transform=ax_c.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.1,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#B0B0B0"},
    )

    # Empirical coupling test: geographic relocation vs change in aggregate capability mix.
    coupling_rows: list[dict[str, object]] = []
    for scenario in MAIN_SCENARIOS:
        pr = release.loc[
            release["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & release["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
        ].iloc[0]
        release_total = float(pr["GROSS_RELEASE_HA"])
        for rule in PRINCIPAL_RULES[1:]:
            r = release.loc[
                release["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
                & release["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
            ].iloc[0]
            red = tables["redistribution"].loc[
                tables["redistribution"]["PATHWAY_NAME"].astype(str).eq(scenario)
                & tables["redistribution"]["PATHWAY_ALLOCATION_RULE"].astype(str).eq(rule)
            ].iloc[0]
            relocation_share = 100.0 * float(red["TOTAL_DISPLACED_BURDEN_GOBLIN_RELEASED_GRASSLAND_HA"]) / release_total
            max_cap_shift = max(
                abs(float(r["G1_RELEASE_SHARE_PCT"]) - float(pr["G1_RELEASE_SHARE_PCT"])),
                abs(float(r["G2_RELEASE_SHARE_PCT"]) - float(pr["G2_RELEASE_SHARE_PCT"])),
                abs(float(r["G3_RELEASE_SHARE_PCT"]) - float(pr["G3_RELEASE_SHARE_PCT"])),
            )
            coupling_rows.append({"SCENARIO": scenario, "RULE": rule, "RELOCATION": relocation_share, "CAP_SHIFT": max_cap_shift})
    coupling = pd.DataFrame(coupling_rows)
    for scenario in MAIN_SCENARIOS:
        b = coupling.loc[coupling["SCENARIO"].eq(scenario)]
        ax_d.scatter(b["RELOCATION"], b["CAP_SHIFT"], s=58, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
        for _, row in b.iterrows():
            ax_d.annotate(RULE_LABELS_SHORT[str(row["RULE"])][0], (row["RELOCATION"], row["CAP_SHIFT"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax_d.set_xlabel("Released-land relocation (% of total release)")
    ax_d.set_ylabel("Maximum change in G1/G2/G3 share (percentage points)")
    _panel_title(ax_d, "D", "Coupling test: location shifts, aggregate capability barely changes")
    _grid(ax_d, "both")
    ax_d.legend(loc="upper left")

    files = _save(fig, out / "paper_fig05_contested_land")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P05",
            "Released land as a contested transition resource",
            "How do pathway and implementation choices alter the provenance, capability and competing uses of released land?",
            files,
            note="Panel D tests rather than assumes coupling: protection relocates released land while aggregate G1/G2/G3 composition remains nearly invariant in the current results.",
        )
    )

    # ------------------------------------------------------------------
    # P06. Territorial feasibility of competing land-use claims.
    # ------------------------------------------------------------------
    pools = _prorata(tables["shared_pool_summary"], "STUDY_ALLOCATION_POLICY")
    national_main = national_all.loc[national_all["SCENARIO_ID"].astype(str).isin(MAIN_SCENARIOS)].copy()
    fig = plt.figure(figsize=(13.8, 8.0), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    # A: target, realised and unmet across main pathways.
    yy = np.arange(len(use_order))
    for scenario in MAIN_SCENARIOS:
        b = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
        target = pd.to_numeric(b["TARGET_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        realised = pd.to_numeric(b["REALISED_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        ypos = yy + scenario_offsets[scenario]
        for i in range(len(use_order)):
            ax_a.hlines(ypos[i], 0.0, target[i], color=COLORS[scenario], alpha=0.20, linewidth=4.5)
        ax_a.scatter(realised, ypos, color=COLORS[scenario], s=42, label=f"{SCENARIO_LABELS[scenario]} realised")
        ax_a.scatter(target, ypos, facecolors="white", edgecolors=COLORS[scenario], s=52, linewidths=1.5, label=f"{SCENARIO_LABELS[scenario]} target")
    ax_a.set_yticks(yy, [_friendly_use(u) for u in use_order])
    ax_a.invert_yaxis()
    ax_a.set_xlabel("Area (kha)")
    _panel_title(ax_a, "A", "Target delivery")
    _grid(ax_a, "x")
    delivery_handles = [
        Line2D([0], [0], color=COLORS["BE_SG"], lw=2, label="BE–SG"),
        Line2D([0], [0], color=COLORS["ALL_GAS_NZ"], lw=2, label="All-gas NZ"),
        Line2D([0], [0], marker="o", color="#555555", linestyle="None", label="Realised"),
        Line2D([0], [0], marker="o", markerfacecolor="white", markeredgecolor="#555555", linestyle="None", label="National target"),
    ]
    ax_a.legend(handles=delivery_handles, loc="lower right", fontsize=7.5, ncol=2)

    # B: opportunity mobilisation by use.
    width = 0.34
    xx = np.arange(len(use_order))
    for j, scenario in enumerate(MAIN_SCENARIOS):
        b = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
        vals = pd.to_numeric(b["OPPORTUNITY_MOBILISATION_PCT"], errors="coerce").fillna(0.0).to_numpy(float)
        ax_b.bar(xx + (j - 0.5) * width, vals, width, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
    ax_b.set_xticks(xx, [_friendly_use(u) for u in use_order], rotation=30, ha="right")
    ax_b.set_ylabel("Realised / eligible capacity (%)")
    _panel_title(ax_b, "B", "Opportunity mobilisation")
    _grid(ax_b)
    ax_b.legend(loc="upper left")
    ax_b.text(0.98, 0.96, "Mobilisation = realised / eligible; 100% does not imply target fulfilment", transform=ax_b.transAxes, ha="right", va="top", fontsize=7.5, color="#555555")

    # C: shared-pool utilisation.
    pool_order = ["TILLAGE_WILLOW", "AD_BIOREFINERY", "FOREST_MINERAL"]
    pool_labels = ["Tillage–willow", "AD–biorefinery", "Forest–mineral"]
    px = np.arange(len(pool_order))
    for j, scenario in enumerate(MAIN_SCENARIOS):
        b = pools.loc[pools["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("SHARED_POOL").reindex(pool_order)
        vals = pd.to_numeric(b["UTILISATION_PCT"], errors="coerce").fillna(0.0).to_numpy(float)
        ax_c.bar(px + (j - 0.5) * width, vals, width, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
    ax_c.set_xticks(px, pool_labels, rotation=15, ha="right")
    ax_c.set_ylabel("Shared-pool utilisation (%)")
    _panel_title(ax_c, "C", "Competition for overlapping eligible land")
    _grid(ax_c)

    # D: substantial residual land can coexist with a use-specific implementation gap.
    allgas = national_main.loc[national_main["SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")].copy()
    rule_order = list(PRINCIPAL_RULES)
    allgas["_ORDER"] = allgas["ALLOCATION_POLICY"].astype(str).map({r: i for i, r in enumerate(rule_order)})
    allgas = allgas.sort_values("_ORDER")
    residual = pd.to_numeric(allgas["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"], errors="coerce").to_numpy(float) / 1000.0
    unmet = pd.to_numeric(allgas["REWETTING_UNMET_HA"], errors="coerce").to_numpy(float) / 1000.0
    colors = ["#777777", "#0072B2", "#009E73", "#CC79A7"]
    for i, (_, row) in enumerate(allgas.iterrows()):
        ax_d.scatter(residual[i], unmet[i], s=70, color=colors[i], zorder=3)
        ax_d.annotate(RULE_LABELS[str(row["ALLOCATION_POLICY"])], (residual[i], unmet[i]), xytext=(5, 5), textcoords="offset points", fontsize=7.8)
    ax_d.set_xlabel("Final unallocated released land (kha)")
    ax_d.set_ylabel("Unmet rewetting target (kha)")
    _panel_title(ax_d, "D", "Aggregate land surplus can coexist with a use-specific gap")
    _grid(ax_d, "both")
    ax_d.text(
        0.03,
        0.96,
        "All-gas NZ",
        transform=ax_d.transAxes,
        ha="left",
        va="top",
        fontweight="bold",
        fontsize=8.5,
    )

    files = _save(fig, out / "paper_fig06_territorial_feasibility")
    plt.close(fig)
    manifest.append(
        _manifest_row(
            "P06",
            "Territorial feasibility of competing land-use claims",
            "Can competing bioeconomy, cropping, forestry and restoration targets be jointly accommodated within the released-land geography?",
            files,
            note="Eligibility envelopes overlap; shared-pool utilisation and final residual land are therefore reported separately from individual eligible hectares.",
        )
    )

    manifest_path = out / "GOBLIN_Spatial_Paper_Figure_Manifest.csv"
    pd.DataFrame(manifest).to_csv(manifest_path, index=False)
    return {
        "paper_figure_directory": out,
        "paper_figure_manifest": manifest_path,
    }
