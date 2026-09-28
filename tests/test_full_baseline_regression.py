"""Full-data regression gates for the historical GOBLIN-Spatial baseline.

This file is executed only when the canonical compact baseline inputs are
present. It deliberately stops at Stage 09 and does not import soil, LPIS or
scenario modules.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import build_signatures
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import load_config
from goblin_spatial.export.workbook import IDENTIFIERS, STANDARD_OUTPUT
from goblin_spatial.pipeline import run_baseline
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


CONFIG = Path("configs/ireland_2015_2025.yaml")
EXPECTED_YEARS = tuple(range(2015, 2026))
SCENARIO_START_YEARS = (2020, 2025)


def test_full_historical_baseline_through_stage09():
    cfg = load_config(CONFIG)
    baseline = run_baseline(cfg)

    # The baseline is an 11-year ED panel, not only a 2020 anchor table.
    assert len(baseline) == 31_427
    assert baseline["CSOED"].nunique() == 2_857

    year_values = pd.to_numeric(baseline["YEAR"], errors="raise").astype(int)
    assert set(year_values) == set(EXPECTED_YEARS)
    assert not baseline[["YEAR", "CSOED"]].duplicated().any()

    panel = baseline.assign(_YEAR_CHECK=year_values)
    rows_by_year = panel.groupby("_YEAR_CHECK", sort=True).size()
    eds_by_year = panel.groupby("_YEAR_CHECK", sort=True)["CSOED"].nunique()
    assert rows_by_year.to_dict() == {year: 2_857 for year in EXPECTED_YEARS}
    assert eds_by_year.to_dict() == {year: 2_857 for year in EXPECTED_YEARS}

    # Production now uses the finished cattle and sheep chains. Published
    # 2020 ED livestock values must therefore remain unchanged.
    published_2020 = pd.read_csv(cfg.files["cso_ed_2020"], dtype={"CSOED": str}).set_index("CSOED")
    built_2020 = baseline.loc[year_values == 2020].copy()
    built_2020["CSOED"] = built_2020["CSOED"].astype(str)
    built_2020 = built_2020.set_index("CSOED").loc[published_2020.index]
    for column in ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE", "TOTAL_SHEEP"):
        assert np.array_equal(
            pd.to_numeric(built_2020[column], errors="raise").to_numpy(dtype=np.int64),
            pd.to_numeric(published_2020[column], errors="raise").to_numpy(dtype=np.int64),
        )

    # Every reconstructed year must contain the same agricultural ED universe.
    anchor_ed_universe = set(
        baseline.loc[year_values == 2020, "CSOED"].astype(str).tolist()
    )
    assert len(anchor_ed_universe) == 2_857
    for year in EXPECTED_YEARS:
        year_ed_universe = set(
            baseline.loc[year_values == year, "CSOED"].astype(str).tolist()
        )
        assert year_ed_universe == anchor_ed_universe

    cattle = baseline[FINAL_21_COHORTS].apply(pd.to_numeric, errors="raise")
    sheep = baseline[GOBLIN_SHEEP_10].apply(pd.to_numeric, errors="raise")
    total_cattle = pd.to_numeric(baseline["TOTAL_CATTLE"], errors="raise")
    total_sheep = pd.to_numeric(baseline["TOTAL_SHEEP"], errors="raise")

    assert np.array_equal(
        np.rint(cattle.sum(axis=1)).astype(np.int64),
        np.rint(total_cattle).astype(np.int64),
    )
    assert np.array_equal(
        np.rint(sheep.sum(axis=1)).astype(np.int64),
        np.rint(total_sheep).astype(np.int64),
    )
    assert (cattle.to_numpy(dtype=float) >= 0).all()
    assert (sheep.to_numpy(dtype=float) >= 0).all()

    land = baseline[
        ["AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]
    ].apply(pd.to_numeric, errors="raise")
    closure = (
        land["ALL_GRASSLAND"]
        + land["TOTAL_CEREALS"]
        + land["OTHER_CROPS_HA"]
        - land["AREA_FARMED"]
    )
    assert float(closure.abs().max()) <= 1e-6
    assert (land.to_numpy(dtype=float) >= -1e-9).all()

    required_structure = {
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AVERAGE_AGE_OF_HOLDER",
        "MEDIAN_AGE_OF_HOLDER",
    }
    assert required_structure.issubset(baseline.columns)

    # The two canonical public annual panels are emitted from this same
    # production master after land and farm-structure enrichment.
    for key in ("cso_13_cohort_panel", "goblin_31_cohort_panel"):
        panel_path = Path(cfg.raw["outputs"][key])
        if not panel_path.is_absolute():
            panel_path = cfg.project_root / panel_path
        assert panel_path.exists()
        public = pd.read_csv(panel_path)
        assert len(public) == 31_427
        assert public["CSOED"].nunique() == 2_857
        assert not public[["YEAR", "CSOED"]].duplicated().any()
        for column in (
            "AREA_FARMED",
            "ALL_GRASSLAND",
            "TOTAL_CEREALS",
            "OTHER_CROPS_HA",
            "AGRICULTURAL_HOLDINGS",
            "AVERAGE_SIZE_OF_HOLDINGS",
            "AVERAGE_AGE_OF_HOLDER",
            "MEDIAN_AGE_OF_HOLDER",
        ):
            assert column in public.columns
            assert public[column].notna().all()

    cso13_path = Path(cfg.raw["outputs"]["cso_13_cohort_panel"])
    goblin31_path = Path(cfg.raw["outputs"]["goblin_31_cohort_panel"])
    if not cso13_path.is_absolute():
        cso13_path = cfg.project_root / cso13_path
    if not goblin31_path.is_absolute():
        goblin31_path = cfg.project_root / goblin31_path
    cso13_public = pd.read_csv(cso13_path)
    goblin31_public = pd.read_csv(goblin31_path)
    context_columns = [
        "AREA_FARMED",
        "ALL_GRASSLAND",
        "TOTAL_CEREALS",
        "OTHER_CROPS_HA",
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AVERAGE_AGE_OF_HOLDER",
        "MEDIAN_AGE_OF_HOLDER",
    ]
    assert cso13_public[["YEAR", "CSOED", *context_columns]].equals(
        goblin31_public[["YEAR", "CSOED", *context_columns]]
    )

    published_context = pd.read_csv(
        cfg.files["cso_ed_2020"], dtype={"CSOED": str}
    ).set_index("CSOED")
    cso13_2020 = cso13_public.loc[cso13_public["YEAR"] == 2020].copy()
    cso13_2020["CSOED"] = cso13_2020["CSOED"].astype(str)
    cso13_2020 = cso13_2020.set_index("CSOED").loc[published_context.index]
    for column in context_columns:
        assert np.allclose(
            pd.to_numeric(cso13_2020[column], errors="raise").to_numpy(dtype=float),
            pd.to_numeric(published_context[column], errors="raise").to_numpy(dtype=float),
            atol=0.0,
            rtol=0.0,
        )

    # Stage 08 is the final value-enrichment stage. Its fixed-2020 valuation
    # must exist for every ED-year while leaving the activity accounting above
    # intact.
    required_so = {
        "SO_LIVESTOCK_2020_EUR",
        "SO_CEREALS_2020_EUR",
        "SO_OTHER_CROPS_2020_EUR",
        "SO_COVERED_TOTAL_2020_EUR",
    }
    assert required_so.issubset(baseline.columns)
    for column in required_so:
        values = pd.to_numeric(baseline[column], errors="raise")
        assert values.notna().all()
        assert (values >= -1e-9).all()

    # Stage 08 is valuation-only. Component and total identities must close for
    # every ED-year, and all counties must resolve to one of the two historic
    # Irish IFS Standard Output regions.
    assert set(baseline["FADN_REGION"].astype(str).unique()) <= {"381", "382"}
    assert baseline["FADN_REGION_LABEL"].notna().all()

    livestock_components = (
        baseline["SO_DAIRY_COWS_2020_EUR"]
        + baseline["SO_SUCKLER_COWS_2020_EUR"]
        + baseline["SO_BULLS_2020_EUR"]
        + baseline["SO_FOLLOWERS_2020_EUR"]
        + baseline["SO_SHEEP_2020_EUR"]
    )
    assert np.allclose(
        livestock_components.to_numpy(dtype=float),
        baseline["SO_LIVESTOCK_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    )

    assert np.allclose(
        (
            baseline["SO_LIVESTOCK_2020_EUR"]
            + baseline["SO_CEREALS_2020_EUR"]
            + baseline["SO_OTHER_CROPS_2020_EUR"]
        ).to_numpy(dtype=float),
        baseline["SO_COVERED_TOTAL_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    )
    assert np.allclose(
        (
            baseline["SO_LIVESTOCK_2020_EUR"]
            + baseline["SO_CEREALS_2020_EUR"]
            + baseline["SO_OTHER_CROPS_CONSERVATIVE_2020_EUR"]
        ).to_numpy(dtype=float),
        baseline["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    )

    holdings = pd.to_numeric(
        baseline["AGRICULTURAL_HOLDINGS"], errors="raise"
    ).to_numpy(dtype=float)
    positive_holdings = holdings > 0
    per_holding = pd.to_numeric(
        baseline["SO_COVERED_PER_HOLDING_2020_EUR"], errors="coerce"
    ).to_numpy(dtype=float)
    if positive_holdings.any():
        assert np.allclose(
            per_holding[positive_holdings],
            baseline.loc[
                positive_holdings, "SO_COVERED_TOTAL_2020_EUR"
            ].to_numpy(dtype=float)
            / holdings[positive_holdings],
            atol=1e-7,
            rtol=1e-12,
        )
    if (~positive_holdings).any():
        assert np.isnan(per_holding[~positive_holdings]).all()

    # The final clean workbook is a post-Stage-08 deliverable. Standard Output
    # stays on its own sheet and is not folded into the CSO-13 or GOBLIN-31
    # biological panel definitions.
    workbook_path = Path(cfg.raw["outputs"]["clean_workbook"])
    if not workbook_path.is_absolute():
        workbook_path = cfg.project_root / workbook_path
    assert workbook_path.exists()
    workbook = pd.ExcelFile(workbook_path)
    assert "Standard_Output" in workbook.sheet_names
    standard_output_sheet = pd.read_excel(workbook_path, sheet_name="Standard_Output")
    assert len(standard_output_sheet) == 31_427
    assert not standard_output_sheet[["YEAR", "CSOED"]].duplicated().any()
    assert list(standard_output_sheet.columns) == IDENTIFIERS + STANDARD_OUTPUT
    for column in STANDARD_OUTPUT:
        assert column in standard_output_sheet.columns

    cso_workbook = pd.read_excel(
        workbook_path, sheet_name="CSO_13_Cohort_All_Years", nrows=1
    )
    goblin_workbook = pd.read_excel(
        workbook_path, sheet_name="GOBLIN_31_Cohort_All_Years", nrows=1
    )
    assert not any(column.startswith("SO_") for column in cso_workbook.columns)
    assert not any(column.startswith("SO_") for column in goblin_workbook.columns)

    # Both supported scenario starting years must be complete historical states,
    # not partial slices. Scenario code may later choose either snapshot without
    # changing the historical reconstruction.
    required_start_fields = {
        "DAIRY_COW",
        "OTHER_COW",
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        "AREA_FARMED",
        "ALL_GRASSLAND",
        "TOTAL_CEREALS",
        "OTHER_CROPS_HA",
        *required_structure,
        *required_so,
        *FINAL_21_COHORTS,
        *GOBLIN_SHEEP_10,
    }
    assert required_start_fields.issubset(baseline.columns)

    for start_year in SCENARIO_START_YEARS:
        snapshot = baseline.loc[year_values == start_year].copy()
        assert len(snapshot) == 2_857
        assert snapshot["CSOED"].nunique() == 2_857
        assert not snapshot["CSOED"].duplicated().any()
        assert set(snapshot["CSOED"].astype(str)) == anchor_ed_universe

        numeric = snapshot[sorted(required_start_fields)].apply(
            pd.to_numeric, errors="raise"
        )
        assert numeric.notna().all().all()
        assert np.isfinite(numeric.to_numpy(dtype=float)).all()

        start_cattle = snapshot[FINAL_21_COHORTS].apply(
            pd.to_numeric, errors="raise"
        )
        start_sheep = snapshot[GOBLIN_SHEEP_10].apply(
            pd.to_numeric, errors="raise"
        )
        assert np.array_equal(
            np.rint(start_cattle.sum(axis=1)).astype(np.int64),
            np.rint(pd.to_numeric(snapshot["TOTAL_CATTLE"], errors="raise")).astype(
                np.int64
            ),
        )
        assert np.array_equal(
            np.rint(start_sheep.sum(axis=1)).astype(np.int64),
            np.rint(pd.to_numeric(snapshot["TOTAL_SHEEP"], errors="raise")).astype(
                np.int64
            ),
        )

        # Code 09 is baseline-owned and year-selectable. This proves the same
        # dependency-signature machinery can be frozen from either supported
        # scenario starting state, 2020 or 2025.
        start_signatures = build_signatures(baseline, cfg, year=start_year)
        assert len(start_signatures) == 2_857 * 19
        assert start_signatures["CSOED"].nunique() == 2_857
        assert start_signatures["COHORT"].nunique() == 19
        assert set(pd.to_numeric(start_signatures["YEAR"], errors="raise").astype(int)) == {
            start_year
        }
        assert not start_signatures[["CSOED", "COHORT"]].duplicated().any()
        assert set(start_signatures["COHORT_SPATIAL_ROLE"]).issubset(
            {"LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN", "NONE"}
        )

    # The configured Stage 09 output remains a separate long-form baseline
    # deliverable for the default baseline year.
    signature_value = cfg.raw.get("outputs", {}).get(
        "ed_signatures", "data/processed/09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv"
    )
    signature_path = Path(signature_value)
    if not signature_path.is_absolute():
        signature_path = cfg.project_root / signature_path
    assert signature_path.exists()

    signatures = pd.read_csv(signature_path)
    assert len(signatures) == 2_857 * 19
    assert signatures["CSOED"].nunique() == 2_857
    assert signatures["COHORT"].nunique() == 19
    assert not signatures[["CSOED", "COHORT"]].duplicated().any()
    assert set(signatures["COHORT_SPATIAL_ROLE"]).issubset(
        {"LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN", "NONE"}
    )
