"""Data-contract tests for the canonical Ireland 2015-2025 package inputs."""

from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


def _config():
    return load_config(CONFIG)


def test_config_uses_only_canonical_baseline_package() -> None:
    cfg = _config()
    expected = {
        "cso_ed_2020": "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv",
        "cso_cattle_county": "data/inputs/baseline/01_CSO_AAA10_Cattle_County_2015_2025.csv",
        "cso_sheep_workbook": "data/inputs/baseline/03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx",
        "sheep_breed_anchors": "data/inputs/baseline/05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv",
        "dafm_sheep_county_validation": "data/inputs/baseline/03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv",
        "goblin_cohorts": "data/inputs/baseline/05C_Cattle_Cohort_Relationships_2012_2020.csv",
        "cso_land": "data/inputs/baseline/06_CSO_AQA06_Agricultural_Land_Use.xlsx",
        "se_controls": "data/inputs/baseline/06_Farm_Structure_Demographic_Controls.csv",
        "standard_output_mapping": "data/inputs/baseline/08_IFS2020_Standard_Output_Mapping.xlsx",
    }
    for key, relative in expected.items():
        assert cfg.files[key] == ROOT / relative
        assert cfg.files[key].exists(), key


def test_cso_ed_2020_contract() -> None:
    frame = pd.read_csv(_config().files["cso_ed_2020"])
    assert len(frame) == 2857
    assert frame["CSOED"].nunique() == 2857
    assert set(frame["CENSUS_YEAR"].unique()) == {2020}
    required = {
        "DAIRY_COW",
        "OTHER_COW",
        "OTHER_CATTLE",
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        "AREA_FARMED",
        "ALL_GRASSLAND",
        "TOTAL_CEREALS",
        "OTHER_CROPS_HA",
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AVERAGE_AGE_OF_HOLDER",
        "MEDIAN_AGE_OF_HOLDER",
    }
    assert required.issubset(frame.columns)


def test_cattle_county_control_contract() -> None:
    frame = pd.read_csv(_config().files["cso_cattle_county"])
    assert len(frame) == 26 * 11
    assert set(frame["Year"].unique()) == set(range(2015, 2026))
    assert frame["Region and County"].nunique() == 26
    assert (frame["UNIT"] == "000 Head").all()


def test_sheep_workbook_contains_production_hierarchy() -> None:
    workbook = pd.ExcelFile(_config().files["cso_sheep_workbook"])
    assert {"County_WIDE", "Region_WIDE"}.issubset(set(workbook.sheet_names))


def test_dafm_breed_anchor_contract() -> None:
    frame = pd.read_csv(_config().files["sheep_breed_anchors"])
    assert frame["County"].nunique() == 26
    assert set(frame["YEAR"].unique()) == {2016, 2020, 2022, 2025}
    assert set(frame["CATEGORY"].unique()) == {"EWES", "RAMS", "OTHER"}


def test_required_small_runtime_controls_exist() -> None:
    cfg = _config()
    for key in (
        "standard_output_coefficients",
        "scenario_controls",
        "pasture_dm_controls",
    ):
        assert cfg.files[key].exists(), key
