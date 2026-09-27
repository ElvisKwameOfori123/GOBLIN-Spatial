"""Data-contract tests for the canonical Ireland 2015-2025 package inputs."""

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


def _config():
    return load_config(CONFIG)


def test_config_uses_only_canonical_baseline_package() -> None:
    cfg = _config()
    expected = {
        "cso_ed_2010": "data/inputs/baseline/CSO_ED2010.csv",
        "cso_ed_2020": "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv",
        "cso_cattle_county": "data/inputs/baseline/01_CSO_AAA10_Cattle_County_2015_2025.csv",
        "dafm_aim_ed_cattle_profile_2020": "data/inputs/baseline/02_DAFM_AIM_ED_Cattle_Profile_2020.csv",
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


def test_cso_ed_2010_contract_and_2020_frame_mapping() -> None:
    frame = pd.read_csv(
        _config().files["cso_ed_2010"],
        dtype=str,
        keep_default_na=False,
    )
    assert len(frame) == 3409

    required = {
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED",
        "DAIRY_COW",
        "OTHER_COW",
        "OTHER_CATTLE",
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        "LSU",
    }
    assert required.issubset(frame.columns)

    keys_2010 = frame["CSOED"].map(canonical_ed_key)
    assert keys_2010.nunique() == 3409

    frame_2020 = pd.read_csv(
        _config().files["cso_ed_2020"],
        dtype={"CSOED": str},
    )
    keys_2020 = frame_2020["CSOED"].map(canonical_ed_key)
    assert len(frame_2020) == 2857
    assert keys_2020.nunique() == 2857

    indexed_2010 = frame.assign(_ED_KEY=keys_2010).set_index("_ED_KEY")
    matched = indexed_2010.reindex(keys_2020)
    assert len(matched) == 2857
    assert matched["CSOED"].notna().all()

    expected_counts = {
        "DAIRY_COW": {"blank": 956, "zero": 487, "positive": 1414},
        "OTHER_COW": {"blank": 50, "zero": 4, "positive": 2803},
        "OTHER_CATTLE": {"blank": 980, "zero": 2, "positive": 1875},
        "TOTAL_CATTLE": {"blank": 29, "zero": 2, "positive": 2826},
    }
    for column, expected in expected_counts.items():
        values = matched[column].astype(str).str.strip()
        blank = values.eq("")
        numeric = pd.to_numeric(values.mask(blank), errors="raise")
        assert int(blank.sum()) == expected["blank"]
        assert int(numeric.eq(0).sum()) == expected["zero"]
        assert int(numeric.gt(0).sum()) == expected["positive"]


def test_canonical_ed_key_normalises_historical_codes() -> None:
    assert canonical_ed_key("01003") == "1003"
    assert canonical_ed_key("1003") == "1003"
    assert canonical_ed_key("32028/32025") == "32025/32028"
    assert canonical_ed_key("32025/32028") == "32025/32028"


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



def test_dafm_aim_ed_cattle_profile_2020_contract() -> None:
    frame = pd.read_csv(_config().files["dafm_aim_ed_cattle_profile_2020"])
    assert len(frame) == 2826
    assert set(frame["AVERAGE_YEAR"].unique()) == {2020}

    age_columns = [
        "AVERAGE_CATTLE_AGE_0_3MTH",
        "AVERAGE_CATTLE_AGE_3_6MTH",
        "AVERAGE_CATTLE_AGE_6_12MTH",
        "AVERAGE_CATTLE_AGE_12_18MTH",
        "AVERAGE_CATTLE_AGE_18_24MTH",
        "AVERAGE_CATTLE_AGE_24_36MTH",
        "AVERAGE_CATTLE_AGE_36MTH_PLUS",
    ]
    numeric_columns = [
        "NUMBER_OF_HERDS",
        "AVERAGE_NUMBER_CATTLE",
        "AVERAGE_CATTLE_BEEF",
        "AVERAGE_CATTLE_DAIRY",
        *age_columns,
    ]
    required = {"AVERAGE_YEAR", "COUNTY", "ELECTORAL_DIVISION", *numeric_columns}
    assert required.issubset(frame.columns)
    assert (frame[numeric_columns] >= 0).all().all()

    age_sum = frame[age_columns].sum(axis=1)
    assert (age_sum - frame["AVERAGE_NUMBER_CATTLE"]).abs().max() < 1e-9
    beef_dairy_diff = (
        frame["AVERAGE_CATTLE_BEEF"]
        + frame["AVERAGE_CATTLE_DAIRY"]
        - frame["AVERAGE_NUMBER_CATTLE"]
    ).abs()
    assert beef_dairy_diff.max() <= 1.0


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
