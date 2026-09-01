"""Final manuscript diagnostics and publication figures for GOBLIN-Spatial.

This module is deliberately downstream of the frozen final-results package.  It
adds no scenario science and changes no SC1/SC2/SC3 allocation.  Its purpose is
to answer the final manuscript gates and render the agreed Python-reproducible
Figures 2--7 from authoritative result tables.

The package tests rather than assumes the connection between the two spatial
allocation problems:

    national pathway -> territorial exposure -> released-land geography
    -> competing land claims -> territorial feasibility.

Figure 1 is the conceptual schematic and is maintained separately.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.map_reporting import (
    build_joined_map_layer,
    prepare_model_geometry,
    resolve_geometry_path,
)

VERSION = "1.0"
MAIN_SCENARIOS = ("BE_SG", "ALL_GAS_NZ")
ALL_SCENARIOS = ("SI_SG", "BE_SG", "ALL_GAS_NZ")
RULES = (
    "PRORATA",
    "DAIRY_PROTECTION",
    "ECONOMIC_CAPACITY_PROTECTION",
    "SOCIAL_VULNERABILITY_PROTECTION",
)
PROTECTION_RULES = RULES[1:]
SCENARIO_LABELS = {
    "SI_SG": "SI-SG",
    "BE_SG": "BE-SG",
    "ALL_GAS_NZ": "All-gas NZ",
}
RULE_LABELS = {
    "PRORATA": "Proportional",
    "DAIRY_PROTECTION": "Dairy dependence",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic vulnerability",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social vulnerability",
}
USE_LABELS = {
    "AD_GRASS": "AD grass",
    "BIOREFINERY_GRASS": "Biorefinery grass",
    "WILLOW": "Willow",
    "ADDITIONAL_TILLAGE": "Additional tillage",
    "FOREST": "Forestry",
    "REWETTING": "Rewetting",
}


def _read_sqlite(path: Path) -> dict[str, pd.DataFrame]:
    with sqlite3.connect(path) as con:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {name: pd.read_sql_query(f'SELECT * FROM "{name}"', con) for name in names}


def _num(frame: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(float(default), index=frame.index, dtype=float)
    return pd.to_numeric(frame[name], errors="coerce").fillna(float(default))


def _gini(values) -> float:
    x = np.maximum(np.nan_to_num(np.asarray(values, dtype=float), nan=0.0), 0.0)
    if len(x) == 0 or x.sum() <= 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return float((2.0 * np.dot(np.arange(1, n + 1), x) / (n * x.sum())) - (n + 1.0) / n)


def _eds_for_share(values, share: float = 0.5) -> int:
    x = np.sort(np.maximum(np.nan_to_num(np.asarray(values, dtype=float), nan=0.0), 0.0))[::-1]
    if len(x) == 0 or x.sum() <= 0:
        return 0
    return int(np.searchsorted(np.cumsum(x), float(share) * x.sum(), side="left") + 1)


def _theil_t(values, groups: pd.Series) -> dict[str, float]:
    """Additive Theil-T decomposition into within- and between-group terms."""
    x = np.maximum(np.nan_to_num(np.asarray(values, dtype=float), nan=0.0), 0.0)
    n = len(x)
    mu = float(x.mean()) if n else 0.0
    if n == 0 or mu <= 0:
        return {
            "THEIL_TOTAL": 0.0,
            "THEIL_WITHIN": 0.0,
            "THEIL_BETWEEN": 0.0,
            "WITHIN_SHARE_PCT": 0.0,
            "BETWEEN_SHARE_PCT": 0.0,
            "CLOSURE": 0.0,
        }
    ratio = x / mu
    positive = ratio > 0
    total = float(np.mean(np.where(positive, ratio * np.log(ratio), 0.0)))
    g = groups.astype("string").fillna("<NA>").to_numpy()
    within = 0.0
    between = 0.0
    for label in pd.unique(g):
        mask = g == label
        xg = x[mask]
        ng = len(xg)
        if ng == 0:
            continue
        mug = float(xg.mean())
        if mug <= 0:
            continue
        pg = ng / n
        income_share = pg * mug / mu
        rg = xg / mug
        posg = rg > 0
        tg = float(np.mean(np.where(posg, rg * np.log(rg), 0.0)))
        within += income_share * tg
        between += income_share * np.log(mug / mu)
    within = max(float(within), 0.0)
    between = max(float(between), 0.0)
    return {
        "THEIL_TOTAL": total,
        "THEIL_WITHIN": within,
        "THEIL_BETWEEN": between,
        "WITHIN_SHARE_PCT": 100.0 * within / total if total > 0 else 0.0,
        "BETWEEN_SHARE_PCT": 100.0 * between / total if total > 0 else 0.0,
        "CLOSURE": total - within - between,
    }


def _prorata(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].copy()


def _run(frame: pd.DataFrame, scenario: str, rule: str) -> pd.DataFrame:
    return frame.loc[
        frame["STUDY_SCENARIO_ID"].astype(str).eq(str(scenario))
        & frame["STUDY_ALLOCATION_POLICY"].astype(str).eq(str(rule))
    ].copy()


def _baseline_names(project_root: Path) -> pd.DataFrame:
    path = project_root / "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"
    x = pd.read_csv(path, usecols=["CSOED", "EDNAME", "County"], dtype={"CSOED": "string"})
    x["CSOED"] = x["CSOED"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.lstrip("0")
    x["CSOED"] = x["CSOED"].mask(x["CSOED"].eq(""), "0")
    return x.drop_duplicates("CSOED")


def build_diagnostics(tables: dict[str, pd.DataFrame], sensitivity: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    c = tables["transition_conditions"].copy()
    if "County" not in c.columns:
        raise ValueError("transition_conditions requires County for manuscript diagnostics")

    # Gate 1: baseline comparator + additive Theil T.
    base_block = _run(c, "BE_SG", "PRORATA")
    base_so = _num(base_block, "BASE_SO_LIVESTOCK_2020_EUR")
    rows = []
    b = _theil_t(base_so, base_block["County"])
    rows.append({
        "GEOGRAPHY": "BASELINE_LIVESTOCK_SO",
        "SCENARIO": "BASELINE",
        "RULE": "BASELINE",
        "TOTAL_EUR": float(base_so.sum()),
        "GINI": _gini(base_so),
        "EDS_FOR_50PCT": _eds_for_share(base_so),
        **b,
    })
    for scenario in ALL_SCENARIOS:
        block = _run(c, scenario, "PRORATA")
        loss = _num(block, "SO_LIVESTOCK_GROSS_LOSS_2020_EUR")
        d = _theil_t(loss, block["County"])
        rows.append({
            "GEOGRAPHY": "SO_GROSS_EXPOSURE",
            "SCENARIO": scenario,
            "RULE": "PRORATA",
            "TOTAL_EUR": float(loss.sum()),
            "GINI": _gini(loss),
            "EDS_FOR_50PCT": _eds_for_share(loss),
            **d,
        })
    theil = pd.DataFrame(rows)

    # Gate 2: capability composition across rules under the deep pathway.
    lr = tables["land_release_summary"].copy()
    all_lr = lr.loc[lr["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")].copy()
    cap_rows = []
    pr = all_lr.loc[all_lr["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].iloc[0]
    for group in ("G1", "G2", "G3"):
        col = f"{group}_RELEASE_SHARE_PCT"
        vals = pd.to_numeric(all_lr[col], errors="coerce")
        pr_val = float(pr[col])
        cap_rows.append({
            "CAPABILITY_GROUP": group,
            "PRORATA_SHARE_PCT": pr_val,
            "MIN_SHARE_PCT": float(vals.min()),
            "MAX_SHARE_PCT": float(vals.max()),
            "RANGE_PP": float(vals.max() - vals.min()),
            "MAX_ABS_DIFFERENCE_FROM_PRORATA_PP": float(np.max(np.abs(vals - pr_val))),
        })
    capability = pd.DataFrame(cap_rows)

    # Gate 3: SC3 target, realised, use-specific unused eligibility and explicit constraints.
    om = tables["opportunity_mobilisation"].copy()
    feasibility = om[[
        "STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY", "LAND_USE", "LAND_USE_LABEL",
        "ELIGIBLE_HA", "TARGET_HA", "REALISED_HA", "UNMET_HA", "UNUSED_ELIGIBLE_HA",
        "TARGET_REALISATION_PCT", "OPPORTUNITY_MOBILISATION_PCT",
    ]].copy()
    feasibility["PREALLOCATION_ELIGIBILITY_HEADROOM_HA"] = (
        pd.to_numeric(feasibility["ELIGIBLE_HA"], errors="coerce")
        - pd.to_numeric(feasibility["TARGET_HA"], errors="coerce")
    )
    rw = tables.get("rewetting_summary", pd.DataFrame()).copy()
    if not rw.empty:
        rw["POST_STAGE_A_REWETTING_MARGIN_HA"] = (
            pd.to_numeric(rw["POST_STAGE_A_CAPACITY_HA"], errors="coerce")
            - pd.to_numeric(rw["TARGET_HA"], errors="coerce")
        )
    pools = tables.get("shared_pool_summary", pd.DataFrame()).copy()
    if not pools.empty:
        pools["POOL_HEADROOM_HA"] = pd.to_numeric(pools["CAPACITY_HA"], errors="coerce") - pd.to_numeric(pools["USED_HA"], errors="coerce")

    # Gate 5: persistence against the null of baseline production concentration.
    persistence = tables["persistence"].copy()
    bso = base_block[["CSOED", "BASE_SO_LIVESTOCK_2020_EUR"]].copy()
    positive = pd.to_numeric(bso["BASE_SO_LIVESTOCK_2020_EUR"], errors="coerce").fillna(0.0)
    threshold = float(positive.loc[positive > 0].quantile(0.90)) if (positive > 0).any() else np.inf
    bso["BASELINE_TOP_DECILE_SO"] = positive.ge(threshold) & positive.gt(0)
    p = persistence.merge(bso[["CSOED", "BASELINE_TOP_DECILE_SO"]], on="CSOED", how="left", validate="one_to_one")
    freq_col = "TOP_DECILE_SO_FREQUENCY"
    p["PERSISTENT_ALL_12"] = pd.to_numeric(p[freq_col], errors="coerce").fillna(0).eq(12)
    p["PERSISTENT_9PLUS"] = pd.to_numeric(p[freq_col], errors="coerce").fillna(0).ge(9)
    persistence_summary = pd.DataFrame([
        {
            "CLASS": "Persistent all 12",
            "ED_COUNT": int(p["PERSISTENT_ALL_12"].sum()),
            "BASELINE_TOP_DECILE_OVERLAP": int((p["PERSISTENT_ALL_12"] & p["BASELINE_TOP_DECILE_SO"].fillna(False)).sum()),
            "NOT_BASELINE_TOP_DECILE": int((p["PERSISTENT_ALL_12"] & ~p["BASELINE_TOP_DECILE_SO"].fillna(False)).sum()),
        },
        {
            "CLASS": "Persistent at least 9 of 12",
            "ED_COUNT": int(p["PERSISTENT_9PLUS"].sum()),
            "BASELINE_TOP_DECILE_OVERLAP": int((p["PERSISTENT_9PLUS"] & p["BASELINE_TOP_DECILE_SO"].fillna(False)).sum()),
            "NOT_BASELINE_TOP_DECILE": int((p["PERSISTENT_9PLUS"] & ~p["BASELINE_TOP_DECILE_SO"].fillna(False)).sum()),
        },
    ])

    out = {
        "theil_baseline_comparator": theil,
        "capability_rule_sensitivity": capability,
        "sc3_feasibility_by_use": feasibility,
        "sc3_rewetting_margin": rw,
        "sc3_shared_pool_margin": pools,
        "persistence_baseline_null": persistence_summary,
        "persistence_ed_detail": p,
    }
    if sensitivity is not None:
        out["protection_strength_sensitivity"] = sensitivity.copy()
    return out


def _setup():
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 10.5,
        "axes.labelsize": 9.0,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.frameon": False,
        "legend.fontsize": 7.8,
        "font.size": 8.5,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    return plt


def _save(fig, base: Path) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("png", "svg", "pdf"):
        path = base.with_suffix(f".{ext}")
        kw = {"bbox_inches": "tight", "pad_inches": 0.08}
        if ext == "png":
            kw["dpi"] = 600
        fig.savefig(path, **kw)
        out.append(path)
    return out


def _label_panel(ax, letter: str, title: str):
    ax.set_title(f"{letter}. {title}", loc="left", pad=8)


def _map_names(frame, names: pd.DataFrame):
    x = frame.copy()
    x["CSOED"] = x["CSOED"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.lstrip("0")
    x["CSOED"] = x["CSOED"].mask(x["CSOED"].eq(""), "0")
    return x.merge(names, on="CSOED", how="left", suffixes=("", "_NAME"), validate="many_to_one")


def _rank_percentile(values: pd.Series) -> pd.Series:
    return values.rank(method="average", pct=True)


def _select_exposure_callouts(conditions: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    be = _run(conditions, "BE_SG", "PRORATA")[["CSOED", "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"]].rename(columns={"SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": "BE_PCT"})
    ag = _run(conditions, "ALL_GAS_NZ", "PRORATA")[["CSOED", "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"]].rename(columns={"SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": "ALL_PCT"})
    x = be.merge(ag, on="CSOED", validate="one_to_one")
    x["BE_RANK"] = _rank_percentile(pd.to_numeric(x["BE_PCT"], errors="coerce").fillna(0.0))
    x["ALL_RANK"] = _rank_percentile(pd.to_numeric(x["ALL_PCT"], errors="coerce").fillna(0.0))
    x["RANK_SHIFT"] = x["ALL_RANK"] - x["BE_RANK"]
    picks = []
    for label, idx in (
        ("Highest BE-SG exposure", pd.to_numeric(x["BE_PCT"], errors="coerce").idxmax()),
        ("Highest All-gas NZ exposure", pd.to_numeric(x["ALL_PCT"], errors="coerce").idxmax()),
        ("Largest upward rank shift", x["RANK_SHIFT"].idxmax()),
        ("Largest downward rank shift", x["RANK_SHIFT"].idxmin()),
    ):
        row = x.loc[idx].copy()
        row["CALLOUT_REASON"] = label
        picks.append(row)
    out = pd.DataFrame(picks).drop_duplicates("CSOED").head(4)
    out = out.merge(names, on="CSOED", how="left", validate="one_to_one")
    out.insert(0, "CALLOUT", np.arange(1, len(out) + 1))
    return out


def _delta_pct(block: pd.DataFrame) -> pd.Series:
    signed = _num(block, "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR")
    base = _num(block, "BASE_SO_LIVESTOCK_2020_EUR")
    return pd.Series(np.divide(100.0 * signed, base, out=np.zeros(len(block)), where=base.to_numpy(float) > 0), index=block.index)


def _select_redistribution_callouts(conditions: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    merged = None
    for rule, short in (
        ("DAIRY_PROTECTION", "DAIRY"),
        ("ECONOMIC_CAPACITY_PROTECTION", "ECONOMIC"),
        ("SOCIAL_VULNERABILITY_PROTECTION", "SOCIAL"),
    ):
        b = _run(conditions, "ALL_GAS_NZ", rule).copy()
        b[f"{short}_DELTA_SO_PCT"] = _delta_pct(b)
        b[f"{short}_DELTA_RELEASE_HA"] = _num(b, "SIGNED_DIFFERENCE_FROM_PRORATA_GOBLIN_RELEASED_GRASSLAND_HA")
        keep = b[["CSOED", f"{short}_DELTA_SO_PCT", f"{short}_DELTA_RELEASE_HA"]]
        merged = keep if merged is None else merged.merge(keep, on="CSOED", validate="one_to_one")
    x = merged.copy()
    candidates = []
    mask = (x["DAIRY_DELTA_SO_PCT"] < 0) & (x["SOCIAL_DELTA_SO_PCT"] > 0)
    if mask.any():
        score = -x.loc[mask, "DAIRY_DELTA_SO_PCT"] + x.loc[mask, "SOCIAL_DELTA_SO_PCT"]
        candidates.append(("Dairy relief / social burden", score.idxmax()))
    mask = (x["SOCIAL_DELTA_SO_PCT"] < 0) & (x["DAIRY_DELTA_SO_PCT"] > 0)
    if mask.any():
        score = -x.loc[mask, "SOCIAL_DELTA_SO_PCT"] + x.loc[mask, "DAIRY_DELTA_SO_PCT"]
        candidates.append(("Social relief / dairy burden", score.idxmax()))
    candidates.append(("Largest economic-vulnerability relief", x["ECONOMIC_DELTA_SO_PCT"].idxmin()))
    rows = []
    for reason, idx in candidates:
        row = x.loc[idx].copy()
        row["CALLOUT_REASON"] = reason
        rows.append(row)
    out = pd.DataFrame(rows).drop_duplicates("CSOED").head(3)
    out = out.merge(names, on="CSOED", how="left", validate="one_to_one")
    out.insert(0, "CALLOUT", np.arange(1, len(out) + 1))
    return out


def _annotate_numbers(ax, block, callouts: pd.DataFrame):
    for _, row in callouts.iterrows():
        hit = block.loc[block["CSOED"].astype(str).eq(str(row["CSOED"]))]
        if hit.empty:
            continue
        point = hit.geometry.iloc[0].representative_point()
        ax.scatter([point.x], [point.y], s=24, facecolors="white", edgecolors="black", linewidths=0.8, zorder=5)
        ax.text(point.x, point.y, str(int(row["CALLOUT"])), ha="center", va="center", fontsize=6.5, fontweight="bold", zorder=6)


def build_figures(
    tables: dict[str, pd.DataFrame],
    diagnostics: dict[str, pd.DataFrame],
    *,
    project_root: Path,
    output_dir: Path,
    geometry_path: Path,
) -> tuple[list[Path], dict[str, pd.DataFrame]]:
    plt = _setup()
    import matplotlib as mpl

    output_dir.mkdir(parents=True, exist_ok=True)
    conditions = tables["transition_conditions"].copy()
    names = _baseline_names(project_root)
    map_data = _map_names(tables["map_data"].copy(), names)
    model_geometry, _ = prepare_model_geometry(map_data, geometry_path)
    joined = build_joined_map_layer(map_data, model_geometry)
    joined = _map_names(joined, names)
    files: list[Path] = []
    callout_tables: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # Figure 2. Economic incidence.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.3), constrained_layout=True)
    base = _run(conditions, "BE_SG", "PRORATA")
    base_total = float(_num(base, "BASE_SO_LIVESTOCK_2020_EUR").sum()) / 1e9
    labels = [SCENARIO_LABELS[s] for s in ALL_SCENARIOS]
    retained, exposed, gains = [], [], []
    for s in ALL_SCENARIOS:
        b = _run(conditions, s, "PRORATA")
        loss = float(_num(b, "SO_LIVESTOCK_GROSS_LOSS_2020_EUR").sum()) / 1e9
        gain = float(_num(b, "SO_LIVESTOCK_GAIN_2020_EUR").sum()) / 1e9
        retained.append(max(base_total - loss, 0.0))
        exposed.append(loss)
        gains.append(gain)
    y = np.arange(len(labels))
    axes[0].barh(y, retained, label="Baseline value not exposed")
    axes[0].barh(y, exposed, left=retained, label="Gross production-value exposure")
    axes[0].barh(y, gains, left=[base_total] * len(y), label="Gross gains")
    axes[0].axvline(base_total, color="black", linewidth=0.8, linestyle="--")
    for i, (e, g) in enumerate(zip(exposed, gains)):
        axes[0].text(retained[i] + e / 2, i, f"€{e:.2f}bn", ha="center", va="center", fontsize=7.5)
        if g > 0.002:
            axes[0].text(base_total + g, i, f" +€{g:.2f}bn", va="center", ha="left", fontsize=7.2)
    axes[0].set_yticks(y, labels)
    axes[0].set_xlabel("Livestock Standard Output (€ billion, fixed 2020 coefficients)")
    axes[0].legend(loc="lower center", bbox_to_anchor=(0.5, -0.33), ncol=1)
    _label_panel(axes[0], "A", "Baseline production value partitioned into retained, exposed and gross gains")

    d = diagnostics["theil_baseline_comparator"]
    base_row = d.loc[d["SCENARIO"].eq("BASELINE")].iloc[0]
    gx = [float(base_row["GINI"])]
    gl = ["2020 baseline"]
    e50 = [int(base_row["EDS_FOR_50PCT"])]
    for s in ALL_SCENARIOS:
        r = d.loc[d["SCENARIO"].eq(s)].iloc[0]
        gx.append(float(r["GINI"])); gl.append(SCENARIO_LABELS[s]); e50.append(int(r["EDS_FOR_50PCT"]))
    yy = np.arange(len(gl))
    axes[1].scatter(gx, yy, s=55)
    axes[1].axvline(float(base_row["GINI"]), color="black", linewidth=0.8, linestyle="--", label="Baseline Gini")
    for x0, y0, n50 in zip(gx, yy, e50):
        axes[1].text(x0 + 0.004, y0, f"{x0:.3f}  |  {n50} EDs for 50%", va="center", fontsize=7.5)
    axes[1].set_yticks(yy, gl)
    axes[1].set_xlabel("Gini coefficient")
    axes[1].set_xlim(max(0.0, min(gx) - 0.04), max(gx) + 0.10)
    _label_panel(axes[1], "B", "Concentration relative to the baseline livestock-production geography")

    gross_red, gross_exp, net_red = [], [], []
    for s in ALL_SCENARIOS:
        b = _run(conditions, s, "PRORATA")
        red = float(_num(b, "TOTAL_CATTLE_REDUCTION_HEAD").sum()) / 1e6
        exp = float(_num(b, "TOTAL_CATTLE_EXPANSION_HEAD").sum()) / 1e6
        gross_red.append(red); gross_exp.append(exp); net_red.append(red - exp)
    xx = np.arange(len(labels))
    axes[2].bar(xx - 0.22, gross_red, width=0.22, label="Gross contraction")
    axes[2].bar(xx, gross_exp, width=0.22, label="Gross expansion")
    axes[2].bar(xx + 0.22, net_red, width=0.22, label="Net national reduction")
    axes[2].set_xticks(xx, labels, rotation=18, ha="right")
    axes[2].set_ylabel("Million head")
    axes[2].legend(loc="lower center", bbox_to_anchor=(0.5, -0.33), ncol=1)
    _label_panel(axes[2], "C", "Gross territorial movement versus net national cattle change")
    files += _save(fig, output_dir / "Fig02_economic_incidence")
    plt.close(fig)

    # ------------------------------------------------------------------
    # Figure 3. Exposure geography with comparable callouts.
    # ------------------------------------------------------------------
    exposure_callouts = _select_exposure_callouts(conditions, names)
    callout_tables["Fig03_callouts"] = exposure_callouts
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 6.2), constrained_layout=True)
    blocks = []
    for s in MAIN_SCENARIOS:
        b = joined.loc[
            joined["STUDY_SCENARIO_ID"].astype(str).eq(s)
            & joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
        ].copy()
        blocks.append(b)
    pooled = pd.concat([pd.DataFrame({"v": pd.to_numeric(b["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"], errors="coerce")}) for b in blocks])
    vmax = float(np.nanquantile(pooled["v"], 0.98)) if pooled["v"].notna().any() else 1.0
    vmax = max(vmax, 1e-9)
    for ax, s, b in zip(axes, MAIN_SCENARIOS, blocks):
        b.plot(column="SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", ax=ax, cmap="viridis", vmin=0, vmax=vmax, linewidth=0.05, edgecolor="white")
        try:
            b.dissolve(by="County").boundary.plot(ax=ax, linewidth=0.35, edgecolor="black")
        except Exception:
            pass
        _annotate_numbers(ax, b, exposure_callouts)
        ax.set_axis_off(); ax.set_title(SCENARIO_LABELS[s])
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(0, vmax), cmap="viridis")
    cbar = fig.colorbar(sm, ax=axes, shrink=0.72, pad=0.02)
    cbar.set_label("Gross livestock production-value exposure (% of ED baseline SO)")
    fig.suptitle("Figure 3. Geography of production-value exposure under proportional implementation", fontsize=12.5, fontweight="bold")
    files += _save(fig, output_dir / "Fig03_exposure_geography")
    plt.close(fig)

    # ------------------------------------------------------------------
    # Figure 4. Protection trade-offs.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 4.7), constrained_layout=True)
    ypos = np.arange(len(PROTECTION_RULES))
    width = 0.34
    for j, s in enumerate(MAIN_SCENARIOS):
        relief = []; transfer = []
        for rule in PROTECTION_RULES:
            b = _run(conditions, s, rule)
            signed = _num(b, "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR") / 1e6
            relief.append(float((-signed[signed < 0]).sum()))
            transfer.append(float(signed[signed > 0].sum()))
        offset = (-width / 2 if j == 0 else width / 2)
        axes[0].barh(ypos + offset, -np.asarray(relief), height=width, label=f"{SCENARIO_LABELS[s]} relief")
        axes[0].barh(ypos + offset, transfer, height=width, label=f"{SCENARIO_LABELS[s]} transfer")
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[0].set_yticks(ypos, [RULE_LABELS[r] for r in PROTECTION_RULES])
    axes[0].set_xlabel("€ million relative to proportional allocation\n(left = relief; right = additional exposure)")
    axes[0].legend(fontsize=6.8)
    _label_panel(axes[0], "A", "Protection relieves one geography by transferring exposure elsewhere")

    for s in MAIN_SCENARIOS:
        pr = _run(conditions, s, "PRORATA")
        gpr = _gini(_num(pr, "SO_LIVESTOCK_GROSS_LOSS_2020_EUR"))
        vals = []
        for rule in PROTECTION_RULES:
            vals.append(_gini(_num(_run(conditions, s, rule), "SO_LIVESTOCK_GROSS_LOSS_2020_EUR")) - gpr)
        axes[1].plot(np.arange(len(PROTECTION_RULES)), vals, marker="o", label=SCENARIO_LABELS[s])
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xticks(np.arange(len(PROTECTION_RULES)), ["Dairy", "Economic", "Social"], rotation=20)
    axes[1].set_ylabel("Δ Gini relative to proportional allocation")
    axes[1].legend()
    _label_panel(axes[1], "B", "The equality effect of the same protection principle is pathway dependent")

    score_cols = {
        "Dairy dependence": "DAIRY_STRENGTH_SCORE",
        "Economic vulnerability": "ECONOMIC_VULNERABILITY_SCORE",
        "Social vulnerability": "SOCIAL_VULNERABILITY_SCORE",
    }
    pr_all = _run(conditions, "ALL_GAS_NZ", "PRORATA")
    memberships = {}
    for label, col in score_cols.items():
        v = _num(pr_all, col)
        cutoff = float(v.quantile(2 / 3))
        memberships[label] = set(pr_all.loc[v.ge(cutoff), "CSOED"].astype(str))
    matrix = np.zeros((3, 3))
    for i, rule in enumerate(PROTECTION_RULES):
        b = _run(conditions, "ALL_GAS_NZ", rule).copy()
        signed = _num(b, "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR") / 1e6
        for j, ids in enumerate(memberships.values()):
            matrix[i, j] = float(signed.loc[b["CSOED"].astype(str).isin(ids)].sum())
    vmax_m = max(float(np.max(np.abs(matrix))), 1e-9)
    im = axes[2].imshow(matrix, cmap="coolwarm", vmin=-vmax_m, vmax=vmax_m, aspect="auto")
    axes[2].set_xticks(np.arange(3), list(memberships.keys()), rotation=30, ha="right")
    axes[2].set_yticks(np.arange(3), ["Dairy protection", "Economic protection", "Social protection"])
    for i in range(3):
        for j in range(3):
            axes[2].text(j, i, f"{matrix[i,j]:+.0f}", ha="center", va="center", fontsize=7.2)
    cb = fig.colorbar(im, ax=axes[2], shrink=0.70)
    cb.set_label("Δ gross SO exposure (€ million vs proportional)")
    _label_panel(axes[2], "C", "Cross-protection trade-offs under All-gas NZ")
    files += _save(fig, output_dir / "Fig04_protection_tradeoffs")
    plt.close(fig)

    # ------------------------------------------------------------------
    # Figure 5. Geography of redistribution + coupling scatter.
    # ------------------------------------------------------------------
    redis_callouts = _select_redistribution_callouts(conditions, names)
    callout_tables["Fig05_callouts"] = redis_callouts
    fig, axes = plt.subplots(1, 4, figsize=(17.0, 5.3), constrained_layout=True)
    map_blocks = []
    pooled_delta = []
    for rule in PROTECTION_RULES:
        b = joined.loc[
            joined["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
            & joined["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ].copy()
        b["DELTA_SO_PCT"] = np.divide(
            100.0 * pd.to_numeric(b["SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR"], errors="coerce").fillna(0.0),
            pd.to_numeric(b["BASE_SO_LIVESTOCK_2020_EUR"], errors="coerce").fillna(0.0),
            out=np.zeros(len(b)),
            where=pd.to_numeric(b["BASE_SO_LIVESTOCK_2020_EUR"], errors="coerce").fillna(0.0).to_numpy(float) > 0,
        )
        map_blocks.append((rule, b)); pooled_delta.extend(b["DELTA_SO_PCT"].tolist())
    limit = float(np.nanquantile(np.abs(np.asarray(pooled_delta, dtype=float)), 0.98))
    limit = max(limit, 1e-9)
    for ax, (rule, b) in zip(axes[:3], map_blocks):
        b.plot(column="DELTA_SO_PCT", ax=ax, cmap="coolwarm", vmin=-limit, vmax=limit, linewidth=0.04, edgecolor="white")
        try:
            b.dissolve(by="County").boundary.plot(ax=ax, linewidth=0.30, edgecolor="black")
        except Exception:
            pass
        _annotate_numbers(ax, b, redis_callouts)
        ax.set_axis_off(); ax.set_title(RULE_LABELS[rule])
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit), cmap="coolwarm")
    cb = fig.colorbar(sm, ax=axes[:3], shrink=0.70, pad=0.015)
    cb.set_label("Change in gross SO exposure vs proportional (% of ED baseline SO)")

    ax = axes[3]
    for rule, b in map_blocks:
        x = b["DELTA_SO_PCT"].to_numpy(float)
        delta_release = pd.to_numeric(b["SIGNED_DIFFERENCE_FROM_PRORATA_GOBLIN_RELEASED_GRASSLAND_HA"], errors="coerce").fillna(0.0).to_numpy(float)
        base_grass = pd.to_numeric(b.get("BASE_ALL_GRASSLAND_HA", b.get("ALL_GRASSLAND", pd.Series(1.0, index=b.index))), errors="coerce").fillna(0.0).to_numpy(float)
        yv = np.divide(100.0 * delta_release, base_grass, out=np.zeros(len(b)), where=base_grass > 0)
        ax.scatter(x, yv, s=6, alpha=0.22, label=RULE_LABELS[rule])
    ax.axhline(0, color="black", linewidth=0.7); ax.axvline(0, color="black", linewidth=0.7)
    ax.set_xlabel("Δ production-value exposure (% of baseline SO)")
    ax.set_ylabel("Δ released land (% of baseline grassland)")
    ax.legend(fontsize=6.5)
    ax.set_title("Coupling between burden redistribution and released-land geography")
    fig.suptitle("Figure 5. Geography of redistribution under All-gas NZ", fontsize=12.5, fontweight="bold")
    files += _save(fig, output_dir / "Fig05_redistribution_geography")
    plt.close(fig)

    # ------------------------------------------------------------------
    # Figure 6. Contested land resource.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(14.6, 4.7), constrained_layout=True)
    lr = tables["land_release_summary"]
    x = np.arange(len(MAIN_SCENARIOS))
    bottom = np.zeros(len(MAIN_SCENARIOS))
    for comp in ("DAIRY", "BEEF", "SHEEP"):
        vals = []
        for s in MAIN_SCENARIOS:
            r = lr.loc[(lr["STUDY_SCENARIO_ID"].astype(str).eq(s)) & (lr["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA"))].iloc[0]
            vals.append(float(r[f"{comp}_RELEASE_HA"]) / float(r["GROSS_RELEASE_HA"]) * 100.0)
        axes[0].bar(x, vals, bottom=bottom, label=comp.title())
        bottom += np.asarray(vals)
    axes[0].set_xticks(x, [SCENARIO_LABELS[s] for s in MAIN_SCENARIOS])
    axes[0].set_ylabel("Share of released land (%)"); axes[0].legend()
    _label_panel(axes[0], "A", "Agricultural provenance of released land")

    bottom = np.zeros(len(MAIN_SCENARIOS))
    for comp in ("G1", "G2", "G3"):
        vals = []
        for s in MAIN_SCENARIOS:
            r = lr.loc[(lr["STUDY_SCENARIO_ID"].astype(str).eq(s)) & (lr["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA"))].iloc[0]
            vals.append(float(r[f"{comp}_RELEASE_SHARE_PCT"]))
        axes[1].bar(x, vals, bottom=bottom, label=comp)
        bottom += np.asarray(vals)
    axes[1].set_xticks(x, [SCENARIO_LABELS[s] for s in MAIN_SCENARIOS]); axes[1].set_ylabel("Share of released land (%)"); axes[1].legend()
    _label_panel(axes[1], "B", "Capability composition changes much less than system provenance")

    om = tables["opportunity_mobilisation"]
    uses = list(USE_LABELS)
    ypos = np.arange(len(uses))
    for k, s in enumerate(MAIN_SCENARIOS):
        b = om.loc[(om["STUDY_SCENARIO_ID"].astype(str).eq(s)) & (om["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA"))].set_index("LAND_USE")
        elig = np.array([float(b.loc[u, "ELIGIBLE_HA"]) / 1000.0 for u in uses])
        targ = np.array([float(b.loc[u, "TARGET_HA"]) / 1000.0 for u in uses])
        offset = (-0.12 if k == 0 else 0.12)
        for i, (e, t) in enumerate(zip(elig, targ)):
            axes[2].plot([t, e], [i + offset, i + offset], linewidth=1.0)
        axes[2].scatter(targ, ypos + offset, marker="|", s=80, label=f"{SCENARIO_LABELS[s]} target")
        axes[2].scatter(elig, ypos + offset, s=22, label=f"{SCENARIO_LABELS[s]} eligible")
    axes[2].set_yticks(ypos, [USE_LABELS[u] for u in uses]); axes[2].set_xlabel("Thousand hectares")
    axes[2].legend(fontsize=6.4, ncol=2)
    _label_panel(axes[2], "C", "Use-specific opportunity envelopes overlap and compete")
    files += _save(fig, output_dir / "Fig06_contested_land")
    plt.close(fig)

    # ------------------------------------------------------------------
    # Figure 7. Territorial feasibility.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.0), constrained_layout=True)
    uses = list(USE_LABELS)
    ypos = np.arange(len(uses))
    for k, s in enumerate(MAIN_SCENARIOS):
        b = om.loc[(om["STUDY_SCENARIO_ID"].astype(str).eq(s)) & (om["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA"))].set_index("LAND_USE")
        target = np.array([float(b.loc[u, "TARGET_HA"]) / 1000.0 for u in uses])
        realised = np.array([float(b.loc[u, "REALISED_HA"]) / 1000.0 for u in uses])
        off = -0.12 if k == 0 else 0.12
        for i, (t, r) in enumerate(zip(target, realised)):
            axes[0].plot([r, t], [i + off, i + off], linewidth=1.2)
        axes[0].scatter(target, ypos + off, marker="|", s=90, label=f"{SCENARIO_LABELS[s]} target")
        axes[0].scatter(realised, ypos + off, s=24, label=f"{SCENARIO_LABELS[s]} realised")
    axes[0].set_yticks(ypos, [USE_LABELS[u] for u in uses]); axes[0].set_xlabel("Thousand hectares")
    axes[0].legend(fontsize=6.5, ncol=2)
    _label_panel(axes[0], "A", "National targets versus territorially realised allocation")

    rw = diagnostics["sc3_rewetting_margin"]
    all_rw = rw.loc[rw["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")].copy()
    x2 = np.arange(len(RULES))
    margin = np.array([
        float(all_rw.loc[all_rw["STUDY_ALLOCATION_POLICY"].astype(str).eq(r), "POST_STAGE_A_REWETTING_MARGIN_HA"].iloc[0]) / 1000.0
        for r in RULES
    ])
    unmet = np.array([
        float(all_rw.loc[all_rw["STUDY_ALLOCATION_POLICY"].astype(str).eq(r), "UNMET_HA"].iloc[0]) / 1000.0
        for r in RULES
    ])
    axes[1].bar(x2, margin, label="Post-Stage-A rewetting margin")
    axes[1].scatter(x2, -unmet, marker="x", s=48, label="Unmet target (shown below zero)")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xticks(x2, ["Proportional", "Dairy", "Economic", "Social"], rotation=22, ha="right")
    axes[1].set_ylabel("Thousand hectares")
    axes[1].legend(fontsize=7.0)
    _label_panel(axes[1], "B", "Use-specific feasibility can tighten despite aggregate residual land")
    files += _save(fig, output_dir / "Fig07_feasibility")
    plt.close(fig)

    return files, callout_tables


def _write_key_results(diagnostics: dict[str, pd.DataFrame], tables: dict[str, pd.DataFrame], path: Path):
    d = diagnostics["theil_baseline_comparator"]
    cap = diagnostics["capability_rule_sensitivity"]
    pers = diagnostics["persistence_baseline_null"]
    rw = diagnostics["sc3_rewetting_margin"]
    lines = [f"GOBLIN-Spatial final manuscript diagnostics v{VERSION}", ""]
    for _, r in d.iterrows():
        lines.append(
            f"THEIL {r['SCENARIO']}: Gini={r['GINI']:.6f}; EDs50={int(r['EDS_FOR_50PCT'])}; "
            f"Theil={r['THEIL_TOTAL']:.6f}; within={r['WITHIN_SHARE_PCT']:.3f}%; between={r['BETWEEN_SHARE_PCT']:.3f}%; closure={r['CLOSURE']:.3e}"
        )
    lines.append("")
    for _, r in cap.iterrows():
        lines.append(
            f"CAPABILITY ALL_GAS_NZ {r['CAPABILITY_GROUP']}: PR={r['PRORATA_SHARE_PCT']:.6f}%; "
            f"range={r['RANGE_PP']:.6f} pp; max|ΔPR|={r['MAX_ABS_DIFFERENCE_FROM_PRORATA_PP']:.6f} pp"
        )
    lines.append("")
    for _, r in pers.iterrows():
        lines.append(
            f"PERSISTENCE {r['CLASS']}: n={int(r['ED_COUNT'])}; baseline-top-decile overlap={int(r['BASELINE_TOP_DECILE_OVERLAP'])}; "
            f"not-baseline-top-decile={int(r['NOT_BASELINE_TOP_DECILE'])}"
        )
    lines.append("")
    if not rw.empty:
        for _, r in rw.loc[rw["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")].iterrows():
            lines.append(
                f"REWETTING ALL_GAS_NZ {r['STUDY_ALLOCATION_POLICY']}: target={r['TARGET_HA']:.3f}; "
                f"postA_capacity={r['POST_STAGE_A_CAPACITY_HA']:.3f}; realised={r['REALISED_HA']:.3f}; unmet={r['UNMET_HA']:.3f}; "
                f"margin={r['POST_STAGE_A_REWETTING_MARGIN_HA']:.3f}"
            )
    sens = diagnostics.get("protection_strength_sensitivity")
    if sens is not None and not sens.empty:
        lines.append("")
        for _, r in sens.iterrows():
            lines.append("SENSITIVITY " + "; ".join(f"{c}={r[c]}" for c in sens.columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_package(
    results_dir: str | Path,
    *,
    output_dir: str | Path,
    sensitivity_summary: str | Path | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    geometry: str | Path | None = None,
) -> dict[str, Path]:
    results = Path(results_dir).resolve()
    db = results / "GOBLIN_Spatial_Final_Results.sqlite"
    if not db.exists():
        raise FileNotFoundError(db)
    out = Path(output_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    tables = _read_sqlite(db)
    required = {
        "transition_conditions", "land_release_summary", "opportunity_mobilisation",
        "persistence", "map_data", "rewetting_summary", "shared_pool_summary",
    }
    missing = sorted(required - set(tables))
    if missing:
        raise ValueError(f"final results database missing manuscript tables: {missing}")
    sensitivity = None
    if sensitivity_summary is not None and Path(sensitivity_summary).exists():
        sensitivity = pd.read_csv(sensitivity_summary)
    diagnostics = build_diagnostics(tables, sensitivity)
    diag_dir = out / "diagnostics"; diag_dir.mkdir(exist_ok=True)
    for name, frame in diagnostics.items():
        frame.to_csv(diag_dir / f"{name}.csv", index=False)

    cfg = load_config(Path(config_path))
    project_root = cfg.project_root
    geometry_path = resolve_geometry_path(config_path=config_path, geometry=geometry)
    fig_dir = out / "figures"
    figure_files, callouts = build_figures(
        tables, diagnostics, project_root=project_root, output_dir=fig_dir, geometry_path=geometry_path
    )
    for name, frame in callouts.items():
        frame.to_csv(diag_dir / f"{name}.csv", index=False)

    key_results = out / "manuscript_key_results.txt"
    _write_key_results(diagnostics, tables, key_results)
    manifest = pd.DataFrame([
        {"FILE": str(p.relative_to(out)), "FORMAT": p.suffix.lstrip("."), "VERSION": VERSION}
        for p in figure_files
    ])
    manifest_path = out / "manuscript_figure_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    return {"output_dir": out, "key_results": key_results, "manifest": manifest_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build final GOBLIN-Spatial manuscript diagnostics and Figures 2-7")
    parser.add_argument("results_dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sensitivity-summary", default=None)
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument("--geometry", default=None)
    args = parser.parse_args(argv)
    outputs = build_package(
        args.results_dir,
        output_dir=args.output_dir,
        sensitivity_summary=args.sensitivity_summary,
        config_path=args.config,
        geometry=args.geometry,
    )
    for k, v in outputs.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
