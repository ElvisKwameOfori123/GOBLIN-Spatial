"""Standard Output valuation for baseline and scenario livestock states."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.standard_output.coefficients import (
    COHORT_PRODUCT_CODE,
    add_fadn_region,
    cereal_composite_coefficients,
    coefficient_lookup,
    load_soc2020_controls,
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


def _pathway_column(state: str, cohort: str) -> str:
    state = state.upper()
    if cohort in SHEEP:
        return f"{state}_SHEEP_COHORT_{cohort}"
    return f"{state}_COHORT_{cohort}"


def _value_state(
    frame: pd.DataFrame,
    *,
    state: str | None,
    controls: pd.DataFrame,
) -> dict[str, np.ndarray]:
    lookup = coefficient_lookup(controls)
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
        product = COHORT_PRODUCT_CODE[cohort]
        coeff = np.array(
            [lookup[(product, region)] for region in regions], dtype=float
        )
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
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Add fixed-2020 SO exposure to a direct 31-cohort ED baseline/panel.

    The same 2020 coefficients are applied to every year. Temporal differences
    therefore measure structural/activity change rather than a mixture of herd
    change and changing valuation coefficients.

    ``OTHER_CROPS_HA`` is deliberately not assigned an invented composite SO
    coefficient. Its area is carried as an explicit unvalued field until a
    documented mixed-crop crosswalk is added. ``SO_COVERED_TOTAL_2020_EUR`` is
    therefore livestock plus cereals, not a claim of complete farm SO.
    """

    controls = load_soc2020_controls(coefficient_path)
    out = add_fadn_region(frame)
    values = _value_state(out, state=None, controls=controls)
    for component, array in values.items():
        out[f"SO_{component}_2020_EUR"] = array

    if "TOTAL_CEREALS" in out.columns:
        cereal_area = pd.to_numeric(
            out["TOTAL_CEREALS"], errors="raise"
        ).to_numpy(dtype=float)
    elif "CEREALS_HA" in out.columns:
        cereal_area = pd.to_numeric(
            out["CEREALS_HA"], errors="raise"
        ).to_numpy(dtype=float)
    else:
        cereal_area = np.zeros(len(out), dtype=float)

    if np.any(cereal_area < -1e-12):
        raise ValueError("negative cereal area cannot be valued")
    cereal_area = np.maximum(cereal_area, 0.0)
    cereal_coeff = cereal_composite_coefficients(controls)
    out["SO_CEREALS_2020_EUR"] = (
        cereal_area * out["FADN_REGION"].map(cereal_coeff).astype(float)
    )
    out["SO_COVERED_TOTAL_2020_EUR"] = (
        out["SO_LIVESTOCK_2020_EUR"] + out["SO_CEREALS_2020_EUR"]
    )

    if "OTHER_CROPS_HA" in out.columns:
        out["SO_OTHER_CROPS_UNVALUED_HA"] = pd.to_numeric(
            out["OTHER_CROPS_HA"], errors="raise"
        ).clip(lower=0.0)
    else:
        out["SO_OTHER_CROPS_UNVALUED_HA"] = 0.0

    if "AGRICULTURAL_HOLDINGS" in out.columns:
        holdings = pd.to_numeric(
            out["AGRICULTURAL_HOLDINGS"], errors="coerce"
        ).fillna(0.0)
        out["SO_COVERED_PER_HOLDING_2020_EUR"] = np.where(
            holdings > 0,
            out["SO_COVERED_TOTAL_2020_EUR"] / holdings,
            np.nan,
        )
    return out


def add_pathway_standard_output(
    pathway: pd.DataFrame,
    *,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Add baseline/scenario fixed-2020 livestock SO to a 31-cohort pathway."""

    controls = load_soc2020_controls(coefficient_path)
    out = add_fadn_region(pathway)

    for state in ("BASE", "SCENARIO"):
        values = _value_state(out, state=state, controls=controls)
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
