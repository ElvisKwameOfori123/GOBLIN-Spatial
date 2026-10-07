#!/usr/bin/env python
"""GOBLIN-Spatial Paper 1: figures, tables and map layers from one frozen build.

Run from the repository root after the release build:

    python scripts/build_historical_release.py
    python scripts/paper1_figures.py

Story line of the Results, one figure per step:

    F1  Methods     evidence hierarchy and workflow (census preparation to reporting)
    F2  3.1         validation: is the reconstruction trustworthy?
    F3  3.2         scale and time: national change 2015-2025 and where it happened
    F4  3.3         ED signatures: abundance is not system
    F5  3.4         observed local restructuring between the 2010 and 2020 censuses
    F6  3.5         catchments: WFD planning units hide ED variation
    F7  3.6         illustrative adjustment: where a national change lands

Tables (main text T1-T6, supplementary S1-S5) go to one formatted workbook and to
CSV; map layers go to one GeoPackage; a manifest records the model commit and
every setting. The script reads the release bundle and the Stage 00 audit tables
and never changes the scientific state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ======================================================================================
# 0  CONFIG
# ======================================================================================

CONFIG = {
    "bundle_dir": "reporting/report_data/historical",
    "stage00_dir": "data/inputs/baseline/census_reconciliation",
    "ava42": "data/inputs/baseline/00_CSO_AVA42_Livestock_ED_2000_2010_2020.csv",
    "ed_geometry": "data/inputs/spatial/ED_Boundaries_Frozen.gpkg",
    "wfd_geometry": "data/inputs/spatial/WFD_Catchments_Frozen.gpkg",
    "crosswalk": "data/processed/ed_wfd_catchment_crosswalk.csv",
    "output_dir": "reporting/paper1",
    "crs": 2157,
    "simplify_ed_m": 25.0,
    "simplify_catchment_m": 60.0,
    "base_year": 2020,
    "start_year": 2015,
    "end_year": 2025,
    # Ratio indicators are shown only where the denominator is meaningful.
    "min_adult_cows": 10,
    "min_cattle": 50,
    "min_farmed_ha": 50,
    # Livestock-system typology, applied in this order (first match wins).
    "typology": {
        "minimal_lu": 20.0,
        "sheep_led_share": 0.5,
        "follower_rearing_ratio": 3.0,
        "dairy_centred_pct": 70.0,
        "suckler_centred_pct": 30.0,
    },
    "stable_herd_pct": 5.0,
    "material_shift_pp": 10.0,
    "share_breaks": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    "lu_breaks": [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    "dpi": 600,
}
FIG_W = 7.48  # 190 mm, Elsevier double column
TYPE_ORDER = ["Dairy-centred", "Mixed breeding", "Suckler-centred", "Follower-rearing", "Sheep-led", "Minimal livestock"]

# ---- one colour per livestock system, used in every map, line and bar -------------------
C = {
    "dairy": "#1f5f8b",
    "dxb": "#8e7cc3",
    "suckler": "#c0392b",
    "follower": "#e39b2d",
    "sheep": "#5a8f3c",
    "mixed": "#8fb9d9",
    "minimal": "#dcdcdc",
    "so": "#b8860b",
    "total": "#333333",
    "grey": "#7f7f7f",
    "nodata": "#ececec",
    "county": "#5a5a5a",
    "catchment": "#1a1a1a",
}
TYPE_COLOURS = {
    "Dairy-centred": C["dairy"], "Mixed breeding": C["mixed"], "Suckler-centred": C["suckler"],
    "Follower-rearing": C["follower"], "Sheep-led": C["sheep"], "Minimal livestock": C["minimal"],
}
ORIGIN = {"DxD": C["dairy"], "DxB": C["dxb"], "BxB": C["suckler"]}
DIVERGING = "RdBu_r"  # one diverging palette for every signed difference

# CSO livestock-unit convention (as used for the published 2020 LSU screen).
LU = {"DAIRY_COW": 1.0, "OTHER_COW": 0.8, "BULLS": 1.0, "CATTLE_MALE_UNDER_1": 0.4,
      "CATTLE_FEMALE_UNDER_1": 0.4, "CATTLE_MALE_1_2": 0.7, "CATTLE_FEMALE_1_2": 0.7,
      "CATTLE_MALE_2_PLUS": 1.0, "CATTLE_FEMALE_2_PLUS": 0.8}
SHEEP_LU = 0.1

# ======================================================================================
# helpers
# ======================================================================================


def style():
    import matplotlib as mpl

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
        "font.size": 7.5,
        "axes.titlesize": 8,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 4,
        "axes.labelsize": 7.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 6.8,
        "legend.frameon": False,
        "figure.dpi": 110,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
        "pdf.fonttype": 42,
    })


def title(ax, letter, text):
    ax.set_title(f"{letter}   {text}", loc="left", fontsize=8, fontweight="bold")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ratio(num, den, scale=1.0, min_den=0.0):
    num = pd.to_numeric(num, errors="coerce").astype(float)
    den = pd.to_numeric(den, errors="coerce").astype(float)
    out = pd.Series(np.nan, index=num.index)
    ok = den > max(min_den, 0)
    out[ok] = scale * num[ok] / den[ok]
    return out


def spearman(a, b) -> float:
    a, b = pd.Series(np.asarray(a, float)), pd.Series(np.asarray(b, float))
    ok = a.notna() & b.notna()
    return float(np.corrcoef(a[ok].rank(), b[ok].rank())[0, 1])


def livestock_units(frame: pd.DataFrame) -> pd.Series:
    lu = sum(frame[c] * w for c, w in LU.items())
    return lu + SHEEP_LU * frame["TOTAL_SHEEP"]


def save(fig, out: Path, name: str, written: list):
    import matplotlib.pyplot as plt

    for ext in ("png", "pdf"):
        path = out / "figures" / f"{name}.{ext}"
        fig.savefig(path, dpi=CONFIG["dpi"] if ext == "png" else None, facecolor="white")
        written.append(path)
    plt.close(fig)
    print(f"  figure  {name}")


def map_axes(ax):
    ax.set_axis_off()
    ax.set_aspect("equal")


def scale_bar(ax, km=50, loc=(0.74, 0.02)):
    """Plain 50 km bar in map units (EPSG:2157 metres)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + loc[0] * (x1 - x0)
    y = y0 + loc[1] * (y1 - y0)
    ax.plot([x, x + km * 1000], [y, y], color="black", lw=1.4, solid_capstyle="butt")
    ax.text(x + km * 500, y + 0.015 * (y1 - y0), f"{km} km", ha="center", va="bottom", fontsize=6)


def classed_cmap(colour, n, light=0.07, dark=0.9):
    import matplotlib.colors as mcolors

    ramp = mcolors.LinearSegmentedColormap.from_list("r", ["#ffffff", colour, "#08172a"])
    return mcolors.ListedColormap([ramp(x) for x in np.linspace(light, dark, n)])


def classed(colour, breaks):
    import matplotlib.colors as mcolors

    cmap = classed_cmap(colour, len(breaks) - 1)
    return cmap, mcolors.BoundaryNorm(breaks, cmap.N)


def diverging_norm(values, q=0.98, floor=1.0):
    import matplotlib.colors as mcolors

    v = pd.to_numeric(pd.Series(np.ravel(values)), errors="coerce").dropna()
    lim = float(np.nanquantile(np.abs(v), q)) if len(v) else floor
    return mcolors.TwoSlopeNorm(vmin=-max(lim, floor), vcenter=0.0, vmax=max(lim, floor))


def choropleth(ax, gdf, column=None, *, cmap=None, norm=None, colours=None, outlines=(), lw=0.0):
    """Every map: no-data grey first, then values or categories, then outline layers."""
    if column is None:
        gdf.plot(ax=ax, color=C["nodata"], linewidth=0)
    else:
        missing = gdf[gdf[column].isna()]
        if len(missing):
            missing.plot(ax=ax, color=C["nodata"], linewidth=0)
        present = gdf[gdf[column].notna()]
        if colours is not None:
            present.plot(ax=ax, color=present[column].map(colours).fillna(C["nodata"]), linewidth=lw, edgecolor="white")
        elif len(present):
            present.plot(ax=ax, column=column, cmap=cmap, norm=norm, linewidth=lw, edgecolor="white")
    for layer, colour, width in outlines:
        layer.boundary.plot(ax=ax, color=colour, linewidth=width)
    map_axes(ax)
    return ax


def colorbar(fig, ax, cmap, norm, label, extend="neither", ticks=None, shrink=0.8):
    import matplotlib.cm as cm

    cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, orientation="horizontal",
                      fraction=0.045, pad=0.02, aspect=28, shrink=shrink, extend=extend, ticks=ticks)
    cb.set_label(label, fontsize=7)
    cb.ax.tick_params(labelsize=6.5, width=0.5, length=2)
    cb.outline.set_visible(False)
    return cb


def git_info(root: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    return {"commit": run("rev-parse", "HEAD"), "tags": run("tag", "--points-at", "HEAD"),
            "describe": run("describe", "--tags", "--always"), "dirty": bool(run("status", "--porcelain"))}


# ======================================================================================
# 1  LOAD
# ======================================================================================


def load(root: Path) -> dict:
    b = root / CONFIG["bundle_dir"]
    if not (b / "ed_year.parquet").exists():
        raise FileNotFoundError(f"No results bundle at {b}; run scripts/build_historical_release.py first")
    names = [
        "ed_year", "county_year", "wfd_catchment_year", "national_year", "validation_summary",
        "validation_detail_sheep_composition_holdout_2022", "validation_detail_dafm_county_sheep_diagnostics",
        "validation_detail_temporal_rank_stability", "concentration_2020", "matched_pairs_2020",
        "baseline_coherence_audit", "information_geography_2020", "livestock_signature",
        "wfd_signature_spread",
    ]
    data = {n: pd.read_parquet(b / f"{n}.parquet") for n in names}
    data["ed_year"]["CSOED"] = data["ed_year"]["CSOED"].astype(str)
    s = root / CONFIG["stage00_dir"]
    for n in ("state_closure", "shrinkage_selection", "temporal_holdout_2010_2020", "robustness_variants",
              "county_closure", "filled_cells", "coverage_outside_model"):
        data[f"s00_{n}"] = pd.read_csv(s / f"{n}.csv", dtype={"KEY": str})

    # Guard: the bundle must be built from the committed Stage 00 inputs.
    closure = data["s00_state_closure"].set_index(["YEAR", "VARIABLE"])
    nat = data["national_year"].set_index("YEAR").loc[CONFIG["base_year"]]
    for column in ("DAIRY_COW", "OTHER_COW", "TOTAL_CATTLE", "TOTAL_SHEEP"):
        expected = int(closure.loc[(CONFIG["base_year"], column), "MODEL_UNIVERSE_TOTAL"])
        if int(round(nat[column])) != expected:
            raise AssertionError(f"bundle 2020 {column} {int(nat[column]):,} differs from Stage 00 {expected:,}: "
                                 "rebuild with scripts/build_historical_release.py")
    audit = data["baseline_coherence_audit"]
    if not bool(audit["PASS"].all()):
        raise AssertionError("baseline_coherence_audit has failing checks; fix the build before plotting")
    data["audit_pass"] = f"{int(audit['PASS'].sum())}/{len(audit)}"
    print(f"1 LOAD      bundle {len(names)} tables + Stage 00 audit; coherence {data['audit_pass']} PASS")
    return data


# ======================================================================================
# 2  GEOMETRY
# ======================================================================================


def geometry(root: Path, ed_year: pd.DataFrame) -> dict:
    import geopandas as gpd
    import shapely

    from goblin_spatial.aggregation.catchments import _normalise_wfd_id, canonical_wfd_catchment_name
    from goblin_spatial.soil.overlay import canonical_csoed, select_baseline_ed_geometries

    crs = CONFIG["crs"]
    keys = ed_year[["CSOED"]].drop_duplicates()
    raw = gpd.read_file(root / CONFIG["ed_geometry"])
    eds = select_baseline_ed_geometries(keys, raw, baseline_key="CSOED", ed_key="CSOED")
    eds = gpd.GeoDataFrame(eds[["CSOED_CANONICAL", "geometry"]], geometry="geometry", crs=raw.crs).to_crs(crs)
    eds["geometry"] = eds.geometry.make_valid()
    eds = eds.dissolve(by="CSOED_CANONICAL", as_index=False)
    lookup = ed_year.drop_duplicates("CSOED")[["CSOED", "County", "EDNAME"]].copy()
    lookup["CSOED_CANONICAL"] = lookup["CSOED"].map(canonical_csoed)
    eds = eds.merge(lookup, on="CSOED_CANONICAL", how="inner", validate="one_to_one")
    if len(eds) != len(keys):
        raise AssertionError(f"matched {len(eds)} ED geometries for {len(keys)} model EDs")

    def simplify(gdf, tol):
        out = gdf.copy()
        out["geometry"] = shapely.coverage_simplify(out.geometry.values, tol) if hasattr(shapely, "coverage_simplify") \
            else out.geometry.simplify(tol, preserve_topology=True)
        out["geometry"] = out.geometry.make_valid()
        return out

    eds_s = simplify(eds, CONFIG["simplify_ed_m"])
    county = eds_s.dissolve(by="County", as_index=False)[["County", "geometry"]]
    ireland = gpd.GeoDataFrame({"NAME": ["Ireland"]}, geometry=[eds_s.union_all()], crs=crs)

    wfd = gpd.read_file(root / CONFIG["wfd_geometry"]).to_crs(crs)
    wfd["WFD_CATCHMENT_ID"] = wfd["CATCHMENTI"].map(_normalise_wfd_id)
    wfd["WFD_CATCHMENT"] = wfd["NAME"].map(canonical_wfd_catchment_name)
    wfd["geometry"] = wfd.geometry.make_valid()
    wfd = wfd.dissolve(by=["WFD_CATCHMENT_ID", "WFD_CATCHMENT"], as_index=False)
    wfd = simplify(wfd[["WFD_CATCHMENT_ID", "WFD_CATCHMENT", "geometry"]], CONFIG["simplify_catchment_m"])
    # Catchment IDs are always included because several official names repeat.
    wfd["LABEL"] = [
        f"{i} {n}" for n, i in zip(wfd["WFD_CATCHMENT"], wfd["WFD_CATCHMENT_ID"])
    ]
    # Clip catchments to the State for display (several cross the border).
    wfd_state = gpd.clip(wfd, ireland)

    xw = pd.read_csv(root / CONFIG["crosswalk"], dtype={"CSOED": str, "WFD_CATCHMENT_ID": str})
    dominant = xw.sort_values("ED_CATCHMENT_WEIGHT", ascending=False).drop_duplicates("CSOED")
    eds_s = eds_s.merge(dominant[["CSOED", "WFD_CATCHMENT_ID"]], on="CSOED", how="left")
    print(f"2 GEOMETRY  EDs {len(eds_s):,}, counties {len(county)}, WFD catchments {len(wfd)}")
    return {"ed": eds_s, "county": county, "ireland": ireland, "wfd": wfd, "wfd_state": wfd_state, "crosswalk": xw}


# ======================================================================================
# 3  DERIVE
# ======================================================================================


def derive(data: dict) -> dict:
    t = CONFIG["typology"]
    ed = data["ed_year"].copy()
    adults = ed["dairy_cows"] + ed["suckler_cows"]
    ok_adult = adults >= CONFIG["min_adult_cows"]
    ed["LU"] = livestock_units(ed)
    ed["LU_PER_HA"] = ratio(ed["LU"], ed["AREA_FARMED"], min_den=CONFIG["min_farmed_ha"] - 1e-9)
    ed["DAIRY_SHARE_PLOT"] = ed["DAIRY_SHARE_ADULT_PCT"].where(ok_adult)
    ed["FOLLOWERS_PER_COW_PLOT"] = ed["FOLLOWER_TO_ADULT_RATIO"].where(ok_adult)
    sheep_lu = SHEEP_LU * ed["TOTAL_SHEEP"]
    cond = [
        ed["LU"] < t["minimal_lu"],
        ratio(sheep_lu, ed["LU"]).fillna(0) >= t["sheep_led_share"],
        (~ok_adult) | (ed["FOLLOWER_TO_ADULT_RATIO"] >= t["follower_rearing_ratio"]),
        ed["DAIRY_SHARE_ADULT_PCT"] >= t["dairy_centred_pct"],
        ed["DAIRY_SHARE_ADULT_PCT"] <= t["suckler_centred_pct"],
    ]
    ed["SYSTEM_TYPE"] = np.select(cond, ["Minimal livestock", "Sheep-led", "Follower-rearing", "Dairy-centred",
                                         "Suckler-centred"], default="Mixed breeding")
    y0, yb, y1 = CONFIG["start_year"], CONFIG["base_year"], CONFIG["end_year"]
    e20 = ed.loc[ed["YEAR"] == yb].copy()

    typology = (e20.groupby("SYSTEM_TYPE")
                .agg(EDS=("CSOED", "size"), CATTLE=("TOTAL_CATTLE", "sum"), DAIRY_COWS=("dairy_cows", "sum"),
                     SUCKLER_COWS=("suckler_cows", "sum"), FOLLOWERS=("FOLLOWER_TOTAL", "sum"),
                     SHEEP=("TOTAL_SHEEP", "sum"), LU=("LU", "sum"), FARMED_HA=("AREA_FARMED", "sum"),
                     SO_EUR=("SO_COVERED_TOTAL_2020_EUR", "sum"))
                .reindex(TYPE_ORDER).fillna(0))
    for col in ("EDS", "FARMED_HA", "CATTLE", "LU", "SO_EUR"):
        typology[f"{col}_SHARE_PCT"] = 100 * typology[col] / typology[col].sum()
    typology["LU_PER_HA"] = typology["LU"] / typology["FARMED_HA"]
    typology = typology.reset_index().rename(columns={"index": "SYSTEM_TYPE"})

    # Typology sensitivity: shift every class break by +/-10 (dairy share) and +/-1 (ratio).
    sens = []
    for d_shift, r_shift, label in [(0, 0, "central"), (-10, 0, "dairy/suckler cut -10 pp"),
                                    (10, 0, "dairy/suckler cut +10 pp"), (0, -1, "follower ratio -1"),
                                    (0, 1, "follower ratio +1")]:
        c2 = [
            e20["LU"] < t["minimal_lu"],
            ratio(SHEEP_LU * e20["TOTAL_SHEEP"], e20["LU"]).fillna(0) >= t["sheep_led_share"],
            (e20["dairy_cows"] + e20["suckler_cows"] < CONFIG["min_adult_cows"])
            | (e20["FOLLOWER_TO_ADULT_RATIO"] >= t["follower_rearing_ratio"] + r_shift),
            e20["DAIRY_SHARE_ADULT_PCT"] >= t["dairy_centred_pct"] + d_shift,
            e20["DAIRY_SHARE_ADULT_PCT"] <= t["suckler_centred_pct"] + d_shift,
        ]
        typ = pd.Series(np.select(c2, ["Minimal livestock", "Sheep-led", "Follower-rearing", "Dairy-centred",
                                       "Suckler-centred"], default="Mixed breeding"), index=e20.index)
        so = e20.groupby(typ)["SO_COVERED_TOTAL_2020_EUR"].sum()
        n = typ.value_counts()
        for k in TYPE_ORDER:
            sens.append({"VARIANT": label, "SYSTEM_TYPE": k, "EDS_SHARE_PCT": 100 * n.get(k, 0) / len(typ),
                         "SO_SHARE_PCT": 100 * so.get(k, 0) / so.sum()})
    typology_sensitivity = pd.DataFrame(sens)

    nat = data["national_year"].set_index("YEAR")
    nat_lu = ed.groupby("YEAR")["LU"].sum()
    items = {
        "Total cattle (head)": nat["TOTAL_CATTLE"], "Dairy cows (head)": nat["dairy_cows"],
        "Suckler cows (head)": nat["suckler_cows"], "DxD followers (head)": nat["DXD_FOLLOWERS"],
        "DxB followers (head)": nat["DXB_FOLLOWERS"], "BxB followers (head)": nat["BXB_FOLLOWERS"],
        "Total sheep (head)": nat["TOTAL_SHEEP"], "Grazing livestock units (LU)": nat_lu,
        "Farmed area (ha)": nat["AREA_FARMED"], "Standard Output (EUR m, 2020 prices)": nat["SO_COVERED_TOTAL_2020_EUR"] / 1e6,
    }
    national_change = pd.DataFrame({
        "INDICATOR": list(items),
        str(y0): [float(s[y0]) for s in items.values()],
        str(yb): [float(s[yb]) for s in items.values()],
        str(y1): [float(s[y1]) for s in items.values()],
    })
    national_change[f"CHANGE_{y0}_{y1}_PCT"] = 100 * (national_change[str(y1)] / national_change[str(y0)] - 1)

    w = data["wfd_catchment_year"].copy()
    w["WFD_CATCHMENT_ID"] = w["WFD_CATCHMENT_ID"].astype(str)
    w["LU"] = livestock_units(w)
    w["LU_PER_HA"] = ratio(w["LU"], w["AREA_FARMED"])
    w["CATTLE_PER_HA"] = ratio(w["TOTAL_CATTLE"], w["AREA_FARMED"])
    w["FOLLOWERS_PER_ADULT_COW"] = ratio(w["FOLLOWER_TOTAL"], w["ADULT_COWS"])
    w["DXB_SHARE_FOLLOWERS_PCT"] = ratio(w["DXB_FOLLOWERS"], w["FOLLOWER_TOTAL"], 100)
    w["BXB_SHARE_FOLLOWERS_PCT"] = ratio(w["BXB_FOLLOWERS"], w["FOLLOWER_TOTAL"], 100)
    w["SO_PER_HA"] = ratio(w["SO_COVERED_TOTAL_2020_EUR"], w["AREA_FARMED"])
    print(f"3 DERIVE    typology {int((typology['EDS'] > 0).sum())} classes; national and catchment indicators")
    return {"ed": ed, "e20": e20, "typology": typology, "typology_sensitivity": typology_sensitivity,
            "national_change": national_change, "wfd": w}


def observed_restructuring(root: Path, data: dict, model_keys: set) -> pd.DataFrame:
    """ED change 2010-2020 using only cells published in BOTH censuses (raw AVA42)."""
    sys.path.insert(0, str(root / "src"))
    from goblin_spatial.preparation.census_suppression import load_ava42

    census, _ = load_ava42(root / CONFIG["ava42"])
    a, b = census[2010], census[2020]
    keep = a.index.isin(model_keys)
    p = pd.DataFrame({"KEY": a.index, "County": b["COUNTY"].reindex(a.index).to_numpy(),
                      "ED_NAME": a["ED_NAME"].to_numpy(),
                      "D10": a["D"].to_numpy(), "S10": a["S"].to_numpy(), "T10": a["T"].to_numpy(),
                      "D20": b["D"].reindex(a.index).to_numpy(), "S20": b["S"].reindex(a.index).to_numpy(),
                      "T20": b["T"].reindex(a.index).to_numpy()})[keep]
    p = p.dropna(subset=["D10", "S10", "T10", "D20", "S20", "T20"])  # published in both censuses
    p = p.loc[((p["D10"] + p["S10"]) >= CONFIG["min_adult_cows"]) & ((p["D20"] + p["S20"]) >= CONFIG["min_adult_cows"])
              & (p["T10"] > 0)].copy()
    p["DS10"] = 100 * p["D10"] / (p["D10"] + p["S10"])
    p["DS20"] = 100 * p["D20"] / (p["D20"] + p["S20"])
    p["DS_CHANGE_PP"] = p["DS20"] - p["DS10"]
    cty = p.groupby("County")[["D10", "S10", "D20", "S20"]].sum()
    cty["CTY_CHANGE_PP"] = 100 * (cty["D20"] / (cty["D20"] + cty["S20"]) - cty["D10"] / (cty["D10"] + cty["S10"]))
    p = p.merge(cty[["CTY_CHANGE_PP"]], left_on="County", right_index=True)
    p["RELATIVE_PP"] = p["DS_CHANGE_PP"] - p["CTY_CHANGE_PP"]
    p["CATTLE_CHANGE_PCT"] = 100 * (p["T20"] / p["T10"] - 1)
    p["STABLE_HERD_SHIFTED_SYSTEM"] = (p["CATTLE_CHANGE_PCT"].abs() <= CONFIG["stable_herd_pct"]) & \
        (p["DS_CHANGE_PP"].abs() >= CONFIG["material_shift_pp"])
    p["ZERO_DAIRY_BOTH"] = (p["D10"] == 0) & (p["D20"] == 0)
    return p


def temporal_points(root: Path, model_keys: set, crosswalk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """2010 within-county shares x 2020 county totals, on dairy cells published in both censuses."""
    from goblin_spatial.preparation.census_suppression import canonical_key, load_ava42

    census, _ = load_ava42(root / CONFIG["ava42"])
    a, b = census[2010]["D"], census[2020]["D"]
    keep = a.notna() & b.notna() & a.index.isin(model_keys)
    t = pd.DataFrame({"COUNTY": census[2020]["COUNTY"], "Y10": a, "Y20": b}).loc[keep]
    t["PRED"] = t["Y10"] / t.groupby("COUNTY")["Y10"].transform("sum") * t.groupby("COUNTY")["Y20"].transform("sum")
    t = t.dropna()
    xw = crosswalk.assign(KEY=crosswalk["CSOED"].map(canonical_key))
    m = t.join(xw.set_index("KEY")[["WFD_CATCHMENT_ID", "ED_CATCHMENT_WEIGHT"]], how="inner")
    g = m.assign(P=m["PRED"] * m["ED_CATCHMENT_WEIGHT"], O=m["Y20"] * m["ED_CATCHMENT_WEIGHT"]) \
        .groupby("WFD_CATCHMENT_ID")[["P", "O"]].sum()
    return t, g


# ======================================================================================
# 4  FIGURES
# ======================================================================================


def f1_workflow(out, written):
    """Methods: evidence hierarchy and processing chain."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, ax = plt.subplots(figsize=(FIG_W, 2.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(2, 43)
    ax.set_axis_off()

    def box(x, y, w, h, head, body, face, edge):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                    facecolor=face, edgecolor=edge, linewidth=0.8))
        ax.text(x + w / 2, y + h - 1.6, head, ha="center", va="top", fontsize=7.4, fontweight="bold")
        ax.text(x + w / 2, y + h - 4.6, body, ha="center", va="top", fontsize=6.3, linespacing=1.35)

    def arrow(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8,
                                     color="#555555", linewidth=0.8))

    top = 26
    box(1, top, 18, 16, "Observed evidence",
        "CSO Census of\nAgriculture 2000,\n2010, 2020 (ED)\nexact county and\nState totals", "#eef3f8", C["dairy"])
    box(22, top, 18, 16, "Stage 00",
        "published cells kept\nsuppressed cells filled\ninside exact county\ntotals; tested priors\nwith shrinkage", "#fdf2e3", C["follower"])
    box(43, top, 18, 16, "ED baseline",
        "2,857 EDs, 2015-2025\nannual CSO controls\n(AAA10, AAA09, AQA06)\n2010 to 2020 share path", "#eef3f8", C["dairy"])
    box(64, top, 16, 16, "Cohorts",
        "21 cattle cohorts\n(DxD, DxB, BxB)\n10 sheep cohorts\nDAFM/AIM priors", "#f3eff9", C["dxb"])
    box(83, top, 16, 16, "Indicators",
        "livestock signatures\nLU per ha\nStandard Output\n(2020 prices)", "#f1f6ec", C["sheep"])
    for x0, x1 in ((19.4, 21.6), (40.4, 42.6), (61.4, 63.6), (80.4, 82.6)):
        arrow(x0, top + 8, x1, top + 8)

    low = 5
    box(8, low, 25, 11.5, "Reporting geographies",
        "ED, county, 46 WFD catchments,\nnational; every table sums\nexactly from the ED state", "#f7f7f7", C["grey"])
    box(37.5, low, 25, 11.5, "Verification and evaluation",
        "47 coherence checks; withheld\n2022 sheep composition; hidden-\ncell and 2010-2020 holdout tests", "#f7f7f7", C["grey"])
    box(67, low, 25, 11.5, "Multiscale reporting",
        "county and WFD catchment views\nfrom the same ED baseline;\naggregate values plus ED spread", "#f7f7f7", C["grey"])
    arrow(91, top - 0.6, 79.5, low + 11.9)
    arrow(52, top - 0.6, 50, low + 11.9)
    arrow(52, top - 0.6, 20.5, low + 11.9)
    save(fig, out, "F1_workflow", written)


def f2_validation(data, tp, out, written):
    """3.1 Validation: holdout, temporal persistence, suppression test, continuity."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(FIG_W, 5.6), constrained_layout=True)

    ax = axes[0, 0]
    h = data["validation_detail_sheep_composition_holdout_2022"]
    groups = {"LOWLAND": ("Lowland", "#2b6c9e"), "LOWLAND_CROSS": ("Lowland cross", "#7fb2d6"),
              "MOUNTAIN": ("Mountain", "#3d7a2a"), "MOUNTAIN_CROSS": ("Mountain cross", "#9bc77f")}
    for key, (label, colour) in groups.items():
        g = h.loc[h["BREED_GROUP"] == key]
        ax.scatter(100 * g["OBSERVED_SHARE"], 100 * g["PREDICTED_SHARE"], s=6, color=colour, alpha=0.8,
                   linewidths=0, label=label)
    ax.plot([0, 90], [0, 90], color="#444444", lw=0.6, ls="--")
    rho = spearman(h["OBSERVED_SHARE"], h["PREDICTED_SHARE"])
    mae = float((100 * (h["PREDICTED_SHARE"] - h["OBSERVED_SHARE"])).abs().mean())
    ax.text(0.03, 0.97, f"ρ = {rho:.3f}   MAE = {mae:.1f} pp   n = {len(h)}", transform=ax.transAxes, va="top")
    ax.set(xlim=(0, 90), ylim=(0, 90), xlabel="Observed share, 2022 (%)", ylabel="Reconstructed share (%)")
    ax.legend(loc="lower right", handletextpad=0.1, markerscale=1.8)
    title(ax, "a", "Withheld 2022 sheep breed composition")

    ax = axes[0, 1]
    t, g = tp
    ax.scatter(t["Y20"], t["PRED"], s=3, color="#b0b0b0", alpha=0.6, linewidths=0, label=f"ED (n = {len(t):,})")
    ax.scatter(g["O"], g["P"], s=14, color=C["dairy"], edgecolors="white", linewidths=0.4,
               label=f"WFD catchment (n = {len(g)})")
    lim = [5, max(t["Y20"].max(), g["O"].max()) * 1.4]
    ax.plot(lim, lim, color="#444444", lw=0.6, ls="--")
    ed_err = 50 * (t["PRED"] - t["Y20"]).abs().sum() / t["Y20"].sum()
    w_err = 50 * (g["P"] - g["O"]).abs().sum() / g["O"].sum()
    ax.text(0.03, 0.97, f"misplaced: ED {ed_err:.1f}%, catchment {w_err:.1f}%\n"
            f"ρ: ED {spearman(t['Y20'], t['PRED']):.2f}, catchment {spearman(g['O'], g['P']):.3f}",
            transform=ax.transAxes, va="top")
    ax.set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="Census dairy cows, 2020",
           ylabel="Predicted from 2010 pattern")
    ax.legend(loc="lower right", handletextpad=0.1, markerscale=1.5)
    title(ax, "b", "2010 pattern carried to 2020 (published cells)")

    ax = axes[1, 0]
    s = data["s00_shrinkage_selection"]
    s = s.loc[s["YEAR"] == CONFIG["base_year"]]
    names = {"DAIRY_COW": ("Dairy cows", C["dairy"]), "OTHER_COW": ("Other cows", C["suckler"]),
             "TOTAL_CATTLE": ("Total cattle", C["total"]), "TOTAL_SHEEP": ("Sheep", C["sheep"])}
    for var, (label, colour) in names.items():
        g2 = s.loc[s["VARIABLE"] == var].sort_values("LAMBDA")
        ax.plot(g2["LAMBDA"], g2["MEAN_DISPLACED_PCT"], color=colour, lw=1.2, marker="o", ms=2.5, label=label)
        sel = g2.loc[g2["SELECTED"].astype(str).str.lower() == "true"]
        ax.scatter(sel["LAMBDA"], sel["MEAN_DISPLACED_PCT"], s=46, facecolors="none", edgecolors=colour, linewidths=1.0)
    ax.set(xticks=[0, 0.25, 0.5, 0.75, 1.0], xlabel="λ (0 = equal split, 1 = prior only)",
           ylabel="Hidden animals misplaced (%)", ylim=(0, None))
    ax.legend(loc="upper left", ncol=2)
    ax.text(0.98, 0.04, "circles: selected λ (one-SE rule)", transform=ax.transAxes, ha="right", fontsize=6.3,
            color="#555555")
    title(ax, "c", "Suppressed cells: hidden-cell test, 2020")

    ax = axes[1, 1]
    r = data["validation_detail_temporal_rank_stability"]
    lines = {"TOTAL_CATTLE": ("Total cattle", C["total"]), "TOTAL_SHEEP": ("Total sheep", C["sheep"]),
             "SIG_DAIRY_SHARE_ADULT_COWS": ("Dairy share", C["dairy"]),
             "SIG_FOLLOWERS_PER_ADULT_COW": ("Followers per cow", C["follower"]),
             "SIG_DXB_SHARE_ORIGIN_FOLLOWERS": ("DxB share", C["dxb"])}
    for key, (label, colour) in lines.items():
        g3 = r.loc[r["INDICATOR"] == key].sort_values("YEAR_TO")
        ax.plot(g3["YEAR_TO"], g3["SPEARMAN_RHO"], color=colour, lw=1.1, marker="o", ms=2, label=label)
    ax.axvline(2020, color="#999999", lw=0.5, ls=":")
    ax.text(2020.1, 0.9893, "census year", fontsize=6, color="#777777")
    ax.set(ylim=(0.989, 1.0005), xticks=range(2016, 2026, 2), xlabel="Year (compared with previous year)",
           ylabel="ED rank correlation (ρ)")
    ax.legend(loc="lower left", ncol=2)
    title(ax, "d", "Year-to-year continuity of ED ranks")
    save(fig, out, "F2_validation", written)


def f3_scale_time(data, geo, out, written):
    """3.2 National change 2015-2025 and where it happened (county controls)."""
    import matplotlib.pyplot as plt

    y0, y1 = CONFIG["start_year"], CONFIG["end_year"]
    nat = data["national_year"].set_index("YEAR")
    fig = plt.figure(figsize=(FIG_W, 5.9), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[0.8, 1.0])
    ax = fig.add_subplot(gs[0, 0])
    series = [("Dairy cows", "dairy_cows", C["dairy"]), ("Suckler cows", "suckler_cows", C["suckler"]),
              ("Total cattle", "TOTAL_CATTLE", C["total"]), ("Total sheep", "TOTAL_SHEEP", C["sheep"]),
              ("Standard Output", "SO_COVERED_TOTAL_2020_EUR", C["so"])]
    ends = []
    for label, col, colour in series:
        idx = 100 * nat[col] / nat.loc[y0, col]
        ax.plot(nat.index, idx, color=colour, lw=1.4)
        ends.append([idx.iloc[-1], f"{label} {idx.iloc[-1] - 100:+.0f}%", colour])
    ends.sort(key=lambda e: e[0])
    for i in range(1, len(ends)):  # keep end labels at least 3.2 index points apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 3.2)
    for y, text, colour in ends:
        ax.text(y1 + 0.25, y, text, color=colour, va="center", fontsize=6.6)
    ax.axhline(100, color="#999999", lw=0.5, ls=":")
    ax.set(xlim=(y0, y1 + 3.6), xticks=range(y0, y1 + 1, 2), ylabel=f"Index ({y0} = 100)")
    ax.spines["bottom"].set_bounds(y0, y1)
    title(ax, "a", "National herd and output, 2015-2025")

    ax = fig.add_subplot(gs[0, 1])
    comp = nat[["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]]
    comp = 100 * comp.div(comp.sum(axis=1), axis=0)
    ax.stackplot(comp.index, comp.T.values, colors=[ORIGIN["DxD"], ORIGIN["DxB"], ORIGIN["BxB"]], alpha=0.92,
                 edgecolor="white", linewidth=0.4)
    for label, lo, hi in [("DxD (dairy x dairy)", 0, comp["DXD_FOLLOWERS"]),
                          ("DxB (dairy x beef)", comp["DXD_FOLLOWERS"], comp["DXD_FOLLOWERS"] + comp["DXB_FOLLOWERS"]),
                          ("BxB (beef x beef)", comp["DXD_FOLLOWERS"] + comp["DXB_FOLLOWERS"], 100)]:
        lo_v = lo if np.isscalar(lo) else lo.iloc[len(comp) // 2]
        hi_v = hi if np.isscalar(hi) else hi.iloc[len(comp) // 2]
        ax.text(comp.index[len(comp) // 2], (lo_v + hi_v) / 2, label, ha="center", va="center", color="white",
                fontsize=6.8, fontweight="bold")
    ax.set(xlim=(y0, y1), ylim=(0, 100), xticks=range(y0, y1 + 1, 2), ylabel="Share of followers (%)")
    title(ax, "b", "Parental origin of young stock")

    cy = data["county_year"]
    for k, (col, colour, label, letter) in enumerate([
            ("dairy_cows", C["dairy"], "Dairy cows", "c"), ("suckler_cows", C["suckler"], "Suckler cows", "d")]):
        ax = fig.add_subplot(gs[1, k])
        a = cy.loc[cy["YEAR"] == y0].set_index("County")[col]
        b = cy.loc[cy["YEAR"] == y1].set_index("County")[col]
        chg = (100 * (b / a - 1)).rename("CHG").reset_index()
        g = geo["county"].merge(chg, on="County")
        norm = diverging_norm(np.r_[100 * (cy.loc[cy["YEAR"] == y1].set_index("County")["dairy_cows"]
                                            / cy.loc[cy["YEAR"] == y0].set_index("County")["dairy_cows"] - 1),
                                    100 * (cy.loc[cy["YEAR"] == y1].set_index("County")["suckler_cows"]
                                           / cy.loc[cy["YEAR"] == y0].set_index("County")["suckler_cows"] - 1)], q=1.0)
        choropleth(ax, g, "CHG", cmap=DIVERGING, norm=norm, lw=0.4)
        for _, row in g.iterrows():
            p = row.geometry.representative_point()
            ax.text(p.x, p.y, f"{row['CHG']:+.0f}", ha="center", va="center", fontsize=5.2,
                    color="white" if abs(row["CHG"]) > 0.55 * norm.vmax else "#222222")
        scale_bar(ax)
        colorbar(fig, ax, DIVERGING, norm, f"{label}: change {y0}-{y1} (%)")
        title(ax, letter, f"{label}, change by county")
    save(fig, out, "F3_scale_and_time", written)


def f4_signatures(derived, geo, out, written):
    """3.3 ED signatures: how much livestock versus what kind of system."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    eds = geo["ed"].merge(derived["e20"], on=["CSOED", "County"], how="left", suffixes=("", "_y"))
    county = (geo["county"], C["county"], 0.25)
    fig = plt.figure(figsize=(FIG_W, 8.6), constrained_layout=True)
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.5])
    ax_a, ax_b, ax_c = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_d = fig.add_subplot(gs[1, :2])
    ax_e = fig.add_subplot(gs[1:, 2])
    ax_f = fig.add_subplot(gs[2, :2])

    cmap, norm = classed(C["total"], CONFIG["lu_breaks"] + [6.0])
    choropleth(ax_a, eds, "LU_PER_HA", cmap=cmap, norm=norm, outlines=[county])
    cb = colorbar(fig, ax_a, cmap, norm, "LU per farmed ha", ticks=CONFIG["lu_breaks"] + [6.0])
    cb.ax.set_xticklabels([f"{v:g}" for v in CONFIG["lu_breaks"]] + [""])
    cb.ax.text(1.0, 0.5, " 3+", transform=cb.ax.transAxes, va="center", ha="left", fontsize=6.5)
    title(ax_a, "a", "How much: grazing density")

    cmap, norm = classed(C["dairy"], CONFIG["share_breaks"])
    choropleth(ax_b, eds, "DAIRY_SHARE_PLOT", cmap=cmap, norm=norm, outlines=[county])
    colorbar(fig, ax_b, cmap, norm, "Dairy share of adult cows (%)", ticks=[0, 20, 40, 60, 80, 100])
    title(ax_b, "b", "What kind: dairy orientation")

    eds["FPC"] = eds["FOLLOWERS_PER_COW_PLOT"]
    cmap, norm = classed(C["follower"], [0, 1, 1.5, 2, 2.5, 3, 5, 25])
    choropleth(ax_c, eds, "FPC", cmap=cmap, norm=norm, outlines=[county])
    colorbar(fig, ax_c, cmap, norm, "Followers per adult cow", ticks=[0, 1, 1.5, 2, 2.5, 3, 5, 25])
    title(ax_c, "c", "Rearing intensity")

    choropleth(ax_d, eds, "SYSTEM_TYPE", colours=TYPE_COLOURS, outlines=[county])
    ax_d.legend(handles=[Patch(color=TYPE_COLOURS[k], label=k) for k in TYPE_ORDER], loc="center right",
                bbox_to_anchor=(-0.04, 0.5), fontsize=6.8, handlelength=1.0, handleheight=1.0)
    scale_bar(ax_d, loc=(0.60, 0.02))
    title(ax_d, "d", "Livestock-system type, 2020")

    # e: equal herd, different system: cattle density against dairy share, coloured by type
    e = derived["e20"]
    sel = e["DAIRY_SHARE_PLOT"].notna() & e["LU_PER_HA"].notna()
    for k in TYPE_ORDER[:-1]:
        g = e.loc[sel & (e["SYSTEM_TYPE"] == k)]
        ax_e.scatter(g["DAIRY_SHARE_PLOT"], g["LU_PER_HA"], s=2.5, color=TYPE_COLOURS[k], alpha=0.65, linewidths=0)
    ax_e.set(xlim=(-2, 100), ylim=(0, 3.0), xlabel="Dairy share of adult cows (%)", ylabel="LU per farmed ha")
    band = e.loc[sel & e["LU_PER_HA"].between(1.4, 1.6)]
    ax_e.axhspan(1.4, 1.6, color="#bbbbbb", alpha=0.35, lw=0)
    ax_e.text(2, 1.62, f"{len(band):,} EDs at 1.4-1.6 LU/ha span\n"
              f"{band['DAIRY_SHARE_PLOT'].quantile(0.05):.0f}-{band['DAIRY_SHARE_PLOT'].quantile(0.95):.0f}% dairy (P5-P95)",
              fontsize=6.2, va="bottom")
    ax_e.text(0.02, 0.98, f"ρ = {spearman(e.loc[sel, 'DAIRY_SHARE_PLOT'], e.loc[sel, 'LU_PER_HA']):.2f}",
              transform=ax_e.transAxes, va="top")
    title(ax_e, "e", "Same density, different systems")

    t = derived["typology"].set_index("SYSTEM_TYPE")
    metrics = [("EDS_SHARE_PCT", "EDs"), ("FARMED_HA_SHARE_PCT", "Farmed area"), ("LU_SHARE_PCT", "Livestock units"),
               ("SO_EUR_SHARE_PCT", "Standard Output")]
    left = np.zeros(len(metrics))
    for k in TYPE_ORDER:
        vals = np.array([t.loc[k, m] for m, _ in metrics])
        ax_f.barh([lab for _, lab in metrics], vals, left=left, color=TYPE_COLOURS[k], edgecolor="white", linewidth=0.5,
                  height=0.7)
        for i, v in enumerate(vals):
            if v >= 5.5:
                ax_f.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=6.5,
                          color="white" if k in ("Dairy-centred", "Suckler-centred", "Sheep-led") else "#222222")
        left += vals
    ax_f.set(xlim=(0, 100), xlabel="Share of national total, 2020 (%)")
    ax_f.invert_yaxis()
    ax_f.spines["left"].set_visible(False)
    ax_f.tick_params(axis="y", length=0)
    title(ax_f, "f", "What each system type holds")
    save(fig, out, "F4_ed_signatures", written)


def f5_restructuring(p, geo, out, written):
    """3.4 Observed local restructuring between the 2010 and 2020 censuses."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    eds = geo["ed"].copy()
    from goblin_spatial.preparation.census_suppression import canonical_key

    eds["KEY"] = eds["CSOED"].map(canonical_key)
    eds = eds.merge(p[["KEY", "RELATIVE_PP", "STABLE_HERD_SHIFTED_SYSTEM"]], on="KEY", how="left")
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(FIG_W, 4.3), constrained_layout=True,
                                     gridspec_kw={"width_ratios": [1.1, 1]})
    norm = diverging_norm(p["RELATIVE_PP"], q=0.98)
    shifted = eds.loc[eds["STABLE_HERD_SHIFTED_SYSTEM"] == True]  # noqa: E712
    choropleth(ax_a, eds, "RELATIVE_PP", cmap=DIVERGING, norm=norm,
               outlines=[(geo["county"], C["county"], 0.25), (shifted, "black", 0.5)])
    ax_a.legend(handles=[Line2D([], [], color="black", lw=0.8, label="stable herd, shifted system"),
                         Line2D([], [], marker="s", ls="", color=C["nodata"], ms=6, label="not published in both censuses")],
                loc="lower left", fontsize=6.3, bbox_to_anchor=(0.0, -0.02))
    scale_bar(ax_a)
    colorbar(fig, ax_a, DIVERGING, norm, "ED minus county change in dairy share, 2010-2020 (pp)", extend="both")
    title(ax_a, "a", "Local departures from the county trend")

    q = p.loc[~p["ZERO_DAIRY_BOTH"]]
    x = q["CATTLE_CHANGE_PCT"].clip(-60, 60)
    ax_b.axvspan(-CONFIG["stable_herd_pct"], CONFIG["stable_herd_pct"], color="#f3f3f3", lw=0)
    ax_b.scatter(x, q["DS_CHANGE_PP"], s=3, color="#9a9a9a", alpha=0.5, linewidths=0)
    hl = q.loc[q["STABLE_HERD_SHIFTED_SYSTEM"]]
    ax_b.scatter(hl["CATTLE_CHANGE_PCT"], hl["DS_CHANGE_PP"], s=6, color=C["follower"], linewidths=0,
                 label=f"stable herd (±{CONFIG['stable_herd_pct']:.0f}%), shift ≥{CONFIG['material_shift_pp']:.0f} pp (n = {len(hl)})")
    ax_b.axhline(0, color="#555555", lw=0.5)
    ax_b.axvline(0, color="#555555", lw=0.5)
    ax_b.set(xlim=(-62, 62), xlabel="Change in total cattle, 2010-2020 (%, clipped at ±60)",
             ylabel="Change in dairy share of adult cows (pp)")
    ax_b.legend(loc="lower left", handletextpad=0.2, markerscale=1.5)
    up = int((q["DS_CHANGE_PP"] >= CONFIG["material_shift_pp"]).sum())
    ax_b.text(0.02, 0.98, f"EDs published in both censuses: {len(p):,}\n"
              f"(zero dairy in both, not shown: {int(p['ZERO_DAIRY_BOTH'].sum()):,})\n"
              f"dairy share up ≥{CONFIG['material_shift_pp']:.0f} pp: {up:,} EDs\n"
              f"ρ (herd change, system change) = {spearman(q['CATTLE_CHANGE_PCT'], q['DS_CHANGE_PP']):.2f}",
              transform=ax_b.transAxes, va="top", fontsize=6.4)
    title(ax_b, "b", "Herd size and herd system changed separately")
    save(fig, out, "F5_observed_restructuring_2010_2020", written)


def f6_catchments(data, derived, geo, out, written):
    """3.5 Catchments: WFD planning units and the ED variation they contain."""
    import matplotlib.pyplot as plt

    yb = CONFIG["base_year"]
    w = derived["wfd"]
    w20 = w.loc[w["YEAR"] == yb].copy()
    wfd = geo["wfd_state"].merge(w20, on=["WFD_CATCHMENT_ID", "WFD_CATCHMENT"], how="left")
    eds = geo["ed"].merge(derived["e20"], on=["CSOED", "County"], how="left", suffixes=("", "_y"))
    catch = (geo["wfd_state"], C["catchment"], 0.35)

    fig = plt.figure(figsize=(FIG_W, 8.3), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.05])
    ax_a, ax_b, ax_c = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_d = fig.add_subplot(gs[1, :])

    cmap, norm = classed(C["total"], CONFIG["lu_breaks"])
    choropleth(ax_a, wfd, "LU_PER_HA", cmap=cmap, norm=norm, lw=0.35)
    colorbar(fig, ax_a, cmap, norm, "LU per farmed ha", ticks=CONFIG["lu_breaks"])
    scale_bar(ax_a)
    title(ax_a, "a", "Catchment grazing density")

    cmap, norm = classed(C["dairy"], CONFIG["share_breaks"])
    choropleth(ax_b, wfd, "DAIRY_SHARE_ADULT_PCT", cmap=cmap, norm=norm, lw=0.35)
    title(ax_b, "b", "Catchment dairy share")
    choropleth(ax_c, eds, "DAIRY_SHARE_PLOT", cmap=cmap, norm=norm, outlines=[catch])
    title(ax_c, "c", "Same indicator by ED")
    colorbar(fig, [ax_b, ax_c], cmap, norm, f"Dairy share of adult cows, {yb} (%)", ticks=[0, 20, 40, 60, 80, 100],
             shrink=0.6)

    # d: catchment accounting value against the structural ED spread inside it.
    # The spread table uses all intersecting EDs with denominator x fractional
    # ED-catchment weights; no majority-inside threshold enters the calculation.
    spread = data["wfd_signature_spread"].loc[
        (data["wfd_signature_spread"]["YEAR"] == yb)
        & (data["wfd_signature_spread"]["SIGNATURE"] == "DAIRY_SHARE_ADULT_PCT")
    ].rename(
        columns={
            "ED_WEIGHTED_P10": "P10",
            "ED_WEIGHTED_P90": "P90",
            "INTERSECTING_EDS": "N",
        }
    )[["WFD_CATCHMENT_ID", "P10", "P90", "N"]].copy()
    labels = geo["wfd"][["WFD_CATCHMENT_ID", "LABEL"]]
    d = w20[["WFD_CATCHMENT_ID", "DAIRY_SHARE_ADULT_PCT", "LU_PER_HA"]].merge(spread, on="WFD_CATCHMENT_ID") \
        .merge(labels, on="WFD_CATCHMENT_ID").sort_values("DAIRY_SHARE_ADULT_PCT").reset_index(drop=True)
    x = np.arange(len(d))
    ax_d.vlines(x, d["P10"], d["P90"], color=C["mixed"], lw=3.2, label="ED range inside the catchment (P10-P90)")
    ax_d.scatter(x, d["DAIRY_SHARE_ADULT_PCT"], s=16, color=C["dairy"], zorder=3, edgecolors="white", linewidths=0.4,
                 label="catchment value")
    ax_d.set_xticks(x, d["LABEL"], rotation=90, fontsize=5.6)
    ax_d.set(xlim=(-0.8, len(d) - 0.2), ylim=(0, 100), ylabel="Dairy share of adult cows (%)")
    width = float((d["P90"] - d["P10"]).median())
    ax_d.text(0.01, 0.97, f"median P10-P90 width inside a catchment: {width:.0f} pp\n"
              f"(all intersecting EDs; adult-cow denominator × fractional catchment weight)", transform=ax_d.transAxes,
              va="top", fontsize=6.4)
    ax_d.legend(loc="lower right", ncol=2)
    title(ax_d, "d", "A catchment value hides the EDs inside it (sorted by catchment dairy share)")
    save(fig, out, "F6_catchments_wfd", written)
    return d


# ======================================================================================
# 5  TABLES AND EXPORT
# ======================================================================================


def tables(data, derived, restructuring, catchment_spread) -> dict:
    yb = CONFIG["base_year"]
    t1 = pd.DataFrame([
        ["CSO Census of Agriculture (AVA42), ED", "2000, 2010, 2020", "ED", "Anchor: published cells kept exactly; suppressed cells filled (Stage 00)"],
        ["CSO Census county totals (2010 Tables 8A/8B; 2020 Tables 4.2/4.4)", "2010, 2020", "County", "Exact control for suppressed cells"],
        ["CSO AAA10 cattle by county (June)", "2015-2025", "County", "Annual control; 2020 cross-check of census totals"],
        ["CSO AAA09 sheep by region (June)", "2015-2025", "7 regions", "Annual control; 2020 cross-check"],
        ["CSO AQA06 land use", "2015-2025", "Region", "Annual land control"],
        ["DAFM/AIM cattle profile", "2020", "ED", "Prior for suppressed cells and age/genetic composition; not a control"],
        ["DAFM sheep breed and county data", "2016-2025", "County", "Breed composition and within-region weighting; pattern diagnostic"],
        ["GOBLIN/COHORTS relationships", "2012-2020", "National", "Cohort structure (21 cattle, 10 sheep)"],
        ["IFS 2020 Standard Output coefficients", "2020", "Region", "Fixed-price production value"],
        ["Frozen ED and WFD geometry", "-", "ED, 46 catchments", "Reporting only"],
    ], columns=["SOURCE", "YEARS", "RESOLUTION", "ROLE"])

    v = data["validation_summary"]
    keep = v["EVIDENCE"].isin(["2022 sheep-composition holdout", "DAFM county sheep pattern fidelity",
                               "Adjacent-year continuity"])
    t2 = v.loc[keep].copy()
    th = data["s00_temporal_holdout_2010_2020"].copy()
    th_rows = []
    for _, r in th.iterrows():
        th_rows += [["2010 pattern carried to 2020 (published cells)", r["VARIABLE"], "ED misplaced share", r["ED_DISPLACED_PCT"], "%"],
                    ["2010 pattern carried to 2020 (published cells)", r["VARIABLE"], "WFD misplaced share", r["UNIT_DISPLACED_PCT"], "%"],
                    ["2010 pattern carried to 2020 (published cells)", r["VARIABLE"], "ED Spearman rho", r["ED_SPEARMAN"], "rho"]]
    s = data["s00_shrinkage_selection"]
    s = s.loc[s["SELECTED"].astype(str).str.lower() == "true"]
    for _, r in s.iterrows():
        th_rows.append(["Suppressed-cell hidden-cell test", f"{r['VARIABLE']} {r['YEAR']}",
                        f"misplaced share at selected lambda {r['LAMBDA']}", r["MEAN_DISPLACED_PCT"], "%"])
    th_rows.append(["Coherence audit", "all products", "checks passed", float(data["audit_pass"].split("/")[0]), "of " + data["audit_pass"].split("/")[1]])
    t2 = pd.concat([t2, pd.DataFrame(th_rows, columns=t2.columns)], ignore_index=True)

    t3 = derived["national_change"]
    t4 = derived["typology"][["SYSTEM_TYPE", "EDS", "EDS_SHARE_PCT", "FARMED_HA_SHARE_PCT", "LU_SHARE_PCT", "SO_EUR_SHARE_PCT",
                              "LU_PER_HA", "DAIRY_COWS", "SUCKLER_COWS", "FOLLOWERS", "SHEEP"]]

    w = derived["wfd"]
    w20 = w.loc[w["YEAR"] == yb]
    t5 = w20[["WFD_CATCHMENT_ID", "WFD_CATCHMENT", "AREA_FARMED", "TOTAL_CATTLE", "TOTAL_SHEEP", "LU_PER_HA",
              "DAIRY_SHARE_ADULT_PCT", "FOLLOWERS_PER_ADULT_COW", "DXB_SHARE_FOLLOWERS_PCT", "BXB_SHARE_FOLLOWERS_PCT",
              "SO_PER_HA"]].merge(catchment_spread[["WFD_CATCHMENT_ID", "P10", "P90", "N"]], on="WFD_CATCHMENT_ID", how="left") \
        .rename(columns={"P10": "ED_DAIRY_SHARE_P10", "P90": "ED_DAIRY_SHARE_P90", "N": "INTERSECTING_EDS"}) \
        .sort_values("WFD_CATCHMENT_ID")

    ig = data["information_geography_2020"].copy()
    rv = data["s00_robustness_variants"].set_index("METRIC")
    rb = rv.loc[rv.index.isin(ig["METRIC"])][["B_JOINT", "C_AIM_FIRST"]]
    ig = ig.merge(rb, left_on="METRIC", right_index=True, how="left")
    ig["RANGE_B_C"] = ig[["B_JOINT", "C_AIM_FIRST"]].min(axis=1).round(3).astype(str) + "-" + \
        ig[["B_JOINT", "C_AIM_FIRST"]].max(axis=1).round(3).astype(str)
    ig["NOTE"] = np.where(ig["METRIC"] == "UPLAND_SHARE_SHEEP_PCT", "by construction (county breed anchors)",
                          np.where(ig["METRIC"] == "FOLLOWER_TO_ADULT_RATIO", "sensitive to suppressed-cell inputs", ""))
    s1 = ig[["METRIC", "N_ED", "BETWEEN_COUNTY_SHARE_RB", "RANGE_B_C", "NOTE"]]

    cc = data["s00_county_closure"]
    s2 = cc.groupby(["YEAR", "VARIABLE"]).agg(BLANK_CELLS=("BLANK_CELLS", "sum"), HIDDEN_ANIMALS=("HIDDEN_TOTAL", "sum"),
                                              FILLED_OUTSIDE_MODEL=("FILLED_OUTSIDE_MODEL", "sum"),
                                              FILLED_ABOVE_COW_CAP=("FILLED_ABOVE_COW_CAP", "sum")).reset_index()
    lam = data["s00_shrinkage_selection"]
    lam = lam.loc[lam["SELECTED"].astype(str).str.lower() == "true", ["YEAR", "VARIABLE", "LAMBDA", "MEAN_DISPLACED_PCT"]]
    s2 = s2.merge(lam, on=["YEAR", "VARIABLE"], how="left")
    fc = data["s00_filled_cells"]
    werr = fc.groupby(["YEAR", "VARIABLE"]).apply(lambda g: (g["FILLED_VALUE"] * g["TEST_ERROR_PCT"]).sum()
                                                   / max(g["FILLED_VALUE"].sum(), 1), include_groups=False).rename("WEIGHTED_TEST_ERROR_PCT")
    s2 = s2.merge(werr.reset_index(), on=["YEAR", "VARIABLE"], how="left")

    out = {
        "T1_evidence_hierarchy": t1, "T2_validation": t2, "T3_national_change": t3, "T4_system_typology_2020": t4,
        "T5_catchment_signatures_2020": t5,
        "S1_where_variation_sits_RB": s1, "S2_census_reconciliation": s2,
        "S3_typology_sensitivity": derived["typology_sensitivity"],
        "S4_robustness_variants": data["s00_robustness_variants"],
        "S5_observed_restructuring_ed": restructuring,
        "S6_ed_typology_2020": derived["e20"][["CSOED", "County", "EDNAME", "SYSTEM_TYPE", "TOTAL_CATTLE", "TOTAL_SHEEP",
                                               "LU_PER_HA", "DAIRY_SHARE_ADULT_PCT", "FOLLOWER_TO_ADULT_RATIO"]],
        "S7_concentration_2020": data["concentration_2020"], "S8_matched_pairs_2020": data["matched_pairs_2020"],
    }
    return out


def write_tables(tabs: dict, out: Path, written: list):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    tdir = out / "tables"
    for name, frame in tabs.items():
        path = tdir / f"{name}.csv"
        frame.to_csv(path, index=False)
        written.append(path)
    book = tdir / "GOBLIN_Spatial_Paper1_tables.xlsx"
    with pd.ExcelWriter(book, engine="openpyxl") as xl:
        for name, frame in tabs.items():
            frame.to_excel(xl, sheet_name=name[:31], index=False)
            ws = xl.sheets[name[:31]]
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F5F8B")
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            ws.freeze_panes = "A2"
            for i, col in enumerate(frame.columns, start=1):
                width = min(48, max(10, int(frame[col].astype(str).str.len().quantile(0.9)) + 2, len(str(col)) * 0.9))
                ws.column_dimensions[get_column_letter(i)].width = width
                if pd.api.types.is_float_dtype(frame[col]):
                    for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                        row[0].number_format = "#,##0.00" if frame[col].abs().max() < 1000 else "#,##0"
    written.append(book)
    print(f"5 TABLES    {len(tabs)} tables -> {book.name}")


def write_layers(derived, geo, out: Path, written: list):
    gpkg = out / "maps" / "goblin_spatial_paper1_layers.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    ed = geo["ed"].merge(derived["e20"][["CSOED", "SYSTEM_TYPE", "LU_PER_HA", "DAIRY_SHARE_PLOT", "FOLLOWERS_PER_COW_PLOT",
                                         "CATTLE_PER_FARMED_HA", "SHEEP_PER_FARMED_HA",
                                         "GRASSLAND_SHARE_FARMED_PCT", "CEREAL_SHARE_FARMED_PCT",
                                         "SO_PER_FARMED_HA"]], on="CSOED", how="left")
    w20 = derived["wfd"].loc[derived["wfd"]["YEAR"] == CONFIG["base_year"]]
    wfd = geo["wfd_state"].merge(w20[["WFD_CATCHMENT_ID", "LU_PER_HA", "DAIRY_SHARE_ADULT_PCT", "FOLLOWERS_PER_ADULT_COW",
                                      "CATTLE_PER_FARMED_HA", "SHEEP_PER_FARMED_HA",
                                      "GRASSLAND_SHARE_FARMED_PCT", "CEREAL_SHARE_FARMED_PCT",
                                      "SO_PER_HA"]], on="WFD_CATCHMENT_ID", how="left")
    for layer, gdf in (("ed_2020", ed), ("county", geo["county"]), ("wfd_catchment_2020", wfd), ("ireland", geo["ireland"])):
        gdf.to_file(gpkg, layer=layer, driver="GPKG")
    written.append(gpkg)


def storyline(data, derived, restructuring, tp, spread) -> str:
    """Results skeleton with every number computed from this build (no hand-typed values)."""
    y0, yb, y1 = CONFIG["start_year"], CONFIG["base_year"], CONFIG["end_year"]
    h = data["validation_detail_sheep_composition_holdout_2022"]
    t, g = tp
    ed_err = 50 * (t["PRED"] - t["Y20"]).abs().sum() / t["Y20"].sum()
    w_err = 50 * (g["P"] - g["O"]).abs().sum() / g["O"].sum()
    sel = data["s00_shrinkage_selection"]
    sel = sel.loc[(sel["YEAR"] == yb) & (sel["SELECTED"].astype(str).str.lower() == "true")].set_index("VARIABLE")
    unshrunk = data["s00_shrinkage_selection"]
    unshrunk = unshrunk.loc[(unshrunk["YEAR"] == yb) & (unshrunk["LAMBDA"] == 1.0)].set_index("VARIABLE")
    r = data["validation_detail_temporal_rank_stability"]
    nat = data["national_year"].set_index("YEAR")
    chg = lambda c: 100 * (nat.loc[y1, c] / nat.loc[y0, c] - 1)
    f = nat[["DXD_FOLLOWERS", "DXB_FOLLOWERS", "BXB_FOLLOWERS"]]
    dxb0, dxb1 = 100 * f.loc[y0, "DXB_FOLLOWERS"] / f.loc[y0].sum(), 100 * f.loc[y1, "DXB_FOLLOWERS"] / f.loc[y1].sum()
    bxb0, bxb1 = 100 * f.loc[y0, "BXB_FOLLOWERS"] / f.loc[y0].sum(), 100 * f.loc[y1, "BXB_FOLLOWERS"] / f.loc[y1].sum()
    cy = data["county_year"]
    dc = 100 * (cy.loc[cy["YEAR"] == y1].set_index("County")["dairy_cows"] / cy.loc[cy["YEAR"] == y0].set_index("County")["dairy_cows"] - 1)
    typ = derived["typology"].set_index("SYSTEM_TYPE")
    e = derived["e20"]
    ts = derived["typology_sensitivity"]
    band = e.loc[e["LU_PER_HA"].between(1.4, 1.6) & e["DAIRY_SHARE_PLOT"].notna(), "DAIRY_SHARE_PLOT"]
    p = restructuring
    q = p.loc[~p["ZERO_DAIRY_BOTH"]]
    w20 = derived["wfd"].loc[derived["wfd"]["YEAR"] == yb]
    width = (spread["P90"] - spread["P10"])
    lines = [
        "# Paper 1 Results: storyline and numbers",
        "",
        f"Generated from this build (coherence audit {data['audit_pass']} PASS). Re-run the script and paste again if the build changes.",
        "",
        "## 3.1 Validation (Figure 2, Table 2)",
        f"- Withheld 2022 sheep breed composition: Spearman rho {spearman(h['OBSERVED_SHARE'], h['PREDICTED_SHARE']):.3f}, "
        f"MAE {(100 * (h['PREDICTED_SHARE'] - h['OBSERVED_SHARE'])).abs().mean():.1f} pp (n = {len(h)}).",
        f"- Carrying the 2010 ED pattern to 2020 county totals misplaces {ed_err:.1f}% of dairy cows across EDs but only "
        f"{w_err:.1f}% across WFD catchments (cells published in both censuses, n = {len(t):,} EDs).",
        f"- Suppressed census cells: shrinkage lowers the hidden-cell error for 2020 dairy cows from {unshrunk.loc['DAIRY_COW', 'MEAN_DISPLACED_PCT']:.1f}% "
        f"to {sel.loc['DAIRY_COW', 'MEAN_DISPLACED_PCT']:.1f}%, other cows {unshrunk.loc['OTHER_COW', 'MEAN_DISPLACED_PCT']:.1f}% to "
        f"{sel.loc['OTHER_COW', 'MEAN_DISPLACED_PCT']:.1f}%, total cattle {unshrunk.loc['TOTAL_CATTLE', 'MEAN_DISPLACED_PCT']:.1f}% to "
        f"{sel.loc['TOTAL_CATTLE', 'MEAN_DISPLACED_PCT']:.1f}%, sheep {unshrunk.loc['TOTAL_SHEEP', 'MEAN_DISPLACED_PCT']:.1f}% to "
        f"{sel.loc['TOTAL_SHEEP', 'MEAN_DISPLACED_PCT']:.1f}%.",
        f"- Year-to-year ED rank correlation never falls below {r['SPEARMAN_RHO'].min():.3f} for any indicator.",
        "",
        "## 3.2 Scale and time (Figure 3, Table 3)",
        f"- {y0}-{y1}: dairy cows {chg('dairy_cows'):+.0f}%, suckler cows {chg('suckler_cows'):+.0f}%, total cattle "
        f"{chg('TOTAL_CATTLE'):+.0f}%, sheep {chg('TOTAL_SHEEP'):+.0f}%, Standard Output {chg('SO_COVERED_TOTAL_2020_EUR'):+.0f}% (2020 prices).",
        f"- Young stock shifted from beef to dairy origin: DxB share {dxb0:.0f}% to {dxb1:.0f}%, BxB {bxb0:.0f}% to {bxb1:.0f}%.",
        f"- County dairy change ranged from {dc.min():+.0f}% ({dc.idxmin()}) to {dc.max():+.0f}% ({dc.idxmax()}).",
        "",
        "## 3.3 ED signatures (Figure 4, Table 4)",
        f"- Dairy-centred EDs are {typ.loc['Dairy-centred', 'EDS_SHARE_PCT']:.0f}% of EDs and {typ.loc['Dairy-centred', 'FARMED_HA_SHARE_PCT']:.0f}% "
        f"of farmed area but hold {typ.loc['Dairy-centred', 'LU_SHARE_PCT']:.0f}% of livestock units and "
        f"{typ.loc['Dairy-centred', 'SO_EUR_SHARE_PCT']:.0f}% of Standard Output "
        f"({ts.loc[ts['SYSTEM_TYPE'] == 'Dairy-centred', 'SO_SHARE_PCT'].min():.0f}-"
        f"{ts.loc[ts['SYSTEM_TYPE'] == 'Dairy-centred', 'SO_SHARE_PCT'].max():.0f}% when the class cuts move by +/-10 pp "
        "or the follower ratio by +/-1; Table S3).",
        f"- At the same grazing density (1.4-1.6 LU/ha, {len(band):,} EDs), dairy share spans {band.quantile(0.05):.0f}-"
        f"{band.quantile(0.95):.0f}% (P5-P95): abundance does not identify the system.",
        "",
        "## 3.4 Observed restructuring 2010-2020 (Figure 5)",
        f"- {len(p):,} EDs have cow data published in both censuses; dairy share rose by at least "
        f"{CONFIG['material_shift_pp']:.0f} pp in {int((q['DS_CHANGE_PP'] >= CONFIG['material_shift_pp']).sum()):,}.",
        f"- {int(p['STABLE_HERD_SHIFTED_SYSTEM'].sum())} EDs kept their herd within +/-{CONFIG['stable_herd_pct']:.0f}% yet shifted system by "
        f"{CONFIG['material_shift_pp']:.0f} pp or more; herd change and system change are weakly related "
        f"(rho = {spearman(q['CATTLE_CHANGE_PCT'], q['DS_CHANGE_PP']):.2f}).",
        "",
        "## 3.5 Catchments and the WFD (Figure 6, Table 5)",
        f"- Catchment grazing density ranges {w20['LU_PER_HA'].min():.2f}-{w20['LU_PER_HA'].max():.2f} LU per farmed ha.",
        f"- Inside a typical catchment, ED dairy share spans {width.median():.0f} pp (median P10-P90 width; widest "
        f"{width.max():.0f} pp): a catchment average is the right unit for WFD reporting but hides the EDs where "
        "livestock systems, and the measures that suit them, differ.",
        "- River proximity (riparian buffers) needs a river-network layer that the repository does not hold; this is an extension.",
        "",
        "",
    ]
    return "\n".join(lines)


# ======================================================================================
# main
# ======================================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--only", nargs="*", default=None, help="subset of figures, e.g. F2 F6")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root / "src"))
    out = root / CONFIG["output_dir"]
    for sub in ("figures", "tables", "maps"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    want = set(args.only) if args.only else {f"F{i}" for i in range(1, 7)}
    style()

    data = load(root)
    geo = geometry(root, data["ed_year"])
    derived = derive(data)
    from goblin_spatial.preparation.census_suppression import canonical_key

    model_keys = set(data["ed_year"]["CSOED"].map(canonical_key))
    restructuring = observed_restructuring(root, data, model_keys)
    tp = temporal_points(root, model_keys, geo["crosswalk"])
    written: list[Path] = []
    print("4 FIGURES")
    if "F1" in want:
        f1_workflow(out, written)
    if "F2" in want:
        f2_validation(data, tp, out, written)
    if "F3" in want:
        f3_scale_time(data, geo, out, written)
    if "F4" in want:
        f4_signatures(derived, geo, out, written)
    if "F5" in want:
        f5_restructuring(restructuring, geo, out, written)
    spread = f6_catchments(data, derived, geo, out, written) if "F6" in want else None
    if spread is not None:
        tabs = tables(data, derived, restructuring, spread)
        write_tables(tabs, out, written)
        write_layers(derived, geo, out, written)
        story = out / "RESULTS_STORYLINE.md"
        story.write_text(storyline(data, derived, restructuring, tp, spread), encoding="utf-8")
        written.append(story)
    manifest = {
        "package": "GOBLIN_SPATIAL_PAPER1",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": git_info(root),
        "coherence_audit": data["audit_pass"],
        "config": CONFIG,
        "files": {str(p.relative_to(out)): sha(p) for p in written if p.exists()},
    }
    (out / "paper1_manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    if manifest["repository"]["dirty"]:
        print("WARNING: working tree has uncommitted changes; regenerate from a clean tagged checkout for submission")
    print(f"\nDone: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
