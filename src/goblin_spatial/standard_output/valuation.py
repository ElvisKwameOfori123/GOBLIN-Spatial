"""Standard Output valuation for baseline and scenario livestock states."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.standard_output.coefficients import (
    add_fadn_region,
    load_model_mapping,
    load_soc2020_controls,
    model_coefficient_lookup,
)


DAIRY = {"dairy_cows"}
SUCKLER = {"suckler_cows"}
BULLS = {"bulls"}
SHEEP = set(GOBLIN_SHEEP_10)
FOLLOWERS = set(FINAL_21_COHORTS) - DAIRY - SUCKLER - BULLS


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise KeyError(f"missing Standard Output activity column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if np.any(values < -1e-12):
        raise ValueError(f"negative activity in {column}")
    return np.maximum(values, 0.0)


def _optional_numeric(frame: pd.DataFrame, *columns: str) -> np.ndarray:
    for column in columns:
        if column in frame.columns:
            return _numeric(frame, column)
    return np.zeros(len(frame), dtype=float)


def _pathway_column(state: str, cohort: str) -> str:
    state = state.upper()
    if cohort in SHEEP:
        return f"{state}_SHEEP_COHORT_{cohort}"
    return f"{state}_COHORT_{cohort}"


def _coefficient_array(
    regions: np.ndarray,
    lookup: dict[tuple[str, str], float],
    model_variable: str,
) -> np.ndarray:
    return np.array(
        [lookup[(model_variable, str(region))] for region in regions],
        dtype=float,
    )


def _value_state(
    frame: pd.DataFrame,
    *,
    state: str | None,
    mapping: pd.DataFrame,
) -> dict[str, np.ndarray]:
    lookup = model_coefficient_lookup(mapping)
    regions = frame["FADN_REGION"].astype(str).to_numpy()
    n = len(frame)

    components = {
        "DAIRY_COWS": np.zeros(n, dtype=float),
        "SUCKLER_COWS": np.zeros(n, dtype=float),
        "BULLS": np.zeros(n, dtype=float),
        "FOLLOWERS": np.zeros(n, dtype=float),
        "SHEEP": np.zeros(n, dtype=float),
    }

    for cohort in [*FINAL_21_COHORTS, *GOBLIN_SHEEP_10]:
        column = cohort if state is None else _pathway_column(state, cohort)
        activity = _numeric(frame, column)
        coeff = _coefficient_array(regions, lookup, cohort)
        value = activity * coeff

        if cohort in DAIRY:
            components["DAIRY_COWS"] += value
        elif cohort in SUCKLER:
            components["SUCKLER_COWS"] += value
        elif cohort in BULLS:
            components["BULLS"] += value
        elif cohort in SHEEP:
            components["SHEEP"] += value
        else:
            components["FOLLOWERS"] += value

    components["LIVESTOCK"] = sum(
        components[key]
        for key in (
            "DAIRY_COWS",
            "SUCKLER_COWS",
            "BULLS",
            "FOLLOWERS",
            "SHEEP",
        )
    )
    return components


def add_baseline_standard_output(
    frame: pd.DataFrame,
    *,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Add fixed-2020 SO-weighted production-value exposure to the ED baseline.

    Runtime valuation is driven by ``GOBLIN_SO_mapping.csv``. The same fixed
    coefficients are applied to every baseline year so temporal changes reflect
    activity/structure rather than price drift. ``coefficient_path`` is retained
    as an optional audit hook: when supplied, the original IFS control source is
    loaded and validated but the direct model mapping remains the runtime input.

    ``OTHER_CROPS_HA`` is valued using the documented 2020 regional residual-
    crop composite in the mapping CSV. A conservative alternative is also
    reported because the raw CSO ``Other crops`` component includes fallow and
    wild-bird cover as well as productive crops.
    """

    if coefficient_path is not None:
        load_soc2020_controls(coefficient_path)

    mapping = load_model_mapping(mapping_path)
    out = add_fadn_region(frame)
    values = _value_state(out, state=None, mapping=mapping)
    for component, array in values.items():
        out[f"SO_{component}_2020_EUR"] = array

    regions = out["FADN_REGION"].astype(str).to_numpy()
    main_lookup = model_coefficient_lookup(mapping)
    sensitivity_lookup = model_coefficient_lookup(mapping, sensitivity=True)

    cereal_area = _optional_numeric(out, "TOTAL_CEREALS", "CEREALS_HA")
    cereal_coeff = _coefficient_array(regions, main_lookup, "TOTAL_CEREALS")
    out["SO_CEREALS_2020_EUR"] = cereal_area * cereal_coeff

    other_crop_area = _optional_numeric(out, "OTHER_CROPS_HA")
    other_crop_coeff = _coefficient_array(
        regions, main_lookup, "OTHER_CROPS_HA"
    )
    other_crop_conservative_coeff = _coefficient_array(
        regions, sensitivity_lookup, "OTHER_CROPS_HA"
    )
    out["SO_OTHER_CROPS_2020_EUR"] = other_crop_area * other_crop_coeff
    out["SO_OTHER_CROPS_CONSERVATIVE_2020_EUR"] = (
        other_crop_area * other_crop_conservative_coeff
    )
    out["SO_OTHER_CROPS_IMPUTED_HA"] = other_crop_area

    out["SO_COVERED_TOTAL_2020_EUR"] = (
        out["SO_LIVESTOCK_2020_EUR"]
        + out["SO_CEREALS_2020_EUR"]
        + out["SO_OTHER_CROPS_2020_EUR"]
    )
    out["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"] = (
        out["SO_LIVESTOCK_2020_EUR"]
        + out["SO_CEREALS_2020_EUR"]
        + out["SO_OTHER_CROPS_CONSERVATIVE_2020_EUR"]
    )

    if "AGRICULTURAL_HOLDINGS" in out.columns:
        holdings = pd.to_numeric(
            out["AGRICULTURAL_HOLDINGS"], errors="coerce"
        ).fillna(0.0)
        out["SO_COVERED_PER_HOLDING_2020_EUR"] = np.where(
            holdings > 0,
            out["SO_COVERED_TOTAL_2020_EUR"] / holdings,
            np.nan,
        )
        out["SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR"] = np.where(
            holdings > 0,
            out["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"] / holdings,
            np.nan,
        )
    return out


def add_pathway_standard_output(
    pathway: pd.DataFrame,
    *,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Add baseline/scenario fixed-2020 livestock SO to a 31-cohort pathway."""

    if coefficient_path is not None:
        load_soc2020_controls(coefficient_path)

    mapping = load_model_mapping(mapping_path)
    out = add_fadn_region(pathway)

    for state in ("BASE", "SCENARIO"):
        values = _value_state(out, state=state, mapping=mapping)
        for component, array in values.items():
            out[f"{state}_SO_{component}_2020_EUR"] = array

    out["SO_LIVESTOCK_CHANGE_2020_EUR"] = (
        out["SCENARIO_SO_LIVESTOCK_2020_EUR"]
        - out["BASE_SO_LIVESTOCK_2020_EUR"]
    )
    out["SO_LIVESTOCK_EXPOSURE_2020_EUR"] = (
        out["BASE_SO_LIVESTOCK_2020_EUR"]
        - out["SCENARIO_SO_LIVESTOCK_2020_EUR"]
    )
    base = out["BASE_SO_LIVESTOCK_2020_EUR"].to_numpy(dtype=float)
    change = out["SO_LIVESTOCK_CHANGE_2020_EUR"].to_numpy(dtype=float)
    out["SO_LIVESTOCK_CHANGE_PCT"] = np.where(
        base > 0,
        100.0 * change / base,
        np.nan,
    )
    return out
