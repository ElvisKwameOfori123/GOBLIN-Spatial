"""Cross-run scientific reporting for the final GOBLIN-Spatial study.

This module is downstream of the model. It never changes SC1, SC2 or SC3
mathematics. It discovers completed principal-run directories, combines their
canonical CSV outputs, builds cross-run foresight diagnostics, writes a master
Excel workbook and SQLite database, and generates publication-grade comparison
figures.

The design follows the parent GOBLIN reporting philosophy: model results are
first materialised as structured data frames, and visualisations consume those
frames rather than recomputing model science.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable

import numpy as np
import pandas as pd

from goblin_spatial.reporting import (
    add_sc3_reporting_aliases,
    build_sc3_land_accounting_summary,
    build_sc3_validation_table,
)
from goblin_spatial.scenario.comparison import (
    build_sc1_robust_exposure,
    compare_sc1_to_prorata,
    summarise_sc1_redistribution,
)
from goblin_spatial.scenario.principal_allocation import PRINCIPAL_ALLOCATION_POLICIES


STUDY_REPORTING_VERSION = "1.0"
PRINCIPAL_SCENARIOS = ("SI_SG", "BE_SG", "ALL_GAS_NZ")
PRINCIPAL_RULES = tuple(PRINCIPAL_ALLOCATION_POLICIES)
SC3_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
    "REWETTING",
)

USE_LABELS = {
    "AD_GRASS": "AD grass",
    "BIOREFINERY_GRASS": "Biorefinery grass",
    "WILLOW": "Willow",
    "ADDITIONAL_TILLAGE": "Additional tillage",
    "FOREST": "Additional forest",
    "REWETTING": "Rewetting",
    "FINAL_RESIDUAL": "Final unallocated land",
}

RULE_LABELS = {
    "PRORATA": "Pro rata",
    "DAIRY_PROTECTION": "Dairy protection",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic vulnerability protection",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social vulnerability protection",
}


@dataclass(frozen=True)
class RunBundle:
    run_dir: Path
    scenario_id: str
    scenario_name: str
    allocation_policy: str
    controls: pd.DataFrame
    livestock: pd.DataFrame
    metrics: pd.DataFrame
    county: pd.DataFrame
    reconciliation: pd.DataFrame
    sc1_ed: pd.DataFrame
    sc2_ed: pd.DataFrame
    sc3_ed: pd.DataFrame
    sc3_national: pd.DataFrame
    accounting: pd.DataFrame
    validation: pd.DataFrame


def _read_required(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path, low_memory=False)


def _identity(frame: pd.DataFrame, bundle: RunBundle | None = None, *, scenario: str | None = None,
              rule: str | None = None, run_dir: Path | None = None) -> pd.DataFrame:
    out = frame.copy()
    scenario_id = scenario if scenario is not None else bundle.scenario_id  # type: ignore[union-attr]
    allocation_rule = rule if rule is not None else bundle.allocation_policy  # type: ignore[union-attr]
    directory = run_dir if run_dir is not None else bundle.run_dir  # type: ignore[union-attr]
    out["STUDY_SCENARIO_ID"] = str(scenario_id)
    out["STUDY_ALLOCATION_POLICY"] = str(allocation_rule)
    out["STUDY_RUN_DIR"] = str(directory)
    return out


def _discover_run_dirs(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"study root not found: {root}")
    dirs = sorted({p.parent for p in root.rglob("sc1_control_summary.csv")})
    if not dirs:
        raise FileNotFoundError(
            f"no completed principal runs found beneath {root}; expected sc1_control_summary.csv"
        )
    return dirs


def _load_run(run_dir: Path) -> RunBundle:
    controls = _read_required(run_dir / "sc1_control_summary.csv", "SC1 control summary")
    if len(controls) != 1:
        raise ValueError(f"{run_dir}: sc1_control_summary.csv must contain exactly one row")
    c = controls.iloc[0]
    scenario_id = str(c["SCENARIO_ID"])
    scenario_name = str(c.get("SCENARIO_NAME", scenario_id))
    allocation_policy = str(c["ALLOCATION_POLICY"])

    livestock = _read_required(run_dir / "sc1_national_livestock_summary.csv", "SC1 national livestock summary")
    metrics = _read_required(run_dir / "sc1_national_metrics.csv", "SC1 national metrics")
    county = _read_required(run_dir / "sc1_county_summary.csv", "SC1 county summary")
    reconciliation = _read_required(run_dir / "sc1_goblin_reconciliation.csv", "SC1 reconciliation")
    sc1_ed = _read_required(run_dir / "sc1_ed_results.csv", "SC1 ED results")
    sc2_ed = _read_required(run_dir / "sc2_ed_context.csv", "SC2 ED context")
    sc3_ed = _read_required(run_dir / "sc3_ed_results.csv", "SC3 ED results")
    sc3_national = _read_required(run_dir / "sc3_national_summary.csv", "SC3 national summary")

    required_controls = {
        "RUN_GROSS_RELEASE_HA",
        "STAGE_A_TARGET_HA",
        "GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA",
        "REWETTING_TARGET_HA",
    }
    missing = sorted(required_controls - set(controls.columns))
    if missing:
        raise ValueError(f"{run_dir}: control summary missing {missing}")

    enriched_sc3 = add_sc3_reporting_aliases(sc3_ed)
    accounting = build_sc3_land_accounting_summary(
        enriched_sc3,
        gross_release_ha=float(c["RUN_GROSS_RELEASE_HA"]),
        stage_a_target_ha=float(c["STAGE_A_TARGET_HA"]),
        parent_available_target_ha=float(c["GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA"]),
        rewetting_target_ha=float(c["REWETTING_TARGET_HA"]),
    )
    validation = build_sc3_validation_table(enriched_sc3, accounting)
    if not validation["STATUS"].eq("PASS").all():
        failed = validation.loc[~validation["STATUS"].eq("PASS"), "CHECK"].tolist()
        raise AssertionError(f"{run_dir}: scientific validation failed: {failed}")

    return RunBundle(
        run_dir=run_dir,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        allocation_policy=allocation_policy,
        controls=controls,
        livestock=livestock,
        metrics=metrics,
        county=county,
        reconciliation=reconciliation,
        sc1_ed=sc1_ed,
        sc2_ed=sc2_ed,
        sc3_ed=enriched_sc3,
        sc3_national=sc3_national,
        accounting=accounting,
        validation=validation,
    )


def _validate_matrix(bundles: list[RunBundle], *, require_complete_matrix: bool) -> None:
    keys = [(b.scenario_id, b.allocation_policy) for b in bundles]
    if len(keys) != len(set(keys)):
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(f"duplicate scenario/allocation runs found: {duplicates}")

    if not require_complete_matrix:
        return
    expected = {(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES}
    found = set(keys)
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    if missing or extra:
        raise ValueError(
            "final principal study requires the exact 3 pathway x 4 allocation-rule matrix; "
            f"missing={missing}, extra={extra}"
        )


def _merge_one_row_frames(bundle: RunBundle) -> dict[str, object]:
    row: dict[str, object] = {
        "SCENARIO_ID": bundle.scenario_id,
        "SCENARIO_NAME": bundle.scenario_name,
        "ALLOCATION_POLICY": bundle.allocation_policy,
        "ALLOCATION_POLICY_LABEL": RULE_LABELS.get(bundle.allocation_policy, bundle.allocation_policy),
        "RUN_DIR": str(bundle.run_dir),
    }

    for frame in (bundle.controls, bundle.livestock, bundle.metrics, bundle.accounting, bundle.sc3_national):
        if len(frame) != 1:
            continue
        for key, value in frame.iloc[0].items():
            if key not in row:
                row[key] = value
            elif row[key] != value:
                row[f"SOURCE_{key}"] = value
    return row


def _combined_frames(bundles: list[RunBundle]) -> dict[str, pd.DataFrame]:
    national = pd.DataFrame([_merge_one_row_frames(b) for b in bundles])
    registry = pd.DataFrame(
        [
            {
                "SCENARIO_ID": b.scenario_id,
                "SCENARIO_NAME": b.scenario_name,
                "ALLOCATION_POLICY": b.allocation_policy,
                "ALLOCATION_POLICY_LABEL": RULE_LABELS.get(b.allocation_policy, b.allocation_policy),
                "RUN_DIR": str(b.run_dir),
                "SC1_ROWS": len(b.sc1_ed),
                "SC2_ROWS": len(b.sc2_ed),
                "SC3_ROWS": len(b.sc3_ed),
                "VALIDATION_STATUS": "PASS" if b.validation["STATUS"].eq("PASS").all() else "FAIL",
            }
            for b in bundles
        ]
    )

    def combine(attr: str) -> pd.DataFrame:
        frames = []
        for b in bundles:
            frame = getattr(b, attr)
            frames.append(_identity(frame, b))
        return pd.concat(frames, ignore_index=True, sort=False)

    sc1_ed = combine("sc1_ed")
    sc1_ed["PATHWAY_NAME"] = sc1_ed["STUDY_SCENARIO_ID"].astype(str)
    sc1_ed["PATHWAY_ALLOCATION_RULE"] = sc1_ed["STUDY_ALLOCATION_POLICY"].astype(str)

    compared = compare_sc1_to_prorata(sc1_ed)
    robust = build_sc1_robust_exposure(sc1_ed)
    redistribution = summarise_sc1_redistribution(compared)

    return {
        "run_registry": registry,
        "national_results": national,
        "controls": combine("controls"),
        "livestock": combine("livestock"),
        "metrics": combine("metrics"),
        "county": combine("county"),
        "reconciliation": combine("reconciliation"),
        "land_accounting": combine("accounting"),
        "validation": combine("validation"),
        "sc3_national": combine("sc3_national"),
        "sc1_ed": sc1_ed,
        "sc2_ed": combine("sc2_ed"),
        "sc3_ed": combine("sc3_ed"),
        "sc1_comparison": compared,
        "redistribution": redistribution,
        "robust_exposure": robust,
    }


def _figure_data(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    national = tables["national_results"]

    def add(fig: str, scenario: str, rule: str, component: str, value: float, unit: str) -> None:
        rows.append(
            {
                "FIGURE_ID": fig,
                "SCENARIO_ID": scenario,
                "ALLOCATION_POLICY": rule,
                "COMPONENT": component,
                "VALUE": float(value),
                "UNIT": unit,
            }
        )

    for _, r in national.iterrows():
        scenario = str(r["SCENARIO_ID"])
        rule = str(r["ALLOCATION_POLICY"])
        if rule == "PRORATA":
            dairy = float(r.get("SCENARIO_DAIRY_COW", r.get("SCENARIO_DAIRY_COWS", 0.0)))
            suckler = float(r.get("SCENARIO_SUCKLER_COW", r.get("SCENARIO_SUCKLER_COWS", 0.0)))
            total = float(r.get("SCENARIO_TOTAL_CATTLE", 0.0))
            followers = max(total - dairy - suckler, 0.0)
            add("F01_LIVESTOCK_ENDPOINT", scenario, rule, "Dairy cows", dairy, "head")
            add("F01_LIVESTOCK_ENDPOINT", scenario, rule, "Suckler cows", suckler, "head")
            add("F01_LIVESTOCK_ENDPOINT", scenario, rule, "Follower/other cattle", followers, "head")

        so_loss = r.get("GROSS_SO_LIVESTOCK_LOSS_2020_EUR", np.nan)
        if pd.notna(so_loss):
            add("F02_SO_EXPOSURE", scenario, rule, "Gross SO loss", float(so_loss) / 1e6, "EUR million")

        for use in SC3_USES:
            value = r.get(f"REALISED_{use}_HA", np.nan)
            if pd.notna(value):
                add("F03_LAND_ALLOCATION", scenario, rule, USE_LABELS[use], float(value) / 1000.0, "kha")
            unmet = r.get(f"UNMET_{use}_HA", np.nan)
            if pd.notna(unmet):
                add("F04_UNMET_TARGETS", scenario, rule, USE_LABELS[use], float(unmet) / 1000.0, "kha")
        final_resid = r.get("SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA", np.nan)
        if pd.notna(final_resid):
            add("F03_LAND_ALLOCATION", scenario, rule, USE_LABELS["FINAL_RESIDUAL"], float(final_resid) / 1000.0, "kha")

    redistribution = tables["redistribution"]
    suffix = "SO_LIVESTOCK_GROSS_LOSS_2020_EUR"
    relief_col = f"TOTAL_PROTECTION_RELIEF_{suffix}"
    burden_col = f"TOTAL_DISPLACED_BURDEN_{suffix}"
    if relief_col in redistribution.columns and burden_col in redistribution.columns:
        for _, r in redistribution.iterrows():
            scenario = str(r["PATHWAY_NAME"])
            rule = str(r["PATHWAY_ALLOCATION_RULE"])
            if rule == "PRORATA":
                continue
            add("F05_REDISTRIBUTION", scenario, rule, "Protection relief", float(r[relief_col]) / 1e6, "EUR million")
            add("F05_REDISTRIBUTION", scenario, rule, "Displaced burden", float(r[burden_col]) / 1e6, "EUR million")

    return pd.DataFrame(rows)


def _run_label(scenario: str, rule: str) -> str:
    short = {
        "PRORATA": "PR",
        "DAIRY_PROTECTION": "DP",
        "ECONOMIC_CAPACITY_PROTECTION": "EP",
        "SOCIAL_VULNERABILITY_PROTECTION": "SP",
    }.get(rule, rule)
    return f"{scenario}\n{short}"


def _save_figure(fig, output_base: Path) -> list[Path]:
    paths = []
    for suffix in (".png", ".svg"):
        path = output_base.with_suffix(suffix)
        kwargs = {"bbox_inches": "tight"}
        if suffix == ".png":
            kwargs["dpi"] = 400
        fig.savefig(path, **kwargs)
        paths.append(path)
    return paths


def _setup_matplotlib():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.frameon": False,
            "legend.fontsize": 8.5,
            "font.size": 9.5,
        }
    )
    return plt


def generate_study_figures(tables: dict[str, pd.DataFrame], figure_data: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Generate a compact, high-resolution GOBLIN-style comparison suite."""

    plt = _setup_matplotlib()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    f1 = figure_data.loc[figure_data["FIGURE_ID"].eq("F01_LIVESTOCK_ENDPOINT")].copy()
    if not f1.empty:
        pivot = f1.pivot(index="SCENARIO_ID", columns="COMPONENT", values="VALUE").reindex(PRINCIPAL_SCENARIOS)
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        bottom = np.zeros(len(pivot))
        for component in ("Dairy cows", "Suckler cows", "Follower/other cattle"):
            values = pivot.get(component, pd.Series(0.0, index=pivot.index)).fillna(0.0).to_numpy(float)
            ax.bar(pivot.index, values, bottom=bottom, label=component)
            bottom += values
        ax.set_ylabel("Cattle head")
        ax.set_title("National cattle composition at the 2050 pathway endpoint")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig01_livestock_endpoint")
        plt.close(fig)

    f2 = figure_data.loc[figure_data["FIGURE_ID"].eq("F02_SO_EXPOSURE")].copy()
    if not f2.empty:
        order = [(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES]
        lookup = {(str(r.SCENARIO_ID), str(r.ALLOCATION_POLICY)): float(r.VALUE) for r in f2.itertuples()}
        labels = [_run_label(s, r) for s, r in order if (s, r) in lookup]
        values = [lookup[(s, r)] for s, r in order if (s, r) in lookup]
        fig, ax = plt.subplots(figsize=(10.5, 5.0))
        ax.bar(labels, values)
        ax.set_ylabel("Gross Standard Output exposure (EUR million)")
        ax.set_title("Production-value exposure across pathways and incidence rules")
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig02_standard_output_exposure")
        plt.close(fig)

    f3 = figure_data.loc[figure_data["FIGURE_ID"].eq("F03_LAND_ALLOCATION")].copy()
    if not f3.empty:
        order = [(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES]
        components = [USE_LABELS[u] for u in SC3_USES] + [USE_LABELS["FINAL_RESIDUAL"]]
        fig, ax = plt.subplots(figsize=(11.5, 6.0))
        bottoms = np.zeros(len(order))
        labels = [_run_label(s, r) for s, r in order]
        for component in components:
            vals = []
            for scenario, rule in order:
                hit = f3.loc[
                    f3["SCENARIO_ID"].eq(scenario)
                    & f3["ALLOCATION_POLICY"].eq(rule)
                    & f3["COMPONENT"].eq(component),
                    "VALUE",
                ]
                vals.append(float(hit.iloc[0]) if not hit.empty else 0.0)
            values = np.asarray(vals, float)
            ax.bar(labels, values, bottom=bottoms, label=component)
            bottoms += values
        ax.set_ylabel("Released-land allocation (kha)")
        ax.set_title("Spatial allocation of released livestock land")
        ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig03_released_land_allocation")
        plt.close(fig)

    f4 = figure_data.loc[figure_data["FIGURE_ID"].eq("F04_UNMET_TARGETS")].copy()
    if not f4.empty and float(f4["VALUE"].abs().sum()) > 1e-9:
        order = [(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES]
        components = [USE_LABELS[u] for u in SC3_USES]
        fig, ax = plt.subplots(figsize=(11.5, 5.5))
        bottoms = np.zeros(len(order))
        labels = [_run_label(s, r) for s, r in order]
        for component in components:
            vals = []
            for scenario, rule in order:
                hit = f4.loc[
                    f4["SCENARIO_ID"].eq(scenario)
                    & f4["ALLOCATION_POLICY"].eq(rule)
                    & f4["COMPONENT"].eq(component),
                    "VALUE",
                ]
                vals.append(float(hit.iloc[0]) if not hit.empty else 0.0)
            values = np.asarray(vals, float)
            ax.bar(labels, values, bottom=bottoms, label=component)
            bottoms += values
        ax.set_ylabel("Unmet target (kha)")
        ax.set_title("Spatially unmet land-use targets")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig04_unmet_land_targets")
        plt.close(fig)

    f5 = figure_data.loc[figure_data["FIGURE_ID"].eq("F05_REDISTRIBUTION")].copy()
    if not f5.empty:
        pivot = f5.pivot_table(
            index=["SCENARIO_ID", "ALLOCATION_POLICY"],
            columns="COMPONENT",
            values="VALUE",
            aggfunc="sum",
        )
        labels = [_run_label(str(s), str(r)) for s, r in pivot.index]
        x = np.arange(len(pivot), dtype=float)
        width = 0.38
        relief = pivot.get("Protection relief", pd.Series(0.0, index=pivot.index)).to_numpy(float)
        burden = pivot.get("Displaced burden", pd.Series(0.0, index=pivot.index)).to_numpy(float)
        fig, ax = plt.subplots(figsize=(10.5, 5.3))
        ax.bar(x - width / 2, relief, width, label="Protection relief")
        ax.bar(x + width / 2, burden, width, label="Displaced burden")
        ax.set_xticks(x, labels)
        ax.set_ylabel("Standard Output redistribution (EUR million)")
        ax.set_title("Redistribution of production-value exposure relative to pro rata")
        ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.14))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig05_protection_redistribution")
        plt.close(fig)

    robust = tables["robust_exposure"]
    xcol = "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT"
    ycol = "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT"
    if xcol in robust.columns and ycol in robust.columns and not robust.empty:
        fig, ax = plt.subplots(figsize=(7.2, 6.0))
        ax.scatter(
            pd.to_numeric(robust[xcol], errors="raise"),
            pd.to_numeric(robust[ycol], errors="raise"),
            s=14,
            alpha=0.55,
        )
        ax.set_xlabel("Pathway sensitivity (percentage points)")
        ax.set_ylabel("Allocation-rule sensitivity (percentage points)")
        ax.set_title("ED sensitivity to national pathway and spatial incidence rule")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig06_pathway_allocation_sensitivity")
        plt.close(fig)

    return outputs


def _format_sheet(writer: pd.ExcelWriter, name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[name]
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(1, 0)
    if len(frame.columns):
        worksheet.autofilter(0, 0, max(len(frame), 1), len(frame.columns) - 1)
    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    num = workbook.add_format({"num_format": "#,##0.00"})
    integer = workbook.add_format({"num_format": "#,##0"})
    for col, column in enumerate(frame.columns):
        worksheet.write(0, col, column, header)
        text_col = str(column).upper()
        width = max(12, min(34, len(str(column)) + 2))
        if any(token in text_col for token in ("DESCRIPTION", "INTERPRETATION", "CHECK", "RUN_DIR")):
            width = 40
        fmt = None
        if any(text_col.endswith(suffix) for suffix in ("_HA", "_EUR", "_PCT")):
            fmt = num
        elif any(text_col.endswith(suffix) for suffix in ("_YEAR", "_COUNT", "_HEAD")):
            fmt = integer
        worksheet.set_column(col, col, width, fmt)
    worksheet.set_row(0, 28)
    if "STATUS" in frame.columns:
        idx = int(frame.columns.get_loc("STATUS"))
        worksheet.conditional_format(1, idx, max(len(frame), 1), idx, {
            "type": "text",
            "criteria": "containing",
            "value": "PASS",
            "format": workbook.add_format({"bg_color": "#E2F0D9", "font_color": "#375623"}),
        })
        worksheet.conditional_format(1, idx, max(len(frame), 1), idx, {
            "type": "text",
            "criteria": "containing",
            "value": "FAIL",
            "format": workbook.add_format({"bg_color": "#FCE4D6", "font_color": "#9C0006"}),
        })


def _read_me(root: Path, require_complete_matrix: bool) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ITEM": "Purpose", "VALUE": "Final cross-run scientific reporting package for GOBLIN-Spatial."},
            {"ITEM": "Canonical data", "VALUE": "The workbook, SQLite database and figures are derived from completed SC1-SC3 CSV runs; canonical run CSVs are never overwritten."},
            {"ITEM": "Principal design", "VALUE": "Three national pathways x four spatial incidence rules = 12 principal 2020 runs."},
            {"ITEM": "Matrix requirement", "VALUE": "Exact 12-run matrix required" if require_complete_matrix else "Partial study allowed for development/testing"},
            {"ITEM": "Land accounting", "VALUE": "Parent GOBLIN Available, realised post-Stage-A unallocated release, and final post-rewetting residual remain distinct."},
            {"ITEM": "Figures", "VALUE": "High-resolution PNG and vector SVG figures are generated from structured figure-data tables, following the parent GOBLIN separation of results and graphics."},
            {"ITEM": "Maps", "VALUE": "Maps are intentionally outside this reporting version and can be added after the tabular and graph result layer is frozen."},
            {"ITEM": "Study root", "VALUE": str(root)},
            {"ITEM": "Reporting version", "VALUE": STUDY_REPORTING_VERSION},
        ]
    )


def _data_dictionary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("STUDY_SCENARIO_ID", "", "National GOBLIN pathway identifier for the completed run."),
            ("STUDY_ALLOCATION_POLICY", "", "Spatial incidence rule used to distribute the fixed national pathway."),
            ("GOBLIN_PARENT_AVAILABLE_TARGET_HA", "ha", "Parent pathway residual after national Stage-A targets; not a realised ED allocation."),
            ("SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA", "ha", "Realised released land left after feasible Stage-A allocation."),
            ("SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA", "ha", "Strict physical residual after realised Stage-A uses and rewetting."),
            ("ROBUST_MIN_CATTLE_REDUCTION_PCT", "%", "Minimum ED cattle-reduction exposure observed across all supplied pathway/rule runs."),
            ("PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT", "percentage points", "Maximum between-pathway ED exposure range while holding the incidence rule fixed."),
            ("ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT", "percentage points", "Maximum between-rule ED exposure range while holding the national pathway fixed."),
        ],
        columns=["VARIABLE", "UNIT", "INTERPRETATION"],
    )


def _write_sqlite(path: Path, tables: dict[str, pd.DataFrame], figure_data: pd.DataFrame) -> None:
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        for name, frame in tables.items():
            frame.to_sql(name, connection, if_exists="replace", index=False)
        figure_data.to_sql("figure_data", connection, if_exists="replace", index=False)
        pd.DataFrame(
            [{"reporting_version": STUDY_REPORTING_VERSION, "table_count": len(tables) + 1}]
        ).to_sql("report_metadata", connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sc1_ed_run ON sc1_ed (STUDY_SCENARIO_ID, STUDY_ALLOCATION_POLICY, CSOED)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sc3_ed_run ON sc3_ed (STUDY_SCENARIO_ID, STUDY_ALLOCATION_POLICY, CSOED)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_county_run ON county (STUDY_SCENARIO_ID, STUDY_ALLOCATION_POLICY)")
        connection.commit()


def export_study_results(
    study_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    require_complete_matrix: bool = True,
    generate_figures: bool = True,
) -> dict[str, Path]:
    """Build the final workbook, SQLite database and graph package."""

    root = Path(study_root)
    out = Path(output_dir) if output_dir is not None else root / "final_results"
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    bundles = [_load_run(path) for path in _discover_run_dirs(root)]
    _validate_matrix(bundles, require_complete_matrix=require_complete_matrix)
    bundles = sorted(
        bundles,
        key=lambda b: (
            PRINCIPAL_SCENARIOS.index(b.scenario_id) if b.scenario_id in PRINCIPAL_SCENARIOS else 999,
            PRINCIPAL_RULES.index(b.allocation_policy) if b.allocation_policy in PRINCIPAL_RULES else 999,
        ),
    )

    tables = _combined_frames(bundles)
    fig_data = _figure_data(tables)
    tables["figure_data"] = fig_data

    figure_dir = out / "figures"
    figure_paths: list[Path] = []
    if generate_figures:
        figure_paths = generate_study_figures(tables, fig_data, figure_dir)

    sqlite_path = out / "GOBLIN_Spatial_Final_Results.sqlite"
    _write_sqlite(sqlite_path, {k: v for k, v in tables.items() if k != "figure_data"}, fig_data)

    workbook_path = out / "GOBLIN_Spatial_Final_Results_Master.xlsx"
    sheets: list[tuple[str, pd.DataFrame]] = [
        ("00_Read_Me", _read_me(root, require_complete_matrix)),
        ("01_Run_Registry", tables["run_registry"]),
        ("02_National_Results", tables["national_results"]),
        ("03_Livestock", tables["livestock"]),
        ("04_SC1_Metrics", tables["metrics"]),
        ("05_Land_Accounting", tables["land_accounting"]),
        ("06_SC3_Allocation", tables["sc3_national"]),
        ("07_Validation", tables["validation"]),
        ("08_Protection_PRORATA", tables["sc1_comparison"]),
        ("09_Redistribution", tables["redistribution"]),
        ("10_Robust_Exposure", tables["robust_exposure"]),
        ("11_County_Results", tables["county"]),
        ("12_ED_SC1", tables["sc1_ed"]),
        ("13_ED_SC2", tables["sc2_ed"]),
        ("14_ED_SC3", tables["sc3_ed"]),
        ("15_Reconciliation", tables["reconciliation"]),
        ("16_Figure_Data", fig_data),
        ("17_Data_Dictionary", _data_dictionary()),
    ]

    with pd.ExcelWriter(
        workbook_path,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}},
    ) as writer:
        for sheet_name, frame in sheets:
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            _format_sheet(writer, sheet_name, frame)

        if figure_paths:
            figure_sheet = writer.book.add_worksheet("18_Figures")
            writer.sheets["18_Figures"] = figure_sheet
            figure_sheet.hide_gridlines(2)
            figure_sheet.set_column("A:A", 3)
            figure_sheet.set_column("B:N", 14)
            row = 1
            for png in [p for p in figure_paths if p.suffix.lower() == ".png"]:
                figure_sheet.write(row, 1, png.stem.replace("_", " ").title())
                figure_sheet.insert_image(row + 1, 1, str(png), {"x_scale": 0.72, "y_scale": 0.72})
                row += 27

    if not workbook_path.exists() or not sqlite_path.exists():
        raise AssertionError("final study reporting package was not created")

    outputs: dict[str, Path] = {
        "workbook": workbook_path,
        "sqlite": sqlite_path,
        "figure_data_csv": out / "GOBLIN_Spatial_Figure_Data.csv",
        "figure_directory": figure_dir,
    }
    fig_data.to_csv(outputs["figure_data_csv"], index=False)
    return outputs
