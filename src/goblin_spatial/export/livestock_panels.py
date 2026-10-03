"""Merged annual ED livestock panels, 2015-2025 (YEAR x CSOED, 2,857 EDs).

  CSO_13_Cohort_Annual_Panel_2015_2025   (config outputs.cso_13_cohort_panel)
      9 CSO cattle groups: DAIRY_COW, OTHER_COW and the 7 AAA10 age-sex groups
      of other cattle (BULLS, male/female under 1, 1-2, 2+);
      4 AAA09 sheep classes: EWES_2_PLUS, EWES_UNDER_2, RAMS, OTHER_SHEEP.
      No genetics, breed-system or GOBLIN assumptions.

  GOBLIN_31_Cohort_Annual_Panel_2015_2025   (config outputs.goblin_31_cohort_panel)
      21 cattle cohorts (DxD/DxB/BxB) + 10 sheep cohorts (upland/lowland
      breed-system), derived from the 13 groups. The 13 groups and the CSO
      totals are kept as control columns, prefixed CSO_ (so CSO_BULLS and the
      cohort bulls are never confused; SQLite column names ignore case).

Both come from the finished chains, unchanged:
  cattle: CSO annual panel -> age-sex -> genetics -> 21 cohorts
  sheep:  CSO annual panel -> 4 AAA09 classes -> breed/system -> 10 cohorts
2020 ED totals are the published Census of Agriculture values; other years
sum exactly to AAA10 county cattle and AAA09 regional sheep.

A separate national GOBLIN/COHORTS calibration derivative is not part of the
historical baseline release.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_panel import KNOWN_YEAR
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import SpatialConfig
from goblin_spatial.export.workbook import CSO_13_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

YEARS = tuple(range(2015, 2026))
ID_COLS = [
    "YEAR",
    "ELECTORAL_DIVISIONS",
    "ED",
    "County",
    "EDID",
    "CSOED",
    "CSOED_RAW",
    "EDNAME",
    "COUNTYNAME",
    "Region",
    "NUTS2",
]
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
if CSO_13 != CSO_13_COHORTS:
    raise AssertionError("CSO 13 cohort contract differs from export.workbook.CSO_13_COHORTS")
CSO_TOTALS = ["TOTAL_CATTLE", "OTHER_CATTLE", "TOTAL_SHEEP"]
COHORTS_31 = [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
PROVENANCE = ["CATTLE_PROVENANCE", "SHEEP_PROVENANCE"]
CONTEXT_COLUMNS = [
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "OTHER_CROPS_HA",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_SIZE_OF_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER",
]
CONTROL_PREFIX = {c: f"CSO_{c}" for c in [*CSO_TOTALS, *CSO_13]}
NAME_13 = "CSO_13_Cohort_Annual_Panel_2015_2025"
NAME_31 = "GOBLIN_31_Cohort_Annual_Panel_2015_2025"


def build_livestock_panels(config: SpatialConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return livestock-only views from the canonical production builders.

    This function is retained for tests and lightweight livestock exports, but
    it no longer owns a separate cattle/sheep reconstruction route.
    """

    from goblin_spatial.baseline.cattle import build_cattle_baseline
    from goblin_spatial.baseline.merge import merge_livestock
    from goblin_spatial.baseline.sheep import build_sheep_baseline

    cattle = build_cattle_baseline(config)
    sheep = build_sheep_baseline(config)
    ed_anchor = pd.read_csv(config.files["cso_ed_2020"], dtype={"CSOED": str})
    merged = merge_livestock(cattle, sheep, ed_anchor=ed_anchor).rename(
        columns={
            "PROVENANCE": "CATTLE_PROVENANCE",
            "SHEEP_DATA_STATUS": "SHEEP_PROVENANCE",
        }
    )
    panel13, panel31 = project_enriched_livestock_panels(merged)
    for column in [*CSO_TOTALS, *CSO_13]:
        panel13[column] = panel13[column].astype(np.int64)
    for column in [*CONTROL_PREFIX.values(), *COHORTS_31]:
        panel31[column] = panel31[column].astype(np.int64)

    checks = run_checks(panel13, panel31, config)
    if not checks["PASS"].all():
        failed = checks.loc[~checks["PASS"], "CHECK"].tolist()
        raise AssertionError(f"livestock panel checks failed: {failed}")
    return panel13, panel31


def project_enriched_livestock_panels(
    master: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Project the canonical CSO-13 and GOBLIN-31 products from an enriched master.

    The master must already contain the finished livestock chains. Historical
    land and farm-structure variables are copied onto both public panels without
    changing livestock values.
    """

    missing_ids = [column for column in ID_COLS if column not in master.columns]
    if missing_ids:
        raise ValueError(
            f"enriched master missing canonical ED identifiers: {missing_ids}"
        )
    ids = list(ID_COLS)
    context = [column for column in CONTEXT_COLUMNS if column in master.columns]
    # The production master names provenance PROVENANCE (cattle) and
    # SHEEP_DATA_STATUS (sheep); the public panels call them CATTLE_PROVENANCE
    # and SHEEP_PROVENANCE. Accept either so both build paths carry them.
    master = master.rename(
        columns={
            old: new
            for old, new in (("PROVENANCE", "CATTLE_PROVENANCE"), ("SHEEP_DATA_STATUS", "SHEEP_PROVENANCE"))
            if old in master.columns and new not in master.columns
        }
    )
    provenance = [column for column in PROVENANCE if column in master.columns]
    if len(provenance) != len(PROVENANCE):
        raise ValueError(
            f"enriched master missing provenance fields: {sorted(set(PROVENANCE) - set(provenance))}"
        )
    required = {*CSO_TOTALS, *CSO_13, *COHORTS_31}
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"enriched master missing livestock fields: {missing}")

    panel13 = master[
        ids + CSO_TOTALS + CSO_13 + context + provenance
    ].copy()
    panel31 = master[
        ids + CSO_TOTALS + CSO_13 + COHORTS_31 + context + provenance
    ].copy()
    panel31 = panel31.rename(columns=CONTROL_PREFIX)

    for frame in (panel13, panel31):
        if frame[["YEAR", "CSOED"]].duplicated().any():
            raise AssertionError("enriched livestock projection has duplicate YEAR-CSOED rows")
        frame.sort_values(["YEAR", "CSOED"], kind="stable", inplace=True)
        frame.reset_index(drop=True, inplace=True)

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
    shared_ids = [column for column in ID_COLS if column in p.columns and column in q.columns]
    add(
        "31",
        "CSO_ control columns identical to the 13-group panel",
        q[shared_ids + CSO_TOTALS + CSO_13].equals(
            p[shared_ids + CSO_TOTALS + CSO_13]
        ),
    )

    context_present = [column for column in CONTEXT_COLUMNS if column in p.columns]
    if context_present:
        add(
            "13+31",
            "historical context identical between CSO 13 and GOBLIN 31 panels",
            context_present
            == [column for column in CONTEXT_COLUMNS if column in q.columns]
            and q[["YEAR", "CSOED", *context_present]].equals(
                p[["YEAR", "CSOED", *context_present]]
            ),
        )

        published_context = pd.read_csv(
            config.files["cso_ed_2020"], dtype={"CSOED": str}
        ).set_index("CSOED")
        known_context = (
            p.loc[p["YEAR"] == KNOWN_YEAR, ["CSOED", *context_present]]
            .assign(CSOED=lambda x: x["CSOED"].astype(str))
            .set_index("CSOED")
            .loc[published_context.index]
        )
        add(
            "13+31",
            "2020 land and socioeconomic context equal the published CSO ED anchor",
            all(
                np.allclose(
                    pd.to_numeric(known_context[column], errors="raise").to_numpy(dtype=float),
                    pd.to_numeric(published_context[column], errors="raise").to_numpy(dtype=float),
                    atol=0.0,
                    rtol=0.0,
                )
                for column in context_present
            ),
        )
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
    (NAME_13, "Sheet CSO_13_Cohort_All_Years. 9 CSO cattle groups (DAIRY_COW, OTHER_COW, BULLS, male/female under 1, 1-2, 2+) + 4 AAA09 sheep classes (EWES_2_PLUS, EWES_UNDER_2, RAMS, OTHER_SHEEP), with TOTAL_CATTLE, OTHER_CATTLE, TOTAL_SHEEP. No genetics, breed-system or GOBLIN assumptions."),
    (NAME_31, "Sheet GOBLIN_31_Cohort_All_Years. 21 cattle cohorts (DxD/DxB/BxB genetics) + 10 sheep cohorts (upland/lowland breed-system), derived from the 13 groups, which are kept as control columns prefixed CSO_."),
    ("2020", "ED totals are the CSO Census of Agriculture 2020 values: every published cell unchanged, suppressed cells filled in Stage 00 so that the census State totals hold exactly (cattle age-sex and sheep classes within them are estimated)."),
    ("Other years", "ED values are estimated. They sum exactly to AAA10 county cattle and AAA09 regional sheep (June). 2020 ED sums sit slightly below those controls because census animals in EDs outside the 2,857-ED model universe are not moved into it (cattle 7,666, sheep 7,198 head) and because the controls are rounded to 100 head."),
    ("Cattle chain", "CSO annual ED panel (2010 to 2020 share path, 2020 pattern held after) -> age-sex (AAA10 county, DAFM/AIM pattern) -> DxD/DxB/BxB genetics -> 21 cohorts."),
    ("Sheep chain", "AAA09 region -> county (CSO 2020 reference x DAFM breeding-ewe index) -> ED (2010 to 2020 share path) -> 4 AAA09 classes -> DAFM breed/system (2015 uses 2016 composition) -> 10 cohorts."),
    ("Upland / lowland", "Upland = mountain + mountain-cross breed type (DAFM): a breed/system proxy, not observed land location."),
    ("Provenance", "CATTLE_PROVENANCE and SHEEP_PROVENANCE say whether a row is the published 2020 census or a reconstructed year."),
    ("Historical context", "Production-pipeline exports also carry AREA_FARMED, ALL_GRASSLAND, TOTAL_CEREALS, OTHER_CROPS_HA, AGRICULTURAL_HOLDINGS, AVERAGE_SIZE_OF_HOLDINGS, AVERAGE_AGE_OF_HOLDER and MEDIAN_AGE_OF_HOLDER. No historical forestry variable is included."),
    ("Not included", "A separate national GOBLIN/COHORTS calibration derivative is not part of the historical baseline release. Standard Output is added later on the same YEAR x CSOED backbone."),
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
        "County_CSO_13_Cohort": panel13.groupby(county_cols, as_index=False)[CSO_TOTALS + CSO_13].sum(),
        "County_GOBLIN_31_Cohort": panel31.groupby(county_cols, as_index=False)[[CONTROL_PREFIX[c] for c in CSO_TOTALS] + COHORTS_31].sum(),
        "CSO_13_Cohort_All_Years": panel13,
        "GOBLIN_31_Cohort_All_Years": panel31,
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
