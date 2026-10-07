#!/usr/bin/env python
"""Final Paper 1 figures/tables for the four-section Results architecture.

Main text
---------
3.1 Table 2: model integrity and technical validation
3.2 Figure 2 + Figure 4: national and observed local restructuring
3.3 Figure 3 + Figure 5: ED livestock-system signatures and agricultural context
3.4 Figure 6: catchment accounting and within-catchment ED heterogeneity

Run after:
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
FOLLOWER_COEF_BREAKS = [0, 1, 1.5, 2, 2.5, 3, 4]
EXPECTED_EDS = 2857


def _canonical(value: object) -> str:
    from goblin_spatial.preparation.census_suppression import canonical_key
    return canonical_key(str(value))


def _assert_ed_base(frame: pd.DataFrame, label: str) -> None:
    if len(frame) != EXPECTED_EDS:
        raise AssertionError(f"{label}: expected {EXPECTED_EDS} ED rows, found {len(frame)}")
    if frame["CSOED"].astype(str).nunique() != EXPECTED_EDS:
        raise AssertionError(f"{label}: ED keys are not one-to-one")


def _follower_cmap_norm():
    import matplotlib.colors as mcolors
    cmap = base.classed_cmap(base.C["follower"], len(FOLLOWER_COEF_BREAKS))
    norm = mcolors.BoundaryNorm(FOLLOWER_COEF_BREAKS, cmap.N, extend="max")
    return cmap, norm


def _weighted_quantile(values: pd.Series, weights: pd.Series, q: float) -> float:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    w = pd.to_numeric(weights, errors="coerce").astype(float)
    ok = x.notna() & w.notna() & (w > 0)
    x, w = x[ok], w[ok]
    if x.empty:
        return np.nan
    order = np.argsort(x.to_numpy())
    xs, ws = x.to_numpy()[order], w.to_numpy()[order]
    c = np.cumsum(ws)
    return float(np.interp(q * c[-1], c, xs))


def select_case_pair(data: dict, restructuring: pd.DataFrame, derived: dict) -> dict:
    r = restructuring.set_index("KEY")
    e20 = derived["e20"].copy()
    e20["KEY"] = e20["CSOED"].map(_canonical)
    e20 = e20.drop_duplicates("KEY").set_index("KEY")
    rows = []
    for _, x in data["matched_pairs_2020"].iterrows():
        a, b = _canonical(x["CSOED_A"]), _canonical(x["CSOED_B"])
        if a not in r.index or b not in r.index or a not in e20.index or b not in e20.index:
            continue
        ra, rb = r.loc[a], r.loc[b]
        if max(abs(float(ra["DS_CHANGE_PP"])), abs(float(rb["DS_CHANGE_PP"]))) < base.CONFIG["material_shift_pp"]:
            continue
        dairy_contrast = abs(float(ra["DS20"]) - float(rb["DS20"]))
        follower_contrast = abs(float(e20.loc[a, "FOLLOWER_TO_ADULT_RATIO"]) - float(e20.loc[b, "FOLLOWER_TO_ADULT_RATIO"]))
        rows.append({
            "County": x["County"], "ED_A": x["ED_A"], "ED_B": x["ED_B"],
            "CSOED_A": str(x["CSOED_A"]), "CSOED_B": str(x["CSOED_B"]),
            "KEY_A": a, "KEY_B": b,
            "CATTLE_GAP_PCT_PAIR_MEAN": float(x["CATTLE_GAP_PCT_PAIR_MEAN"]),
            "CENSUS_DAIRY_SHARE_CONTRAST_PP": dairy_contrast,
            "CENSUS_FOLLOWERS_PER_COW_CONTRAST": follower_contrast,
            "CENSUS_CONTRAST_SCORE": dairy_contrast * follower_contrast,
        })
    if not rows:
        raise AssertionError("No matched ED pair satisfies the frozen census-grounded rule")
    return pd.DataFrame(rows).sort_values(
        ["CENSUS_CONTRAST_SCORE", "CENSUS_DAIRY_SHARE_CONTRAST_PP", "CENSUS_FOLLOWERS_PER_COW_CONTRAST", "CATTLE_GAP_PCT_PAIR_MEAN"],
        ascending=[False, False, False, True],
    ).iloc[0].to_dict()


def f2_national_restructuring(data, out, written):
    import matplotlib.pyplot as plt
    nat = data["national_year"].set_index("YEAR")
    years = nat.index.to_numpy(int)
    y0 = base.CONFIG["start_year"]
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(base.FIG_W, 3.35), constrained_layout=True)
    for col, label, colour in [
        ("TOTAL_CATTLE", "Total cattle", base.C["total"]),
        ("dairy_cows", "Dairy cows", base.C["dairy"]),
        ("suckler_cows", "Suckler cows", base.C["suckler"]),
    ]:
        idx = 100 * nat[col] / nat.loc[y0, col]
        ax_a.plot(years, idx, lw=1.7, label=label, color=colour)
    ax_a.axvline(2020, color="#777777", lw=.7, ls="--")
    ax_a.set(xlabel="Year", ylabel="Index (2015 = 100)")
    ax_a.legend(loc="best")
    base.title(ax_a, "a", "A near-flat cattle total concealed divergent cow populations")

    sel = nat.loc[[2015, 2020, 2025], ["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]].copy()
    shares = 100 * sel.div(sel.sum(axis=1), axis=0)
    bottom = np.zeros(3)
    x = np.arange(3)
    for col, lab, colour in [
        ("DXD_FOLLOWERS", "DxD", base.C["dairy"]),
        ("DXB_FOLLOWERS", "DxB", base.C["dxb"]),
        ("BXB_FOLLOWERS", "BxB", base.C["suckler"]),
    ]:
        vals = shares[col].to_numpy(float)
        ax_b.bar(x, vals, bottom=bottom, width=.62, color=colour, label=lab)
        for xx, bot, val, heads in zip(x, bottom, vals, sel[col]):
            if val >= 8:
                ax_b.text(xx, bot + val/2, f"{val:.0f}%\n{heads/1e6:.2f}m", ha="center", va="center", fontsize=5.8)
        bottom += vals
    ax_b.set_xticks(x, ["2015", "2020", "2025"])
    ax_b.set(ylabel="Follower-origin share (%)", ylim=(0, 100))
    ax_b.legend(ncol=3, loc="upper center")
    base.title(ax_b, "b", "Follower origin shifted toward dairy-beef")
    base.save(fig, out, "F2_national_restructuring", written)


def f3_signatures(derived, geo, pair, out, written):
    """2025 ED livestock-system signatures with distinct information content."""
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    e25 = derived["e25"].copy()
    edgeo = geo["ed"].copy()
    _assert_ed_base(edgeo, "F3 geometry")
    eds = edgeo.merge(
        e25,
        on=["CSOED", "County"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_y"),
    )
    if eds["TOTAL_CATTLE"].isna().any():
        raise AssertionError("F3: one or more EDs failed the 2025 model-data join")

    county = (geo["county"], base.C["county"], 0.25)
    panels = [
        ("DAIRY_SHARE_ADULT_PCT", "Dairy share of adult cows (%)", base.C["dairy"], "a", 0.0, 100.0),
        ("FOLLOWER_TO_ADULT_RATIO", "Followers per adult cow", base.C["follower"], "b", 0.0, None),
        ("UNDER1_SHARE_FOLLOWERS_PCT", "Under-1 share of followers (%)", base.C["total"], "c", 0.0, 100.0),
        ("DXD_SHARE_FOLLOWERS_PCT", "DxD share of followers (%)", base.C["dxb"], "d", 0.0, 100.0),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(base.FIG_W, 6.4), constrained_layout=True)
    for ax, (column, label, colour, letter, vmin, vmax) in zip(axes.ravel(), panels):
        values = pd.to_numeric(eds[column], errors="coerce")
        if vmax is None:
            vmax = max(0.5, float(values.quantile(0.98)))
        cmap = base.classed_cmap(colour, 8)
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        base.choropleth(ax, eds, column, cmap=cmap, norm=norm, outlines=[county])
        base.colorbar(fig, ax, cmap, norm, label, extend="max", shrink=0.72)
        base.title(ax, letter, label)
    base.save(fig, out, "F3_spatial_livestock_signatures_2025", written)


def f4_restructuring(restructuring, geo, pair, out, written):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    p = restructuring.copy(); eds = geo["ed"].copy(); _assert_ed_base(eds, "F4 geometry"); eds["KEY"] = eds["CSOED"].map(_canonical)
    eds = eds.merge(p[["KEY", "RELATIVE_PP", "STABLE_HERD_SHIFTED_SYSTEM"]], on="KEY", how="left", validate="one_to_one")
    if not set(p["KEY"]).issubset(set(eds["KEY"])):
        raise AssertionError("F4: census-restructuring keys failed to match the ED geography")

    fig = plt.figure(figsize=(base.FIG_W, 6.1), constrained_layout=True); gs = fig.add_gridspec(2, 2, height_ratios=[1.25, .75])
    ax_a, ax_b, ax_c = fig.add_subplot(gs[0,0]), fig.add_subplot(gs[0,1]), fig.add_subplot(gs[1,:])
    norm = base.diverging_norm(p["RELATIVE_PP"]); shifted = eds.loc[eds["STABLE_HERD_SHIFTED_SYSTEM"] == True]
    base.choropleth(ax_a, eds, "RELATIVE_PP", cmap=base.DIVERGING, norm=norm, outlines=[(geo["county"], base.C["county"], .25), (shifted, "black", .5)])
    ax_a.legend(handles=[Line2D([], [], color="black", lw=.8, label="stable herd, shifted system")], loc="lower left")
    base.colorbar(fig, ax_a, base.DIVERGING, norm, "ED minus county change in dairy share, 2010-2020 (pp)", extend="both")
    base.title(ax_a, "a", "Local departures from the county trend")

    q = p.loc[~p["ZERO_DAIRY_BOTH"]]; rho = base.spearman(q["CATTLE_CHANGE_PCT"], q["DS_CHANGE_PP"])
    ax_b.axvspan(-base.CONFIG["stable_herd_pct"], base.CONFIG["stable_herd_pct"], color="#f3f3f3", lw=0)
    ax_b.scatter(q["CATTLE_CHANGE_PCT"].clip(-60,60), q["DS_CHANGE_PP"], s=3, color="#999999", alpha=.5); hl = q.loc[q["STABLE_HERD_SHIFTED_SYSTEM"]]
    ax_b.scatter(hl["CATTLE_CHANGE_PCT"], hl["DS_CHANGE_PP"], s=6, color=base.C["follower"]); ax_b.axhline(0,color="#555",lw=.5); ax_b.axvline(0,color="#555",lw=.5)
    ax_b.set(xlim=(-62,62), xlabel="Change in total cattle, 2010-2020 (%)", ylabel="Change in dairy share (pp)")
    base.title(ax_b, "b", f"Herd-size and system change were weakly associated (rho = {rho:.2f})")

    rp = p.set_index("KEY").reindex([pair["KEY_A"], pair["KEY_B"]])
    for tag, row, colour, marker in zip(("A","B"), rp.itertuples(), (base.C["dairy"], base.C["suckler"]), ("o","s")):
        yy=[row.DS10,row.DS20]; ax_c.plot([2010,2020], yy, marker=marker, lw=1.5, color=colour, label=f"{tag} {pair['ED_'+tag]}")
        for x,y,n in zip((2010,2020), yy, (row.T10,row.T20)):
            off = ((-42,-14) if tag=="A" else (8,10)) if x==2010 else (5,6); ax_c.annotate(f"{int(round(n)):,} cattle", (x,y), xytext=off, textcoords="offset points", fontsize=6)
    ax_c.set(xticks=[2010,2020], ylim=(0,100), ylabel="Dairy share of adult cows (%)"); ax_c.legend(); base.title(ax_c, "c", f"Matched pair, {pair['County']}: census observations only")
    base.save(fig, out, "F4_local_restructuring_2010_2020", written)


def f5_agricultural_context(derived, geo, out, written):
    """ED-scale livestock density and agricultural land composition."""
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    eds = geo["ed"].merge(
        derived["e25"],
        on=["CSOED", "County"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_y"),
    )
    county = (geo["county"], base.C["county"], 0.25)
    panels = [
        ("CATTLE_PER_FARMED_HA", "Cattle per farmed ha", base.C["total"], "a"),
        ("SHEEP_PER_FARMED_HA", "Sheep per farmed ha", base.C["sheep"], "b"),
        ("GRASSLAND_SHARE_FARMED_PCT", "Grassland share of farmed area (%)", base.C["follower"], "c"),
        ("CEREAL_SHARE_FARMED_PCT", "Cereal share of farmed area (%)", base.C["dairy"], "d"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(base.FIG_W, 6.4), constrained_layout=True)
    for ax, (column, label, colour, letter) in zip(axes.ravel(), panels):
        values = pd.to_numeric(eds[column], errors="coerce")
        if column.endswith("_PCT"):
            vmax = 100.0 if column == "GRASSLAND_SHARE_FARMED_PCT" else max(5.0, float(values.quantile(0.98)))
        else:
            vmax = max(0.1, float(values.quantile(0.98)))
        cmap = base.classed_cmap(colour, 8)
        norm = mcolors.Normalize(vmin=0.0, vmax=vmax)
        base.choropleth(ax, eds, column, cmap=cmap, norm=norm, outlines=[county])
        base.colorbar(fig, ax, cmap, norm, label, extend="max", shrink=0.72)
        base.title(ax, letter, label)
    base.save(fig, out, "F5_ed_agricultural_context", written)


def _fill_holes(geom):
    from shapely.geometry import MultiPolygon, Polygon
    if geom.geom_type == "Polygon": return Polygon(geom.exterior)
    if geom.geom_type == "MultiPolygon": return MultiPolygon([Polygon(g.exterior) for g in geom.geoms])
    return geom


def f6_blackwater(data, derived, geo, out, written):
    import geopandas as gpd
    import matplotlib.pyplot as plt

    year = base.CONFIG["end_year"]
    w25 = derived["wfd"].loc[derived["wfd"]["YEAR"] == year].copy(); match = w25.loc[w25["WFD_CATCHMENT"].astype(str).str.contains("Blackwater", case=False, na=False)]
    if len(match)!=1: raise AssertionError(f"Expected one Blackwater catchment, found {len(match)}")
    row=match.iloc[0]; cid=str(row["WFD_CATCHMENT_ID"]); name=row["WFD_CATCHMENT"]; catch_value=float(row["FOLLOWERS_PER_ADULT_COW"])
    xw=geo["crosswalk"].loc[geo["crosswalk"]["WFD_CATCHMENT_ID"].astype(str)==cid,["CSOED","ED_CATCHMENT_WEIGHT"]].copy()
    e25=derived["e25"][["CSOED","County","FOLLOWERS_PER_COW_PLOT","ADULT_COWS"]].copy(); z=geo["ed"].merge(e25,on=["CSOED","County"],how="left",validate="one_to_one").merge(xw,on="CSOED",how="inner")
    poly=geo["wfd_state"].loc[geo["wfd_state"]["WFD_CATCHMENT_ID"].astype(str)==cid].copy(); z=gpd.clip(z,poly); z["WEIGHT"]=z["ADULT_COWS"]*z["ED_CATCHMENT_WEIGHT"]
    spread=data["wfd_signature_spread"].loc[
        (data["wfd_signature_spread"]["YEAR"]==year)
        & (data["wfd_signature_spread"]["WFD_CATCHMENT_ID"].astype(str)==cid)
        & (data["wfd_signature_spread"]["SIGNATURE"]=="FOLLOWER_TO_ADULT_RATIO")
    ]
    if len(spread)!=1: raise AssertionError(f"Expected one catchment-spread row for {name}")
    sr=spread.iloc[0]; p10=float(sr["ED_WEIGHTED_P10"]); p50=float(sr["ED_WEIGHTED_P50"]); p90=float(sr["ED_WEIGHTED_P90"])
    stats={"YEAR":year,"WFD_CATCHMENT_ID":cid,"WFD_CATCHMENT":name,"WFD_CATCHMENT_LABEL":f"{cid} {name}","N_ED":int(sr["INTERSECTING_EDS"]),"P10":p10,"P50":p50,"P90":p90,"CATCHMENT_COEFFICIENT":catch_value,"METRIC":"followers per adult cow","WEIGHTING":"adult cows x fractional ED-catchment weight"}
    cmap,norm=_follower_cmap_norm(); fig=plt.figure(figsize=(base.FIG_W,4.2),constrained_layout=True); gs=fig.add_gridspec(1,4,width_ratios=[.65,1.15,1.5,1.0]); ax_loc,ax_a,ax_b,ax_c=[fig.add_subplot(gs[0,i]) for i in range(4)]
    geo["ireland"].plot(ax=ax_loc,color="#eeeeee",edgecolor="#888888",linewidth=.35); poly.plot(ax=ax_loc,color=base.C["follower"],edgecolor="black",linewidth=.45); base.map_axes(ax_loc); base.title(ax_loc,"","Ireland locator")
    display_poly=poly.copy(); display_poly["geometry"]=display_poly.geometry.apply(_fill_holes); display_poly["COEF"]=catch_value; base.choropleth(ax_a,display_poly,"COEF",cmap=cmap,norm=norm,lw=.4); base.title(ax_a,"a",f"{cid} {name}\n{catch_value:.2f} followers/adult cow")
    base.choropleth(ax_b,z,"FOLLOWERS_PER_COW_PLOT",cmap=cmap,norm=norm,lw=.15,outlines=[(poly,"black",.8)]); base.title(ax_b,"b","ED structure inside the same catchment"); base.colorbar(fig,[ax_a,ax_b],cmap,norm,"Followers per adult cow",ticks=FOLLOWER_COEF_BREAKS,extend="max",shrink=.78)
    v=pd.to_numeric(z["FOLLOWERS_PER_COW_PLOT"],errors="coerce"); weights=pd.to_numeric(z["WEIGHT"],errors="coerce"); ok=v.notna()&weights.notna()&(weights>0); ax_c.hist(v[ok],bins=18,weights=weights[ok],color=base.C["follower"],edgecolor="white",lw=.4)
    for xx,ls in ((p10,":"),(p50,"-"),(p90,":")): ax_c.axvline(xx,color="black",lw=.8,ls=ls)
    ax_c.axvline(catch_value,color=base.C["total"],lw=1.2,ls="--",label="catchment value"); ax_c.set(xlabel="Followers per adult cow",ylabel="Adult-cow weighted ED mass"); ax_c.legend(); base.title(ax_c,"c",f"Weighted P10-P90: {p10:.2f}-{p90:.2f}")
    base.save(fig,out,"F6_blackwater_ed_catchment_signatures",written); return stats


def build_table2(root: Path, data: dict) -> pd.DataFrame:
    gpath=root/"data/processed/validation/historical/cattle_genetics_summary.csv"
    if not gpath.exists(): raise FileNotFoundError(f"Missing {gpath}; run scripts/build_historical_release.py")
    g=pd.read_csv(gpath).set_index("METRIC")["VALUE"]; h=data["validation_detail_sheep_composition_holdout_2022"].copy(); h_rho=[]; h_mae=[]
    for _,grp in h.groupby("BREED_GROUP"):
        h_rho.append(base.spearman(grp["OBSERVED_SHARE"],grp["PREDICTED_SHARE"])); h_mae.append(float((100*(grp["PREDICTED_SHARE"]-grp["OBSERVED_SHARE"])).abs().mean()))
    hold=data["s00_temporal_holdout_2010_2020"].loc[lambda d:d["VARIABLE"]=="DAIRY_COW"]
    if len(hold)!=1: raise AssertionError("Expected one dairy row in temporal_holdout_2010_2020")
    hold=hold.iloc[0]
    lsu=data["validation_detail_cattle_lsu_age_prior_summary"].set_index("AGE_PRIOR")
    return pd.DataFrame([
        {"VALIDATION_TEST":"Livestock accounting identities","N":f"{EXPECTED_EDS*11:,} ED-years","SPEARMAN_RHO":"-","ERROR":"0 head","ROLE":"internal closure"},
        {"VALIDATION_TEST":"ED cattle-type composition vs AIM, 2020","N":f"{int(g['dafm_type_matched_ed_count']):,} EDs","SPEARMAN_RHO":f"{g['g1_dafm_type_model_spearman_rho']:.3f}","ERROR":f"{g['g1_dafm_type_weighted_mae_percentage_points']:.2f} pp","ROLE":"information-retention diagnostic"},
        {"VALIDATION_TEST":"Withheld 2022 sheep composition, county scale","N":f"{len(h):,} county-by-class observations","SPEARMAN_RHO":f"{min(h_rho):.3f}-{max(h_rho):.3f}","ERROR":f"{min(h_mae):.2f}-{max(h_mae):.2f} pp","ROLE":"withheld validation"},
        {"VALIDATION_TEST":"2020 ED livestock-unit age-prior screen","N":f"{int(lsu.loc['dafm_log_odds','eligible_eds']):,} EDs","SPEARMAN_RHO":"-","ERROR":f"AIM {lsu.loc['dafm_log_odds','median_abs_residual']:.1f} LSU; flat {lsu.loc['flat_county','median_abs_residual']:.1f} LSU","ROLE":"model-selection/plausibility diagnostic"},
        {"VALIDATION_TEST":"2010->2020 dairy spatial carry-forward","N":f"{int(hold['EDS_SCORED']):,} EDs","SPEARMAN_RHO":f"ED {hold['ED_SPEARMAN']:.3f}; WFD {hold['UNIT_SPEARMAN']:.3f}","ERROR":f"ED {hold['ED_DISPLACED_PCT']:.2f}%; WFD {hold['UNIT_DISPLACED_PCT']:.2f}%","ROLE":"cross-census persistence test"},
    ])


def build_table3(data: dict, derived: dict) -> pd.DataFrame:
    nat=data["national_year"].set_index("YEAR"); ed=derived["ed"]; lu=ed.groupby("YEAR")["LU"].sum(); years=[2015,2020,2025]
    series={"Total cattle (head)":nat["TOTAL_CATTLE"],"Dairy cows (head)":nat["dairy_cows"],"Suckler cows (head)":nat["suckler_cows"],"Sheep (head)":nat["TOTAL_SHEEP"],"Livestock units (LU)":lu,"Standard Output (EUR m, 2020 coefficients)":nat["SO_COVERED_TOTAL_2020_EUR"]/1e6,"DxD followers (head)":nat["DXD_FOLLOWERS"],"DxB followers (head)":nat["DXB_FOLLOWERS"],"BxB followers (head)":nat["BXB_FOLLOWERS"]}
    tf=nat["DXD_FOLLOWERS"]+nat["DXB_FOLLOWERS"]+nat["BXB_FOLLOWERS"]; series.update({"DxD share of followers (%)":100*nat["DXD_FOLLOWERS"]/tf,"DxB share of followers (%)":100*nat["DXB_FOLLOWERS"]/tf,"BxB share of followers (%)":100*nat["BXB_FOLLOWERS"]/tf,"Followers per adult cow":nat["FOLLOWER_TOTAL"]/nat["ADULT_COWS"],"DxD followers per dairy cow":nat["DXD_FOLLOWERS"]/nat["dairy_cows"],"DxB followers per dairy cow":nat["DXB_FOLLOWERS"]/nat["dairy_cows"],"BxB followers per suckler cow":nat["BXB_FOLLOWERS"]/nat["suckler_cows"]})
    rows=[]
    for name,s in series.items():
        vals=[float(s.loc[y]) for y in years]; row={"INDICATOR":name,"2015":vals[0],"2020":vals[1],"2025":vals[2],"CHANGE_2015_2020_PCT":100*(vals[1]/vals[0]-1) if vals[0] else np.nan,"CHANGE_2020_2025_PCT":100*(vals[2]/vals[1]-1) if vals[1] else np.nan,"CHANGE_2015_2025_PCT":100*(vals[2]/vals[0]-1) if vals[0] else np.nan,"2020_2025_DECOMPOSITION":"","SOURCE_NOTE":""}
        if name=="DxB followers (head)":
            d0,d1=float(nat.loc[2020,"dairy_cows"]),float(nat.loc[2025,"dairy_cows"]); b0=float(nat.loc[2020,"DXB_FOLLOWERS"]/nat.loc[2020,"dairy_cows"]); b1=float(nat.loc[2025,"DXB_FOLLOWERS"]/nat.loc[2025,"dairy_cows"]); herd=.5*(b0+b1)*(d1-d0); ratio=.5*(d0+d1)*(b1-b0); total=herd+ratio; row["2020_2025_DECOMPOSITION"]=f"ratio {100*ratio/total:.1f}%; herd {100*herd/total:.1f}%"
        if name in {"Total cattle (head)","Dairy cows (head)","Suckler cows (head)"}: row["SOURCE_NOTE"]="2020 is the 2,857-ED census anchor; 2015/2025 use AAA10 annual controls"
        elif name=="Sheep (head)": row["SOURCE_NOTE"]="2020 is the census anchor; 2015/2025 use AAA09 annual controls"
        rows.append(row)
    return pd.DataFrame(rows)


def build_table5(data: dict) -> pd.DataFrame:
    spread = data["wfd_signature_spread"].loc[
        data["wfd_signature_spread"]["YEAR"] == base.CONFIG["end_year"]
    ].copy()
    selected = [
        "CATTLE_PER_FARMED_HA",
        "SHEEP_PER_FARMED_HA",
        "GRASSLAND_SHARE_FARMED_PCT",
        "CEREAL_SHARE_FARMED_PCT",
        "DAIRY_SHARE_ADULT_PCT",
        "UNDER1_SHARE_FOLLOWERS_PCT",
        "FOLLOWER_TO_ADULT_RATIO",
    ]
    spread = spread.loc[spread["SIGNATURE"].isin(selected)]
    values = spread.pivot(
        index=["WFD_CATCHMENT_ID", "WFD_CATCHMENT"],
        columns="SIGNATURE",
        values="CATCHMENT_VALUE",
    )
    follower = spread.loc[
        spread["SIGNATURE"] == "FOLLOWER_TO_ADULT_RATIO",
        [
            "WFD_CATCHMENT_ID",
            "WFD_CATCHMENT",
            "ED_WEIGHTED_P10",
            "ED_WEIGHTED_P50",
            "ED_WEIGHTED_P90",
            "ED_WEIGHTED_P90_P10",
            "INTERSECTING_EDS",
        ],
    ].set_index(["WFD_CATCHMENT_ID", "WFD_CATCHMENT"])
    out = values.join(follower).reset_index()
    return out.sort_values("WFD_CATCHMENT_ID").reset_index(drop=True)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__.split("\n")[0]); parser.add_argument("--root",default="."); args=parser.parse_args(); root=Path(args.root).resolve(); sys.path.insert(0,str(root/"src")); out=root/base.CONFIG["output_dir"]
    for sub in ("figures","tables","maps"): (out/sub).mkdir(parents=True,exist_ok=True)
    base.style(); data=base.load(root); geo=base.geometry(root,data["ed_year"]); derived=base.derive(data); model_keys=set(data["ed_year"]["CSOED"].map(_canonical)); p=base.observed_restructuring(root,data,model_keys); pair=select_case_pair(data,p,derived); written=[]; print(f"Case pair: {pair['ED_A']} / {pair['ED_B']} ({pair['County']})")
    f2_national_restructuring(data,out,written); f4_restructuring(p,geo,pair,out,written); f3_signatures(derived,geo,pair,out,written); f5_agricultural_context(derived,geo,out,written); bw=f6_blackwater(data,derived,geo,out,written)
    follower_spread=data["wfd_signature_spread"].loc[(data["wfd_signature_spread"]["YEAR"]==base.CONFIG["end_year"]) & (data["wfd_signature_spread"]["SIGNATURE"]=="DAIRY_SHARE_ADULT_PCT")].rename(columns={"ED_WEIGHTED_P10":"P10","ED_WEIGHTED_P90":"P90","INTERSECTING_EDS":"N"})[["WFD_CATCHMENT_ID","P10","P90","N"]]
    tabs=base.tables(data,derived,p,follower_spread); tabs.pop("T5_catchment_signatures_2020", None); tabs["T2_validation"]=build_table2(root,data); tabs["T3_national_change"]=build_table3(data,derived); tabs["T5_catchment_signatures_2025"]=build_table5(data)
    if "T4_system_typology_2020" in tabs: tabs["S9_system_typology_2020"]=tabs.pop("T4_system_typology_2020")
    tabs["MAIN_case_pair"]=pd.DataFrame([pair]); tabs["MAIN_blackwater_spread"]=pd.DataFrame([bw]); base.write_tables(tabs,out,written); base.write_layers(derived,geo,out,written)
    tp=base.temporal_points(root,model_keys,geo["crosswalk"]); base.f2_validation(data,tp,out,written)
    for ext in ("png","pdf"):
        src=out/"figures"/f"F2_validation.{ext}"; dst=out/"figures"/f"S1_validation_diagnostics.{ext}"
        if src.exists(): src.replace(dst); written[:]=[dst if x==src else x for x in written]
    manifest={"package":"GOBLIN_SPATIAL_PAPER1_FINAL","created_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"repository":base.git_info(root),"coherence_audit":data["audit_pass"],"case_pair":pair,"case_pair_rule":"same county + similar herd + published cow cells in both censuses + material shift; candidate pairs ranked on dairy share, followers/adult cow, under-1 follower share and DxD follower share","case_catchment":CASE_CATCHMENT,"blackwater_spread":bw,"architecture":["3.1 Table 2 integrity/validation","3.2 F2+F4 national and observed restructuring","3.3 F3 ED livestock-system geography","3.4 F5 agricultural context","3.5 F6 catchment structure"],"files":{str(x.relative_to(out)):base.sha(x) for x in written if x.exists()}}
    (out/"paper1_manifest_final.json").write_text(json.dumps(manifest,indent=2,default=str)+"\n",encoding="utf-8"); print(f"Done: {out}"); return 0


if __name__=="__main__": raise SystemExit(main())
