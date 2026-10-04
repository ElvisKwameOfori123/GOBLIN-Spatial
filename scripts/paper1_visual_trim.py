#!/usr/bin/env python
"""Presentation-trimmed Paper 1 runner.

Main text:
  3.1 Table 2 only
  3.2 Figure 2: national history + follower composition + 2010-2020 census scatter
  3.3 Figure 3: one signature at Ireland, catchment and local ED scales
  3.4 Figure 4: ED incidence map + displacement-by-scale bars

This is a presentation-only follow-up to paper1_figures_final.py. It does not
change the historical baseline or scientific calculations.
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
import paper1_figures_final as legacy

EXPECTED_AUDIT = "47/47"


def f2_history(data, restructuring, pair, out, written):
    import matplotlib.pyplot as plt
    nat = data["national_year"].set_index("YEAR")
    fig = plt.figure(figsize=(base.FIG_W, 3.25), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, .85, 1.15])
    ax_a, ax_b, ax_c = [fig.add_subplot(gs[0, i]) for i in range(3)]

    for col, label, colour in [
        ("TOTAL_CATTLE", "Total cattle", base.C["total"]),
        ("dairy_cows", "Dairy cows", base.C["dairy"]),
        ("suckler_cows", "Suckler cows", base.C["suckler"]),
    ]:
        ax_a.plot(nat.index, 100 * nat[col] / nat.loc[2015, col], lw=1.55,
                  label=label, color=colour)
    ax_a.axvline(2020, color="#777777", lw=.6, ls="--")
    ax_a.set(xlabel="Year", ylabel="Index (2015 = 100)")
    ax_a.legend(loc="best")
    base.title(ax_a, "a", "National cattle structure")

    sel = nat.loc[[2015, 2020, 2025], ["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]]
    shares = 100 * sel.div(sel.sum(axis=1), axis=0)
    x = np.arange(3); bottom = np.zeros(3)
    for col, lab, colour in [
        ("DXD_FOLLOWERS", "DxD", base.C["dairy"]),
        ("DXB_FOLLOWERS", "DxB", base.C["dxb"]),
        ("BXB_FOLLOWERS", "BxB", base.C["suckler"]),
    ]:
        vals = shares[col].to_numpy(float)
        ax_b.bar(x, vals, bottom=bottom, width=.62, color=colour, label=lab)
        for xx, bot, val in zip(x, bottom, vals):
            if val >= 10:
                ax_b.text(xx, bot + val/2, f"{val:.0f}%", ha="center", va="center", fontsize=6)
        bottom += vals
    ax_b.set_xticks(x, ["2015", "2020", "2025"])
    ax_b.set(ylabel="Follower-origin share (%)", ylim=(0, 100))
    ax_b.legend(ncol=3, loc="upper center")
    base.title(ax_b, "b", "Follower-origin composition")

    q = restructuring.loc[~restructuring["ZERO_DAIRY_BOTH"]].copy()
    rho = base.spearman(q["CATTLE_CHANGE_PCT"], q["DS_CHANGE_PP"])
    ax_c.axvspan(-base.CONFIG["stable_herd_pct"], base.CONFIG["stable_herd_pct"], color="#f1f1f1", lw=0)
    ax_c.scatter(q["CATTLE_CHANGE_PCT"].clip(-60, 60), q["DS_CHANGE_PP"], s=4, color="#999999", alpha=.45, linewidths=0)
    hl = q.loc[q["STABLE_HERD_SHIFTED_SYSTEM"]]
    ax_c.scatter(hl["CATTLE_CHANGE_PCT"].clip(-60, 60), hl["DS_CHANGE_PP"], s=7, color=base.C["follower"], alpha=.8, linewidths=0,
                 label="stable herd, shifted system")
    rp = q.set_index("KEY")
    for tag, key, colour in [("A", pair["KEY_A"], base.C["dairy"]), ("B", pair["KEY_B"], base.C["suckler"])]:
        row = rp.loc[key]; xx = float(np.clip(row["CATTLE_CHANGE_PCT"], -60, 60)); yy = float(row["DS_CHANGE_PP"])
        ax_c.scatter([xx], [yy], s=28, color=colour, edgecolor="black", linewidth=.5, zorder=5)
        ax_c.annotate(f"{tag} {pair['ED_' + tag]}", (xx, yy), xytext=(5, 5), textcoords="offset points", fontsize=5.8)
    ax_c.axhline(0, color="#555555", lw=.5); ax_c.axvline(0, color="#555555", lw=.5)
    ax_c.set(xlim=(-62, 62), xlabel="Change in total cattle, 2010-2020 (%)", ylabel="Change in dairy share (pp)")
    ax_c.legend(loc="lower left", fontsize=5.7)
    base.title(ax_c, "c", f"Published-census restructuring (rho = {rho:.2f})")
    base.save(fig, out, "F2_historical_restructuring", written)


def _signature_frame(derived, geo, label):
    e20 = derived["e20"].copy(); e20["KEY"] = e20["CSOED"].map(legacy._canonical)
    eds = geo["ed"].copy(); legacy._assert_ed_base(eds, f"{label} geometry"); eds["KEY"] = eds["CSOED"].map(legacy._canonical)
    attrs = e20.drop(columns=["CSOED", "County"], errors="ignore")
    eds = eds.merge(attrs, on="KEY", how="left", validate="one_to_one")
    if eds["TOTAL_CATTLE"].isna().any():
        raise AssertionError(f"{label}: one or more EDs failed the model-data join")
    return eds


def _blackwater(derived, geo):
    import geopandas as gpd
    w20 = derived["wfd"].loc[derived["wfd"]["YEAR"] == 2020]
    match = w20.loc[w20["WFD_CATCHMENT"].astype(str).str.contains("Blackwater", case=False, na=False)]
    if len(match) != 1:
        raise AssertionError(f"Expected one Blackwater catchment, found {len(match)}")
    row = match.iloc[0]; cid = str(row["WFD_CATCHMENT_ID"])
    xw = geo["crosswalk"].loc[geo["crosswalk"]["WFD_CATCHMENT_ID"].astype(str) == cid, ["CSOED", "ED_CATCHMENT_WEIGHT"]].copy()
    xw["KEY"] = xw["CSOED"].map(legacy._canonical)
    majority = xw.loc[xw["ED_CATCHMENT_WEIGHT"] >= .5].copy()
    eds = _signature_frame(derived, geo, "Blackwater")
    z = eds.merge(majority[["KEY", "ED_CATCHMENT_WEIGHT"]], on="KEY", how="inner", validate="one_to_one")
    if len(z) != majority["KEY"].nunique():
        raise AssertionError("Blackwater: canonical-key join lost one or more majority-inside EDs")
    poly = geo["wfd_state"].loc[geo["wfd_state"]["WFD_CATCHMENT_ID"].astype(str) == cid].copy()
    z = gpd.clip(z, poly); z["WEIGHT"] = z["ADULT_COWS"] * z["ED_CATCHMENT_WEIGHT"]
    stats = {"WFD_CATCHMENT": row["WFD_CATCHMENT"], "N_ED": int(len(z)),
             "P10": legacy._weighted_quantile(z["FOLLOWERS_PER_COW_PLOT"], z["WEIGHT"], .10),
             "P50": legacy._weighted_quantile(z["FOLLOWERS_PER_COW_PLOT"], z["WEIGHT"], .50),
             "P90": legacy._weighted_quantile(z["FOLLOWERS_PER_COW_PLOT"], z["WEIGHT"], .90),
             "CATCHMENT_COEFFICIENT": float(row["FOLLOWERS_PER_ADULT_COW"]),
             "METRIC": "followers per adult cow", "WEIGHTING": "adult cows x ED catchment weight"}
    return z, poly, stats


def f3_multiscale(derived, geo, pair, out, written):
    import matplotlib.pyplot as plt
    eds = _signature_frame(derived, geo, "F3")
    bw, bw_poly, stats = _blackwater(derived, geo)
    cmap, norm = legacy._follower_cmap_norm()
    fig = plt.figure(figsize=(base.FIG_W, 3.85), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1, 1]); ax_a, ax_b, ax_c = [fig.add_subplot(gs[0, i]) for i in range(3)]
    base.choropleth(ax_a, eds, "FOLLOWERS_PER_COW_PLOT", cmap=cmap, norm=norm, outlines=[(geo["county"], base.C["county"], .18)])
    base.scale_bar(ax_a); base.title(ax_a, "a", "Ireland: ED livestock signature")
    base.choropleth(ax_b, bw, "FOLLOWERS_PER_COW_PLOT", cmap=cmap, norm=norm, lw=.12, outlines=[(bw_poly, "black", .75)])
    base.title(ax_b, "b", f"Blackwater WFD catchment\nP10-P90 {stats['P10']:.2f}-{stats['P90']:.2f}")
    case = eds.loc[eds["KEY"].isin([pair["KEY_A"], pair["KEY_B"]])].copy()
    if len(case) != 2:
        raise AssertionError("F3 local ED view: expected both case EDs")
    xmin, ymin, xmax, ymax = case.total_bounds; pad = 14000.; local = eds.cx[xmin-pad:xmax+pad, ymin-pad:ymax+pad].copy()
    base.choropleth(ax_c, local, "FOLLOWERS_PER_COW_PLOT", cmap=cmap, norm=norm, lw=.12)
    for tag, key in (("A", pair["KEY_A"]), ("B", pair["KEY_B"])):
        g = case.loc[case["KEY"] == key]; g.boundary.plot(ax=ax_c, color="black", linewidth=1.2); pt = g.geometry.iloc[0].representative_point()
        ax_c.text(pt.x, pt.y, tag, ha="center", va="center", fontsize=7, fontweight="bold", bbox=dict(facecolor="white", edgecolor="none", pad=.4))
    base.title(ax_c, "c", f"Local ED scale: {pair['ED_A']} / {pair['ED_B']}")
    base.colorbar(fig, [ax_a, ax_b, ax_c], cmap, norm, "Followers per adult cow", ticks=legacy.FOLLOWER_COEF_BREAKS, extend="max", shrink=.74)
    base.save(fig, out, "F3_multiscale_spatial_signatures", written)
    return stats


def f4_incidence(data, geo, out, written):
    import matplotlib.pyplot as plt
    yr = 2020; arm = "DAIRY_PARENT"
    ce = data["utility_comparison_ed"].loc[lambda d: (d["YEAR"] == yr) & (d["ARM"] == arm), ["CSOED", "DIFFERENCE_FOLLOWERS"]].copy(); ce["KEY"] = ce["CSOED"].map(legacy._canonical)
    e = geo["ed"].copy(); legacy._assert_ed_base(e, "F4 incidence geometry"); e["KEY"] = e["CSOED"].map(legacy._canonical)
    e = e.merge(ce[["KEY", "DIFFERENCE_FOLLOWERS"]], on="KEY", how="left", validate="one_to_one")
    if e["DIFFERENCE_FOLLOWERS"].isna().any(): raise AssertionError("F4: one or more EDs failed the utility join")
    fig = plt.figure(figsize=(base.FIG_W, 3.8), constrained_layout=True); gs = fig.add_gridspec(1, 2, width_ratios=[1.25, .85]); ax_a, ax_b = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    norm = base.diverging_norm(e["DIFFERENCE_FOLLOWERS"]); base.choropleth(ax_a, e, "DIFFERENCE_FOLLOWERS", cmap=base.DIVERGING, norm=norm, outlines=[(geo["county"], base.C["county"], .18)])
    base.scale_bar(ax_a); base.colorbar(fig, ax_a, base.DIVERGING, norm, "signature minus headcount attribution (followers per ED)", extend="both", shrink=.8)
    base.title(ax_a, "a", "Illustrative 30% dairy-cow reduction: ED incidence")
    d = data["utility_displacement"].loc[lambda d: (d["YEAR"] == yr) & (d["QUANTITY"] == "FOLLOWERS")].set_index("ARM"); r = d.loc[arm]; nat = abs(r["NATIONAL_CHANGE"])
    ratio = 100*r["ED_RATIO_COMPONENT"]/nat; parent = 100*r["ED_RECEIVER_COMPONENT"]/nat; county = 100*r["COUNTY_TOTAL_DISPLACEMENT"]/nat; wfd = 100*r["WFD_TOTAL_DISPLACEMENT"]/nat
    ax_b.bar(0, ratio, color=base.C["dairy"], width=.58, label="ratio component"); ax_b.bar(0, parent, bottom=ratio, color=base.C["dairy"], alpha=.45, hatch="////", edgecolor="white", width=.58, label="parent-absent component"); ax_b.bar([1, 2], [county, wfd], color=base.C["dairy"], width=.58)
    for xx, vv in zip([0, 1, 2], [ratio+parent, county, wfd]): ax_b.text(xx, vv+.35, f"{vv:.1f}%", ha="center", fontsize=6.6)
    ax_b.set_xticks([0, 1, 2], ["ED", "County", "WFD\ncatchment"]); ax_b.set_ylabel("Misattributed followers\n(% of national change)"); ax_b.legend(loc="upper right", fontsize=6)
    base.title(ax_b, "b", "Spatial mismatch falls with aggregation")
    base.save(fig, out, "F4_spatial_transition_incidence", written)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", default="."); args = parser.parse_args(); root = Path(args.root).resolve(); sys.path.insert(0, str(root/"src")); out = root/base.CONFIG["output_dir"]
    for sub in ("figures", "tables", "maps"): (out/sub).mkdir(parents=True, exist_ok=True)
    base.style(); data = base.load(root)
    if data.get("audit_pass") != EXPECTED_AUDIT: raise AssertionError(f"Expected live coherence audit {EXPECTED_AUDIT}; found {data.get('audit_pass')}")
    geo = base.geometry(root, data["ed_year"]); derived = base.derive(data); model_keys = set(data["ed_year"]["CSOED"].map(legacy._canonical)); p = base.observed_restructuring(root, data, model_keys); pair = legacy.select_case_pair(data, p, derived); written=[]
    print(f"Case pair: {pair['ED_A']} / {pair['ED_B']} ({pair['County']})")
    f2_history(data, p, pair, out, written); bw = f3_multiscale(derived, geo, pair, out, written); f4_incidence(data, geo, out, written)
    spread = legacy.catchment_spread(derived, geo); tabs = base.tables(data, derived, p, spread); tabs["T2_validation"] = legacy.build_table2(root, data); tabs["T3_national_change"] = legacy.build_table3(data, derived)
    tabs["S10_catchment_signatures_2020"] = legacy.build_table5(derived, spread); tabs.pop("T5_catchment_signatures_2020", None)
    if "T4_system_typology_2020" in tabs: tabs["S9_system_typology_2020"] = tabs.pop("T4_system_typology_2020")
    if "T6_illustrative_displacement" in tabs:
        d = tabs.pop("T6_illustrative_displacement").rename(columns={"RECEIVER_SHARE_OF_ED_PCT":"PARENT_ABSENT_SHARE_OF_ED_PCT", "PARENTLESS_EDS_WITH_FOLLOWERS":"PARENT_ABSENT_EDS_WITH_FOLLOWERS"}); tabs["T4_illustrative_displacement"] = d
    tabs["MAIN_case_pair"] = pd.DataFrame([pair]); tabs["MAIN_blackwater_spread"] = pd.DataFrame([bw]); base.write_tables(tabs, out, written)
    manifest = {"package":"GOBLIN_SPATIAL_PAPER1_VISUAL_TRIM", "created_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"), "repository":base.git_info(root), "coherence_audit":data["audit_pass"], "case_pair":pair, "blackwater_spread":bw, "architecture":["3.1 Table 2 only", "3.2 Figure 2 + Table 3", "3.3 Figure 3 Ireland/catchment/local ED", "3.4 Figure 4 + Table 4"], "files":{str(x.relative_to(out)):base.sha(x) for x in written if x.exists()}}
    (out/"paper1_manifest_visual_trim.json").write_text(json.dumps(manifest, indent=2, default=str)+"\n", encoding="utf-8")
    print(f"Done: {out}"); return 0


if __name__ == "__main__": raise SystemExit(main())
