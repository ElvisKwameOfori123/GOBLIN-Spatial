"""Final polish layer for the GOBLIN-Spatial publication visuals.

This module is deliberately downstream of the validated numerical model and the
base publication visual layer. It does not change SC1, SC2 or SC3 science.
Instead it applies the final manuscript-facing refinements agreed for the two
main contraction pathways, BE_SG and ALL_GAS_NZ:

* common comparison thresholds across the two pathways;
* a shared exposure-vulnerability diagnostic for early-attention geography;
* bivariate maps whose classes have the same numerical meaning in both pathways;
* released-land maps with analytical callouts linking exposure to future-use
  opportunity;
* explicit map/graph manifest notes documenting those comparison rules.

The base publication package is generated first. The three polished outputs use
the same filenames as their base counterparts and therefore replace them in the
final publication directory without creating additional manuscript figures.
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
from goblin_spatial.publication_visuals import (
    NODATA_COLOR,
    PAPER_SCENARIOS,
    SCENARIO_LABELS,
    TARGET_CRS,
    _add_north_arrow,
    _add_scale_bar,
    _county_outline,
    _draw_callout,
    _paper_only,
    _project,
    _save_graph,
    _save_map,
    _setup_matplotlib,
    _union_all,
    _zoom_to,
    generate_publication_visuals as _generate_base_visuals,
)


FINAL_PUBLICATION_VISUAL_VERSION = "1.1"
EXPOSURE_COLUMN = "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
VULNERABILITY_COLUMNS = (
    ("ECONOMIC_VULNERABILITY_SCORE", "Economic vulnerability"),
    ("SOCIAL_VULNERABILITY_SCORE", "Social vulnerability"),
)
OPPORTUNITY_COLUMNS = (
    ("FOREST_ELIGIBILITY_COVERAGE_PCT", "Forest"),
    ("AD_GRASS_ELIGIBILITY_COVERAGE_PCT", "AD grass"),
    ("WILLOW_ELIGIBILITY_COVERAGE_PCT", "Willow"),
)


def _finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values[np.isfinite(values)]


def _common_median(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = _finite(frame[column])
    return float(values.median()) if len(values) else None


def _tercile_breaks(values: pd.Series) -> tuple[float, float] | None:
    x = _finite(values)
    if len(x) < 3:
        return None
    q1 = float(x.quantile(1.0 / 3.0))
    q2 = float(x.quantile(2.0 / 3.0))
    if np.isfinite(q1) and np.isfinite(q2) and q2 > q1:
        return q1, q2
    lo, hi = float(x.min()), float(x.max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    return lo + (hi - lo) / 3.0, lo + 2.0 * (hi - lo) / 3.0


def _classify(values: pd.Series, breaks: tuple[float, float] | None) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce")
    out = pd.Series(np.nan, index=x.index, dtype=float)
    valid = x.notna()
    if breaks is None:
        return out
    q1, q2 = breaks
    out.loc[valid] = np.digitize(x.loc[valid].to_numpy(float), [q1, q2], right=True).astype(float)
    return out


def _read_transition_conditions(database: str | Path) -> pd.DataFrame:
    path = Path(database).resolve()
    if not path.exists():
        raise FileNotFoundError(f"final results database not found: {path}")
    with sqlite3.connect(path) as con:
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "transition_conditions" not in names:
            raise ValueError("final results database missing transition_conditions")
        frame = pd.read_sql_query('SELECT * FROM "transition_conditions"', con)
    return _paper_only(frame)


def generate_polished_exposure_vulnerability_graph(
    database: str | Path,
    output_dir: str | Path,
) -> Path:
    """Overwrite G04 using common pathway comparison cut-lines.

    The exposure median is calculated once across the pooled BE-SG and All-Gas
    NZ PRORATA observations. Vulnerability medians are calculated once over the
    common ED baseline. Consequently a quadrant has the same numerical meaning
    in both pathway panels.
    """
    cond = _read_transition_conditions(database)
    pr = cond.loc[cond["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].copy()
    present = [(c, label) for c, label in VULNERABILITY_COLUMNS if c in pr.columns]
    if EXPOSURE_COLUMN not in pr.columns or not present:
        raise ValueError("polished exposure-vulnerability graph requires exposure and vulnerability columns")

    x_cut = _common_median(pr, EXPOSURE_COLUMN)
    vulnerability_cuts: dict[str, float | None] = {}
    for column, _ in present:
        # Vulnerability is a frozen baseline characteristic. Deduplicate the ED
        # universe before deriving a common threshold so each ED contributes once.
        if "CSOED" in pr.columns:
            baseline = pr[["CSOED", column]].drop_duplicates("CSOED")
            vulnerability_cuts[column] = _common_median(baseline, column)
        else:
            vulnerability_cuts[column] = _common_median(pr, column)

    plt = _setup_matplotlib()
    fig, axes = plt.subplots(len(present), 2, figsize=(12.2, 4.2 * len(present)), constrained_layout=True)
    axes = np.asarray(axes).reshape(len(present), 2)
    for row, (vcol, vlabel) in enumerate(present):
        y_cut = vulnerability_cuts[vcol]
        for col, scenario in enumerate(PAPER_SCENARIOS):
            ax = axes[row, col]
            block = pr.loc[pr["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].copy()
            x = pd.to_numeric(block[EXPOSURE_COLUMN], errors="coerce")
            y = pd.to_numeric(block[vcol], errors="coerce")
            release = pd.to_numeric(block.get("GOBLIN_RELEASED_GRASSLAND_HA", 0.0), errors="coerce").fillna(0.0)
            valid = x.notna() & y.notna()
            x, y, release = x[valid], y[valid], release[valid]
            max_release = float(release.max()) if len(release) else 0.0
            sizes = 16.0 + (95.0 * np.sqrt(np.maximum(release, 0.0) / max_release) if max_release > 0 else 0.0)
            ax.scatter(x, y, s=sizes, color="#3B6FB6", alpha=0.42, edgecolors="white", linewidth=0.25)
            if x_cut is not None:
                ax.axvline(x_cut, color="#666666", linestyle="--", linewidth=0.9)
            if y_cut is not None:
                ax.axhline(y_cut, color="#666666", linestyle="--", linewidth=0.9)
            if x_cut is not None and y_cut is not None:
                x_hi = ax.get_xlim()[1]
                ax.axvspan(x_cut, x_hi, ymin=max(min(y_cut, 1.0), 0.0), ymax=1.0, color="#8B1E3F", alpha=0.035, zorder=-10)
                ax.text(
                    0.985,
                    0.97,
                    "Early-attention\nquadrant",
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=7.6,
                    color="#6B1730",
                )
            ax.set_xlabel("Gross livestock SO exposure (% of baseline)")
            ax.set_ylabel(vlabel + " score")
            ax.set_ylim(-0.03, 1.03)
            ax.grid(alpha=0.12)
            prefix = chr(ord("A") + row * 2 + col)
            ax.set_title(f"{prefix}. {vlabel} | {SCENARIO_LABELS[scenario]}")

    fig.suptitle("Transition exposure and structural vulnerability", fontsize=13.2, fontweight="bold")
    out = Path(output_dir).resolve()
    files = _save_graph(fig, out / "pub_fig04_exposure_vulnerability")
    plt.close(fig)
    return next(p for p in files if p.suffix.lower() == ".png")


def _load_map_layer(
    map_data: str | Path,
    *,
    geometry: str | Path | None,
    geometry_key: str | None,
    config_path: str | Path,
):
    path = Path(map_data).resolve()
    if path.is_dir():
        path = path / "GOBLIN_Spatial_Map_Data.csv"
    if not path.exists():
        raise FileNotFoundError(f"map-ready result table not found: {path}")
    raw = _paper_only(pd.read_csv(path, low_memory=False))
    geometry_path = resolve_geometry_path(config_path=config_path, geometry=geometry)
    model_geometry, _ = prepare_model_geometry(raw, geometry_path, geometry_key)
    joined = _project(build_joined_map_layer(raw, model_geometry))
    return raw, model_geometry, joined


def generate_polished_bivariate_map(
    map_data: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path,
) -> Path:
    """Overwrite M03 with pooled, numerically comparable bivariate classes."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Rectangle

    _, _, joined = _load_map_layer(
        map_data,
        geometry=geometry,
        geometry_key=geometry_key,
        config_path=config_path,
    )
    pr = joined.loc[joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].copy()
    if EXPOSURE_COLUMN not in pr.columns:
        raise ValueError("polished bivariate map requires Standard Output exposure")

    vulnerability_rows = [(c, label) for c, label in VULNERABILITY_COLUMNS if c in pr.columns]
    if not vulnerability_rows:
        raise ValueError("polished bivariate map requires vulnerability scores")

    exposure_breaks = _tercile_breaks(pr[EXPOSURE_COLUMN])
    vulnerability_breaks: dict[str, tuple[float, float] | None] = {}
    for column, _ in vulnerability_rows:
        baseline = pr[["CSOED", column]].drop_duplicates("CSOED") if "CSOED" in pr.columns else pr[[column]]
        vulnerability_breaks[column] = _tercile_breaks(baseline[column])

    colors = [
        "#e8e8e8", "#d1b6d6", "#be64ac",
        "#b5c0da", "#a5add3", "#8c62aa",
        "#6c83b5", "#5698b9", "#3b4994",
    ]
    fig, axes = plt.subplots(len(vulnerability_rows), 2, figsize=(12.7, 5.4 * len(vulnerability_rows)), constrained_layout=True)
    axes = np.asarray(axes).reshape(len(vulnerability_rows), 2)
    for row, (vcol, vlabel) in enumerate(vulnerability_rows):
        y_breaks = vulnerability_breaks[vcol]
        for col, scenario in enumerate(PAPER_SCENARIOS):
            ax = axes[row, col]
            block = pr.loc[pr["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].copy()
            xclass = _classify(block[EXPOSURE_COLUMN], exposure_breaks)
            yclass = _classify(block[vcol], y_breaks)
            valid = xclass.notna() & yclass.notna()
            block["BIVARIATE_CLASS"] = np.nan
            block.loc[valid, "BIVARIATE_CLASS"] = (
                xclass.loc[valid].astype(int) * 3 + yclass.loc[valid].astype(int)
            ).to_numpy(float)
            block.plot(
                column="BIVARIATE_CLASS",
                categorical=True,
                cmap=ListedColormap(colors),
                ax=ax,
                linewidth=0.07,
                edgecolor="white",
                legend=False,
                missing_kwds={"color": NODATA_COLOR},
            )
            outline = _county_outline(block)
            if outline is not None:
                outline.plot(ax=ax, color="#444444", linewidth=0.35, alpha=0.55)
            ax.set_axis_off()
            ax.set_title(f"{SCENARIO_LABELS[scenario]} | {vlabel}", fontsize=10.0)

    legend_ax = fig.add_axes([0.82, 0.035, 0.12, 0.12])
    for i in range(3):
        for j in range(3):
            legend_ax.add_patch(Rectangle((j, i), 1, 1, facecolor=colors[i * 3 + j], edgecolor="white"))
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

    out = Path(output_dir).resolve()
    files = _save_map(fig, out / "pub_map03_exposure_vulnerability")
    plt.close(fig)
    return next(p for p in files if p.suffix.lower() == ".png")


def _top_release_area(block: pd.DataFrame):
    value_col = "GOBLIN_RELEASED_GRASSLAND_HA"
    if "County" in block.columns and block["County"].notna().any():
        totals = (
            block.assign(_VALUE=pd.to_numeric(block[value_col], errors="coerce").fillna(0.0))
            .groupby("County", observed=True)["_VALUE"]
            .sum()
        )
        if len(totals) and float(totals.max()) > 0:
            county = totals.idxmax()
            return block.loc[block["County"].eq(county)].copy(), f"Largest-release county: {county}"
    n = max(10, int(np.ceil(0.05 * len(block))))
    return (
        block.assign(_VALUE=pd.to_numeric(block[value_col], errors="coerce"))
        .nlargest(n, "_VALUE")
        .drop(columns="_VALUE"),
        f"Top {n} released-land EDs",
    )


def generate_polished_released_land_map(
    map_data: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path,
) -> Path:
    """Overwrite M05 with callouts linking released land to future opportunity."""
    import matplotlib.pyplot as plt

    _, _, joined = _load_map_layer(
        map_data,
        geometry=geometry,
        geometry_key=geometry_key,
        config_path=config_path,
    )
    release_col = "GOBLIN_RELEASED_GRASSLAND_HA"
    if release_col not in joined.columns:
        raise ValueError("polished released-land map requires released grassland")
    pr = joined.loc[joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")].copy()
    values = pd.to_numeric(pr[release_col], errors="coerce")
    vmax = float(values.quantile(0.98)) if values.notna().any() else 1.0
    vmax = max(vmax, 1e-9)

    fig = plt.figure(figsize=(15.5, 8.2))
    gs = fig.add_gridspec(
        2,
        4,
        width_ratios=[1.65, 0.72, 1.65, 0.72],
        hspace=0.14,
        wspace=0.12,
        left=0.03,
        right=0.97,
        top=0.92,
        bottom=0.07,
    )
    callouts = []
    for i, scenario in enumerate(PAPER_SCENARIOS):
        main = fig.add_subplot(gs[:, i * 2])
        inset = fig.add_subplot(gs[0, i * 2 + 1])
        stat = fig.add_subplot(gs[1, i * 2 + 1])
        block = pr.loc[pr["STUDY_SCENARIO_ID"].astype(str).eq(scenario)].copy()
        block.plot(
            column=release_col,
            ax=main,
            cmap="YlGn",
            vmin=0.0,
            vmax=vmax,
            linewidth=0.08,
            edgecolor="white",
            legend=True,
            legend_kwds={"shrink": 0.62, "label": "Released grassland (ha)"},
            missing_kwds={"color": NODATA_COLOR},
        )
        outline = _county_outline(block)
        if outline is not None:
            outline.plot(ax=main, color="#333333", linewidth=0.45, alpha=0.65)
        main.set_title(SCENARIO_LABELS[scenario], fontsize=12.5, fontweight="bold")
        main.set_axis_off()
        _add_scale_bar(main)
        _add_north_arrow(main)

        focus, focus_label = _top_release_area(block)
        block.plot(ax=inset, color="#F3F3F3", edgecolor="white", linewidth=0.06)
        focus.plot(column=release_col, ax=inset, cmap="YlGn", vmin=0.0, vmax=vmax, linewidth=0.10, edgecolor="white")
        _zoom_to(inset, focus)
        inset.set_xticks([])
        inset.set_yticks([])
        for spine in inset.spines.values():
            spine.set_color("#2A7F62")
            spine.set_linewidth(1.8)
        inset.set_title("Released-land callout", fontsize=9.5, fontweight="bold", color="#2A7F62")

        stat.set_axis_off()
        lines = [
            focus_label,
            "",
            f"EDs: {len(focus):,}",
            f"Released grassland: {pd.to_numeric(focus[release_col], errors='coerce').sum():,.0f} ha",
        ]
        if EXPOSURE_COLUMN in focus.columns:
            lines.append(f"Mean SO exposure: {pd.to_numeric(focus[EXPOSURE_COLUMN], errors='coerce').mean():.1f}%")
        for column, label in OPPORTUNITY_COLUMNS:
            if column in focus.columns:
                value = pd.to_numeric(focus[column], errors="coerce").mean()
                if np.isfinite(value):
                    lines.append(f"Mean {label} eligibility: {value:.1f}%")
        stat.text(
            0.02,
            0.96,
            "\n".join(lines[:8]),
            va="top",
            ha="left",
            fontsize=8.6,
            bbox={"facecolor": "white", "edgecolor": "#2A7F62", "boxstyle": "round,pad=0.55", "linewidth": 1.2},
        )
        geom = _union_all(focus.geometry)
        callouts.append((main, (geom.centroid.x, geom.centroid.y), inset))

    fig.suptitle("Released grassland and future-use opportunity", fontsize=14, fontweight="bold", y=0.975)
    fig.canvas.draw()
    for main, point, inset in callouts:
        _draw_callout(fig, main, point, inset, "#2A7F62")
    out = Path(output_dir).resolve()
    files = _save_map(fig, out / "pub_map05_released_grassland")
    plt.close(fig)
    return next(p for p in files if p.suffix.lower() == ".png")


def _update_manifest_note(path: Path, figure_id: str, note: str) -> None:
    if not path.exists():
        return
    frame = pd.read_csv(path)
    if "FIGURE_ID" not in frame.columns:
        return
    frame.loc[frame["FIGURE_ID"].astype(str).eq(figure_id), "NOTE"] = note
    frame.loc[frame["FIGURE_ID"].astype(str).eq(figure_id), "PUBLICATION_VISUAL_VERSION"] = FINAL_PUBLICATION_VISUAL_VERSION
    frame.to_csv(path, index=False)


def generate_final_publication_visuals(
    final_results: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path | None = None,
    graphs_only: bool = False,
) -> dict[str, Path]:
    """Generate the base package and apply the final manuscript polish."""
    root = Path(final_results).resolve()
    if root.is_dir():
        database = root / "GOBLIN_Spatial_Final_Results.sqlite"
        map_csv = root / "GOBLIN_Spatial_Map_Data.csv"
        out = Path(output_dir).resolve() if output_dir is not None else root / "publication_visuals"
    else:
        database = root
        map_csv = root.parent / "GOBLIN_Spatial_Map_Data.csv"
        out = Path(output_dir).resolve() if output_dir is not None else root.parent / "publication_visuals"

    outputs = _generate_base_visuals(
        final_results,
        geometry=geometry,
        geometry_key=geometry_key,
        config_path=config_path,
        output_dir=out,
        graphs_only=graphs_only,
    )

    generate_polished_exposure_vulnerability_graph(database, out / "graphs")
    graph_manifest = out / "graphs" / "GOBLIN_Spatial_Publication_Graph_Manifest.csv"
    _update_manifest_note(
        graph_manifest,
        "G04",
        "Common pooled exposure cut-line and common baseline vulnerability cut-line are used in both pathways; top-right is the early-attention quadrant. No composite risk index is constructed.",
    )

    if not graphs_only:
        generate_polished_bivariate_map(
            map_csv,
            geometry=geometry,
            geometry_key=geometry_key,
            config_path=config_path,
            output_dir=out / "maps",
        )
        generate_polished_released_land_map(
            map_csv,
            geometry=geometry,
            geometry_key=geometry_key,
            config_path=config_path,
            output_dir=out / "maps",
        )
        map_manifest = out / "maps" / "GOBLIN_Spatial_Publication_Map_Manifest.csv"
        _update_manifest_note(
            map_manifest,
            "M03",
            "Bivariate classes use pooled BE-SG/All-Gas NZ exposure terciles and common baseline vulnerability terciles, so identical colours have identical numerical meaning across pathways.",
        )
        _update_manifest_note(
            map_manifest,
            "M05",
            "National released-land maps use shared scales and analytical callouts for the largest-release geography, including opportunity-eligibility summary statistics where available.",
        )

    outputs["final_visual_version"] = Path(str(FINAL_PUBLICATION_VISUAL_VERSION))
    return outputs
