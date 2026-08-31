"""Publication visual layer for the main GOBLIN-Spatial paper.

This module is deliberately downstream of the frozen numerical study. It does
not recompute SC1, SC2 or SC3 science. It consumes the final reporting SQLite
and map-ready CSV and creates publication-facing figures focused on the two
contraction pathways used in the main paper:

* BE_SG        (Bioeconomy / Split Gas)
* ALL_GAS_NZ   (All-Gas Net Zero)

The visual story is SC1-led:

    national transition pressure
        -> local incidence
        -> production-value exposure
        -> economic/social vulnerability
        -> protection relief and displaced burden
        -> released-land bridge to opportunity / SC3

SI_SG remains part of the validated model envelope and can be reported in the
supplement, but is intentionally excluded from this main-paper visual layer.

Graphs are written as PNG and SVG. Maps use the same frozen ED geometry and
map-ready numerical outputs as :mod:`goblin_spatial.map_reporting`; geometry is
presentation infrastructure only.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from goblin_spatial.map_reporting import (
    build_joined_map_layer,
    prepare_model_geometry,
    resolve_geometry_path,
)
from goblin_spatial.study_reporting import SC3_USES, USE_LABELS


PUBLICATION_VISUAL_VERSION = "1.0"
PAPER_SCENARIOS = ("BE_SG", "ALL_GAS_NZ")
PAPER_RULES = (
    "PRORATA",
    "DAIRY_PROTECTION",
    "ECONOMIC_CAPACITY_PROTECTION",
    "SOCIAL_VULNERABILITY_PROTECTION",
)
SCENARIO_LABELS = {
    "BE_SG": "Bioeconomy / Split Gas",
    "ALL_GAS_NZ": "All-Gas Net Zero",
}
RULE_LABELS = {
    "PRORATA": "Pro rata",
    "DAIRY_PROTECTION": "Dairy-dependence protection",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic-vulnerability protection",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social-vulnerability protection",
}
RULE_LABELS_SHORT = {
    "PRORATA": "Pro rata",
    "DAIRY_PROTECTION": "Dairy",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social",
}
RULE_COLORS = {
    "PRORATA": "#4D4D4D",
    "DAIRY_PROTECTION": "#2C7BB6",
    "ECONOMIC_CAPACITY_PROTECTION": "#FDAE61",
    "SOCIAL_VULNERABILITY_PROTECTION": "#7B3294",
}
NODATA_COLOR = "#E3E3E3"
TARGET_CRS = 2157


def _setup_matplotlib():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "axes.titlesize": 11.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.frameon": False,
            "legend.fontsize": 8.0,
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9.0,
            "savefig.facecolor": "white",
        }
    )
    return plt


def _save_graph(fig, base: Path) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for suffix in (".png", ".svg"):
        path = base.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight", "facecolor": "white"}
        if suffix == ".png":
            kwargs["dpi"] = 500
        fig.savefig(path, **kwargs)
        outputs.append(path)
    return outputs


def _save_map(fig, base: Path) -> list[Path]:
    """Save without bbox_inches='tight' so figure-fraction callouts stay valid."""
    base.parent.mkdir(parents=True, exist_ok=True)
    png = base.with_suffix(".png")
    svg = base.with_suffix(".svg")
    fig.savefig(png, dpi=500, facecolor="white")
    fig.savefig(svg, facecolor="white")
    return [png, svg]


def _read_final_tables(database: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(database).resolve()
    if not path.exists():
        raise FileNotFoundError(f"final results database not found: {path}")
    required = {"lorenz_data", "transition_conditions", "opportunity_mobilisation"}
    with sqlite3.connect(path) as con:
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"final results database missing publication tables: {missing}")
        return {name: pd.read_sql_query(f'SELECT * FROM "{name}"', con) for name in required}


def _paper_only(frame: pd.DataFrame, scenario_col: str = "STUDY_SCENARIO_ID") -> pd.DataFrame:
    if scenario_col not in frame.columns:
        raise ValueError(f"publication visual table missing {scenario_col}")
    return frame.loc[frame[scenario_col].astype(str).isin(PAPER_SCENARIOS)].copy()


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"publication visual input missing column: {column}")
    return pd.to_numeric(frame[column], errors="coerce")


def _manifest_row(fig_id: str, title: str, question: str, files: list[Path], note: str = "") -> dict[str, object]:
    return {
        "FIGURE_ID": fig_id,
        "TITLE": title,
        "SCIENTIFIC_QUESTION": question,
        "PNG": next((str(p) for p in files if p.suffix.lower() == ".png"), ""),
        "SVG": next((str(p) for p in files if p.suffix.lower() == ".svg"), ""),
        "NOTE": note,
        "PUBLICATION_VISUAL_VERSION": PUBLICATION_VISUAL_VERSION,
    }


def _violin_box(ax, datasets: list[np.ndarray], labels: list[str], colors: list[str], *, horizontal: bool = False) -> None:
    positions = np.arange(1, len(datasets) + 1)
    usable = [np.asarray(d, float)[np.isfinite(np.asarray(d, float))] for d in datasets]
    usable = [d if len(d) else np.array([np.nan]) for d in usable]
    parts = ax.violinplot(
        usable,
        positions=positions,
        showmeans=False,
        showmedians=False,
        showextrema=False,
        vert=not horizontal,
        widths=0.82,
    )
    for body, color in zip(parts["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor("white")
        body.set_alpha(0.55)
    ax.boxplot(
        usable,
        positions=positions,
        widths=0.20,
        patch_artist=True,
        showfliers=False,
        vert=not horizontal,
        boxprops={"facecolor": "white", "edgecolor": "#333333", "linewidth": 0.9},
        medianprops={"color": "#111111", "linewidth": 1.3},
        whiskerprops={"color": "#555555", "linewidth": 0.8},
        capprops={"color": "#555555", "linewidth": 0.8},
    )
    if horizontal:
        ax.set_yticks(positions, labels)
    else:
        ax.set_xticks(positions, labels, rotation=20, ha="right")


def generate_publication_graphs(database: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Generate the SC1-led main-paper graph package for BE_SG and ALL_GAS_NZ."""
    tables = _read_final_tables(database)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plt = _setup_matplotlib()
    manifest: list[dict[str, object]] = []

    # ------------------------------------------------------------------
    # G01. Concentration curves: who carries physical and economic exposure?
    # ------------------------------------------------------------------
    lorenz = _paper_only(tables["lorenz_data"])
    lorenz = lorenz.loc[lorenz["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")]
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.0), constrained_layout=True)
    for ax, metric, title in (
        (axes[0], "Cattle reduction", "A. Physical transition exposure"),
        (axes[1], "Standard Output gross loss", "B. Production-value exposure"),
    ):
        ax.plot([0, 100], [0, 100], linestyle="--", color="#9A9A9A", linewidth=1.0, label="Equal distribution")
        for scenario, color in zip(PAPER_SCENARIOS, ("#2C7BB6", "#D7191C")):
            block = lorenz.loc[
                lorenz["METRIC"].astype(str).eq(metric)
                & lorenz["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            ].sort_values("CUMULATIVE_ED_SHARE_PCT")
            if not block.empty:
                ax.plot(
                    block["CUMULATIVE_ED_SHARE_PCT"],
                    block["CUMULATIVE_EXPOSURE_SHARE_PCT"],
                    linewidth=2.2,
                    color=color,
                    label=SCENARIO_LABELS[scenario],
                )
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Cumulative share of Electoral Divisions (%)")
        ax.set_ylabel("Cumulative share of national exposure (%)")
        ax.set_title(title)
        ax.grid(alpha=0.14)
    axes[1].legend(loc="lower right")
    files = _save_graph(fig, out / "pub_fig01_exposure_concentration")
    plt.close(fig)
    manifest.append(_manifest_row(
        "G01",
        "Concentration of transition exposure",
        "How concentrated are livestock adjustment and production-value exposure under the two main contraction pathways?",
        files,
        note="PRORATA only; Standard Output is production-value exposure, not income, profit, welfare or compensation.",
    ))

    # ------------------------------------------------------------------
    # G02. Distribution small multiples across incidence rules.
    # ------------------------------------------------------------------
    cond = _paper_only(tables["transition_conditions"])
    metrics = [
        ("TOTAL_CATTLE_REDUCTION_PCT_OF_BASE", "Livestock adjustment", "% of baseline cattle"),
        ("SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", "Production-value exposure", "% of baseline livestock SO"),
        ("GOBLIN_RELEASED_GRASSLAND_HA", "Released grassland", "ha per ED"),
    ]
    present = [(c, t, u) for c, t, u in metrics if c in cond.columns]
    if present:
        fig, axes = plt.subplots(len(present), 2, figsize=(12.6, 3.45 * len(present)), constrained_layout=True)
        axes = np.asarray(axes).reshape(len(present), 2)
        for row, (column, title, unit) in enumerate(present):
            for col, scenario in enumerate(PAPER_SCENARIOS):
                ax = axes[row, col]
                block = cond.loc[cond["STUDY_SCENARIO_ID"].astype(str).eq(scenario)]
                datasets = []
                labels = []
                colors = []
                for rule in PAPER_RULES:
                    values = pd.to_numeric(
                        block.loc[block["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule), column],
                        errors="coerce",
                    ).dropna().to_numpy(float)
                    datasets.append(values)
                    labels.append(RULE_LABELS_SHORT[rule])
                    colors.append(RULE_COLORS[rule])
                _violin_box(ax, datasets, labels, colors)
                ax.set_ylabel(unit)
                ax.grid(axis="y", alpha=0.14)
                prefix = chr(ord("A") + row * 2 + col)
                ax.set_title(f"{prefix}. {title} | {SCENARIO_LABELS[scenario]}")
        files = _save_graph(fig, out / "pub_fig02_ed_exposure_distributions")
        plt.close(fig)
        manifest.append(_manifest_row(
            "G02",
            "ED-level transition exposure distributions",
            "How does the distribution of local adjustment, economic exposure and released land change across incidence rules?",
            files,
        ))

    # ------------------------------------------------------------------
    # G03. Signed relief / displaced burden relative to PRORATA.
    # ------------------------------------------------------------------
    signed_metrics = [
        ("SIGNED_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD", 1000.0, "thousand head", "Physical adjustment"),
        ("SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR", 1e6, "EUR million", "Production-value exposure"),
    ]
    signed_present = [(c, s, u, t) for c, s, u, t in signed_metrics if c in cond.columns]
    if signed_present:
        fig, axes = plt.subplots(len(signed_present), 2, figsize=(12.6, 3.6 * len(signed_present)), constrained_layout=True)
        axes = np.asarray(axes).reshape(len(signed_present), 2)
        rules = PAPER_RULES[1:]
        for row, (column, scale, unit, title) in enumerate(signed_present):
            for col, scenario in enumerate(PAPER_SCENARIOS):
                ax = axes[row, col]
                block = cond.loc[cond["STUDY_SCENARIO_ID"].astype(str).eq(scenario)]
                datasets = []
                for rule in rules:
                    values = pd.to_numeric(
                        block.loc[block["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule), column],
                        errors="coerce",
                    ).dropna().to_numpy(float) / scale
                    datasets.append(values)
                _violin_box(
                    ax,
                    datasets,
                    [RULE_LABELS_SHORT[r] for r in rules],
                    [RULE_COLORS[r] for r in rules],
                    horizontal=True,
                )
                ax.axvline(0.0, color="#222222", linewidth=1.0)
                low, high = ax.get_xlim()
                if low < 0:
                    ax.axvspan(low, 0, color="#2C7BB6", alpha=0.045, zorder=-10)
                if high > 0:
                    ax.axvspan(0, high, color="#D7191C", alpha=0.045, zorder=-10)
                ax.set_xlabel(f"Difference from PRORATA ({unit})\nRelief  ←  0  →  Displaced burden")
                ax.grid(axis="x", alpha=0.14)
                prefix = chr(ord("A") + row * 2 + col)
                ax.set_title(f"{prefix}. {title} | {SCENARIO_LABELS[scenario]}")
        files = _save_graph(fig, out / "pub_fig03_protection_redistribution")
        plt.close(fig)
        manifest.append(_manifest_row(
            "G03",
            "Protection relief and displaced burden",
            "Which EDs receive protection relief and which absorb the displaced adjustment under the same national endpoint?",
            files,
            note="Negative signed differences mean less exposure than PRORATA; positive differences mean additional displaced burden.",
        ))

    # ------------------------------------------------------------------
    # G04. Exposure x vulnerability plane: main SC1 just-transition diagnostic.
    # ------------------------------------------------------------------
    vulnerability_metrics = [
        ("ECONOMIC_VULNERABILITY_SCORE", "Economic vulnerability"),
        ("SOCIAL_VULNERABILITY_SCORE", "Social vulnerability"),
    ]
    vulnerability_present = [(c, l) for c, l in vulnerability_metrics if c in cond.columns]
    exposure_col = "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if vulnerability_present and exposure_col in cond.columns:
        fig, axes = plt.subplots(len(vulnerability_present), 2, figsize=(12.2, 4.1 * len(vulnerability_present)), constrained_layout=True)
        axes = np.asarray(axes).reshape(len(vulnerability_present), 2)
        for row, (vcol, vlabel) in enumerate(vulnerability_present):
            for col, scenario in enumerate(PAPER_SCENARIOS):
                ax = axes[row, col]
                block = cond.loc[
                    cond["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
                    & cond["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
                ].copy()
                x = pd.to_numeric(block[exposure_col], errors="coerce")
                y = pd.to_numeric(block[vcol], errors="coerce")
                release = pd.to_numeric(block.get("GOBLIN_RELEASED_GRASSLAND_HA", 0.0), errors="coerce").fillna(0.0)
                valid = x.notna() & y.notna()
                x, y, release = x[valid], y[valid], release[valid]
                max_release = float(release.max()) if len(release) else 0.0
                size = 16.0 + (95.0 * np.sqrt(np.maximum(release, 0.0) / max_release) if max_release > 0 else 0.0)
                ax.scatter(x, y, s=size, color="#3B6FB6", alpha=0.42, edgecolors="white", linewidth=0.25)
                if len(x):
                    ax.axvline(float(x.median()), color="#777777", linestyle="--", linewidth=0.8)
                    ax.axhline(float(y.median()), color="#777777", linestyle="--", linewidth=0.8)
                ax.set_xlabel("Gross livestock SO exposure (% of baseline)")
                ax.set_ylabel(vlabel + " score")
                ax.set_ylim(-0.03, 1.03)
                ax.grid(alpha=0.12)
                prefix = chr(ord("A") + row * 2 + col)
                ax.set_title(f"{prefix}. {vlabel} | {SCENARIO_LABELS[scenario]}")
        files = _save_graph(fig, out / "pub_fig04_exposure_vulnerability")
        plt.close(fig)
        manifest.append(_manifest_row(
            "G04",
            "Transition exposure and vulnerability",
            "Where does production-value exposure coincide with economic or social vulnerability?",
            files,
            note="Point size represents released grassland. Scores remain separate; no composite just-transition index is constructed.",
        ))

    # ------------------------------------------------------------------
    # G05. Secondary downstream consequence: target -> realised -> unmet.
    # ------------------------------------------------------------------
    mobilisation = _paper_only(tables["opportunity_mobilisation"])
    mobilisation = mobilisation.loc[mobilisation["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")]
    if not mobilisation.empty:
        fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.5), sharey=True, constrained_layout=True)
        use_order = [u for u in SC3_USES if (mobilisation["LAND_USE"].astype(str) == u).any()]
        for ax, scenario in zip(axes, PAPER_SCENARIOS):
            block = mobilisation.loc[mobilisation["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].set_index("LAND_USE").reindex(use_order)
            target = pd.to_numeric(block["TARGET_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
            realised = pd.to_numeric(block["REALISED_HA"], errors="coerce").fillna(0.0).to_numpy(float) / 1000.0
            y = np.arange(len(use_order))
            for yi, r, t in zip(y, realised, target):
                ax.hlines(yi, min(r, t), max(r, t), color="#AAAAAA", linewidth=2.0)
            ax.scatter(realised, y, s=44, color="#2C7BB6", label="Realised", zorder=3)
            ax.scatter(target, y, s=54, facecolors="white", edgecolors="#222222", linewidth=1.2, label="Target", zorder=4)
            ax.set_yticks(y, [USE_LABELS.get(u, u.replace("_", " ").title()) for u in use_order])
            ax.invert_yaxis()
            ax.set_xlabel("Area (thousand ha)")
            ax.set_title(SCENARIO_LABELS[scenario])
            ax.grid(axis="x", alpha=0.14)
        axes[1].legend(loc="lower right")
        fig.suptitle("Downstream spatial delivery of alternative land-use targets", fontweight="bold")
        files = _save_graph(fig, out / "pub_fig05_target_realised_unmet")
        plt.close(fig)
        manifest.append(_manifest_row(
            "G05",
            "Target, realised and unmet land-use demand",
            "Does the released-land geography created by SC1 support the wider pathway?",
            files,
            note="Secondary SC2/SC3 consequence; the paper's main story remains SC1 exposure, vulnerability and redistribution.",
        ))

    manifest_path = out / "GOBLIN_Spatial_Publication_Graph_Manifest.csv"
    pd.DataFrame(manifest).to_csv(manifest_path, index=False)
    return {"graph_directory": out, "graph_manifest": manifest_path}


# =====================================================================
# CARTOGRAPHIC HELPERS
# =====================================================================

def _project(joined):
    if joined.crs is None:
        raise ValueError("map layer has no CRS")
    if not joined.crs.is_projected or joined.crs.to_epsg() != TARGET_CRS:
        joined = joined.to_crs(TARGET_CRS)
    return joined


def _county_outline(block):
    if "County" not in block.columns or block["County"].isna().all():
        return None
    try:
        return block.dissolve(by="County").boundary
    except Exception:
        return None


def _add_scale_bar(ax, length_km: int = 50, loc: tuple[float, float] = (0.05, 0.045)) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length_m = length_km * 1000.0
    if length_m > 0.40 * (x1 - x0):
        for candidate in (25, 10, 5):
            if candidate * 1000.0 <= 0.40 * (x1 - x0):
                length_km = candidate
                length_m = candidate * 1000.0
                break
    xs = x0 + loc[0] * (x1 - x0)
    ys = y0 + loc[1] * (y1 - y0)
    ax.plot([xs, xs + length_m], [ys, ys], color="#222222", linewidth=2.6, solid_capstyle="butt", zorder=50)
    ax.text(xs + length_m / 2.0, ys + 0.012 * (y1 - y0), f"{length_km} km", ha="center", va="bottom", fontsize=7.5, zorder=50)


def _add_north_arrow(ax, loc: tuple[float, float] = (0.94, 0.91)) -> None:
    ax.annotate(
        "N",
        xy=loc,
        xytext=(loc[0], loc[1] - 0.065),
        xycoords="axes fraction",
        textcoords="axes fraction",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        arrowprops={"arrowstyle": "-|>", "color": "#222222", "lw": 1.3},
    )


def _union_all(geoms):
    try:
        return geoms.union_all()
    except AttributeError:  # geopandas/shapely compatibility fallback
        return geoms.unary_union


def _zoom_to(ax, block, pad: float = 0.12) -> None:
    x0, y0, x1, y1 = block.total_bounds
    bx = max((x1 - x0) * pad, 1000.0)
    by = max((y1 - y0) * pad, 1000.0)
    ax.set_xlim(x0 - bx, x1 + bx)
    ax.set_ylim(y0 - by, y1 + by)


def _draw_callout(fig, ax_main, point_xy, ax_inset, color: str) -> None:
    from matplotlib.patches import ConnectionPatch, Circle
    import matplotlib.patheffects as path_effects

    disp = ax_main.transData.transform(point_xy)
    pt = fig.transFigure.inverted().transform(disp)
    box = ax_inset.get_position()
    anchor = (box.x0, box.y0 + box.height / 2.0)
    line = ConnectionPatch(
        xyA=tuple(pt),
        xyB=anchor,
        coordsA="figure fraction",
        coordsB="figure fraction",
        arrowstyle="-",
        linestyle="--",
        linewidth=1.4,
        color=color,
        alpha=0.85,
        connectionstyle="arc3,rad=0.10",
        zorder=5,
    )
    line.set_path_effects([path_effects.withStroke(linewidth=3.0, foreground="white")])
    fig.add_artist(line)
    fig.add_artist(Circle(tuple(pt), radius=0.0048, transform=fig.transFigure, facecolor=color, edgecolor="white", linewidth=1.1, zorder=6))


def _top_exposure_area(block: pd.DataFrame, value_col: str):
    """Prefer the county carrying the largest total exposure; fallback to top 5% EDs."""
    if "County" in block.columns and block["County"].notna().any():
        totals = block.assign(_VALUE=pd.to_numeric(block[value_col], errors="coerce").fillna(0.0)).groupby("County", observed=True)["_VALUE"].sum()
        if len(totals) and float(totals.max()) > 0:
            county = totals.idxmax()
            return block.loc[block["County"].eq(county)].copy(), f"Highest-exposure county: {county}"
    n = max(10, int(np.ceil(0.05 * len(block))))
    fallback = block.assign(_VALUE=pd.to_numeric(block[value_col], errors="coerce")).nlargest(n, "_VALUE").drop(columns="_VALUE")
    return fallback, f"Top {n} exposed EDs"


def _bivariate_class(block: pd.DataFrame, exposure_col: str, vulnerability_col: str) -> pd.Series:
    x = pd.to_numeric(block[exposure_col], errors="coerce")
    y = pd.to_numeric(block[vulnerability_col], errors="coerce")
    valid = x.notna() & y.notna()
    out = pd.Series(np.nan, index=block.index, dtype=float)
    if valid.sum() < 10:
        return out
    try:
        xr = pd.qcut(x[valid].rank(method="first"), 3, labels=False).astype(int)
        yr = pd.qcut(y[valid].rank(method="first"), 3, labels=False).astype(int)
    except ValueError:
        return out
    out.loc[valid] = (xr * 3 + yr).to_numpy(float)
    return out


def _paper_persistence(map_data: pd.DataFrame) -> pd.DataFrame:
    """Recompute top-decile SO exposure frequency over the eight BE/NZ paper runs."""
    data = _paper_only(map_data).copy()
    required = {"CSOED", "STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY", "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"paper persistence missing map columns: {missing}")
    data["_FLAG"] = False
    for _, idx in data.groupby(["STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY"], sort=False).groups.items():
        values = pd.to_numeric(data.loc[idx, "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"], errors="coerce").fillna(0.0)
        positive = values[values > 0]
        if positive.empty:
            continue
        threshold = float(positive.quantile(0.90))
        data.loc[idx, "_FLAG"] = values.ge(threshold) & values.gt(0)
    return data.groupby("CSOED", sort=False)["_FLAG"].sum().rename("PAPER_TOP_DECILE_SO_FREQUENCY").reset_index()


def generate_publication_maps(
    map_data: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path,
) -> dict[str, Path]:
    """Generate the main-paper cartographic package for BE_SG and ALL_GAS_NZ."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, Normalize
    from matplotlib.cm import ScalarMappable
    from matplotlib.patches import Rectangle

    path = Path(map_data).resolve()
    if path.is_dir():
        path = path / "GOBLIN_Spatial_Map_Data.csv"
    if not path.exists():
        raise FileNotFoundError(f"map-ready result table not found: {path}")
    raw = pd.read_csv(path, low_memory=False)
    raw = _paper_only(raw)
    geometry_path = resolve_geometry_path(config_path=config_path, geometry=geometry)
    model_geometry, _ = prepare_model_geometry(raw, geometry_path, geometry_key)
    joined = _project(build_joined_map_layer(raw, model_geometry))

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    # ------------------------------------------------------------------
    # M01. Standard Output exposure: national map + high-exposure callout.
    # ------------------------------------------------------------------
    exposure = "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if exposure in joined.columns:
        pr = joined.loc[joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")]
        values = pd.to_numeric(pr[exposure], errors="coerce")
        vmax = float(values.quantile(0.98)) if values.notna().any() else 1.0
        vmax = max(vmax, 1e-9)
        fig = plt.figure(figsize=(15.5, 8.2))
        gs = fig.add_gridspec(2, 4, width_ratios=[1.65, 0.72, 1.65, 0.72], hspace=0.14, wspace=0.12, left=0.03, right=0.97, top=0.92, bottom=0.07)
        callouts = []
        for i, scenario in enumerate(PAPER_SCENARIOS):
            main = fig.add_subplot(gs[:, i * 2])
            inset = fig.add_subplot(gs[0, i * 2 + 1])
            stat = fig.add_subplot(gs[1, i * 2 + 1])
            block = pr.loc[pr["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].copy()
            block.plot(column=exposure, ax=main, cmap="magma", vmin=0.0, vmax=vmax, linewidth=0.08, edgecolor="white", legend=True, legend_kwds={"shrink": 0.62, "label": "% of baseline livestock SO"}, missing_kwds={"color": NODATA_COLOR})
            outline = _county_outline(block)
            if outline is not None:
                outline.plot(ax=main, color="#333333", linewidth=0.45, alpha=0.65)
            main.set_title(SCENARIO_LABELS[scenario], fontsize=12.5, fontweight="bold")
            main.set_axis_off()
            _add_scale_bar(main)
            _add_north_arrow(main)

            focus, focus_label = _top_exposure_area(block, "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in block.columns else exposure)
            block.plot(ax=inset, color="#F3F3F3", edgecolor="white", linewidth=0.06)
            focus.plot(column=exposure, ax=inset, cmap="magma", vmin=0.0, vmax=vmax, linewidth=0.10, edgecolor="white")
            _zoom_to(inset, focus)
            inset.set_xticks([])
            inset.set_yticks([])
            for spine in inset.spines.values():
                spine.set_color("#7A1F5C")
                spine.set_linewidth(1.8)
            inset.set_title("Exposure callout", fontsize=9.5, fontweight="bold", color="#7A1F5C")

            stat.set_axis_off()
            exp_pct = pd.to_numeric(focus[exposure], errors="coerce")
            cattle_pct = pd.to_numeric(focus.get("TOTAL_CATTLE_REDUCTION_PCT_OF_BASE", np.nan), errors="coerce")
            released = pd.to_numeric(focus.get("GOBLIN_RELEASED_GRASSLAND_HA", np.nan), errors="coerce")
            text = (
                f"{focus_label}\n\n"
                f"EDs: {len(focus):,}\n"
                f"Mean SO exposure: {exp_pct.mean():.1f}%\n"
                f"Mean cattle adjustment: {cattle_pct.mean():.1f}%\n"
                f"Released grassland: {released.sum():,.0f} ha"
            )
            stat.text(0.02, 0.96, text, va="top", ha="left", fontsize=8.7, bbox={"facecolor": "white", "edgecolor": "#7A1F5C", "boxstyle": "round,pad=0.55", "linewidth": 1.2})
            geom = _union_all(focus.geometry)
            callouts.append((main, (geom.centroid.x, geom.centroid.y), inset))
        fig.suptitle("Gross livestock production-value exposure", fontsize=14, fontweight="bold", y=0.975)
        fig.canvas.draw()
        for main, point, inset in callouts:
            _draw_callout(fig, main, point, inset, "#7A1F5C")
        files = _save_map(fig, out / "pub_map01_standard_output_exposure")
        plt.close(fig)
        manifest.append(_manifest_row("M01", "Standard Output exposure", "Where does agricultural production-value exposure fall under the two main contraction pathways?", files))

    # ------------------------------------------------------------------
    # M02. Protection redistribution: two pathways x three protection rules.
    # ------------------------------------------------------------------
    relief_col = "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    burden_col = "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if relief_col in joined.columns and burden_col in joined.columns:
        block = joined.loc[~joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].copy()
        block["SIGNED_SO_REDISTRIBUTION_PCT"] = pd.to_numeric(block[burden_col], errors="coerce").fillna(0.0) - pd.to_numeric(block[relief_col], errors="coerce").fillna(0.0)
        vmax = float(np.nanquantile(np.abs(pd.to_numeric(block["SIGNED_SO_REDISTRIBUTION_PCT"], errors="coerce")), 0.99))
        vmax = max(vmax, 1e-9)
        rules = PAPER_RULES[1:]
        fig, axes = plt.subplots(2, 3, figsize=(13.8, 8.5), constrained_layout=True)
        for r, scenario in enumerate(PAPER_SCENARIOS):
            for c, rule in enumerate(rules):
                ax = axes[r, c]
                b = block.loc[
                    block["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
                    & block["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
                ]
                b.plot(column="SIGNED_SO_REDISTRIBUTION_PCT", ax=ax, cmap="RdBu_r", vmin=-vmax, vmax=vmax, linewidth=0.07, edgecolor="white", legend=False, missing_kwds={"color": NODATA_COLOR})
                outline = _county_outline(b)
                if outline is not None:
                    outline.plot(ax=ax, color="#444444", linewidth=0.35, alpha=0.55)
                ax.set_axis_off()
                ax.set_title(f"{SCENARIO_LABELS[scenario]}\n{RULE_LABELS[rule]}", fontsize=9.4)
        sm = ScalarMappable(norm=Normalize(vmin=-vmax, vmax=vmax), cmap="RdBu_r")
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes.ravel().tolist(), orientation="horizontal", shrink=0.72, pad=0.025, aspect=45)
        cbar.set_label("Difference from PRORATA in SO exposure (percentage points): relief  ←  0  →  displaced burden")
        fig.suptitle("Protection redistributes production-value exposure", fontsize=13.5, fontweight="bold")
        files = _save_map(fig, out / "pub_map02_protection_redistribution")
        plt.close(fig)
        manifest.append(_manifest_row("M02", "Protection redistribution", "Where does each protection principle reduce exposure and where is that fixed adjustment displaced?", files))

    # ------------------------------------------------------------------
    # M03. Exposure x vulnerability bivariate maps, without a composite index.
    # ------------------------------------------------------------------
    if exposure in joined.columns and {"ECONOMIC_VULNERABILITY_SCORE", "SOCIAL_VULNERABILITY_SCORE"}.intersection(joined.columns):
        biv_colors = [
            "#e8e8e8", "#d1b6d6", "#be64ac",
            "#b5c0da", "#a5add3", "#8c62aa",
            "#6c83b5", "#5698b9", "#3b4994",
        ]
        vulnerability_rows = [
            (c, label) for c, label in (
                ("ECONOMIC_VULNERABILITY_SCORE", "Economic vulnerability"),
                ("SOCIAL_VULNERABILITY_SCORE", "Social vulnerability"),
            ) if c in joined.columns
        ]
        fig, axes = plt.subplots(len(vulnerability_rows), 2, figsize=(12.7, 5.4 * len(vulnerability_rows)), constrained_layout=True)
        axes = np.asarray(axes).reshape(len(vulnerability_rows), 2)
        for r, (vcol, vlabel) in enumerate(vulnerability_rows):
            for c, scenario in enumerate(PAPER_SCENARIOS):
                ax = axes[r, c]
                b = joined.loc[
                    joined["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
                    & joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
                ].copy()
                b["BIVARIATE_CLASS"] = _bivariate_class(b, exposure, vcol)
                b.plot(column="BIVARIATE_CLASS", categorical=True, cmap=ListedColormap(biv_colors), ax=ax, linewidth=0.07, edgecolor="white", legend=False, missing_kwds={"color": NODATA_COLOR})
                outline = _county_outline(b)
                if outline is not None:
                    outline.plot(ax=ax, color="#444444", linewidth=0.35, alpha=0.55)
                ax.set_axis_off()
                ax.set_title(f"{SCENARIO_LABELS[scenario]} | {vlabel}", fontsize=10.0)
        legend_ax = fig.add_axes([0.82, 0.035, 0.12, 0.12])
        for i in range(3):
            for j in range(3):
                legend_ax.add_patch(Rectangle((j, i), 1, 1, facecolor=biv_colors[i * 3 + j], edgecolor="white"))
        legend_ax.set_xlim(0, 3)
        legend_ax.set_ylim(0, 3)
        legend_ax.set_xticks([0.5, 1.5, 2.5], ["Low", "Mid", "High"], fontsize=6.8)
        legend_ax.set_yticks([0.5, 1.5, 2.5], ["Low", "Mid", "High"], fontsize=6.8)
        legend_ax.set_xlabel("Vulnerability", fontsize=7.2)
        legend_ax.set_ylabel("SO exposure", fontsize=7.2)
        legend_ax.tick_params(length=0)
        for spine in legend_ax.spines.values():
            spine.set_visible(False)
        fig.suptitle("Production-value exposure and structural vulnerability", fontsize=13.5, fontweight="bold")
        files = _save_map(fig, out / "pub_map03_exposure_vulnerability")
        plt.close(fig)
        manifest.append(_manifest_row("M03", "Exposure-vulnerability geography", "Which EDs combine high production-value exposure with economic or social vulnerability?", files, note="Tercile-by-tercile bivariate classification; no composite risk or just-transition index."))

    # ------------------------------------------------------------------
    # M04. Persistent high exposure over the eight paper runs only.
    # ------------------------------------------------------------------
    persistence = _paper_persistence(raw)
    one = model_geometry.merge(persistence, on="CSOED", how="left", validate="one_to_one")
    one = _project(one)
    one["PAPER_TOP_DECILE_SO_FREQUENCY"] = pd.to_numeric(one["PAPER_TOP_DECILE_SO_FREQUENCY"], errors="coerce").fillna(0.0)
    fig, ax = plt.subplots(figsize=(7.7, 7.2))
    one.plot(column="PAPER_TOP_DECILE_SO_FREQUENCY", ax=ax, cmap="viridis", vmin=0, vmax=8, linewidth=0.08, edgecolor="white", legend=True, legend_kwds={"shrink": 0.66, "label": "Top-decile appearances across 8 BE/NZ paper runs"}, missing_kwds={"color": NODATA_COLOR})
    ax.set_title("Persistent high production-value exposure\nBE-SG and All-Gas NZ across four incidence rules", fontsize=12.0, fontweight="bold")
    ax.set_axis_off()
    _add_scale_bar(ax)
    _add_north_arrow(ax)
    files = _save_map(fig, out / "pub_map04_persistent_exposure")
    plt.close(fig)
    manifest.append(_manifest_row("M04", "Persistent exposure", "Which EDs repeatedly appear among the most exposed across the two main pathways and four incidence rules?", files, note="Frequency across eight modeled runs, not a probability or confidence interval."))

    # ------------------------------------------------------------------
    # M05. Released-land bridge from SC1 to downstream opportunity.
    # ------------------------------------------------------------------
    release_col = "GOBLIN_RELEASED_GRASSLAND_HA"
    if release_col in joined.columns:
        pr = joined.loc[joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")]
        values = pd.to_numeric(pr[release_col], errors="coerce")
        vmax = float(values.quantile(0.98)) if values.notna().any() else 1.0
        vmax = max(vmax, 1e-9)
        fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.0), constrained_layout=True)
        for ax, scenario in zip(axes, PAPER_SCENARIOS):
            b = pr.loc[pr["STUDY_SCENARIO_ID"].astype(str).eq(scenario)]
            b.plot(column=release_col, ax=ax, cmap="YlGn", vmin=0.0, vmax=vmax, linewidth=0.07, edgecolor="white", legend=True, legend_kwds={"shrink": 0.62, "label": "Released grassland (ha)"}, missing_kwds={"color": NODATA_COLOR})
            outline = _county_outline(b)
            if outline is not None:
                outline.plot(ax=ax, color="#444444", linewidth=0.35, alpha=0.55)
            ax.set_title(SCENARIO_LABELS[scenario])
            ax.set_axis_off()
            _add_scale_bar(ax)
        fig.suptitle("Where livestock adjustment releases grassland", fontsize=13.2, fontweight="bold")
        files = _save_map(fig, out / "pub_map05_released_grassland")
        plt.close(fig)
        manifest.append(_manifest_row("M05", "Released grassland", "How does the SC1 incidence geography determine where land becomes available for the wider transition?", files))

    manifest_path = out / "GOBLIN_Spatial_Publication_Map_Manifest.csv"
    pd.DataFrame(manifest).to_csv(manifest_path, index=False)
    return {"map_directory": out, "map_manifest": manifest_path}


def generate_publication_visuals(
    final_results: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path | None = None,
    graphs_only: bool = False,
) -> dict[str, Path]:
    """Generate the complete BE-SG / All-Gas NZ main-paper visual package.

    ``final_results`` may be the final-results directory or the SQLite file.
    When maps are requested, the same directory must contain
    ``GOBLIN_Spatial_Map_Data.csv`` unless an explicit CSV path is passed to
    :func:`generate_publication_maps` directly.
    """
    root = Path(final_results).resolve()
    if root.is_dir():
        database = root / "GOBLIN_Spatial_Final_Results.sqlite"
        map_csv = root / "GOBLIN_Spatial_Map_Data.csv"
        out = Path(output_dir).resolve() if output_dir is not None else root / "publication_visuals"
    else:
        database = root
        map_csv = root.parent / "GOBLIN_Spatial_Map_Data.csv"
        out = Path(output_dir).resolve() if output_dir is not None else root.parent / "publication_visuals"
    outputs = generate_publication_graphs(database, out / "graphs")
    if not graphs_only:
        outputs.update(
            generate_publication_maps(
                map_csv,
                geometry=geometry,
                geometry_key=geometry_key,
                config_path=config_path,
                output_dir=out / "maps",
            )
        )
    return outputs
