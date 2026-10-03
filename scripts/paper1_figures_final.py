#!/usr/bin/env python
"""Final Paper 1 figure set for the four-section Results architecture.

This is a presentation-only overlay on scripts/paper1_figures.py. It reuses the
frozen build loaders, geometry and tables, but replaces the main-text visuals
that were still tied to the provisional typology/R_B layout.

Main text:
  3.1 Table 2 only (validation diagnostics are supplementary)
  3.2 F2 national restructuring + F4 observed 2010/2020 local restructuring
  3.3 F3 ED parent-to-cohort signatures + F5 Blackwater catchment zoom
  3.4 F6 follower-head transition incidence

Run after the historical release build:
    python scripts/build_historical_release.py
    python scripts/paper1_figures_final.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import paper1_figures as base

CASE_CATCHMENT = "Blackwater (Munster)"


def select_case_pair(data: dict, restructuring: pd.DataFrame) -> dict:
    from goblin_spatial.preparation.census_suppression import canonical_key
    r = restructuring.set_index("KEY")
    rows = []
    for _, x in data["matched_pairs_2020"].iterrows():
        a, b = canonical_key(x["CSOED_A"]), canonical_key(x["CSOED_B"])
        if a not in r.index or b not in r.index:
            continue
        ra, rb = r.loc[a], r.loc[b]
        if max(abs(float(ra["DS_CHANGE_PP"])), abs(float(rb["DS_CHANGE_PP"]))) < base.CONFIG["material_shift_pp"]:
            continue
        rows.append({
            "County": x["County"], "ED_A": x["ED_A"], "ED_B": x["ED_B"],
            "CSOED_A": str(x["CSOED_A"]), "CSOED_B": str(x["CSOED_B"]),
            "KEY_A": a, "KEY_B": b,
            "SIGNATURE_DISTANCE": float(x["SIGNATURE_DISTANCE"]),
            "CATTLE_GAP_PCT_PAIR_MEAN": float(x["CATTLE_GAP_PCT_PAIR_MEAN"]),
        })
    if not rows:
        raise AssertionError("No matched ED pair satisfies the published-cell/material-shift rule")
    return pd.DataFrame(rows).sort_values(
        ["SIGNATURE_DISTANCE", "CATTLE_GAP_PCT_PAIR_MEAN"], ascending=[False, True]
    ).iloc[0].to_dict()


def dorling(gdf, size_col: str, iterations: int = 100):
    from scipy.spatial import cKDTree
    pts = np.column_stack([gdf.geometry.centroid.x, gdf.geometry.centroid.y]).astype(float)
    origin = pts.copy()
    size = pd.to_numeric(gdf[size_col], errors="coerce").fillna(0).clip(lower=0).to_numpy(float)
    r = np.sqrt(size / np.pi)
    target = 0.45 * float(gdf.geometry.area.sum())
    r *= np.sqrt(target / max(np.pi * (r ** 2).sum(), 1.0))
    rmax = float(r.max())
    for _ in range(iterations):
        pairs = cKDTree(pts).query_pairs(2 * rmax, output_type="ndarray")
        if len(pairs):
            i, j = pairs[:, 0], pairs[:, 1]
            d = pts[j] - pts[i]
            dist = np.hypot(d[:, 0], d[:, 1]) + 1e-9
            overlap = r[i] + r[j] - dist
            hit = overlap > 0
            if hit.any():
                i, j, d, dist, overlap = i[hit], j[hit], d[hit], dist[hit], overlap[hit]
                step = (overlap / dist)[:, None] * d * 0.5
                move = np.zeros_like(pts)
                np.add.at(move, i, -step)
                np.add.at(move, j, step)
                pts += move
        pts += 0.05 * (origin - pts)
    return pts, r


def f3_signatures(derived, geo, pair, out, written):
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Circle

    e20 = derived["e20"].copy()
    eds = geo["ed"].merge(e20, on=["CSOED", "County"], how="left", suffixes=("", "_y"))
    coef = "FOLLOWERS_PER_COW_PLOT"
    vals = pd.to_numeric(eds[coef], errors="coerce")
    vmax = float(vals.dropna().quantile(0.97))
    cmap = base.classed_cmap(base.C["follower"], 8)
    norm = mcolors.Normalize(0, vmax)

    fig = plt.figure(figsize=(base.FIG_W, 6.1), constrained_layout=True)
    gs = fig.add_gridspec(2, 6, height_ratios=[1.25, 0.75])
    ax_a, ax_b = fig.add_subplot(gs[0, :3]), fig.add_subplot(gs[0, 3:])
    ax_c, ax_d, ax_e = [fig.add_subplot(gs[1, i:i+2]) for i in (0, 2, 4)]

    base.choropleth(ax_a, eds, coef, cmap=cmap, norm=norm,
                    outlines=[(geo["county"], base.C["county"], 0.25)])
    base.scale_bar(ax_a)
    base.colorbar(fig, ax_a, cmap, norm, "Followers per adult cow", extend="max")
    base.title(ax_a, "a", "ED area: parent-to-cohort coefficient")

    pts, rad = dorling(eds, "TOTAL_CATTLE")
    geo["ireland"].plot(ax=ax_b, color="#f4f4f4", edgecolor="#c8c8c8", linewidth=0.3)
    colours = [cmap(norm(v)) if np.isfinite(v) else base.C["nodata"] for v in vals.to_numpy(float)]
    order = np.argsort(-rad)
    ax_b.add_collection(PatchCollection([Circle(tuple(pts[k]), rad[k]) for k in order],
                                         facecolor=[colours[k] for k in order], edgecolor="white", linewidth=0.08))
    base.map_axes(ax_b)
    base.title(ax_b, "b", "Animal-weighted cartogram (circle area = cattle)")

    ids = [str(pair["CSOED_A"]), str(pair["CSOED_B"])]
    pp = e20.set_index(e20["CSOED"].astype(str)).reindex(ids)
    labs = [f"A  {pair['ED_A']}", f"B  {pair['ED_B']}"]
    panels = [
        (ax_c, "DAIRY_SHARE_ADULT_PCT", "Dairy share of adult cows", "%", base.C["dairy"], "Census"),
        (ax_d, "FOLLOWER_TO_ADULT_RATIO", "Followers per adult cow", "ratio", base.C["follower"], "Census"),
        (ax_e, "DXB_SHARE_FOLLOWERS_PCT", "DxB share of followers", "%", base.C["dxb"], "AIM/GOBLIN-informed"),
    ]
    for letter, (ax, col, ttl, unit, colour, source) in zip("cde", panels):
        y = pp[col].astype(float).to_numpy()
        bars = ax.bar(labs, y, color=colour, width=0.58)
        for bar, v in zip(bars, y):
            ax.text(bar.get_x() + bar.get_width()/2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=6.4)
        ax.set_ylabel(unit)
        ax.tick_params(axis="x", labelrotation=18)
        ax.text(0.02, 0.96, source, transform=ax.transAxes, va="top", fontsize=6.2, color="#555555")
        base.title(ax, letter, ttl)
    base.save(fig, out, "F3_spatial_livestock_signatures", written)


def f4_restructuring(restructuring, geo, pair, out, written):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from goblin_spatial.preparation.census_suppression import canonical_key

    p = restructuring.copy()
    eds = geo["ed"].copy()
    eds["KEY"] = eds["CSOED"].map(canonical_key)
    eds = eds.merge(p[["KEY", "RELATIVE_PP", "STABLE_HERD_SHIFTED_SYSTEM"]], on="KEY", how="left")
    fig = plt.figure(figsize=(base.FIG_W, 6.3), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 0.75])
    ax_a, ax_b, ax_c = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])

    norm = base.diverging_norm(p["RELATIVE_PP"])
    shifted = eds.loc[eds["STABLE_HERD_SHIFTED_SYSTEM"] == True]
    base.choropleth(ax_a, eds, "RELATIVE_PP", cmap=base.DIVERGING, norm=norm,
                    outlines=[(geo["county"], base.C["county"], 0.25), (shifted, "black", 0.5)])
    ax_a.legend(handles=[Line2D([], [], color="black", lw=0.8, label="stable herd, shifted system")], loc="lower left")
    base.colorbar(fig, ax_a, base.DIVERGING, norm, "ED minus county change in dairy share, 2010-2020 (pp)", extend="both")
    base.title(ax_a, "a", "Local departures from the county trend")

    q = p.loc[~p["ZERO_DAIRY_BOTH"]]
    ax_b.axvspan(-base.CONFIG["stable_herd_pct"], base.CONFIG["stable_herd_pct"], color="#f3f3f3", lw=0)
    ax_b.scatter(q["CATTLE_CHANGE_PCT"].clip(-60, 60), q["DS_CHANGE_PP"], s=3, color="#999999", alpha=0.5)
    hl = q.loc[q["STABLE_HERD_SHIFTED_SYSTEM"]]
    ax_b.scatter(hl["CATTLE_CHANGE_PCT"], hl["DS_CHANGE_PP"], s=6, color=base.C["follower"])
    ax_b.axhline(0, color="#555", lw=0.5)
    ax_b.axvline(0, color="#555", lw=0.5)
    ax_b.set(xlim=(-62, 62), xlabel="Change in total cattle, 2010-2020 (%)", ylabel="Change in dairy share (pp)")
    base.title(ax_b, "b", "Herd size and herd system changed separately")

    rp = p.set_index("KEY").reindex([pair["KEY_A"], pair["KEY_B"]])
    for tag, row, colour, marker in zip(("A", "B"), rp.itertuples(), (base.C["dairy"], base.C["suckler"]), ("o", "s")):
        yy = [row.DS10, row.DS20]
        ax_c.plot([2010, 2020], yy, marker=marker, lw=1.5, color=colour, label=f"{tag} {pair['ED_'+tag]}")
        for x, y, n in zip((2010, 2020), yy, (row.T10, row.T20)):
            ax_c.annotate(f"{int(round(n)):,} cattle", (x, y), xytext=(4, 5), textcoords="offset points", fontsize=6)
    ax_c.set(xticks=[2010, 2020], ylim=(0, 100), ylabel="Dairy share of adult cows (%)")
    ax_c.legend()
    base.title(ax_c, "c", f"Matched pair, {pair['County']}: census observations only")
    base.save(fig, out, "F4_local_restructuring_2010_2020", written)


def catchment_spread(derived, geo):
    xw = geo["crosswalk"][["CSOED", "WFD_CATCHMENT_ID", "ED_CATCHMENT_WEIGHT"]]
    e = derived["e20"][["CSOED", "DAIRY_SHARE_PLOT", "ADULT_COWS"]].merge(xw, on="CSOED")
    e = e.loc[e["DAIRY_SHARE_PLOT"].notna() & (e["ED_CATCHMENT_WEIGHT"] >= 0.5)]
    def wq(g, q):
        g = g.sort_values("DAIRY_SHARE_PLOT")
        c = (g["ADULT_COWS"] * g["ED_CATCHMENT_WEIGHT"]).cumsum()
        return float(np.interp(q * c.iloc[-1], c, g["DAIRY_SHARE_PLOT"]))
    return e.groupby("WFD_CATCHMENT_ID").apply(
        lambda g: pd.Series({"P10": wq(g, .1), "P90": wq(g, .9), "N": len(g)}), include_groups=False
    ).reset_index()


def f5_blackwater(derived, geo, out, written):
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    w20 = derived["wfd"].loc[derived["wfd"]["YEAR"] == base.CONFIG["base_year"]].copy()
    match = w20.loc[w20["WFD_CATCHMENT"].astype(str).str.contains("Blackwater", case=False, na=False)]
    if len(match) != 1:
        raise AssertionError(f"Expected one Blackwater catchment, found {len(match)}")
    row = match.iloc[0]
    cid = str(row["WFD_CATCHMENT_ID"])
    name = row["WFD_CATCHMENT"]
    catch_value = float(row["FOLLOWERS_PER_ADULT_COW"])
    xw = geo["crosswalk"].loc[geo["crosswalk"]["WFD_CATCHMENT_ID"].astype(str) == cid, ["CSOED", "ED_CATCHMENT_WEIGHT"]]
    z = geo["ed"].merge(derived["e20"], on=["CSOED", "County"], how="left", suffixes=("", "_y")).merge(xw, on="CSOED", how="inner")
    z = z.loc[z["ED_CATCHMENT_WEIGHT"] >= 0.5]
    poly = geo["wfd_state"].loc[geo["wfd_state"]["WFD_CATCHMENT_ID"].astype(str) == cid].copy()
    v = pd.to_numeric(z["FOLLOWERS_PER_COW_PLOT"], errors="coerce").dropna()
    stats = {"WFD_CATCHMENT": name, "N_ED": int(len(v)), "P10": float(v.quantile(.1)),
             "P50": float(v.quantile(.5)), "P90": float(v.quantile(.9)), "CATCHMENT_COEFFICIENT": catch_value}
    norm = mcolors.Normalize(0, max(float(v.quantile(.97)), catch_value))
    cmap = base.classed_cmap(base.C["follower"], 8)

    fig, axes = plt.subplots(1, 3, figsize=(base.FIG_W, 3.6), constrained_layout=True)
    poly["COEF"] = catch_value
    base.choropleth(axes[0], poly, "COEF", cmap=cmap, norm=norm, lw=0.4)
    base.title(axes[0], "a", f"GeoGOBLIN unit: {name}\n{catch_value:.2f} followers/adult cow")
    base.choropleth(axes[1], z, "FOLLOWERS_PER_COW_PLOT", cmap=cmap, norm=norm, lw=0.15,
                    outlines=[(poly, "black", 0.8)])
    base.title(axes[1], "b", "ED structure inside the same catchment")
    base.colorbar(fig, axes[:2], cmap, norm, "Followers per adult cow", extend="max", shrink=0.7)
    axes[2].hist(v, bins=18, color=base.C["follower"], edgecolor="white", linewidth=0.4)
    for x, ls in ((stats["P10"], ":"), (stats["P50"], "-"), (stats["P90"], ":")):
        axes[2].axvline(x, color="black", lw=0.8, ls=ls)
    axes[2].axvline(catch_value, color=base.C["total"], lw=1.2, ls="--", label="catchment value")
    axes[2].set(xlabel="Followers per adult cow", ylabel="EDs")
    axes[2].legend()
    base.title(axes[2], "c", f"Within-catchment spread: P10-P90 {stats['P10']:.2f}-{stats['P90']:.2f}")
    base.save(fig, out, "F5_blackwater_ed_catchment_signatures", written)
    return stats


def f6_incidence(data, geo, out, written):
    import matplotlib.pyplot as plt

    yr = base.CONFIG["perturbation_year"]
    ce = data["utility_comparison_ed"].loc[lambda d: d["YEAR"] == yr].copy()
    ce["CSOED"] = ce["CSOED"].astype(str)
    cw = data["utility_comparison_wfd"].loc[lambda d: d["YEAR"] == yr].copy()
    cw["WFD_CATCHMENT_ID"] = cw["WFD_CATCHMENT_ID"].astype(str)
    arms = [("DAIRY_PARENT", "30% fewer dairy cows", base.C["dairy"]),
            ("SUCKLER_PARENT", "30% fewer suckler cows", base.C["suckler"])]
    fig = plt.figure(figsize=(base.FIG_W, 7.4), constrained_layout=True)
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, .55])
    for j, (arm, label, _) in enumerate(arms):
        e = geo["ed"].merge(ce.loc[ce["ARM"] == arm, ["CSOED", "DIFFERENCE_FOLLOWERS"]], on="CSOED", how="left")
        ax = fig.add_subplot(gs[0, j])
        norm = base.diverging_norm(e["DIFFERENCE_FOLLOWERS"])
        base.choropleth(ax, e, "DIFFERENCE_FOLLOWERS", cmap=base.DIVERGING, norm=norm,
                        outlines=[(geo["county"], base.C["county"], .2)])
        base.colorbar(fig, ax, base.DIVERGING, norm, "signature minus headcount (followers/ED)", extend="both", shrink=.75)
        base.title(ax, "ab"[j], f"{label}: ED")
        wg = geo["wfd_state"].merge(cw.loc[cw["ARM"] == arm, ["WFD_CATCHMENT_ID", "WFD_CATCHMENT", "DIFFERENCE_FOLLOWERS"]],
                                    on=["WFD_CATCHMENT_ID", "WFD_CATCHMENT"], how="left")
        ax = fig.add_subplot(gs[1, j])
        norm = base.diverging_norm(wg["DIFFERENCE_FOLLOWERS"], q=1.0)
        base.choropleth(ax, wg, "DIFFERENCE_FOLLOWERS", cmap=base.DIVERGING, norm=norm, lw=.35)
        base.colorbar(fig, ax, base.DIVERGING, norm, "signature minus headcount (followers/catchment)", shrink=.75)
        base.title(ax, "cd"[j], f"{label}: WFD catchment")

    ax = fig.add_subplot(gs[2, :])
    d = data["utility_displacement"]
    d = d.loc[(d["YEAR"] == yr) & (d["QUANTITY"] == "FOLLOWERS")].set_index("ARM")
    cats = ["ED ratio", "ED parent-absent", "County", "WFD catchment"]
    width = .36
    for k, (arm, label, colour) in enumerate(arms):
        r = d.loc[arm]
        nat = abs(r["NATIONAL_CHANGE"])
        vals = [100*r["ED_RATIO_COMPONENT"]/nat, 100*r["ED_RECEIVER_COMPONENT"]/nat,
                100*r["COUNTY_TOTAL_DISPLACEMENT"]/nat, 100*r["WFD_TOTAL_DISPLACEMENT"]/nat]
        x = np.arange(4) + (k-.5)*width
        bars = ax.bar(x, vals, width, color=colour, label=label)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, v+.25, f"{v:.1f}%", ha="center", fontsize=6.4)
    ax.set_xticks(np.arange(4), cats)
    ax.set_ylabel("Misattributed followers (% of national change)")
    ax.legend(ncol=2)
    base.title(ax, "e", "Spatial mismatch falls with aggregation; ED mismatch has two components")
    base.save(fig, out, "F6_follower_spatial_transition_incidence", written)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root/"src"))
    out = root/base.CONFIG["output_dir"]
    for sub in ("figures", "tables", "maps"):
        (out/sub).mkdir(parents=True, exist_ok=True)
    base.style()
    data = base.load(root)
    geo = base.geometry(root, data["ed_year"])
    derived = base.derive(data)
    from goblin_spatial.preparation.census_suppression import canonical_key
    model_keys = set(data["ed_year"]["CSOED"].map(canonical_key))
    p = base.observed_restructuring(root, data, model_keys)
    pair = select_case_pair(data, p)
    written = []
    print(f"Case pair: {pair['ED_A']} / {pair['ED_B']} ({pair['County']})")

    base.f3_scale_time(data, geo, out, written)
    f4_restructuring(p, geo, pair, out, written)
    f3_signatures(derived, geo, pair, out, written)
    bw = f5_blackwater(derived, geo, out, written)
    f6_incidence(data, geo, out, written)

    spread = catchment_spread(derived, geo)
    tabs = base.tables(data, derived, p, spread)
    if "T4_system_typology_2020" in tabs:
        tabs["S9_system_typology_2020"] = tabs.pop("T4_system_typology_2020")
    tabs["MAIN_case_pair"] = pd.DataFrame([pair])
    tabs["MAIN_blackwater_spread"] = pd.DataFrame([bw])
    base.write_tables(tabs, out, written)
    base.write_layers(derived, geo, out, written)

    tp = base.temporal_points(root, model_keys, geo["crosswalk"])
    base.f2_validation(data, tp, out, written)
    for ext in ("png", "pdf"):
        src = out/"figures"/f"F2_validation.{ext}"
        dst = out/"figures"/f"S1_validation_diagnostics.{ext}"
        if src.exists():
            src.replace(dst)
            written[:] = [dst if x == src else x for x in written]

    manifest = {
        "package": "GOBLIN_SPATIAL_PAPER1_FINAL",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": base.git_info(root),
        "coherence_audit": data["audit_pass"],
        "case_pair": pair,
        "case_catchment": CASE_CATCHMENT,
        "blackwater_spread": bw,
        "architecture": ["3.1 Table 2 validation", "3.2 F2+F4 history", "3.3 F3+F5 signatures", "3.4 F6 incidence"],
        "files": {str(x.relative_to(out)): base.sha(x) for x in written if x.exists()},
    }
    (out/"paper1_manifest_final.json").write_text(json.dumps(manifest, indent=2, default=str)+"\n", encoding="utf-8")
    print(f"Done: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
