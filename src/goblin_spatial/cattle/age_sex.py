"""DAFM-informed age-profile priors for CSO cattle age-sex allocation.

DAFM/AIM provides a 2020 Electoral Division cattle age profile but does not
replace CSO controls. The production rule uses DAFM only to shift the local
odds of under-one versus one-to-two-year cattle. Bulls and cattle aged two
years and over retain the county CSO prior. Exact ED OTHER_CATTLE row totals
and exact rescaled AAA10 county age-sex column totals are restored by IPF and
integer reconciliation.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from goblin_spatial.reconciliation import (
    hamilton_allocate,
    integer_transport,
    integerise_matrix,
    ipf_reconcile,
)

AGE_SEX_PRIOR_MODES = {"flat_county", "dafm_log_odds"}
DEFAULT_LOGIT_EPSILON = 1e-6

DAFM_AGE_COLUMNS = (
    "AVERAGE_CATTLE_AGE_0_3MTH",
    "AVERAGE_CATTLE_AGE_3_6MTH",
    "AVERAGE_CATTLE_AGE_6_12MTH",
    "AVERAGE_CATTLE_AGE_12_18MTH",
    "AVERAGE_CATTLE_AGE_18_24MTH",
    "AVERAGE_CATTLE_AGE_24_36MTH",
    "AVERAGE_CATTLE_AGE_36MTH_PLUS",
)


def _normalise_county(value: object) -> str:
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _normalise_ed_name(value: object) -> str:
    """Return a conservative name key for DAFM-to-CSO ED linkage."""

    text = unicodedata.normalize("NFKD", str(value).upper())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(?:RURAL|URBAN)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def _clip_probability(value: float, epsilon: float) -> float:
    return float(np.clip(float(value), epsilon, 1.0 - epsilon))


def _logit(value: float, epsilon: float) -> float:
    p = _clip_probability(value, epsilon)
    return float(np.log(p / (1.0 - p)))


def _logistic(value: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.asarray(value, dtype=float)))


def build_dafm_age_signal(ed_frame: pd.DataFrame, dafm_path) -> pd.DataFrame:
    """Map the 2020 DAFM age-profile signal to the model ED frame.

    Local q is under1 / (under1 + age1to2), where under1 is
    0-3 + 3-6 + 6-12 months and age1to2 is 12-18 + 18-24 months.

    DAFM rows labelled DED < 5 HERDS contribute to the county reference q but
    are not assigned to an individual ED. EDs without a defensible local name
    match receive the county q, making their log-odds adjustment neutral.
    """

    missing_ed = [c for c in ["County", "ED"] if c not in ed_frame.columns]
    if missing_ed:
        raise ValueError(f"CSO ED frame missing required columns: {missing_ed}")

    dafm = pd.read_csv(dafm_path)
    required = ["AVERAGE_YEAR", "COUNTY", "ELECTORAL_DIVISION", *DAFM_AGE_COLUMNS]
    missing = [column for column in required if column not in dafm.columns]
    if missing:
        raise ValueError(f"DAFM cattle age profile missing required columns: {missing}")

    years = pd.to_numeric(dafm["AVERAGE_YEAR"], errors="raise")
    if set(years.astype(int).unique()) != {2020}:
        raise ValueError("DAFM cattle age profile must contain only the 2020 anchor")

    for column in DAFM_AGE_COLUMNS:
        values = pd.to_numeric(dafm[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"DAFM cattle age profile has invalid values in {column}")
        dafm[column] = values.astype(float)

    dafm["County"] = dafm["COUNTY"].map(_normalise_county)
    dafm["_NAME_KEY"] = dafm["ELECTORAL_DIVISION"].map(_normalise_ed_name)
    dafm["_UNDER_1"] = dafm[
        [
            "AVERAGE_CATTLE_AGE_0_3MTH",
            "AVERAGE_CATTLE_AGE_3_6MTH",
            "AVERAGE_CATTLE_AGE_6_12MTH",
        ]
    ].sum(axis=1)
    dafm["_AGE_1_2"] = dafm[
        ["AVERAGE_CATTLE_AGE_12_18MTH", "AVERAGE_CATTLE_AGE_18_24MTH"]
    ].sum(axis=1)

    county = dafm.groupby("County")[["_UNDER_1", "_AGE_1_2"]].sum().astype(float)
    denominator = county["_UNDER_1"] + county["_AGE_1_2"]
    if (denominator <= 0).any():
        bad = county.index[denominator <= 0].tolist()
        raise ValueError(f"DAFM county young-cattle denominator is zero: {bad}")
    county["_Q_COUNTY"] = county["_UNDER_1"] / denominator

    low_herd = dafm["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )
    local = (
        dafm.loc[~low_herd]
        .groupby(["County", "_NAME_KEY"])[["_UNDER_1", "_AGE_1_2"]]
        .sum()
    )

    signal = pd.DataFrame(index=ed_frame.index)
    signal["DAFM_MATCHED"] = False
    signal["DAFM_Q_COUNTY"] = np.nan
    signal["DAFM_Q_LOCAL"] = np.nan

    for county_name, idx in ed_frame.groupby("County").groups.items():
        if county_name not in county.index:
            raise ValueError(f"DAFM cattle age profile missing county {county_name}")
        q_county = float(county.loc[county_name, "_Q_COUNTY"])
        signal.loc[idx, "DAFM_Q_COUNTY"] = q_county

        for i in idx:
            keys = {
                _normalise_ed_name(part)
                for part in str(ed_frame.at[i, "ED"]).split("/")
                if _normalise_ed_name(part)
            }
            under_1 = 0.0
            age_1_2 = 0.0
            matched = False
            for key in keys:
                lookup = (county_name, key)
                if lookup in local.index:
                    values = local.loc[lookup]
                    under_1 += float(values["_UNDER_1"])
                    age_1_2 += float(values["_AGE_1_2"])
                    matched = True

            if matched and under_1 + age_1_2 > 0:
                signal.at[i, "DAFM_Q_LOCAL"] = under_1 / (under_1 + age_1_2)
                signal.at[i, "DAFM_MATCHED"] = True
            else:
                signal.at[i, "DAFM_Q_LOCAL"] = q_county

    if signal[["DAFM_Q_COUNTY", "DAFM_Q_LOCAL"]].isna().any().any():
        raise AssertionError("DAFM age signal contains missing probabilities")
    if not signal["DAFM_Q_COUNTY"].between(0.0, 1.0).all():
        raise AssertionError("DAFM county age probabilities are outside [0, 1]")
    if not signal["DAFM_Q_LOCAL"].between(0.0, 1.0).all():
        raise AssertionError("DAFM local age probabilities are outside [0, 1]")

    return signal


def allocate_age_sex(
    row_totals,
    raw_county_components,
    mode: str = "flat_county",
    local_q=None,
    county_q: float | None = None,
    epsilon: float = DEFAULT_LOGIT_EPSILON,
) -> tuple[np.ndarray, np.ndarray]:
    """Allocate seven CSO age-sex groups to ED OTHER_CATTLE rows exactly."""

    if mode not in AGE_SEX_PRIOR_MODES:
        raise ValueError(
            "age-sex mode must be one of " + ", ".join(sorted(AGE_SEX_PRIOR_MODES))
        )
    if not 0.0 < float(epsilon) < 0.5:
        raise ValueError("logit epsilon must lie in (0, 0.5)")

    rows = np.asarray(row_totals, dtype=np.int64)
    raw = np.asarray(raw_county_components, dtype=float)
    if rows.ndim != 1 or raw.shape != (7,):
        raise ValueError("age-sex allocation expects row totals and seven county components")
    if (rows < 0).any() or (raw < 0).any():
        raise ValueError("age-sex allocation inputs must be non-negative")
    if float(raw.sum()) <= 0:
        raise ValueError("county age-sex component sum must be positive")

    column_targets = hamilton_allocate(raw / raw.sum(), int(rows.sum()))
    if mode == "flat_county" or int(rows.sum()) == 0:
        return integer_transport(rows, column_targets), column_targets

    if local_q is None or county_q is None:
        raise ValueError("DAFM log-odds mode requires local_q and county_q")

    q_local = np.asarray(local_q, dtype=float)
    if q_local.shape != rows.shape:
        raise ValueError("local_q must have one value per ED row")
    if np.isnan(q_local).any() or not np.isfinite(q_local).all():
        raise ValueError("local_q contains missing or non-finite values")

    grand = float(column_targets.sum())
    under_1 = float(column_targets[1] + column_targets[2])
    age_1_2 = float(column_targets[3] + column_targets[4])
    young = under_1 + age_1_2
    if young <= 0:
        return integer_transport(rows, column_targets), column_targets

    p_county = under_1 / young
    q_county = _clip_probability(float(county_q), epsilon)
    sex_under_1 = float(column_targets[1]) / under_1 if under_1 > 0 else 0.5
    sex_age_1_2 = float(column_targets[3]) / age_1_2 if age_1_2 > 0 else 0.5

    shift = np.array(
        [_logit(value, epsilon) - _logit(q_county, epsilon) for value in q_local],
        dtype=float,
    )
    p_local = np.asarray(_logistic(_logit(p_county, epsilon) + shift), dtype=float)

    bull_share = float(column_targets[0]) / grand
    young_share = young / grand
    male_2_plus_share = float(column_targets[5]) / grand
    female_2_plus_share = float(column_targets[6]) / grand

    prior = np.column_stack(
        [
            np.full(len(rows), bull_share),
            young_share * p_local * sex_under_1,
            young_share * p_local * (1.0 - sex_under_1),
            young_share * (1.0 - p_local) * sex_age_1_2,
            young_share * (1.0 - p_local) * (1.0 - sex_age_1_2),
            np.full(len(rows), male_2_plus_share),
            np.full(len(rows), female_2_plus_share),
        ]
    )
    prior *= rows[:, None].astype(float)

    positive_rows = rows > 0
    positive_cols = column_targets > 0
    prior[np.ix_(positive_rows, positive_cols)] = np.maximum(
        prior[np.ix_(positive_rows, positive_cols)], 1e-12
    )

    reconciled = ipf_reconcile(prior, rows, column_targets)
    allocation = integerise_matrix(reconciled, rows, column_targets)
    return allocation, column_targets
