"""High-impact manuscript figures for the final GOBLIN-Spatial study.

This module is downstream of the validated final results database. It never
recomputes SC1, SC2 or SC3 science. The figures are intentionally question-led
and reduce the full diagnostic graph suite to eight publication-facing figures:

1. national pathway transition;
2. concentration of local transition exposure;
3. protection relief and displaced adjustment;
4. persistent versus policy-contingent exposure;
5. livestock-system and natural-capital composition of released land;
6. local transition conditions: exposure, vulnerability and opportunity;
7. target, realised and unmet alternative land uses;
8. opportunity mobilisation and shared-pool constraints.

PNG and SVG are always written. The selected opportunity dimension for Figure 6
is data-led: the most spatially constrained use is preferred when unmet targets
exist; otherwise the use with the greatest ED variation in eligibility coverage
is selected. This avoids hard-coding a visually convenient result before the
real empirical runs are inspected.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from goblin_spatial.study_reporting import PRINCIPAL_RULES, PRINCIPAL_SCENARIOS, SC3_USES, USE_LABELS


PAPER_FIGURE_VERSION = "1.0"
SCENARIO_LABELS = {
    "SI_SG": "SI–SG",
    "BE_SG": "BE–SG",
    "ALL_GAS_NZ": "All-gas NZ",
}
RULE_LABELS_SHORT = {
    "DAIRY_PROTECTION": "Dairy protection",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic protection",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social protection",
}
ELIGIBILITY_COVERAGE_COLUMNS = {
    "AD_GRASS": "AD_GRASS_ELIGIBILITY_COVERAGE_PCT",
    "BIOREFINERY_GRASS": "BIOREFINERY_GRASS_ELIGIBILITY_COVERAGE_PCT",
    "WILLOW": "WILLOW_ELIGIBILITY_COVERAGE_PCT",
    "ADDITIONAL_TILLAGE": "ADDITIONAL_TILLAGE_ELIGIBILITY_COVERAGE_PCT",
    "FOREST": "FOREST_ELIGIBILITY_COVERAGE_PCT",
    "REWETTING": "REWETTING_ELIGIBILITY_COVERAGE_PCT",
}


def _read_tables(path: Path) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(f"final results database not found: {path}")
    required = {
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
    with sqlite3.connect(path) as con:
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"final results database missing paper-figure tables: {missing}")
        return {name: pd.read_sql_query(f'SELECT * FROM "{name}"', con) for name in required}


def _setup_matplotlib():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "axes.titlesize": 12.5,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 8.5,
            "font.size": 9.5,
            "savefig.facecolor": "white",
        }
    )
    return plt


def _save(fig, base: Path) -> list[Path]:
    paths: list[Path] = []
    for suffix in (".png", ".svg"):
        path = base.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if suffix == ".png":
            kwargs["dpi"] = 500
        fig.savefig(path, **kwargs)
        paths.append(path)
    return paths


def _scenario_order(frame: pd.DataFrame, scenario_col: str) -> pd.DataFrame:
    order = {scenario: i for i, scenario in enumerate(PRINCIPAL_SCENARIOS)}
    out = frame.copy()
    out["_ORDER"] = out[scenario_col].astype(str).map(order).fillna(999)
    return out.sort_values("_ORDER", kind="stable").drop(columns="_ORDER")


def _prorata(frame: pd.DataFrame, rule_col: str) -> pd.DataFrame:
    return frame.loc[frame[rule_col].astype(str).eq("PRORATA")].copy()


def _select_opportunity_use(tables: dict[str, pd.DataFrame]) -> tuple[str, str]:
    mobilisation = _prorata(tables["opportunity_mobilisation"], "STUDY_ALLOCATION_POLICY")
    candidates: list[tuple[float, str]] = []
    for use in SC3_USES:
        block = mobilisation.loc[mobilisation["LAND_USE"].astype(str).eq(use)]
        if block.empty:
            continue
        target = pd.to_numeric(block["TARGET_HA"], errors="coerce").to_numpy(float)
        unmet = pd.to_numeric(block["UNMET_HA"], errors="coerce").to_numpy(float)
        shares = np.divide(unmet, target, out=np.zeros_like(unmet), where=np.isfinite(target) & (target > 0))
        candidates.append((float(np.nanmax(shares)) if len(shares) else 0.0, use))
    if candidates:
        max_unmet, selected = max(candidates, key=lambda item: item[0])
        if max_unmet > 1e-9:
            return selected, "largest unmet-target share across PRORATA pathways"

    conditions = tables["transition_conditions"]
    block = conditions.loc[
        conditions["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
        & conditions["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ]
    spreads: list[tuple[float, str]] = []
    for use, column in ELIGIBILITY_COVERAGE_COLUMNS.items():
        if column not in block.columns:
            continue
        values = pd.to_numeric(block[column], errors="coerce").dropna().to_numpy(float)
        if len(values):
            spreads.append((float(np.nanstd(values)), use))
    if spreads:
        _, selected = max(spreads, key=lambda item: item[0])
        return selected, "largest ED variation in eligibility coverage under ALL_GAS_NZ PRORATA"
    return "FOREST", "fallback because no use-specific eligibility variation was available"


def _friendly_use(use: str) -> str:
    return USE_LABELS.get(use, use.replace("_", " ").title())


def _manifest_row(fig_id: str, title: str, question: str, files: list[Path], note: str = "") -> dict[str, object]:
    return {
        "FIGURE_ID": fig_id,
        "TITLE": title,
        "SCIENTIFIC_QUESTION": question,
        "PNG": next((str(p) for p in files if p.suffix.lower() == ".png"), ""),
        "SVG": next((str(p) for p in files if p.suffix.lower() == ".svg"), ""),
        "NOTE": note,
        "PAPER_FIGURE_VERSION": PAPER_FIGURE_VERSION,
    }


def generate_paper_figures(database: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Generate the eight agreed publication-facing figures from final SQLite results."""
    db = Path(database).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tables = _read_tables(db)
    plt = _setup_matplotlib()
    manifest: list[dict[str, object]] = []

    # Figure 1: national transition, with national endpoints represented only once per pathway.
    national = _prorata(tables["national_results"], "ALLOCATION_POLICY")
    national = _scenario_order(national, "SCENARIO_ID")
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.2), constrained_layout=True)
    x = np.arange(len(national))
    labels = [SCENARIO_LABELS.get(str(s), str(s)) for s in national["SCENARIO_ID"]]
    dairy = pd.to_numeric(national.get("SCENARIO_DAIRY_COW", national.get("SCENARIO_DAIRY_COWS", 0.0)), errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    suckler = pd.to_numeric(national.get("SCENARIO_SUCKLER_COW", national.get("SCENARIO_SUCKLER_COWS", 0.0)), errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    total = pd.to_numeric(national["SCENARIO_TOTAL_CATTLE"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
    followers = np.maximum(total - dairy - suckler, 0.0)
    bottom = np.zeros(len(national))
    for values, label in ((dairy, "Dairy cows"), (suckler, "Suckler cows"), (followers, "Follower/other cattle")):
        axes[0].bar(x, values, bottom=bottom, label=label)
        bottom += values
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Cattle (thousand head)")
    axes[0].set_title("A. National cattle endpoint")
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    axes[0].grid(axis="y", alpha=0.18)
    target_land = pd.to_numeric(national.get("TARGET_LIVESTOCK_LAND_HA", np.nan), errors="coerce").to_numpy(float) / 1000.0
    gross_release = pd.to_numeric(national.get("RUN_GROSS_RELEASE_HA", national.get("GOBLIN_RELEASED_GRASSLAND_HA", np.nan)), errors="coerce").to_numpy(float) / 1000.0
    axes[1].bar(x, target_land, label="Livestock land retained")
    axes[1].bar(x, gross_release, bottom=np.nan_to_num(target_land), label="Gross released land")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Grassland (kha)")
    axes[1].set_title("B. Livestock-land transition")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    axes[1].grid(axis="y", alpha=0.18)
    files = _save(fig, out / "paper_fig01_national_transition")
    plt.close(fig)
    manifest.append(_manifest_row("P01", "National pathway transition", "How large is the national livestock and land transition?", files))

    # Figure 2: concentration of physical and production-value exposure.
    lorenz = _prorata(tables["lorenz_data"], "STUDY_ALLOCATION_POLICY")
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.1), constrained_layout=True)
    for ax, metric, title in (
        (axes[0], "Cattle reduction", "A. Cattle adjustment"),
        (axes[1], "Standard Output gross loss", "B. Production-value exposure"),
    ):
        ax.plot([0, 100], [0, 100], linestyle="--", linewidth=1, label="Equal distribution")
        for scenario in PRINCIPAL_SCENARIOS:
            block = lorenz.loc[
                lorenz["METRIC"].astype(str).eq(metric)
                & lorenz["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            ].sort_values("CUMULATIVE_ED_SHARE_PCT")
            if not block.empty:
                ax.plot(block["CUMULATIVE_ED_SHARE_PCT"], block["CUMULATIVE_EXPOSURE_SHARE_PCT"], linewidth=1.8, label=SCENARIO_LABELS.get(scenario, scenario))
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Cumulative share of EDs (%)")
        ax.set_ylabel("Cumulative share of national exposure (%)")
        ax.set_title(title)
        ax.grid(alpha=0.15)
    axes[1].legend(loc="lower right")
    files = _save(fig, out / "paper_fig02_transition_concentration")
    plt.close(fig)
    manifest.append(_manifest_row("P02", "Concentration of local transition exposure", "How geographically concentrated are cattle adjustment and Standard Output exposure?", files))

    # Figure 3: protection relief and displaced adjustment relative to PRORATA.
    redistribution = tables["redistribution"].loc[~tables["redistribution"]["PATHWAY_ALLOCATION_RULE"].astype(str).eq("PRORATA")].copy()
    scenario_order = {s: i for i, s in enumerate(PRINCIPAL_SCENARIOS)}
    rule_order = {r: i for i, r in enumerate(PRINCIPAL_RULES)}
    redistribution["_S"] = redistribution["PATHWAY_NAME"].astype(str).map(scenario_order).fillna(999)
    redistribution["_R"] = redistribution["PATHWAY_ALLOCATION_RULE"].astype(str).map(rule_order).fillna(999)
    redistribution = redistribution.sort_values(["_S", "_R"], kind="stable")
    y = np.arange(len(redistribution))
    row_labels = [f"{SCENARIO_LABELS.get(str(s), str(s))} | {RULE_LABELS_SHORT.get(str(r), str(r))}" for s, r in zip(redistribution["PATHWAY_NAME"], redistribution["PATHWAY_ALLOCATION_RULE"])]
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.0), constrained_layout=True)
    for ax, suffix, scale, unit, title in (
        (axes[0], "TOTAL_CATTLE_REDUCTION_HEAD", 1000.0, "thousand head", "A. Physical cattle adjustment"),
        (axes[1], "SO_LIVESTOCK_GROSS_LOSS_2020_EUR", 1e6, "EUR million", "B. Standard Output exposure"),
    ):
        relief_col = f"TOTAL_PROTECTION_RELIEF_{suffix}"
        burden_col = f"TOTAL_DISPLACED_BURDEN_{suffix}"
        relief = -pd.to_numeric(redistribution.get(relief_col, 0.0), errors="coerce").fillna(0.0).to_numpy(float) / scale
        burden = pd.to_numeric(redistribution.get(burden_col, 0.0), errors="coerce").fillna(0.0).to_numpy(float) / scale
        ax.barh(y, relief, label="Protection relief")
        ax.barh(y, burden, label="Displaced burden")
        ax.axvline(0.0, linewidth=1)
        ax.set_yticks(y, row_labels if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.set_xlabel(unit)
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.16)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
    files = _save(fig, out / "paper_fig03_protection_redistribution")
    plt.close(fig)
    manifest.append(_manifest_row("P03", "Protection and displaced adjustment", "Who receives relief from protection rules and where is the fixed adjustment displaced?", files))

    # Figure 4: persistence and pathway-vs-allocation sensitivity.
    hist = tables["persistence_histogram"].copy()
    robust = tables["robust_exposure"].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.2), constrained_layout=True)
    hp = hist.pivot(index="FREQUENCY", columns="METRIC", values="ED_COUNT").fillna(0.0)
    max_runs = int(hp.index.max()) if len(hp.index) else 12
    hp = hp.reindex(range(max_runs + 1), fill_value=0.0)
    xx = np.arange(len(hp))
    width = 0.38
    for j, metric in enumerate(list(hp.columns)[:2]):
        axes[0].bar(xx + (j - 0.5) * width, hp[metric].to_numpy(float), width, label=metric)
    axes[0].set_xticks(xx, [str(i) for i in hp.index])
    axes[0].set_xlabel("Top-decile appearances across modeled futures")
    axes[0].set_ylabel("ED count")
    axes[0].set_title("A. Persistence of high exposure")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.16)
    xcol = "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT"
    ycol = "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT"
    xv = pd.to_numeric(robust[xcol], errors="coerce").to_numpy(float)
    yv = pd.to_numeric(robust[ycol], errors="coerce").to_numpy(float)
    axes[1].scatter(xv, yv, s=16, alpha=0.55)
    finite = np.isfinite(xv) & np.isfinite(yv)
    if finite.any():
        high = max(float(np.nanmax(xv[finite])), float(np.nanmax(yv[finite])))
        axes[1].plot([0, high], [0, high], linestyle="--", linewidth=1, label="Equal sensitivity")
    axes[1].set_xlabel("Pathway sensitivity (percentage points)")
    axes[1].set_ylabel("Allocation-rule sensitivity (percentage points)")
    axes[1].set_title("B. Pathway versus allocation sensitivity")
    axes[1].legend(loc="upper left")
    axes[1].grid(alpha=0.16)
    files = _save(fig, out / "paper_fig04_persistence_sensitivity")
    plt.close(fig)
    manifest.append(_manifest_row("P04", "Persistent versus contingent exposure", "Which EDs remain exposed across futures, and which are sensitive to pathway or policy allocation?", files))

    # Figure 5: system and natural-capital composition of released land.
    release = _prorata(tables["land_release_summary"], "STUDY_ALLOCATION_POLICY")
    release = _scenario_order(release, "STUDY_SCENARIO_ID")
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 5.2), constrained_layout=True)
    x = np.arange(len(release))
    labels = [SCENARIO_LABELS.get(str(s), str(s)) for s in release["STUDY_SCENARIO_ID"]]
    bottom = np.zeros(len(release))
    for system in ("DAIRY", "BEEF", "SHEEP"):
        vals = pd.to_numeric(release[f"{system}_RELEASE_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        axes[0].bar(x, vals, bottom=bottom, label=system.title())
        bottom += vals
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Released grassland (kha)")
    axes[0].set_title("A. Livestock-system origin")
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    axes[0].grid(axis="y", alpha=0.16)
    bottom = np.zeros(len(release))
    for group in ("G1", "G2", "G3"):
        vals = pd.to_numeric(release[f"{group}_RELEASE_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        axes[1].bar(x, vals, bottom=bottom, label=group)
        bottom += vals
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Released grassland (kha)")
    axes[1].set_title("B. Agricultural-capability composition")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    axes[1].grid(axis="y", alpha=0.16)
    files = _save(fig, out / "paper_fig05_released_land_composition")
    plt.close(fig)
    manifest.append(_manifest_row("P05", "Composition of released land", "What livestock systems and agricultural-capability classes account for released land?", files))

    # Figure 6: data-led exposure-vulnerability-opportunity transition conditions.
    selected_use, selection_reason = _select_opportunity_use(tables)
    eligibility_col = ELIGIBILITY_COVERAGE_COLUMNS[selected_use]
    conditions = tables["transition_conditions"]
    block = conditions.loc[
        conditions["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
        & conditions["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ].copy()
    required = ["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", eligibility_col]
    block = block.dropna(subset=[c for c in required if c in block.columns])
    fig, ax = plt.subplots(figsize=(7.6, 6.2), constrained_layout=True)
    xv = pd.to_numeric(block["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"], errors="coerce").to_numpy(float)
    yv = pd.to_numeric(block[eligibility_col], errors="coerce").to_numpy(float)
    release_ha = pd.to_numeric(block.get("GOBLIN_RELEASED_GRASSLAND_HA", 0.0), errors="coerce").fillna(0.0).to_numpy(float)
    max_release = float(np.nanmax(release_ha)) if len(release_ha) else 0.0
    sizes = 18.0 + (110.0 * np.sqrt(np.maximum(release_ha, 0.0) / max_release) if max_release > 0 else 0.0)
    vulnerability_col = "SOCIAL_VULNERABILITY_SCORE" if "SOCIAL_VULNERABILITY_SCORE" in block.columns else None
    if vulnerability_col:
        vulnerability = pd.to_numeric(block[vulnerability_col], errors="coerce").to_numpy(float)
        scatter = ax.scatter(xv, yv, s=sizes, c=vulnerability, alpha=0.68, edgecolors="none")
        cbar = fig.colorbar(scatter, ax=ax, pad=0.02)
        cbar.set_label("Social vulnerability score")
    else:
        ax.scatter(xv, yv, s=sizes, alpha=0.68)
    finite = np.isfinite(xv) & np.isfinite(yv)
    if finite.any():
        ax.axvline(float(np.nanmedian(xv[finite])), linestyle="--", linewidth=1)
        ax.axhline(float(np.nanmedian(yv[finite])), linestyle="--", linewidth=1)
    ax.set_xlabel("Gross Standard Output exposure (% of baseline)")
    ax.set_ylabel(f"{_friendly_use(selected_use)}-eligible share of released land (%)")
    ax.set_title("Local transition conditions: exposure, vulnerability and opportunity")
    ax.grid(alpha=0.14)
    files = _save(fig, out / "paper_fig06_transition_conditions")
    plt.close(fig)
    manifest.append(_manifest_row(
        "P06",
        "Local transition conditions",
        "Do highly exposed EDs also possess credible released-land opportunities, and how does vulnerability overlay that relationship?",
        files,
        note=f"Opportunity dimension: {_friendly_use(selected_use)}; selection rule: {selection_reason}.",
    ))

    # Figure 7: pathway targets, realised hectares and unmet hectares.
    mobilisation = _prorata(tables["opportunity_mobilisation"], "STUDY_ALLOCATION_POLICY")
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 5.2), sharey=True, constrained_layout=True)
    use_order = list(SC3_USES)
    for ax, scenario in zip(axes, PRINCIPAL_SCENARIOS):
        b = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
        realised = pd.to_numeric(b["REALISED_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        unmet = pd.to_numeric(b["UNMET_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
        xx = np.arange(len(use_order))
        ax.bar(xx, realised, label="Realised")
        ax.bar(xx, unmet, bottom=realised, label="Unmet")
        ax.set_xticks(xx, [_friendly_use(use).replace("Additional ", "") for use in use_order], rotation=35, ha="right")
        ax.set_title(SCENARIO_LABELS.get(scenario, scenario))
        ax.grid(axis="y", alpha=0.16)
    axes[0].set_ylabel("Pathway target (kha)")
    axes[1].set_xlabel("Alternative land use")
    axes[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2)
    files = _save(fig, out / "paper_fig07_target_delivery")
    plt.close(fig)
    manifest.append(_manifest_row("P07", "Spatial delivery of pathway land-use targets", "Can the national alternative land-use pathway actually be delivered on the released-land geography?", files))

    # Figure 8: opportunity mobilisation and shared-pool utilisation.
    pools = _prorata(tables["shared_pool_summary"], "STUDY_ALLOCATION_POLICY")
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4), constrained_layout=True)
    width = 0.24
    xx = np.arange(len(use_order))
    for j, scenario in enumerate(PRINCIPAL_SCENARIOS):
        b = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
        vals = pd.to_numeric(b["OPPORTUNITY_MOBILISATION_PCT"], errors="coerce").fillna(0.0).to_numpy(float)
        axes[0].bar(xx + (j - 1) * width, vals, width, label=SCENARIO_LABELS.get(scenario, scenario))
    axes[0].set_xticks(xx, [_friendly_use(use).replace("Additional ", "") for use in use_order], rotation=35, ha="right")
    axes[0].set_ylabel("Realised / eligible land (%)")
    axes[0].set_title("A. Pathway mobilisation of spatial opportunity")
    axes[0].grid(axis="y", alpha=0.16)
    pool_order = ["TILLAGE_WILLOW", "AD_BIOREFINERY", "FOREST_MINERAL"]
    pool_labels = ["Tillage–willow", "AD–biorefinery", "Forest–mineral"]
    px = np.arange(len(pool_order))
    for j, scenario in enumerate(PRINCIPAL_SCENARIOS):
        b = pools.loc[pools["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("SHARED_POOL").reindex(pool_order)
        vals = pd.to_numeric(b["UTILISATION_PCT"], errors="coerce").fillna(0.0).to_numpy(float)
        axes[1].bar(px + (j - 1) * width, vals, width, label=SCENARIO_LABELS.get(scenario, scenario))
    axes[1].set_xticks(px, pool_labels, rotation=20, ha="right")
    axes[1].set_ylabel("Shared-pool utilisation (%)")
    axes[1].set_title("B. Competition for overlapping eligible land")
    axes[1].grid(axis="y", alpha=0.16)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    files = _save(fig, out / "paper_fig08_opportunity_constraints")
    plt.close(fig)
    manifest.append(_manifest_row("P08", "Opportunity mobilisation and spatial constraints", "How much feasible opportunity is mobilised and where do overlapping land-use pools become binding?", files))

    manifest_path = out / "GOBLIN_Spatial_Paper_Figure_Manifest.csv"
    pd.DataFrame(manifest).to_csv(manifest_path, index=False)
    return {
        "paper_figure_directory": out,
        "paper_figure_manifest": manifest_path,
    }
