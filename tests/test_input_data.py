"""Data-contract tests for the Irish 2015-2025 package inputs."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_cso_ed_2020_contract() -> None:
    path = ROOT / "data/raw/cattle/CSO_ED_2020.csv.xz"
    frame = pd.read_csv(path)

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
    path = ROOT / "data/raw/cattle/CSO_county_WIDE_2015_2025.csv.xz"
    frame = pd.read_csv(path)

    assert len(frame) == 26 * 11
    assert set(frame["Year"].unique()) == set(range(2015, 2026))
    assert frame["Region and County"].nunique() == 26
    assert (frame["UNIT"] == "000 Head").all()


def test_sheep_control_contract() -> None:
    county = pd.read_csv(
        ROOT / "data/raw/sheep/CSO_Sheep_County_WIDE_2015_2025.csv.xz"
    )
    region = pd.read_csv(
        ROOT / "data/raw/sheep/CSO_Sheep_Region_WIDE_2015_2025.csv.xz"
    )

    assert len(county) == 26 * 11
    assert county["County"].nunique() == 26
    assert set(county["Year"].unique()) == set(range(2015, 2026))

    detailed = {
        "Border",
        "West",
        "Mid-West",
        "South-East",
        "South-West",
        "Dublin and Mid-East",
        "Midland",
    }
    assert detailed.issubset(set(region["Region"]))
    assert set(region["Year"].unique()) == set(range(2015, 2026))


def test_dafm_sheep_breed_anchor_contract() -> None:
    path = ROOT / "data/raw/sheep/DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.zip"
    frame = pd.read_csv(path)

    assert len(frame) == 26 * 4 * 3
    assert frame["County"].nunique() == 26
    assert set(frame["YEAR"].unique()) == {2016, 2020, 2022, 2025}
    assert set(frame["CATEGORY"].unique()) == {"EWES", "RAMS", "OTHER"}

    count_columns = [
        "MOUNTAIN_COUNT",
        "MOUNTAIN_CROSS_COUNT",
        "LOWLAND_COUNT",
        "LOWLAND_CROSS_COUNT",
    ]
    assert frame[count_columns].notna().all().all()
    assert (frame[count_columns] >= 0).all().all()
    assert (
        frame[count_columns].sum(axis=1).astype(int)
        == frame["TOTAL_DAFM"].astype(int)
    ).all()


def test_land_control_contract() -> None:
    frame = pd.read_csv(ROOT / "data/raw/land/AQA06_Unpivoted_2013_2025.csv.xz")

    assert set(range(2013, 2026)).issubset(set(frame["Year"].unique()))
    required_land_types = {
        "Area farmed (AAU)",
        "Pasture",
        "Hay",
        "Grass silage",
        "Rough grazing in use",
        "Total cereals",
    }
    assert required_land_types.issubset(set(frame["Type of Land Use"]))
    assert (frame["UNIT"] == "000 Hectares").all()


def test_small_controls_exist() -> None:
    controls = ROOT / "data/controls"
    for name in (
        "cohort2012-2020.csv",
        "06_SE_Data_Controls.csv",
        "county_region_map.csv",
    ):
        assert (controls / name).exists()
