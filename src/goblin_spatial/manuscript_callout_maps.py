"""Named ED/county callout maps for the final manuscript.

These renderers are downstream presentation only.  They use the frozen
``transition_conditions`` results and the frozen ED geometry.  Numbered map
markers are accompanied by a comparison panel naming the Electoral Division and
county and reporting how the same place changes across pathways or allocation
principles.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.map_reporting import build_joined_map_layer, prepare_model_geometry
from goblin_spatial import manuscript_package as mp


def _normalise_ids(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    x["CSOED"] = x["CSOED"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.lstrip("0")
    x["CSOED"] = x["CSOED"].mask(x["CSOED"].eq(""), "0")
    return x


def _joined(conditions: pd.DataFrame, names: pd.DataFrame, geometry_path: Path):
    data = _normalise_ids(conditions)
    names = _normalise_ids(names)
    data = data.merge(names[["CSOED", "EDNAME", "County"]], on="CSOED", how="left", suffixes=("", "_NAME"), validate="many_to_one")
    model_geometry, _ = prepare_model_geometry(data, geometry_path)
    return build_joined_map_layer(data, model_geometry)


def _county_boundaries(block, ax):
    try:
        county_col = "County" if "County" in block.columns else "County_NAME"
        block.dissolve(by=county_col).boundary.plot(ax=ax, linewidth=0.32, edgecolor="#444444")
    except Exception:
        pass


def _callout_text_exposure(callouts: pd.DataFrame) -> str:
    lines = ["NUMBERED CALLOUTS", ""]
    for _, r in callouts.iterrows():
        name = str(r.get("EDNAME", r.get("CSOED", "")))
        county = str(r.get("County", ""))
        lines.extend([
            f"{int(r['CALLOUT'])}. {name}, {county}",
            f"   {r['CALLOUT_REASON']}",
            f"   BE-SG: {float(r['BE_PCT']):.1f}%   |   All-gas NZ: {float(r['ALL_PCT']):.1f}%",
            f"   rank shift: {100.0 * float(r['RANK_SHIFT']):+.1f} percentile points",
            "",
        ])
    return "\n".join(lines)


def _callout_text_redistribution(callouts: pd.DataFrame) -> str:
    lines = ["SAME EDs ACROSS THREE POLICIES", ""]
    for _, r in callouts.iterrows():
        name = str(r.get("EDNAME", r.get("CSOED", "")))
        county = str(r.get("County", ""))
        lines.extend([
            f"{int(r['CALLOUT'])}. {name}, {county}",
            f"   {r['CALLOUT_REASON']}",
            f"   Dairy: {float(r['DAIRY_DELTA_SO_PCT']):+.1f}% SO | {float(r['DAIRY_DELTA_RELEASE_HA']):+.0f} ha land",
            f"   Economic: {float(r['ECONOMIC_DELTA_SO_PCT']):+.1f}% SO | {float(r['ECONOMIC_DELTA_RELEASE_HA']):+.0f} ha land",
            f"   Social: {float(r['SOCIAL_DELTA_SO_PCT']):+.1f}% SO | {float(r['SOCIAL_DELTA_RELEASE_HA']):+.0f} ha land",
            "",
        ])
    return "\n".join(lines)


def render_named_callout_maps(
    tables: dict[str, pd.DataFrame],
    *,
    project_root: Path,
    geometry_path: Path,
    output_dir: Path,
) -> tuple[list[Path], dict[str, pd.DataFrame]]:
    """Render manuscript Figures 3 and 5 with named ED/county comparison callouts."""
    plt = mp._setup()
    import matplotlib as mpl

    output_dir.mkdir(parents=True, exist_ok=True)
    conditions = tables["transition_conditions"].copy()
    names = mp._baseline_names(project_root)
    conditions_norm = _normalise_ids(conditions)
    callout_names = _normalise_ids(names)
    joined = _joined(conditions, names, geometry_path)

    exposure_callouts = mp._select_exposure_callouts(conditions_norm, callout_names)
    redistribution_callouts = mp._select_redistribution_callouts(conditions_norm, callout_names)
    outputs: list[Path] = []

    # Figure 3: two pathway maps plus an explicit named comparison panel.
    fig = plt.figure(figsize=(15.4, 6.1), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.12])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    note_ax = fig.add_subplot(gs[0, 2]); note_ax.set_axis_off()
    blocks = []
    for s in mp.MAIN_SCENARIOS:
        block = joined.loc[
            joined["STUDY_SCENARIO_ID"].astype(str).eq(s)
            & joined["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
        ].copy()
        blocks.append(block)
    pooled = np.concatenate([
        pd.to_numeric(b["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"], errors="coerce").dropna().to_numpy(float)
        for b in blocks
    ])
    vmax = max(float(np.nanquantile(pooled, 0.98)), 1e-9)
    for ax, s, block in zip(axes, mp.MAIN_SCENARIOS, blocks):
        block.plot(
            column="SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", ax=ax, cmap="viridis",
            vmin=0.0, vmax=vmax, linewidth=0.04, edgecolor="white",
        )
        _county_boundaries(block, ax)
        mp._annotate_numbers(ax, block, exposure_callouts)
        ax.set_axis_off(); ax.set_title(mp.SCENARIO_LABELS[s])
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(0.0, vmax), cmap="viridis")
    cb = fig.colorbar(sm, ax=axes, shrink=0.76, pad=0.01)
    cb.set_label("Gross livestock production-value exposure (% of ED baseline SO)")
    note_ax.text(0.0, 1.0, _callout_text_exposure(exposure_callouts), va="top", ha="left", fontsize=8.2, linespacing=1.32)
    fig.suptitle("Figure 3. Pathway composition changes the geography of production-value exposure", fontsize=12.5, fontweight="bold")
    outputs += mp._save(fig, output_dir / "Fig03_exposure_geography")
    plt.close(fig)

    # Figure 5: the same named places are tracked across all protection maps,
    # then connected to the released-land movement in a common scatter.
    fig = plt.figure(figsize=(16.8, 10.1), constrained_layout=True)
    gs = fig.add_gridspec(2, 4, height_ratios=[1.15, 0.88], width_ratios=[1, 1, 1, 1.13])
    map_axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    note_ax = fig.add_subplot(gs[0, 3]); note_ax.set_axis_off()
    scatter_ax = fig.add_subplot(gs[1, :])

    map_blocks = []
    pooled_delta = []
    for rule in mp.PROTECTION_RULES:
        block = joined.loc[
            joined["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
            & joined["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ].copy()
        signed = pd.to_numeric(block["SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR"], errors="coerce").fillna(0.0).to_numpy(float)
        base_so = pd.to_numeric(block["BASE_SO_LIVESTOCK_2020_EUR"], errors="coerce").fillna(0.0).to_numpy(float)
        block["DELTA_SO_PCT"] = np.divide(100.0 * signed, base_so, out=np.zeros(len(block)), where=base_so > 0)
        map_blocks.append((rule, block)); pooled_delta.extend(block["DELTA_SO_PCT"].tolist())
    limit = max(float(np.nanquantile(np.abs(np.asarray(pooled_delta, dtype=float)), 0.98)), 1e-9)
    norm = mpl.colors.TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    for ax, (rule, block) in zip(map_axes, map_blocks):
        block.plot(column="DELTA_SO_PCT", ax=ax, cmap="coolwarm", norm=norm, linewidth=0.04, edgecolor="white")
        _county_boundaries(block, ax)
        mp._annotate_numbers(ax, block, redistribution_callouts)
        ax.set_axis_off(); ax.set_title(mp.RULE_LABELS[rule])
    sm = mpl.cm.ScalarMappable(norm=norm, cmap="coolwarm")
    cb = fig.colorbar(sm, ax=map_axes, shrink=0.74, pad=0.01)
    cb.set_label("Change in gross SO exposure vs proportional (% of ED baseline SO)")
    note_ax.text(0.0, 1.0, _callout_text_redistribution(redistribution_callouts), va="top", ha="left", fontsize=7.7, linespacing=1.24)

    for rule, block in map_blocks:
        x = block["DELTA_SO_PCT"].to_numpy(float)
        delta_land = pd.to_numeric(block["SIGNED_DIFFERENCE_FROM_PRORATA_GOBLIN_RELEASED_GRASSLAND_HA"], errors="coerce").fillna(0.0).to_numpy(float)
        if "ALL_GRASSLAND" not in block.columns:
            raise ValueError("transition conditions require ALL_GRASSLAND for released-land coupling normalisation")
        grass = pd.to_numeric(block["ALL_GRASSLAND"], errors="coerce").fillna(0.0).to_numpy(float)
        y = np.divide(100.0 * delta_land, grass, out=np.zeros(len(block)), where=grass > 0)
        scatter_ax.scatter(x, y, s=8, alpha=0.20, label=mp.RULE_LABELS[rule])
        for _, c in redistribution_callouts.iterrows():
            hit = block.loc[block["CSOED"].astype(str).eq(str(c["CSOED"]))]
            if hit.empty:
                continue
            i = hit.index[0]
            xx = float(hit["DELTA_SO_PCT"].iloc[0])
            dl = float(pd.to_numeric(hit["SIGNED_DIFFERENCE_FROM_PRORATA_GOBLIN_RELEASED_GRASSLAND_HA"], errors="coerce").iloc[0])
            gh = float(pd.to_numeric(hit["ALL_GRASSLAND"], errors="coerce").iloc[0])
            yy = 100.0 * dl / gh if gh > 0 else 0.0
            scatter_ax.scatter([xx], [yy], s=42, facecolors="white", edgecolors="black", linewidths=0.8, zorder=5)
            scatter_ax.text(xx, yy, str(int(c["CALLOUT"])), ha="center", va="center", fontsize=6.4, fontweight="bold", zorder=6)
    scatter_ax.axhline(0, color="#444444", linewidth=0.7); scatter_ax.axvline(0, color="#444444", linewidth=0.7)
    scatter_ax.set_xlabel("Change in production-value exposure relative to proportional allocation (% of ED baseline SO)")
    scatter_ax.set_ylabel("Change in released land relative to ED baseline grassland (%)")
    scatter_ax.legend(ncol=3, loc="upper center", fontsize=7.2)
    scatter_ax.set_title("Coupling test: burden movement versus released-land movement", loc="left", fontweight="bold")
    fig.suptitle("Figure 5. Where protection moves agricultural burden and released land under All-gas NZ", fontsize=12.5, fontweight="bold")
    outputs += mp._save(fig, output_dir / "Fig05_redistribution_geography")
    plt.close(fig)

    return outputs, {
        "Fig03_callouts": exposure_callouts,
        "Fig05_callouts": redistribution_callouts,
    }
