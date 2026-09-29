"""Cross-product coherence audit of a built historical baseline.

Reads the finished output files and re-derives every accounting identity that
links them, independently of the checks each stage runs on itself:

A  one YEAR x CSOED backbone across every ED-year product
B  CSO 13-group panel: identities, published 2020 values, AAA10 and AAA09 closure
C  GOBLIN 31-cohort panel: carries the CSO controls, closes to them exactly
D  later products (master, Standard Output) add columns and change none
E  land and holdings identities; regional land indices follow AQA06
F  Standard Output recomputed from cohort head counts and IFS 2020 coefficients
G  county, national and catchment tables equal sums of EDs
H  no missing values in counts, land, holdings and holder age

``audit_historical_outputs`` returns one row per check; it never raises, so a
caller can write the table and then decide.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS
from goblin_spatial.cattle.panel import _load_aaa10
from goblin_spatial.config import SpatialConfig
from goblin_spatial.export.livestock_panels import CSO_CATTLE_9, CSO_SHEEP_4
from goblin_spatial.sheep.annual_panel import _load_workbook
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

KNOWN_YEAR = 2020
PUBLISHED_2020 = (
    "DAIRY_COW",
    "OTHER_COW",
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
    "TOTAL_SHEEP",
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "AGRICULTURAL_HOLDINGS",
)
CARRIED = (
    *FINAL_21_COHORTS,
    *GOBLIN_SHEEP_10,
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "OTHER_CROPS_HA",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
)
SO_PARTS = (
    "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR",
    "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR",
)


def _output(cfg: SpatialConfig, key: str, default: str) -> Path:
    path = Path(cfg.raw.get("outputs", {}).get(key, default))
    return path if path.is_absolute() else cfg.project_root / path


def output_paths(cfg: SpatialConfig) -> dict[str, Path]:
    processed = cfg.project_root / "data/processed"
    return {
        "cso13": _output(cfg, "cso_13_cohort_panel", "data/interim/CSO_13_Cohort_Annual_Panel_2015_2025.csv"),
        "goblin31": _output(cfg, "goblin_31_cohort_panel", "data/interim/GOBLIN_31_Cohort_Annual_Panel_2015_2025.csv"),
        "master": _output(cfg, "enriched_master", "data/processed/goblin_spatial_master_2015_2025.csv"),
        "standard_output": _output(cfg, "standard_output_master", "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv"),
        "county": processed / "goblin_spatial_county_2015_2025.csv",
        "national": processed / "goblin_spatial_national_2015_2025.csv",
        "wfd": processed / "goblin_spatial_wfd_catchment_2015_2025.csv",
        "colm": processed / "goblin_spatial_colm_catchment_2015_2025.csv",
    }


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"CSOED": str}, low_memory=False)


def audit_historical_outputs(cfg: SpatialConfig) -> pd.DataFrame:
    paths = output_paths(cfg)
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"coherence audit needs the built baseline: {missing}")

    rows: list[dict[str, object]] = []

    def check(group: str, name: str, ok: bool, detail: str = "") -> None:
        rows.append({"GROUP": group, "CHECK": name, "PASS": bool(ok), "DETAIL": detail})

    c13 = _read(paths["cso13"])
    g31 = _read(paths["goblin31"])
    master = _read(paths["master"])
    so = _read(paths["standard_output"])
    county = pd.read_csv(paths["county"])
    national = pd.read_csv(paths["national"])
    catchments = {"WFD": pd.read_csv(paths["wfd"]), "Colm": pd.read_csv(paths["colm"])}
    published = _read(cfg.files["cso_ed_2020"]).set_index("CSOED")
    n_rows = cfg.expected_eds * (cfg.end_year - cfg.start_year + 1)

    # A. backbone
    keys = set(zip(c13["YEAR"], c13["CSOED"]))
    check("A", f"CSO 13 panel has {n_rows:,} unique YEAR x CSOED rows", len(c13) == n_rows and len(keys) == n_rows)
    for name, frame in (("GOBLIN 31 panel", g31), ("master", master), ("Standard Output master", so)):
        same = len(frame) == n_rows and set(zip(frame["YEAR"], frame["CSOED"])) == keys
        check("A", f"{name} uses the same YEAR x CSOED backbone", same)

    # B. CSO 13 groups
    check("B", "9 CSO cattle groups sum to TOTAL_CATTLE", bool((c13[CSO_CATTLE_9].sum(axis=1) == c13["TOTAL_CATTLE"]).all()))
    check("B", "OTHER_CATTLE = TOTAL_CATTLE - DAIRY_COW - OTHER_COW",
          bool((c13["OTHER_CATTLE"] == c13["TOTAL_CATTLE"] - c13["DAIRY_COW"] - c13["OTHER_COW"]).all()))
    check("B", "4 CSO sheep classes sum to TOTAL_SHEEP", bool((c13[CSO_SHEEP_4].sum(axis=1) == c13["TOTAL_SHEEP"]).all()))
    numeric = c13.select_dtypes("number").drop(columns=["YEAR"])
    check("B", "no negative counts or areas", bool((numeric.fillna(0) >= 0).all().all()))
    y2020 = c13.loc[c13["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    for column in PUBLISHED_2020:
        diff = float((y2020.loc[published.index, column].astype(float) - published[column].astype(float)).abs().max())
        check("B", f"2020 {column} equals the published CSO ED value", diff == 0.0, f"max abs diff {diff:g}")

    aaa10 = _load_aaa10(cfg.files["cso_cattle_county"]).set_index(["Year", "County"])
    cattle = c13.groupby(["YEAR", "County"])[["DAIRY_COW", "OTHER_COW", "TOTAL_CATTLE"]].sum()
    mismatches = 0
    for (year, name), row in cattle.iterrows():
        if year == KNOWN_YEAR:
            continue
        control = aaa10.loc[(year, name)]
        mismatches += int(
            (row["DAIRY_COW"], row["OTHER_COW"], row["TOTAL_CATTLE"])
            != (control["Dairy cows__HEAD"], control["Other cows__HEAD"], control["Total cattle__HEAD"])
        )
    check("B", "non-2020 county cattle equal AAA10 (dairy, other cows, total)", mismatches == 0, f"{mismatches} county-year mismatches")

    crosswalk, region = _load_workbook(cfg.files["cso_sheep_workbook"])
    region = region.loc[region["Region_Level"] == "Detailed region"].set_index(["Year", "Region"])
    sheep = c13.merge(crosswalk[["County", "Region"]].rename(columns={"Region": "_R"}), on="County")
    sheep = sheep.groupby(["YEAR", "_R"])["TOTAL_SHEEP"].sum()
    mismatches, gap_2020 = 0, 0
    for (year, name), value in sheep.items():
        control = int(round(float(region.loc[(year, name), "Total sheep"]) * 1000))
        if year == KNOWN_YEAR:
            gap_2020 += control - int(value)
        else:
            mismatches += int(int(value) != control)
    check("B", "non-2020 regional sheep equal AAA09", mismatches == 0,
          f"{mismatches} region-year mismatches; 2020 AAA09 minus published ED sum {gap_2020:,} (recorded, not reconciled)")

    # C. GOBLIN 31 cohorts
    merged = g31.merge(c13, on=["YEAR", "CSOED"], suffixes=("", "__c13"))
    controls = [c for c in g31.columns if c.startswith("CSO_")]
    unequal = [c for c in controls if not (merged[c] == merged[c[4:]]).all()]
    check("C", "GOBLIN 31 CSO_ control columns equal the CSO 13 panel", not unequal, ", ".join(unequal))
    check("C", "21 cattle cohorts sum to CSO_TOTAL_CATTLE", bool((g31[FINAL_21_COHORTS].sum(axis=1) == g31["CSO_TOTAL_CATTLE"]).all()))
    check("C", "10 sheep cohorts sum to CSO_TOTAL_SHEEP", bool((g31[GOBLIN_SHEEP_10].sum(axis=1) == g31["CSO_TOTAL_SHEEP"]).all()))
    unequal = [
        container for container, mapping in CONTAINERS.items()
        if not (g31[[mapping[g] for g in ("DxD", "DxB", "BxB")]].sum(axis=1) == g31[f"CSO_{container}"]).all()
    ]
    check("C", "each CSO age-sex group = DxD + DxB + BxB", not unequal, ", ".join(unequal))
    carried = (
        (g31["dairy_cows"] == g31["CSO_DAIRY_COW"]).all()
        and (g31["suckler_cows"] == g31["CSO_OTHER_COW"]).all()
        and (g31["bulls"] == g31["CSO_BULLS"]).all()
    )
    check("C", "cows and bulls carried unchanged into the cohorts", bool(carried))
    young = {g: [CONTAINERS[c][g] for c in CONTAINERS] for g in ("DxD", "DxB", "BxB")}
    national_young = g31.groupby("YEAR")[sum(young.values(), [])].sum()
    bxb = national_young[young["BxB"]].sum(axis=1) / national_young.sum(axis=1)
    check("C", "national BxB share of young stock reported by year", True,
          "; ".join(f"{int(y)} {v:.3f}" for y, v in bxb.items()))

    # D. later products
    for name, frame in (("master", master), ("Standard Output master", so)):
        m = g31.merge(frame, on=["YEAR", "CSOED"], suffixes=("", "__x"))
        unequal = [
            c for c in CARRIED
            if not np.allclose(m[c].astype(float), m[f"{c}__x"].astype(float), equal_nan=True)
        ]
        check("D", f"{name}: cohorts, land and farm structure identical to the GOBLIN 31 panel", not unequal, ", ".join(unequal))
    shared = [c for c in master.columns if c in so.columns and c not in ("YEAR", "CSOED")]
    m = master.merge(so, on=["YEAR", "CSOED"], suffixes=("", "__so"))
    changed = [
        c for c in shared
        if m[c].dtype.kind in "if" and not np.allclose(m[c], m[f"{c}__so"], equal_nan=True)
    ]
    check("D", "Standard Output master adds columns and changes none", not changed, ", ".join(changed[:5]))

    # E. land and holdings
    land = (c13["AREA_FARMED"] - c13[["ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]].sum(axis=1)).abs().max()
    check("E", "AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA", land < 1e-6, f"max {land:.2e} ha")
    orphan = int(((c13["AGRICULTURAL_HOLDINGS"] == 0) & (c13["AREA_FARMED"] > 0)).sum())
    check("E", "no farmed area without holdings", orphan == 0, f"{orphan} ED-years")
    aqa06 = pd.read_excel(cfg.files["cso_land"], sheet_name="Unpivoted")
    land_types = {
        "AREA_FARMED": ["Area farmed (AAU)"],
        "TOTAL_CEREALS": ["Total cereals"],
        "ALL_GRASSLAND": ["Pasture", "Hay", "Grass silage", "Rough grazing in use"],
    }
    regional = master.groupby(["AQA06_REGION", "YEAR"])[list(land_types)].sum()
    for column, types in land_types.items():
        control = aqa06.loc[aqa06["Type of Land Use"].isin(types)].groupby(["Region", "Year"])["VALUE"].sum()
        worst = 0.0
        for name in regional.index.get_level_values(0).unique():
            model_index = regional.loc[name, column] / regional.loc[(name, KNOWN_YEAR), column]
            control_index = control.loc[name].reindex(model_index.index) / control.loc[(name, KNOWN_YEAR)]
            worst = max(worst, float((model_index - control_index).abs().max()))
        check("E", f"regional {column} index (year / 2020) follows AQA06 in all 7 regions", worst < 1e-9,
              f"max index gap {worst:.1e}")

    # F. Standard Output
    mapping = pd.read_csv(cfg.project_root / "data/controls/standard_output/GOBLIN_SO_mapping.csv")
    mapping = mapping.loc[mapping["APPLY_IN_SO"] == "YES"].set_index("MODEL_VARIABLE")
    cohorts = [c for c in (*FINAL_21_COHORTS, *GOBLIN_SHEEP_10) if c in mapping.index]
    region_code = so["FADN_REGION"].astype(str).str.extract(r"(38[12])")[0]
    recomputed = sum(
        so[c] * np.where(region_code == "381", mapping.at[c, "SOC_EUR_381"], mapping.at[c, "SOC_EUR_382"])
        for c in cohorts
    )
    diff = float((recomputed - so["SO_LIVESTOCK_2020_EUR"]).abs().max())
    check("F", "SO_LIVESTOCK = sum(cohort head x IFS 2020 coefficient by region)", diff < 1.0,
          f"max abs diff EUR {diff:.3f}; {len(cohorts)} of 31 cohorts valued")
    diff = float((so[list(SO_PARTS)].sum(axis=1) - so["SO_LIVESTOCK_2020_EUR"]).abs().max())
    check("F", "livestock SO components add to SO_LIVESTOCK", diff < 1.0, f"max abs diff EUR {diff:.3f}")
    total = so[["SO_LIVESTOCK_2020_EUR", "SO_CEREALS_2020_EUR", "SO_OTHER_CROPS_2020_EUR"]].sum(axis=1)
    diff = float((total - so["SO_COVERED_TOTAL_2020_EUR"]).abs().max())
    check("F", "SO_COVERED_TOTAL = livestock + cereals + other crops", diff < 1.0, f"max abs diff EUR {diff:.3f}")

    # G. aggregation
    additive = [
        c for c in county.columns
        if c in so.columns and c not in ("YEAR", "County") and not c.startswith("AVERAGE") and "PER_HOLDING" not in c
    ]
    by_ed_county = so.groupby(["YEAR", "County"])[additive].sum().sort_index()
    ok = np.allclose(by_ed_county.to_numpy(), county.set_index(["YEAR", "County"]).sort_index()[additive].to_numpy(), rtol=1e-9, atol=1e-6)
    check("G", "county table = sum of EDs (every additive column)", bool(ok), f"{len(additive)} columns")
    by_ed_nat = so.groupby("YEAR")[additive].sum().sort_index()
    ok = np.allclose(by_ed_nat.to_numpy(), national.set_index("YEAR").sort_index()[additive].to_numpy(), rtol=1e-9, atol=1e-6)
    check("G", "national table = sum of EDs", bool(ok))
    for name, frame in catchments.items():
        cols = [c for c in ("TOTAL_CATTLE", "TOTAL_SHEEP", "AREA_FARMED", "SO_COVERED_TOTAL_2020_EUR") if c in frame.columns]
        ok = np.allclose(frame.groupby("YEAR")[cols].sum().sort_index().to_numpy(), by_ed_nat[cols].to_numpy(), rtol=1e-8)
        check("G", f"{name} catchments sum to the national total", bool(ok), ", ".join(cols))
    gap = float((county["AVERAGE_SIZE_OF_HOLDINGS"] - county["AREA_FARMED"] / county["AGRICULTURAL_HOLDINGS"]).abs().max())
    check("G", "county average holding size = area / holdings", gap < 0.05, f"max gap {gap:.3f} ha")

    # H. completeness
    for name, frame in (("CSO 13", c13), ("GOBLIN 31", g31)):
        present = {"CATTLE_PROVENANCE", "SHEEP_PROVENANCE"} <= set(frame.columns)
        labelled = present and bool(
            frame.loc[frame["YEAR"] == KNOWN_YEAR, ["CATTLE_PROVENANCE", "SHEEP_PROVENANCE"]]
            .eq("CSO_ED_2020_PUBLISHED_UNCHANGED").all().all()
            and not frame.loc[frame["YEAR"] != KNOWN_YEAR, "CATTLE_PROVENANCE"]
            .eq("CSO_ED_2020_PUBLISHED_UNCHANGED").any()
        )
        check("H", f"{name} panel labels published 2020 rows and reconstructed years", labelled)
    key_cols = [*CSO_CATTLE_9, *CSO_SHEEP_4, "TOTAL_CATTLE", "TOTAL_SHEEP", "AREA_FARMED", "AGRICULTURAL_HOLDINGS"]
    check("H", "no missing counts, land or holdings", bool(c13[key_cols].notna().all().all()))
    with_holdings = so.loc[so["AGRICULTURAL_HOLDINGS"] > 0, "AVERAGE_AGE_OF_HOLDER"]
    check("H", "holder age present wherever holdings > 0", bool(with_holdings.notna().all()),
          f"{int(with_holdings.isna().sum())} missing")

    return pd.DataFrame(rows)
