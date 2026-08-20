"""Annual ED land reconstruction around the fixed 2020 CSO baseline.

This module preserves the validated Script 06 land method. The seven AQA06
regions and their 26-county mapping are deterministic model metadata from the
validated script, so no separate county-region input file is required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import ipf_reconcile


YEARS = tuple(range(2015, 2026))
LAND_COLUMNS = ["AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]
COMPONENT_COLUMNS = ["ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]
GRASS_SOURCE_TYPES = ["Pasture", "Hay", "Grass silage", "Rough grazing in use"]

# Exact county -> AQA06 detailed-region mapping used by validated Script 06.
COUNTY_TO_AQA_REGION = {
    # Border
    "Cavan": "Border",
    "Donegal": "Border",
    "Leitrim": "Border",
    "Monaghan": "Border",
    "Sligo": "Border",
    # West
    "Galway": "West",
    "Mayo": "West",
    "Roscommon": "West",
    # Mid-West
    "Clare": "Mid-West",
    "Limerick": "Mid-West",
    "Tipperary": "Mid-West",
    # South-East
    "Carlow": "South-East",
    "Kilkenny": "South-East",
    "Waterford": "South-East",
    "Wexford": "South-East",
    # South-West
    "Cork": "South-West",
    "Kerry": "South-West",
    # Dublin and Mid-East
    "Dublin": "Dublin and Mid-East",
    "Kildare": "Dublin and Mid-East",
    "Louth": "Dublin and Mid-East",
    "Meath": "Dublin and Mid-East",
    "Wicklow": "Dublin and Mid-East",
    # Midland
    "Laois": "Midland",
    "Longford": "Midland",
    "Offaly": "Midland",
    "Westmeath": "Midland",
}

AQA_REGIONS = (
    "Border",
    "West",
    "Mid-West",
    "South-East",
    "South-West",
    "Dublin and Mid-East",
    "Midland",
)


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _read_aqa06(path) -> pd.DataFrame:
    """Read the frozen AQA06 workbook or the legacy tidy CSV."""

    suffix = str(path).lower()
    if suffix.endswith((".xlsx", ".xls")):
        controls = pd.read_excel(path, sheet_name="Unpivoted")
    else:
        controls = pd.read_csv(path)
    controls.columns = [str(column).strip() for column in controls.columns]
    return controls


def _load_land_controls(
    path, regions: set[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    controls = _read_aqa06(path)
    required = {"Year", "Type of Land Use", "Region", "UNIT", "VALUE"}
    if not required.issubset(controls.columns):
        raise ValueError(
            f"AQA06 land input missing columns: {sorted(required - set(controls.columns))}"
        )

    controls["Year"] = pd.to_numeric(controls["Year"], errors="raise").astype(int)
    controls["VALUE"] = pd.to_numeric(controls["VALUE"], errors="raise")
    controls = controls.loc[
        controls["Year"].isin(YEARS) & controls["Region"].isin(regions)
    ].copy()
    if not (controls["UNIT"] == "000 Hectares").all():
        raise ValueError("AQA06 land controls must use UNIT='000 Hectares'")
    controls["VALUE_HA"] = controls["VALUE"] * 1000.0

    required_types = {"Area farmed (AAU)", "Total cereals", *GRASS_SOURCE_TYPES}
    missing_types = required_types - set(controls["Type of Land Use"].unique())
    if missing_types:
        raise ValueError(f"AQA06 missing required land types: {sorted(missing_types)}")

    area = controls.loc[
        controls["Type of Land Use"] == "Area farmed (AAU)"
    ].pivot(index="Year", columns="Region", values="VALUE_HA")
    cereals = controls.loc[
        controls["Type of Land Use"] == "Total cereals"
    ].pivot(index="Year", columns="Region", values="VALUE_HA")
    grass = (
        controls.loc[controls["Type of Land Use"].isin(GRASS_SOURCE_TYPES)]
        .groupby(["Year", "Region"], as_index=False)["VALUE_HA"]
        .sum()
        .pivot(index="Year", columns="Region", values="VALUE_HA")
    )

    expected_years = set(YEARS)
    for label, table in (("area", area), ("grass", grass), ("cereals", cereals)):
        if set(table.index) != expected_years or set(table.columns) != regions:
            raise AssertionError(
                f"AQA06 {label} controls do not cover all required years and regions"
            )
    return area, grass, cereals


def add_land(master: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Add annual land indicators without changing any livestock population.

    The 2020 ED land values are copied exactly. Other years use AQA06 detailed-
    region change indices around that fixed anchor. AREA_FARMED is the ED row
    target, while IPF reconciles grassland, cereals and other crops so that the
    land identity closes for every ED-year without negative components.
    """

    result = master.copy()
    required = ["YEAR", "CSOED", "County", *LAND_COLUMNS]
    missing = [column for column in required if column not in result.columns]
    if missing:
        raise ValueError(f"land module missing required columns: {missing}")

    protected_columns = [
        column
        for column in result.columns
        if column not in LAND_COLUMNS and column != "AQA06_REGION"
    ]
    protected_snapshot = result[protected_columns].copy()

    result["County"] = result["County"].map(_normalise_county)
    land_path = config.files["cso_land"]
    if not land_path.exists():
        raise FileNotFoundError(land_path)

    if set(COUNTY_TO_AQA_REGION) != set(result["County"].dropna().unique()):
        missing_counties = sorted(
            set(result["County"].dropna().unique()) - set(COUNTY_TO_AQA_REGION)
        )
        extra_counties = sorted(
            set(COUNTY_TO_AQA_REGION) - set(result["County"].dropna().unique())
        )
        raise AssertionError(
            "county coverage differs from validated AQA06 mapping; "
            f"missing_mapping={missing_counties}, absent_from_panel={extra_counties}"
        )

    result["AQA06_REGION"] = result["County"].map(COUNTY_TO_AQA_REGION)
    if result["AQA06_REGION"].isna().any():
        raise AssertionError("missing county-to-AQA06 region mapping")
    regions = set(AQA_REGIONS)
    if set(result["AQA06_REGION"].unique()) != regions:
        raise AssertionError("AQA06 region coverage differs from validated Script 06")

    baseline = result.loc[
        result["YEAR"] == config.base_year,
        ["CSOED", "County", "AQA06_REGION", *LAND_COLUMNS],
    ].copy()
    if (
        len(baseline) != config.expected_eds
        or baseline["CSOED"].nunique() != config.expected_eds
    ):
        raise AssertionError("2020 land baseline does not contain the expected EDs")

    for column in LAND_COLUMNS:
        baseline[column] = pd.to_numeric(
            baseline[column], errors="raise"
        ).astype(float)
        if (baseline[column] < -1e-9).any():
            raise AssertionError(f"negative 2020 land values in {column}")

    base_closure = (
        baseline["ALL_GRASSLAND"]
        + baseline["TOTAL_CEREALS"]
        + baseline["OTHER_CROPS_HA"]
        - baseline["AREA_FARMED"]
    )
    if float(base_closure.abs().max()) > 1e-8:
        raise AssertionError("2020 ED land baseline does not close")

    regional_base = baseline.groupby("AQA06_REGION")[LAND_COLUMNS].sum()
    area_control, grass_control, cereal_control = _load_land_controls(
        land_path, regions
    )

    for column in LAND_COLUMNS:
        result[column] = 0.0

    for year in YEARS:
        if year == config.base_year:
            lookup = baseline.set_index("CSOED")
            idx = result.index[result["YEAR"] == year]
            for column in LAND_COLUMNS:
                result.loc[idx, column] = (
                    result.loc[idx, "CSOED"].map(lookup[column]).to_numpy(dtype=float)
                )
            continue

        for region in AQA_REGIONS:
            base_region = baseline.loc[
                baseline["AQA06_REGION"] == region
            ].copy()
            controls = regional_base.loc[region]

            area_index = float(area_control.loc[year, region]) / float(
                area_control.loc[config.base_year, region]
            )
            grass_index = float(grass_control.loc[year, region]) / float(
                grass_control.loc[config.base_year, region]
            )
            cereal_base = float(cereal_control.loc[config.base_year, region])
            cereal_index = (
                float(cereal_control.loc[year, region]) / cereal_base
                if cereal_base > 0
                else 1.0
            )

            area_target = float(controls["AREA_FARMED"]) * area_index
            grass_target = float(controls["ALL_GRASSLAND"]) * grass_index
            cereal_target = float(controls["TOTAL_CEREALS"]) * cereal_index
            other_target = area_target - grass_target - cereal_target
            if other_target < -1e-6:
                raise AssertionError(
                    f"{year} {region}: negative regional OTHER_CROPS_HA target "
                    f"{other_target}"
                )
            other_target = max(0.0, other_target)

            baseline_area = base_region["AREA_FARMED"].to_numpy(dtype=float)
            if float(baseline_area.sum()) <= 0:
                raise AssertionError(f"{region}: zero 2020 AREA_FARMED support")
            row_targets = baseline_area / baseline_area.sum() * area_target
            prior = base_region[COMPONENT_COLUMNS].to_numpy(dtype=float)
            column_targets = np.array(
                [grass_target, cereal_target, other_target], dtype=float
            )
            balanced = ipf_reconcile(
                prior,
                row_targets,
                column_targets,
                tolerance=1e-9,
                max_iterations=20000,
            )

            allocation = pd.DataFrame(
                {
                    "CSOED": base_region["CSOED"].to_numpy(),
                    "AREA_FARMED": row_targets,
                    "ALL_GRASSLAND": balanced[:, 0],
                    "TOTAL_CEREALS": balanced[:, 1],
                    "OTHER_CROPS_HA": balanced[:, 2],
                }
            ).set_index("CSOED")

            idx = result.index[
                (result["YEAR"] == year) & (result["AQA06_REGION"] == region)
            ]
            for column in LAND_COLUMNS:
                result.loc[idx, column] = (
                    result.loc[idx, "CSOED"]
                    .map(allocation[column])
                    .to_numpy(dtype=float)
                )

    closure = (
        result["ALL_GRASSLAND"]
        + result["TOTAL_CEREALS"]
        + result["OTHER_CROPS_HA"]
        - result["AREA_FARMED"]
    )
    if float(closure.abs().max()) > 1e-6:
        raise AssertionError("ED land accounting does not close")
    if (result[LAND_COLUMNS] < -1e-9).any().any():
        raise AssertionError("land reconstruction produced negative values")

    current_2020 = result.loc[
        result["YEAR"] == config.base_year, ["CSOED", *LAND_COLUMNS]
    ]
    lock = baseline[["CSOED", *LAND_COLUMNS]].merge(
        current_2020,
        on="CSOED",
        validate="one_to_one",
        suffixes=("_BASE", "_AFTER"),
    )
    for column in LAND_COLUMNS:
        if not np.allclose(
            lock[f"{column}_BASE"],
            lock[f"{column}_AFTER"],
            atol=0.0,
            rtol=0.0,
        ):
            raise AssertionError(f"2020 land lock failed for {column}")

    if not protected_snapshot.equals(result[protected_columns]):
        raise AssertionError("land module changed pre-existing non-land fields")

    return result
