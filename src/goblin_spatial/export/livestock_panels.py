"""Merged annual ED livestock panels, 2015-2025 (YEAR x CSOED, 2,857 EDs).

  annual_livestock_cso_13_groups_2015_2025
      9 CSO cattle groups: DAIRY_COW, OTHER_COW and the 7 AAA10 age-sex groups
      of other cattle (BULLS, male/female under 1, 1-2, 2+);
      4 AAA09 sheep classes: EWES_2_PLUS, EWES_UNDER_2, RAMS, OTHER_SHEEP.
      No genetics, breed-system or GOBLIN assumptions.

  annual_livestock_31_cohorts_2015_2025
      21 cattle cohorts (DxD/DxB/BxB) + 10 sheep cohorts (upland/lowland
      breed-system), derived from the 13 groups. The 13 groups and the CSO
      totals are kept as control columns, prefixed CSO_ (so CSO_BULLS and the
      cohort bulls are never confused; SQLite column names ignore case).

Both come from the finished chains, unchanged:
  cattle: CSO annual panel -> age-sex -> genetics -> 21 cohorts
  sheep:  CSO annual panel -> 4 AAA09 classes -> breed/system -> 10 cohorts
2020 ED totals are the published Census of Agriculture values; other years
sum exactly to AAA10 county cattle and AAA09 regional sheep.

The national GOBLIN/COHORTS calibration is a later, separate product.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import KNOWN_YEAR, build_annual_ed_panel
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS, add_cattle_cohorts
from goblin_spatial.config import SpatialConfig
from goblin_spatial.sheep import add_sheep_cohorts, build_annual_sheep_panel
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

YEARS = tuple(range(2015, 2026))
ID_COLS = ["YEAR", "CSOED", "EDNAME", "County", "Region", "NUTS2"]
CATTLE_AGE_SEX_7 = [
    "BULLS",
    "CATTLE_MALE_UNDER_1",
    "CATTLE_FEMALE_UNDER_1",
    "CATTLE_MALE_1_2",
    "CATTLE_FEMALE_1_2",
    "CATTLE_MALE_2_PLUS",
    "CATTLE_FEMALE_2_PLUS",
]
CSO_CATTLE_9 = ["DAIRY_COW", "OTHER_COW", *CATTLE_AGE_SEX_7]
CSO_SHEEP_4 = ["EWES_2_PLUS", "EWES_UNDER_2", "RAMS", "OTHER_SHEEP"]
CSO_13 = [*CSO_CATTLE_9, *CSO_SHEEP_4]
CSO_TOTALS = ["TOTAL_CATTLE", "OTHER_CATTLE", "TOTAL_SHEEP"]
COHORTS_31 = [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
PROVENANCE = ["CATTLE_PROVENANCE", "SHEEP_PROVENANCE"]
CONTROL_PREFIX = {c: f"CSO_{c}" for c in [*CSO_TOTALS, *CSO_13]}
NAME_13 = "annual_livestock_cso_13_groups_2015_2025"
NAME_31 = "annual_livestock_31_cohorts_2015_2025"


def build_livestock_panels(config: SpatialConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (13-group CSO panel, 31-cohort panel)."""

    base, _ = build_annual_ed_panel(config)
    cattle = add_cattle_cohorts(build_annual_age_sex_panel(config, base), config)
    sheep_panel, _ = build_annual_sheep_panel(config)
    sheep = add_sheep_cohorts(sheep_panel, config)

    cattle = cattle.rename(columns={"PROVENANCE": "CATTLE_PROVENANCE"})
    sheep = sheep.rename(columns={"SHEEP_DATA_STATUS": "SHEEP_PROVENANCE"})
    cattle["CSOED"] = cattle["CSOED"].astype(str)
    sheep["CSOED"] = sheep["CSOED"].astype(str)

    merged = sheep[
        ["YEAR", "CSOED", "EDNAME", "County", "Region", "NUTS2", "TOTAL_SHEEP", *CSO_SHEEP_4, *GOBLIN_SHEEP_10, "SHEEP_PROVENANCE"]
    ].merge(
        cattle[["YEAR", "CSOED", "County", "TOTAL_CATTLE", "OTHER_CATTLE", "DAIRY_COW", "OTHER_COW",
                *CATTLE_AGE_SEX_7, *FINAL_21_COHORTS, "CATTLE_PROVENANCE"]],
        on=["YEAR", "CSOED"],
        how="outer",
        suffixes=("", "_CATTLE"),
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise AssertionError("cattle and sheep ED-year frames differ")
    if not merged["County"].eq(merged["County_CATTLE"]).all():
        raise AssertionError("cattle and sheep disagree on ED county")
    for column in [*CSO_TOTALS, *CSO_13, *COHORTS_31]:
        merged[column] = merged[column].astype(np.int64)
    merged = merged.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)

    panel13 = merged[ID_COLS + CSO_TOTALS + CSO_13 + PROVENANCE].copy()
    panel31 = merged[ID_COLS + CSO_TOTALS + CSO_13 + COHORTS_31 + PROVENANCE].rename(columns=CONTROL_PREFIX)
    checks = run_checks(panel13, panel31, config)
    if not checks["PASS"].all():
        failed = checks.loc[~checks["PASS"], "CHECK"].tolist()
        raise AssertionError(f"livestock panel checks failed: {failed}")
    return panel13, panel31


def run_checks(panel13: pd.DataFrame, panel31: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Accounting checks for both panels, as a table."""

    rows = []

    def add(panel, check, ok):
        rows.append({"PANEL": panel, "CHECK": check, "PASS": bool(ok)})

    for name, p in (("13", panel13), ("31", panel31)):
        add(name, "2,857 EDs x 11 years, each once", len(p) == 2857 * len(YEARS) and not p[["YEAR", "CSOED"]].duplicated().any()
            and set(p["YEAR"]) == set(YEARS) and p["CSOED"].nunique() == 2857)
        add(name, "no negative values", (p.select_dtypes("number").drop(columns="YEAR") >= 0).all().all())
    p = panel13
    add("13", "9 cattle groups sum to TOTAL_CATTLE", (p[CSO_CATTLE_9].sum(axis=1) == p["TOTAL_CATTLE"]).all())
    add("13", "7 age-sex groups sum to OTHER_CATTLE", (p[CATTLE_AGE_SEX_7].sum(axis=1) == p["OTHER_CATTLE"]).all())
    add("13", "4 sheep classes sum to TOTAL_SHEEP", (p[CSO_SHEEP_4].sum(axis=1) == p["TOTAL_SHEEP"]).all())

    published = pd.read_csv(config.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")
    known = p.loc[p["YEAR"] == KNOWN_YEAR].set_index("CSOED").loc[published.index]
    add("13", "2020 ED values equal the published census",
        all((known[c] == published[c]).all() for c in ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE", "TOTAL_SHEEP")))

    q = panel31.rename(columns={v: k for k, v in CONTROL_PREFIX.items()})
    add("31", "CSO_ control columns identical to the 13-group panel", q[ID_COLS + CSO_TOTALS + CSO_13].equals(p[ID_COLS + CSO_TOTALS + CSO_13]))
    add("31", "21 cattle cohorts sum to TOTAL_CATTLE", (q[FINAL_21_COHORTS].sum(axis=1) == q["TOTAL_CATTLE"]).all())
    add("31", "10 sheep cohorts sum to TOTAL_SHEEP", (q[GOBLIN_SHEEP_10].sum(axis=1) == q["TOTAL_SHEEP"]).all())
    add("31", "dairy_cows = DAIRY_COW, suckler_cows = OTHER_COW, bulls = BULLS",
        (q["dairy_cows"] == q["DAIRY_COW"]).all() and (q["suckler_cows"] == q["OTHER_COW"]).all() and (q["bulls"] == q["BULLS"]).all())
    add("31", "Lowland + Upland ewes = EWES_2_PLUS + EWES_UNDER_2",
        ((q["Lowland ewes"] + q["Upland ewes"]) == q["EWES_2_PLUS"] + q["EWES_UNDER_2"]).all())
    add("31", "Lowland + Upland ram = RAMS", ((q["Lowland ram"] + q["Upland ram"]) == q["RAMS"]).all())
    lambs = [c for c in GOBLIN_SHEEP_10 if c not in ("Lowland ewes", "Upland ewes", "Lowland ram", "Upland ram")]
    add("31", "6 lamb/male sheep cohorts = OTHER_SHEEP", (q[lambs].sum(axis=1) == q["OTHER_SHEEP"]).all())
    return pd.DataFrame(rows)


README = [
    ("Purpose", "Electoral Division (ED) livestock for every YEAR x CSOED, 2015-2025 (2,857 EDs, 31,427 rows), in two merged panels."),
    (NAME_13, "Sheet CSO_13_groups. 9 CSO cattle groups (DAIRY_COW, OTHER_COW, BULLS, male/female under 1, 1-2, 2+) + 4 AAA09 sheep classes (EWES_2_PLUS, EWES_UNDER_2, RAMS, OTHER_SHEEP), with TOTAL_CATTLE, OTHER_CATTLE, TOTAL_SHEEP. No genetics, breed-system or GOBLIN assumptions."),
    (NAME_31, "Sheet Cohorts_31. 21 cattle cohorts (DxD/DxB/BxB genetics) + 10 sheep cohorts (upland/lowland breed-system), derived from the 13 groups, which are kept as control columns prefixed CSO_."),
    ("2020", "ED totals are the published CSO Census of Agriculture 2020 values, unchanged (cattle age-sex and sheep classes within them are estimated)."),
    ("Other years", "ED values are estimated. They sum exactly to AAA10 county cattle and AAA09 regional sheep (June). Published 2020 ED sums fall below those controls (sheep 259,807 head, 4.7%), so expect a dip at 2020 in ED sums."),
    ("Cattle chain", "CSO annual ED panel (2010 to 2020 share path, 2020 pattern held after) -> age-sex (AAA10 county, DAFM/AIM pattern) -> DxD/DxB/BxB genetics -> 21 cohorts."),
    ("Sheep chain", "AAA09 region -> county (CSO 2020 reference x DAFM breeding-ewe index) -> ED (2010 to 2020 share path) -> 4 AAA09 classes -> DAFM breed/system (2015 uses 2016 composition) -> 10 cohorts."),
    ("Upland / lowland", "Upland = mountain + mountain-cross breed type (DAFM): a breed/system proxy, not observed land location."),
    ("Provenance", "CATTLE_PROVENANCE and SHEEP_PROVENANCE say whether a row is the published 2020 census or a reconstructed year."),
    ("Not included", "National GOBLIN/COHORTS calibration, land use, crops, farm structure, farmer age, Standard Output: later, separate steps on this same YEAR x CSOED backbone."),
    ("Checks", "Accounting checks run when the file was built. All must be TRUE."),
    ("Units", "Head of livestock (integers)."),
]


def export_workbook(panel13: pd.DataFrame, panel31: pd.DataFrame, checks: pd.DataFrame, path: str | Path) -> Path:
    from openpyxl.styles import Alignment, Font

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    county_cols = ["YEAR", "County", "Region"]
    sheets = {
        "README": pd.DataFrame(README, columns=["ITEM", "DESCRIPTION"]),
        "Checks": checks,
        "National_by_year": panel31.groupby("YEAR", as_index=False)[list(CONTROL_PREFIX.values()) + COHORTS_31].sum(),
        "County_CSO_13": panel13.groupby(county_cols, as_index=False)[CSO_TOTALS + CSO_13].sum(),
        "County_31": panel31.groupby(county_cols, as_index=False)[[CONTROL_PREFIX[c] for c in CSO_TOTALS] + COHORTS_31].sum(),
        "CSO_13_groups": panel13,
        "Cohorts_31": panel31,
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for i, column in enumerate(frame.columns, start=1):
                width = 100 if (name == "README" and column == "DESCRIPTION") else (46 if name == "README" else min(max(len(str(column)) + 2, 10), 28))
                sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = width
            if name == "README":
                for row in sheet.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
    return path


def export_sqlite(panel13: pd.DataFrame, panel31: pd.DataFrame, checks: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as con:
        for name, frame in ((NAME_13, panel13), (NAME_31, panel31)):
            frame.to_sql(name, con, index=False)
            con.execute(f'CREATE UNIQUE INDEX "ix_{name}" ON "{name}" (YEAR, CSOED)')
        checks.to_sql("checks", con, index=False)
        pd.DataFrame(README, columns=["item", "description"]).to_sql("readme", con, index=False)
    return path
