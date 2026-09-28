"""Validation of the historical ED baseline (v1.1): metrics, tables and figures.

Tests (see goblin_spatial.validation.baseline_metrics for definitions):
  T1  held-out 2020 ED livestock units (INDEPENDENT)
  T2  census backcast: 2020 ED pattern predicted from 2010 shares (INDEPENDENT)
  T3  withheld DAFM ewe county years 2016, 2022 (INDEPENDENT for that step)
  T4  withheld 2022 DAFM breed composition (INDEPENDENT for that step)
  T5  census 2020 ED cattle vs DAFM/AIM register (CONSISTENCY of the anchor)
  T6  reconstructed county sheep vs DAFM December census (CONSISTENCY)
  T7  CSO-chain national cohorts vs COHORTS 2015-2020 (CONSISTENCY)
  T8  adjacent-year continuity (DIAGNOSTIC)

Usage: python scripts/run_baseline_validation.py
Writes data/processed/validation/ (metrics table, detail files, figures, summary).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS, add_cattle_cohorts
from goblin_spatial.config import load_config
from goblin_spatial.sheep import add_sheep_cohorts, build_annual_sheep_panel
from goblin_spatial.sheep.annual_panel import _dafm_ewe_shares
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.sheep.panel import _load_workbook, _normalise_county
from goblin_spatial.validation.baseline_metrics import (
    backcast_2020_from_2010,
    continuity,
    lsu_frame,
    match_aim_totals,
    row,
)
from goblin_spatial.validation.historical import sheep_anchor_holdout

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/validation"


def scatter(ax, o, p, title, xlabel="Observed", ylabel="Reconstructed"):
    o = np.asarray(o, float); p = np.asarray(p, float)
    ax.scatter(o + 1, p + 1, s=4, alpha=0.35, color="#2b6cb0", linewidths=0)
    lim = [1, max(o.max(), p.max()) * 1.3 + 1]
    ax.plot(lim, lim, color="#555", lw=0.8, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_title(title, fontsize=9); ax.set_xlabel(xlabel + " (+1, log)", fontsize=8); ax.set_ylabel(ylabel + " (+1, log)", fontsize=8)
    ax.tick_params(labelsize=7)


def main() -> None:
    cfg = load_config(CONFIG)
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published["County"] = published["County"].map(_normalise_county)
    ed2010 = pd.read_csv(cfg.files["cso_ed_2010"], dtype=str, keep_default_na=False)

    cattle, _ = build_annual_ed_panel(cfg)
    age_dafm = build_annual_age_sex_panel(cfg, cattle, "dafm_log_odds")
    age_flat = build_annual_age_sex_panel(cfg, cattle, "flat_county")
    sheep, _ = build_annual_sheep_panel(cfg)

    # T1 held-out 2020 LSU
    a20 = age_dafm.loc[age_dafm["YEAR"] == 2020].copy(); a20["CSOED"] = a20["CSOED"].astype(str)
    f20 = age_flat.loc[age_flat["YEAR"] == 2020].copy(); f20["CSOED"] = f20["CSOED"].astype(str)
    t1 = lsu_frame(a20, published)
    t1["LSU_FLAT_PRIOR"] = lsu_frame(f20, published).set_index("CSOED").loc[t1["CSOED"], "LSU_MODEL"].to_numpy()
    t1.to_csv(OUT / "T1_lsu_2020_by_ed.csv", index=False)
    livestock = t1["LSU_PUBLISHED"].gt(0) & (t1["TOTAL_CATTLE"] + t1["TOTAL_SHEEP"]).gt(0)
    cattle_dom = livestock & (t1["TOTAL_CATTLE"] >= 5 * 0.1 * t1["TOTAL_SHEEP"])
    for name, m in (("EDs with livestock", livestock), ("cattle-dominated EDs", cattle_dom)):
        s = t1.loc[m]
        rows.append(row("T1 held-out ED livestock units 2020", "INDEPENDENT", "LSU", name,
                        s["LSU_PUBLISHED"], s["LSU_MODEL"], s["LSU_FLAT_PRIOR"], "flat county age-sex prior",
                        "LSU never used in estimation; cattle totals and sheep are published 2020 values, so this tests the age-sex composition"))

    # T2 census backcast
    t2_parts = []
    for col in ("TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"):
        b = backcast_2020_from_2010(published, ed2010, col)
        b["VARIABLE"] = col
        t2_parts.append(b)
        for base, bname in (("BASE_EQUAL", "equal shares within county"), ("BASE_GRASSLAND", "2020 grassland shares")):
            rows.append(row("T2 census backcast 2020 from 2010 pattern", "INDEPENDENT", col, "EDs with published 2010 value",
                            b["OBSERVED_2020"], b["PRED_2010_SHARES"], b[base], bname,
                            "levels fixed at the county 2020 total; tests the persistence of the ED pattern the time rule relies on"))
    t2 = pd.concat(t2_parts, ignore_index=True)
    t2.to_csv(OUT / "T2_backcast_2020_from_2010.csv", index=False)

    # T3 withheld DAFM ewe county years
    crosswalk, region = _load_workbook(cfg.files["cso_sheep_workbook"])
    shares = _dafm_ewe_shares(cfg.files["dafm_sheep_county_pattern"], cfg.files["sheep_breed_anchors"], crosswalk)
    for held, lo, hi in ((2016, 2015, 2020), (2022, 2020, 2025)):
        w = (held - lo) / (hi - lo)
        interp = (1 - w) * shares[lo] + w * shares[hi]
        rows.append(row("T3 withheld DAFM ewe year", "INDEPENDENT", f"county ewe share within region, {held}", "26 counties",
                        shares[held], interp, shares[2020], "frozen 2020 shares",
                        f"interpolated from {lo} and {hi}", ci_metrics=()))

    # T4 withheld 2022 breed composition
    detail, _ = sheep_anchor_holdout(cfg.files["sheep_breed_anchors"])
    anchors = pd.read_csv(cfg.files["sheep_breed_anchors"], encoding="utf-8-sig")
    anchors["County"] = anchors["County"].map(_normalise_county)
    a2020 = anchors.loc[anchors["YEAR"] == 2020].set_index(["County", "CATEGORY"])
    detail["SHARE_2020"] = [a2020.loc[(c, cat), f"{g}_SHARE_EXACT"] for c, cat, g in zip(detail["County"], detail["CATEGORY"], detail["BREED_GROUP"])]
    detail.to_csv(OUT / "T4_breed_holdout_2022.csv", index=False)
    for g, s in detail.groupby("BREED_GROUP"):
        rows.append(row("T4 withheld 2022 breed composition", "INDEPENDENT", f"{g} share", "county x category",
                        s["OBSERVED_SHARE"], s["PREDICTED_SHARE"], s["SHARE_2020"], "frozen 2020 shares",
                        "interpolated from 2020 and 2025", ci_metrics=()))

    # T5 census vs AIM register
    aim = pd.read_csv(cfg.files["dafm_aim_ed_cattle_profile_2020"])
    t5 = match_aim_totals(published, aim)
    t5.to_csv(OUT / "T5_census_vs_aim_2020.csv", index=False)
    rows.append(row("T5 census 2020 vs DAFM/AIM register", "CONSISTENCY", "total cattle", f"name-matched EDs ({len(t5)} of 2857)",
                    t5["CENSUS_TOTAL_CATTLE"], t5["AIM_AVG_CATTLE"], note="June census vs annual-average register; tests the anchor data, not the model"))

    # T6 county sheep vs DAFM December census
    dafm = pd.read_csv(cfg.files["dafm_sheep_county_pattern"]); dafm["County"] = dafm["County"].map(_normalise_county)
    sc = sheep.groupby(["YEAR", "County"])["TOTAL_SHEEP"].sum().reset_index()
    t6 = dafm.merge(sc, on=["YEAR", "County"])
    t6.to_csv(OUT / "T6_county_sheep_vs_dafm.csv", index=False)
    for y, s in t6.groupby("YEAR"):
        rows.append(row("T6 county sheep vs DAFM December census", "CONSISTENCY", f"total sheep {y}", "26 counties",
                        s["TOTAL"], s["TOTAL_SHEEP"], note="June CSO-controlled vs December DAFM; DAFM ewe ratios enter the county split", ci_metrics=()))

    # T7 national cohorts vs COHORTS
    cc = add_cattle_cohorts(age_dafm, cfg); sh = add_sheep_cohorts(sheep, cfg)
    ref = pd.read_csv(cfg.files["goblin_cohorts"]).set_index("Cohorts") * 1000
    nat = pd.concat([cc.groupby("YEAR")[FINAL_21_COHORTS].sum(), sh.groupby("YEAR")[GOBLIN_SHEEP_10].sum()], axis=1)
    t7 = []
    for y in range(2015, 2021):
        for k in [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]:
            t7.append({"YEAR": y, "COHORT": k, "SPECIES": "cattle" if k in FINAL_21_COHORTS else "sheep",
                       "CSO_CHAIN": float(nat.loc[y, k]), "COHORTS": float(ref.loc[k, str(y)])})
    t7 = pd.DataFrame(t7); t7["RATIO"] = t7["COHORTS"] / t7["CSO_CHAIN"]
    t7.to_csv(OUT / "T7_national_cohorts_vs_COHORTS.csv", index=False)
    for sp, s in t7.groupby("SPECIES"):
        rows.append(row("T7 national cohorts vs COHORTS 2015-2020", "CONSISTENCY", f"{sp} cohorts", "cohort x year",
                        s["COHORTS"], s["CSO_CHAIN"], note="different classification systems; see ratios by cohort", ci_metrics=()))

    # T8 continuity
    cat = cattle.copy(); cat["CSOED"] = cat["CSOED"].astype(str)
    shp = sheep[["YEAR", "CSOED", "TOTAL_SHEEP"]].copy(); shp["CSOED"] = shp["CSOED"].astype(str)
    both = cat.merge(shp, on=["YEAR", "CSOED"])
    t8 = continuity(both, ["TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW", "TOTAL_SHEEP"])
    t8.to_csv(OUT / "T8_continuity.csv", index=False)

    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT / "baseline_validation_metrics.csv", index=False)

    # figures
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6))
    s = t1.loc[livestock]
    scatter(ax[0], s["LSU_PUBLISHED"], s["LSU_MODEL"], "T1 ED livestock units, 2020\n(published vs model)")
    b = t2.loc[t2["VARIABLE"] == "TOTAL_CATTLE"]
    scatter(ax[1], b["OBSERVED_2020"], b["PRED_2010_SHARES"], "T2 total cattle, 2020\n(census vs 2010-pattern backcast)")
    b = t2.loc[t2["VARIABLE"] == "DAIRY_COW"]
    scatter(ax[2], b["OBSERVED_2020"], b["PRED_2010_SHARES"], "T2 dairy cows, 2020\n(census vs 2010-pattern backcast)")
    fig.tight_layout(); fig.savefig(OUT / "fig_validation_scatter.png", dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.4))
    for v, g in t8.groupby("VARIABLE"):
        ax.plot(g["TO"], g["SPEARMAN_RHO"], marker="o", ms=3, label=v)
    ax.axvline(2020, color="#999", lw=0.6, ls=":"); ax.axvline(2021, color="#999", lw=0.6, ls=":")
    ax.set_ylabel("Spearman rho, year t-1 to t", fontsize=8); ax.set_xlabel("Year t", fontsize=8)
    ax.legend(fontsize=7, frameon=False); ax.tick_params(labelsize=7)
    fig.tight_layout(); fig.savefig(OUT / "fig_continuity.png", dpi=200); plt.close(fig)

    cols = ["TEST", "INDEPENDENCE", "VARIABLE", "SUBSET", "N", "LIN_CCC", "PEARSON_R", "PEARSON_R_LOG1P",
            "SPEARMAN_RHO", "R2_1TO1", "RMSE", "NRMSE", "MAE", "BIAS", "BASELINE", "SKILL_VS_BASELINE"]
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(metrics[[c for c in cols if c in metrics.columns]].round(3).to_string(index=False))
    print(t8.pivot_table(index="TO", columns="VARIABLE", values="SPEARMAN_RHO").round(3).to_string())


if __name__ == "__main__":
    main()
