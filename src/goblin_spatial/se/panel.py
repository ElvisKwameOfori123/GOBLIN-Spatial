"""Annual ED social-economic reconstruction around the fixed 2020 baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate


YEARS = tuple(range(2015, 2026))
SE_COLUMNS = [
    "AVERAGE_SIZE_OF_HOLDINGS",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER",
]


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _linear_control(controls: dict[int, float], year: int) -> float:
    years = np.array(sorted(controls), dtype=float)
    values = np.array([controls[int(item)] for item in years], dtype=float)
    return float(np.interp(float(year), years, values))


def _minimum_one_allocate(weights, target: int) -> np.ndarray:
    """Hamilton allocation retaining at least one holding on positive support."""

    weights = np.asarray(weights, dtype=float)
    target = int(target)
    positive = weights > 0
    n_positive = int(positive.sum())
    if target < n_positive:
        raise ValueError(
            "target is too small to preserve minimum-one holding support"
        )

    allocation = np.zeros(len(weights), dtype=np.int64)
    allocation[positive] = 1
    remaining = target - n_positive
    if remaining == 0:
        return allocation

    residual_weights = np.where(positive, np.maximum(weights - 1.0, 0.0), 0.0)
    if float(residual_weights.sum()) <= 0:
        residual_weights = np.where(positive, weights, 0.0)
    allocation += hamilton_allocate(residual_weights, remaining)

    if int(allocation.sum()) != target or (allocation[positive] < 1).any():
        raise AssertionError("minimum-one holdings allocation failed")
    return allocation


def add_se(master: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Add holdings, average size and holder-age indicators.

    The exact 2020 ED values are the fixed spatial anchor. National FSS/Census
    controls govern the pre-2020 trajectory. County 2020-2023 changes govern
    the post-2020 trajectory, with the reconstructed 2023 structural state held
    through 2024-2025. Non-2020 values are reconstructed indicators.
    """

    result = master.copy()
    required = ["YEAR", "CSOED", "County", "AREA_FARMED", *SE_COLUMNS]
    missing = [column for column in required if column not in result.columns]
    if missing:
        raise ValueError(f"SE module missing required columns: {missing}")

    protected_columns = [column for column in result.columns if column not in SE_COLUMNS]
    protected_snapshot = result[protected_columns].copy()

    result["County"] = result["County"].map(_normalise_county)
    base = result.loc[
        result["YEAR"] == config.base_year,
        ["CSOED", "County", *SE_COLUMNS, "AREA_FARMED"],
    ].copy()
    if len(base) != config.expected_eds or base["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("2020 SE baseline does not contain the expected EDs")

    controls_path = config.files["se_controls"]
    if not controls_path.exists():
        raise FileNotFoundError(controls_path)
    controls = pd.read_csv(controls_path)
    controls["YEAR"] = pd.to_numeric(controls["YEAR"], errors="raise").astype(int)

    state = controls.loc[controls["LEVEL"] == "State"].copy()
    county_controls = controls.loc[controls["LEVEL"] == "County"].copy()
    county_controls["AREA"] = county_controls["AREA"].map(_normalise_county)

    for column in (
        "AGRICULTURAL_HOLDINGS",
        "MEAN_AGE_HOLDER",
        "MEDIAN_AGE_HOLDER",
    ):
        state[column] = pd.to_numeric(state[column], errors="coerce")
        county_controls[column] = pd.to_numeric(
            county_controls[column], errors="coerce"
        )

    holdings_controls = (
        state.dropna(subset=["AGRICULTURAL_HOLDINGS"])
        .set_index("YEAR")["AGRICULTURAL_HOLDINGS"]
        .to_dict()
    )
    mean_age_controls = (
        state.dropna(subset=["MEAN_AGE_HOLDER"])
        .set_index("YEAR")["MEAN_AGE_HOLDER"]
        .to_dict()
    )
    median_age_controls = (
        state.dropna(subset=["MEDIAN_AGE_HOLDER"])
        .set_index("YEAR")["MEDIAN_AGE_HOLDER"]
        .to_dict()
    )

    county_2020 = county_controls.loc[
        county_controls["YEAR"] == 2020
    ].set_index("AREA")
    county_2023 = county_controls.loc[
        county_controls["YEAR"] == 2023
    ].set_index("AREA")
    if len(county_2020) != 26 or len(county_2023) != 26:
        raise AssertionError(
            "SE controls require 26 county rows for both 2020 and 2023"
        )

    # Agricultural holdings.
    base_holdings = base[["CSOED", "County", "AGRICULTURAL_HOLDINGS"]].copy()
    base_holdings["AGRICULTURAL_HOLDINGS"] = np.rint(
        pd.to_numeric(base_holdings["AGRICULTURAL_HOLDINGS"], errors="raise")
    ).astype(np.int64)
    if (base_holdings["AGRICULTURAL_HOLDINGS"] <= 0).any():
        raise AssertionError(
            "2020 ED holdings must be positive for the current Ireland baseline"
        )

    national_base = int(base_holdings["AGRICULTURAL_HOLDINGS"].sum())
    county_base = base_holdings.groupby("County")["AGRICULTURAL_HOLDINGS"].sum()
    official_2020 = float(holdings_controls[2020])
    result["AGRICULTURAL_HOLDINGS"] = 0

    for year in YEARS:
        idx = result.index[result["YEAR"] == year]
        if year == config.base_year:
            lookup = base_holdings.set_index("CSOED")["AGRICULTURAL_HOLDINGS"]
            result.loc[idx, "AGRICULTURAL_HOLDINGS"] = (
                result.loc[idx, "CSOED"].map(lookup).to_numpy(dtype=np.int64)
            )
            continue

        official_year = _linear_control(holdings_controls, year)
        national_target = int(
            round(national_base * (official_year / official_2020))
        )

        if year < config.base_year:
            allocation = _minimum_one_allocate(
                base_holdings["AGRICULTURAL_HOLDINGS"].to_numpy(dtype=float),
                national_target,
            )
            lookup = pd.Series(allocation, index=base_holdings["CSOED"])
            result.loc[idx, "AGRICULTURAL_HOLDINGS"] = (
                result.loc[idx, "CSOED"].map(lookup).to_numpy(dtype=np.int64)
            )
        else:
            counties = sorted(result["County"].unique())
            raw_targets: list[float] = []
            for county in counties:
                official_county_2020 = float(
                    county_2020.loc[county, "AGRICULTURAL_HOLDINGS"]
                )
                official_county_2023 = float(
                    county_2023.loc[county, "AGRICULTURAL_HOLDINGS"]
                )
                county_index = _linear_control(
                    {2020: official_county_2020, 2023: official_county_2023},
                    year,
                ) / official_county_2020
                raw_targets.append(float(county_base.loc[county]) * county_index)

            county_targets = hamilton_allocate(raw_targets, national_target)
            for county, county_target in zip(counties, county_targets):
                subset = base_holdings.loc[base_holdings["County"] == county]
                allocation = _minimum_one_allocate(
                    subset["AGRICULTURAL_HOLDINGS"].to_numpy(dtype=float),
                    int(county_target),
                )
                lookup = pd.Series(allocation, index=subset["CSOED"])
                county_idx = result.index[
                    (result["YEAR"] == year) & (result["County"] == county)
                ]
                result.loc[county_idx, "AGRICULTURAL_HOLDINGS"] = (
                    result.loc[county_idx, "CSOED"]
                    .map(lookup)
                    .to_numpy(dtype=np.int64)
                )

    result["AGRICULTURAL_HOLDINGS"] = result[
        "AGRICULTURAL_HOLDINGS"
    ].astype(np.int64)
    if (result["AGRICULTURAL_HOLDINGS"] <= 0).any():
        raise AssertionError("SE reconstruction produced non-positive holdings")

    # Holder-age trajectories.
    base_age = base[
        ["CSOED", "County", "AVERAGE_AGE_OF_HOLDER", "MEDIAN_AGE_OF_HOLDER"]
    ].copy()
    result["AVERAGE_AGE_OF_HOLDER"] = np.nan
    result["MEDIAN_AGE_OF_HOLDER"] = np.nan

    for year in YEARS:
        idx = result.index[result["YEAR"] == year]
        if year == config.base_year:
            lookup = base_age.set_index("CSOED")
            result.loc[idx, "AVERAGE_AGE_OF_HOLDER"] = (
                result.loc[idx, "CSOED"]
                .map(lookup["AVERAGE_AGE_OF_HOLDER"])
                .to_numpy(dtype=float)
            )
            result.loc[idx, "MEDIAN_AGE_OF_HOLDER"] = (
                result.loc[idx, "CSOED"]
                .map(lookup["MEDIAN_AGE_OF_HOLDER"])
                .to_numpy(dtype=float)
            )
            continue

        if year < config.base_year:
            mean_delta = _linear_control(mean_age_controls, year) - float(
                mean_age_controls[2020]
            )
            median_delta = _linear_control(median_age_controls, year) - float(
                median_age_controls[2020]
            )
            lookup = base_age.set_index("CSOED")
            result.loc[idx, "AVERAGE_AGE_OF_HOLDER"] = (
                result.loc[idx, "CSOED"]
                .map(lookup["AVERAGE_AGE_OF_HOLDER"] + mean_delta)
                .to_numpy(dtype=float)
            )
            result.loc[idx, "MEDIAN_AGE_OF_HOLDER"] = (
                result.loc[idx, "CSOED"]
                .map(lookup["MEDIAN_AGE_OF_HOLDER"] + median_delta)
                .to_numpy(dtype=float)
            )
        else:
            for county in sorted(result["County"].unique()):
                mean_delta = _linear_control(
                    {
                        2020: float(
                            county_2020.loc[county, "MEAN_AGE_HOLDER"]
                        ),
                        2023: float(
                            county_2023.loc[county, "MEAN_AGE_HOLDER"]
                        ),
                    },
                    year,
                ) - float(county_2020.loc[county, "MEAN_AGE_HOLDER"])
                median_delta = _linear_control(
                    {
                        2020: float(
                            county_2020.loc[county, "MEDIAN_AGE_HOLDER"]
                        ),
                        2023: float(
                            county_2023.loc[county, "MEDIAN_AGE_HOLDER"]
                        ),
                    },
                    year,
                ) - float(county_2020.loc[county, "MEDIAN_AGE_HOLDER"])

                subset = base_age.loc[
                    base_age["County"] == county
                ].set_index("CSOED")
                county_idx = result.index[
                    (result["YEAR"] == year) & (result["County"] == county)
                ]
                result.loc[county_idx, "AVERAGE_AGE_OF_HOLDER"] = (
                    result.loc[county_idx, "CSOED"]
                    .map(subset["AVERAGE_AGE_OF_HOLDER"] + mean_delta)
                    .to_numpy(dtype=float)
                )
                result.loc[county_idx, "MEDIAN_AGE_OF_HOLDER"] = (
                    result.loc[county_idx, "CSOED"]
                    .map(subset["MEDIAN_AGE_OF_HOLDER"] + median_delta)
                    .to_numpy(dtype=float)
                )

    ages = result[["AVERAGE_AGE_OF_HOLDER", "MEDIAN_AGE_OF_HOLDER"]]
    if (ages < 18).any().any() or (ages > 100).any().any():
        raise AssertionError("holder-age reconstruction is outside 18-100 years")

    # Average size preserves the exact reported 2020 ED average-size anchor.
    base_size = base[
        [
            "CSOED",
            "AVERAGE_SIZE_OF_HOLDINGS",
            "AGRICULTURAL_HOLDINGS",
            "AREA_FARMED",
        ]
    ].set_index("CSOED")
    result["AVERAGE_SIZE_OF_HOLDINGS"] = np.nan

    for year in YEARS:
        idx = result.index[result["YEAR"] == year]
        ids = result.loc[idx, "CSOED"]
        if year == config.base_year:
            result.loc[idx, "AVERAGE_SIZE_OF_HOLDINGS"] = (
                ids.map(base_size["AVERAGE_SIZE_OF_HOLDINGS"]).to_numpy(dtype=float)
            )
            continue

        base_average = ids.map(base_size["AVERAGE_SIZE_OF_HOLDINGS"]).to_numpy(
            dtype=float
        )
        base_area = ids.map(base_size["AREA_FARMED"]).to_numpy(dtype=float)
        base_holding_count = ids.map(
            base_size["AGRICULTURAL_HOLDINGS"]
        ).to_numpy(dtype=float)
        current_area = result.loc[idx, "AREA_FARMED"].to_numpy(dtype=float)
        current_holdings = result.loc[
            idx, "AGRICULTURAL_HOLDINGS"
        ].to_numpy(dtype=float)
        result.loc[idx, "AVERAGE_SIZE_OF_HOLDINGS"] = (
            base_average
            * (current_area / base_area)
            / (current_holdings / base_holding_count)
        )

    if not np.isfinite(result[SE_COLUMNS].to_numpy(dtype=float)).all():
        raise AssertionError("SE reconstruction produced non-finite values")

    current_2020 = result.loc[
        result["YEAR"] == config.base_year, ["CSOED", *SE_COLUMNS]
    ]
    lock = base[["CSOED", *SE_COLUMNS]].merge(
        current_2020,
        on="CSOED",
        validate="one_to_one",
        suffixes=("_BASE", "_AFTER"),
    )
    for column in SE_COLUMNS:
        if not np.allclose(
            lock[f"{column}_BASE"],
            lock[f"{column}_AFTER"],
            atol=0.0,
            rtol=0.0,
        ):
            raise AssertionError(f"2020 SE lock failed for {column}")

    if not protected_snapshot.equals(result[protected_columns]):
        raise AssertionError(
            "SE module changed pre-existing livestock or land fields"
        )

    return result
