"""Downstream cartographic reporting for GOBLIN-Spatial final results.

Maps never change SC1, SC2 or SC3 science. They consume the frozen numerical
``GOBLIN_Spatial_Map_Data.csv`` table and join it to a user-supplied or frozen
Electoral Division geometry source by ``CSOED``. A source ESRI Shapefile is
acceptable, but the renderer immediately materialises a compact GeoPackage
containing only the model ED universe so later map runs no longer depend on the
multi-file Shapefile bundle.

The map package therefore sits after the numerical study and paper figures:

    baseline -> SC1 -> SC2 -> SC3 -> final results -> figures -> maps

The numerical CSV/SQLite outputs remain authoritative. Geometry is presentation
infrastructure only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.study_reporting import PRINCIPAL_SCENARIOS


MAP_REPORTING_VERSION = "1.1"
SCENARIO_LABELS = {
    "SI_SG": "SI–SG",
    "BE_SG": "BE–SG",
    "ALL_GAS_NZ": "All-gas NZ",
}
RULE_LABELS = {
    "PRORATA": "PRORATA",
    "DAIRY_PROTECTION": "Dairy protection",
    "ECONOMIC_CAPACITY_PROTECTION": "Economic protection",
    "SOCIAL_VULNERABILITY_PROTECTION": "Social protection",
}


def _gpd():
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError(
            "Mapping requires the optional GIS dependencies. Install with "
            "`pip install -e '.[geo]'`."
        ) from exc
    return gpd


def _normalise_id(values: pd.Series) -> pd.Series:
    """Return the stable cartographic ED key used only for geometry joins.

    The scientific model keeps its source ``CSOED`` values unchanged. For
    cartography we deliberately use the first ED code where a source geography
    is represented by a composite identifier such as ``08045/08046`` and remove
    leading zeroes from numeric codes. This yields a simple text key such as
    ``8045`` while the original source identifier is retained separately in the
    joined map layer.
    """
    out = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    out = out.str.split("/", n=1).str[0].str.strip()
    numeric = out.str.fullmatch(r"\d+", na=False)
    cleaned = out.loc[numeric].str.lstrip("0")
    out.loc[numeric] = cleaned.mask(cleaned.eq(""), "0")
    return out


def _resolve_map_csv(results: str | Path) -> Path:
    path = Path(results).resolve()
    if path.is_dir():
        path = path / "GOBLIN_Spatial_Map_Data.csv"
    if not path.exists():
        raise FileNotFoundError(f"map-ready result table not found: {path}")
    return path


def resolve_geometry_path(
    *,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    geometry: str | Path | None = None,
) -> Path:
    """Resolve map geometry without making it part of scenario runtime."""
    if geometry is not None:
        path = Path(geometry).resolve()
        if not path.exists():
            raise FileNotFoundError(f"explicit map geometry not found: {path}")
        return path

    cfg = load_config(Path(config_path))
    candidates: list[Path] = []
    for key in ("ed_boundaries_frozen", "saps_ed_geography"):
        value = cfg.files.get(key)
        if value is None:
            continue
        path = Path(value)
        path = path if path.is_absolute() else cfg.project_root / path
        candidates.append(path)
        if path.exists():
            return path.resolve()

    listed = ", ".join(str(p) for p in candidates) or "<none configured>"
    raise FileNotFoundError(
        "No ED geometry is available for the optional mapping stage. Scenario "
        "results do not require geometry. Supply `--geometry /path/to/EDs.shp` "
        "or a GeoPackage. The map renderer will freeze the matching model EDs "
        f"to a single GeoPackage for reproducibility. Configured candidates: {listed}"
    )


def _detect_geometry_key(geometry, result_ids: set[str], explicit: str | None = None) -> str:
    columns = [c for c in geometry.columns if c != geometry.geometry.name]
    if explicit is not None:
        if explicit not in columns:
            raise ValueError(f"geometry key {explicit!r} not found; columns={columns}")
        return explicit

    preferred = ["CSOED", "ED_ID", "EDID", "ED_CODE", "GEOGID", "EDCODE", "CODE"]
    ordered = [c for p in preferred for c in columns if c.upper() == p]
    ordered += [c for c in columns if c not in ordered]

    best: tuple[float, str] | None = None
    for column in ordered:
        values = set(_normalise_id(geometry[column]).dropna().astype(str))
        if not values:
            continue
        overlap = len(result_ids & values) / max(len(result_ids), 1)
        if best is None or overlap > best[0]:
            best = (overlap, column)
        if overlap >= 0.999999:
            return column

    if best is None or best[0] < 0.95:
        detail = "none" if best is None else f"{best[1]} ({100.0 * best[0]:.1f}% overlap)"
        raise ValueError(
            "Could not identify a geometry attribute matching model CSOED values. "
            f"Best candidate: {detail}. Supply --geometry-key explicitly."
        )
    return best[1]


def prepare_model_geometry(
    map_data: pd.DataFrame,
    geometry_path: str | Path,
    *,
    geometry_key: str | None = None,
):
    """Read source geometry, identify the ED key and retain the model ED universe."""
    gpd = _gpd()
    if "CSOED" not in map_data.columns:
        raise ValueError("map data requires CSOED")
    result_ids = set(_normalise_id(map_data["CSOED"]).dropna().astype(str))
    if not result_ids:
        raise ValueError("map data contains no CSOED identifiers")

    geometry = gpd.read_file(Path(geometry_path))
    if geometry.empty:
        raise ValueError("ED geometry source is empty")
    if geometry.crs is None:
        raise ValueError("ED geometry has no CRS; provide a georeferenced Shapefile/GeoPackage")
    if geometry.geometry.isna().any() or geometry.geometry.is_empty.any():
        raise ValueError("ED geometry contains missing or empty features")
    if (~geometry.geometry.is_valid).any():
        raise ValueError("ED geometry contains invalid features; repair the source before mapping")

    key = _detect_geometry_key(geometry, result_ids, geometry_key)
    geometry = geometry.copy()
    geometry["CSOED_GEOMETRY_SOURCE"] = geometry[key].astype("string").str.strip()
    geometry["CSOED"] = _normalise_id(geometry[key])
    selected = geometry.loc[
        geometry["CSOED"].isin(result_ids),
        ["CSOED", "CSOED_GEOMETRY_SOURCE", geometry.geometry.name],
    ].copy()
    if selected["CSOED"].duplicated().any():
        dupes = selected.loc[selected["CSOED"].duplicated(), "CSOED"].astype(str).head().tolist()
        raise ValueError(f"ED geometry key is not unique for model EDs; examples={dupes}")
    missing = sorted(result_ids - set(selected["CSOED"].astype(str)))
    if missing:
        raise ValueError(
            f"geometry is missing {len(missing)} model EDs; first missing IDs={missing[:10]}"
        )
    return selected.sort_values("CSOED", kind="stable").reset_index(drop=True), key


def build_joined_map_layer(map_data: pd.DataFrame, model_geometry):
    """Attach the same frozen geometry to every ED x scenario x rule result row."""
    raw_keys = ["STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY", "CSOED"]
    if map_data[raw_keys].duplicated().any():
        raise ValueError("map data must contain one row per ED x scenario x allocation rule")
    data = map_data.copy()
    data["CSOED_SOURCE"] = data["CSOED"].astype("string").str.strip()
    data["CSOED"] = _normalise_id(data["CSOED"])
    if data[raw_keys].duplicated().any():
        raise ValueError(
            "cartographic ED normalisation created a duplicate ED x scenario x allocation-rule key"
        )
    joined = model_geometry.merge(data, on="CSOED", how="right", validate="one_to_many")
    if joined.geometry.isna().any():
        raise AssertionError("map join lost ED geometry")
    return joined


def _save_map(fig, base: Path) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    png = base.with_suffix(".png")
    svg = base.with_suffix(".svg")
    fig.savefig(png, dpi=500, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    return [png, svg]


def _map_style():
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 9.5,
        "axes.titlesize": 11.5,
        "axes.titleweight": "bold",
        "figure.titlesize": 13.0,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })
    return plt


def _panel_map(
    frame,
    *,
    column: str,
    scenarios: tuple[str, ...] = PRINCIPAL_SCENARIOS,
    rule: str = "PRORATA",
    title: str,
    cmap: str,
    vmin: float | None = None,
    vmax: float | None = None,
    legend_label: str = "",
):
    plt = _map_style()
    fig, axes = plt.subplots(1, len(scenarios), figsize=(12.8, 5.0))
    axes = np.atleast_1d(axes)
    for ax, scenario in zip(axes, scenarios):
        block = frame.loc[
            frame["STUDY_SCENARIO_ID"].astype(str).eq(str(scenario))
            & frame["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ]
        if block.empty:
            ax.set_axis_off()
            continue
        block.plot(
            column=column,
            ax=ax,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            linewidth=0.10,
            edgecolor="white",
            legend=True,
            legend_kwds={"shrink": 0.68, "label": legend_label},
            missing_kwds={"color": "#eeeeee"},
        )
        ax.set_title(SCENARIO_LABELS.get(str(scenario), str(scenario)))
        ax.set_axis_off()
    fig.suptitle(title, y=0.98)
    fig.tight_layout()
    return fig


def _choose_opportunity_column(frame: pd.DataFrame) -> tuple[str, str] | None:
    candidates = [
        ("AD_GRASS_ELIGIBILITY_COVERAGE_PCT", "AD grass"),
        ("BIOREFINERY_GRASS_ELIGIBILITY_COVERAGE_PCT", "Biorefinery grass"),
        ("WILLOW_ELIGIBILITY_COVERAGE_PCT", "Willow"),
        ("ADDITIONAL_TILLAGE_ELIGIBILITY_COVERAGE_PCT", "Additional tillage"),
        ("FOREST_ELIGIBILITY_COVERAGE_PCT", "Forest"),
        ("REWETTING_ELIGIBILITY_COVERAGE_PCT", "Rewetting"),
    ]
    block = frame.loc[
        frame["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
        & frame["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ]
    scored: list[tuple[float, str, str]] = []
    for column, label in candidates:
        if column not in block.columns:
            continue
        values = pd.to_numeric(block[column], errors="coerce")
        if values.notna().sum() < 10:
            continue
        scored.append((float(values.std(skipna=True)), column, label))
    if not scored:
        return None
    _, column, label = max(scored, key=lambda x: x[0])
    return column, label


def _bivariate_exposure_opportunity(frame):
    plt = _map_style()
    choice = _choose_opportunity_column(frame)
    exposure = "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if choice is None or exposure not in frame.columns:
        return None, None
    opportunity, label = choice
    block = frame.loc[
        frame["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
        & frame["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
    ].copy()
    x = pd.to_numeric(block[exposure], errors="coerce")
    y = pd.to_numeric(block[opportunity], errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 10:
        return None, None

    try:
        xq = pd.qcut(x[valid].rank(method="first"), 3, labels=False)
        yq = pd.qcut(y[valid].rank(method="first"), 3, labels=False)
    except ValueError:
        return None, None
    block["BIVARIATE_CLASS"] = np.nan
    block.loc[valid, "BIVARIATE_CLASS"] = (xq.astype(int) * 3 + yq.astype(int)).to_numpy()

    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Rectangle

    # Rows increase with exposure; columns increase with opportunity.
    colors = [
        "#e8e8e8", "#b5c0da", "#6c83b5",
        "#dfb0d6", "#a5add3", "#5698b9",
        "#be64ac", "#8c62aa", "#3b4994",
    ]
    fig, ax = plt.subplots(figsize=(7.6, 7.0))
    block.plot(
        column="BIVARIATE_CLASS",
        categorical=True,
        cmap=ListedColormap(colors),
        ax=ax,
        linewidth=0.10,
        edgecolor="white",
        legend=False,
        missing_kwds={"color": "#eeeeee"},
    )
    ax.set_title(f"Transition exposure and {label.lower()} opportunity\nAll-gas NZ, PRORATA")
    ax.set_axis_off()

    legend_ax = ax.inset_axes([0.02, 0.03, 0.22, 0.22])
    for i in range(3):
        for j in range(3):
            legend_ax.add_patch(Rectangle((j, i), 1, 1, facecolor=colors[i * 3 + j], edgecolor="white"))
    legend_ax.set_xlim(0, 3)
    legend_ax.set_ylim(0, 3)
    legend_ax.set_xticks([0.5, 1.5, 2.5], ["Low", "Mid", "High"], fontsize=7)
    legend_ax.set_yticks([0.5, 1.5, 2.5], ["Low", "Mid", "High"], fontsize=7)
    legend_ax.set_xlabel(f"{label} opportunity", fontsize=7.5)
    legend_ax.set_ylabel("SO exposure", fontsize=7.5)
    legend_ax.tick_params(length=0)
    for spine in legend_ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    return fig, label


def generate_core_maps(joined, output_dir: str | Path) -> tuple[list[Path], pd.DataFrame]:
    """Generate a selective main cartographic package from frozen map data."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    manifest: list[dict[str, str]] = []

    # 1. Persistence across the modelled future envelope.
    persistence_col = "TOP_DECILE_SO_FREQUENCY" if "TOP_DECILE_SO_FREQUENCY" in joined.columns else "TOP_DECILE_CATTLE_FREQUENCY"
    if persistence_col in joined.columns:
        one = joined.sort_values(["CSOED", "STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY"]).drop_duplicates("CSOED")
        plt = _map_style()
        fig, ax = plt.subplots(figsize=(7.4, 7.0))
        vmax = float(pd.to_numeric(one[persistence_col], errors="coerce").max())
        one.plot(column=persistence_col, ax=ax, cmap="viridis", vmin=0, vmax=max(vmax, 1), linewidth=0.10, edgecolor="white", legend=True, legend_kwds={"shrink": 0.68, "label": "Top-decile appearances across modelled runs"})
        ax.set_title("Persistence of high transition exposure")
        ax.set_axis_off()
        fig.tight_layout()
        outputs += _save_map(fig, out / "map01_persistent_exposure")
        plt.close(fig)
        manifest.append({"MAP_ID": "M01", "TITLE": "Persistent exposure", "VARIABLE": persistence_col, "QUESTION": "Which EDs repeatedly appear among the most exposed across the modelled future envelope?"})

    # 2. Comparable pathway maps of production-value exposure.
    exposure_col = "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if exposure_col in joined.columns:
        values = pd.to_numeric(joined.loc[joined["STUDY_ALLOCATION_POLICY"].eq("PRORATA"), exposure_col], errors="coerce")
        vmax = float(values.max()) if values.notna().any() else 1.0
        fig = _panel_map(joined, column=exposure_col, title="Gross livestock Standard Output exposure", cmap="magma", vmin=0.0, vmax=max(vmax, 1e-9), legend_label="% of baseline livestock SO")
        outputs += _save_map(fig, out / "map02_standard_output_exposure")
        _map_style().close(fig)
        manifest.append({"MAP_ID": "M02", "TITLE": "Standard Output exposure", "VARIABLE": exposure_col, "QUESTION": "Where does production-value exposure fall under each national pathway?"})

    # 3. Signed protection redistribution in the ambitious pathway.
    relief = "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    burden = "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"
    if relief in joined.columns and burden in joined.columns:
        block = joined.loc[
            joined["STUDY_SCENARIO_ID"].eq("ALL_GAS_NZ")
            & ~joined["STUDY_ALLOCATION_POLICY"].eq("PRORATA")
        ].copy()
        block["SIGNED_SO_REDISTRIBUTION_PCT"] = pd.to_numeric(block[burden], errors="coerce").fillna(0.0) - pd.to_numeric(block[relief], errors="coerce").fillna(0.0)
        rules = [r for r in ("DAIRY_PROTECTION", "ECONOMIC_CAPACITY_PROTECTION", "SOCIAL_VULNERABILITY_PROTECTION") if (block["STUDY_ALLOCATION_POLICY"] == r).any()]
        if rules:
            plt = _map_style()
            fig, axes = plt.subplots(1, len(rules), figsize=(12.8, 5.0))
            axes = np.atleast_1d(axes)
            vmax = float(np.nanmax(np.abs(pd.to_numeric(block["SIGNED_SO_REDISTRIBUTION_PCT"], errors="coerce"))))
            vmax = max(vmax, 1e-9)
            for ax, rule in zip(axes, rules):
                b = block.loc[block["STUDY_ALLOCATION_POLICY"].eq(rule)]
                b.plot(column="SIGNED_SO_REDISTRIBUTION_PCT", ax=ax, cmap="RdBu_r", vmin=-vmax, vmax=vmax, linewidth=0.10, edgecolor="white", legend=True, legend_kwds={"shrink": 0.64, "label": "percentage-point change from PRORATA"})
                ax.set_title(RULE_LABELS.get(rule, rule))
                ax.set_axis_off()
            fig.suptitle("Protection relief and displaced production-value exposure\nAll-gas NZ", y=0.99)
            fig.tight_layout()
            outputs += _save_map(fig, out / "map03_protection_redistribution")
            plt.close(fig)
            manifest.append({"MAP_ID": "M03", "TITLE": "Protection redistribution", "VARIABLE": "burden - relief vs PRORATA", "QUESTION": "Where does protection reduce exposure and where is the displaced adjustment absorbed?"})

    # 4. Bivariate transition conditions.
    fig, opportunity_label = _bivariate_exposure_opportunity(joined)
    if fig is not None:
        outputs += _save_map(fig, out / "map04_exposure_opportunity")
        _map_style().close(fig)
        manifest.append({"MAP_ID": "M04", "TITLE": "Exposure-opportunity transition conditions", "VARIABLE": f"SO exposure x {opportunity_label} eligibility", "QUESTION": "Do highly exposed EDs also possess released-land opportunity for the alternative pathway?"})

    # 5. Pathway uptake of released land.
    uptake = "ALTERNATIVE_USE_UPTAKE_PCT_OF_RELEASE"
    if uptake in joined.columns:
        fig = _panel_map(joined, column=uptake, title="Pathway uptake of released livestock land", cmap="viridis", vmin=0.0, vmax=100.0, legend_label="realised alternative use / released land (%)")
        outputs += _save_map(fig, out / "map05_alternative_use_uptake")
        _map_style().close(fig)
        manifest.append({"MAP_ID": "M05", "TITLE": "Alternative-use uptake", "VARIABLE": uptake, "QUESTION": "Where does the pathway actually mobilise the land released by livestock adjustment?"})

    # 6. Final residual released land.
    residual = "FINAL_UNALLOCATED_PCT_OF_RELEASE"
    if residual in joined.columns:
        fig = _panel_map(joined, column=residual, title="Final unallocated released livestock land", cmap="cividis", vmin=0.0, vmax=100.0, legend_label="final unallocated / released land (%)")
        outputs += _save_map(fig, out / "map06_final_unallocated_land")
        _map_style().close(fig)
        manifest.append({"MAP_ID": "M06", "TITLE": "Final unallocated released land", "VARIABLE": residual, "QUESTION": "Where does the pathway release land that remains unused after feasible Stage A allocation and rewetting?"})

    return outputs, pd.DataFrame(manifest)


def export_maps(
    results: str | Path,
    *,
    geometry: str | Path | None = None,
    geometry_key: str | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    output_dir: str | Path | None = None,
    generate_static_maps: bool = True,
) -> dict[str, Path]:
    """Build a reproducible ED geometry package and optional static map suite."""
    gpd = _gpd()
    map_csv = _resolve_map_csv(results)
    map_data = pd.read_csv(map_csv, low_memory=False)
    required = {"STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY", "CSOED"}
    missing = sorted(required - set(map_data.columns))
    if missing:
        raise ValueError(f"map-ready table missing columns: {missing}")

    geometry_path = resolve_geometry_path(config_path=config_path, geometry=geometry)
    model_geometry, detected_key = prepare_model_geometry(map_data, geometry_path, geometry_key=geometry_key)
    joined = build_joined_map_layer(map_data, model_geometry)

    out = Path(output_dir).resolve() if output_dir is not None else map_csv.parent / "maps"
    out.mkdir(parents=True, exist_ok=True)

    frozen_geometry = out / "GOBLIN_Spatial_Model_ED_Geometry.gpkg"
    model_geometry.to_file(frozen_geometry, layer="model_ed_geometry", driver="GPKG")

    joined_gpkg = out / "GOBLIN_Spatial_Map_Layer.gpkg"
    joined.to_file(joined_gpkg, layer="transition_conditions", driver="GPKG")

    figure_paths: list[Path] = []
    manifest = pd.DataFrame(columns=["MAP_ID", "TITLE", "VARIABLE", "QUESTION"])
    if generate_static_maps:
        figure_paths, manifest = generate_core_maps(joined, out)
    manifest["GEOMETRY_SOURCE"] = str(geometry_path)
    manifest["GEOMETRY_KEY"] = detected_key
    manifest["MAP_REPORTING_VERSION"] = MAP_REPORTING_VERSION
    manifest_path = out / "GOBLIN_Spatial_Map_Manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    outputs = {
        "frozen_geometry": frozen_geometry,
        "joined_map_layer": joined_gpkg,
        "map_manifest": manifest_path,
        "map_directory": out,
    }
    if figure_paths:
        outputs["first_map"] = figure_paths[0]
    return outputs