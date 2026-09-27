"""CSO cattle baseline and annual ED cattle-panel construction.

This module is the modular equivalent of the validated 2020 cattle
reconciliation and 2015-2025 annual ED cattle reconstruction stages.

Fine-scale CSO ED data provide the within-county spatial pattern. Annual CSO
AAA10 county statistics provide the controlling cattle totals and age-sex
composition. The 2020 ED baseline is copied exactly into the annual panel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.age_sex import (
    AGE_SEX_PRIOR_MODES,
    DEFAULT_LOGIT_EPSILON,
    _normalise_ed_name,
    allocate_age_sex,
    build_dafm_age_signal,
)
from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate, integer_transport


YEARS = tuple(range(2015, 2026))

AGE_SEX_MAP = {
    "Bulls": "BULLS",
    "Cattle male: under 1 year": "CATTLE_MALE_UNDER_1",
    "Cattle female: under 1 year": "CATTLE_FEMALE_UNDER_1",
    "Cattle male: 1-2 years": "CATTLE_MALE_1_2",
    "Cattle female: 1-2 years": "CATTLE_FEMALE_1_2",
    "Cattle male: 2 years and over": "CATTLE_MALE_2_PLUS",
    "Cattle female: 2 years and over": "CATTLE_FEMALE_2_PLUS",
}

AAA_AGE_SEX_COLS = list(AGE_SEX_MAP)
AGE_SEX_COLS = list(AGE_SEX_MAP.values())
MAIN_CATTLE_COLS = ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]
SPATIAL_COMPONENTS = ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE")
SPATIAL_WEIGHT_MODES = {"fixed_2020", "two_anchor_2010_2020"}
DAIRY_ANCHOR_MODES = {"positive_proportional", "aim_residual"}


def _normalise_county(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def _as_nonnegative_integer(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{label}: missing/non-numeric values in {column}")
        if (values < 0).any():
            raise ValueError(f"{label}: negative values in {column}")
        frame[column] = np.rint(values).astype(np.int64)


def _load_aaa10(path) -> pd.DataFrame:
    county = pd.read_csv(path)
    required = [
        "Year",
        "Region and County",
        "UNIT",
        "Total cattle",
        "Dairy cows",
        "Other cows",
        *AAA_AGE_SEX_COLS,
    ]
    _require_columns(county, required, "AAA10 county cattle data")

    county["Year"] = pd.to_numeric(county["Year"], errors="raise").astype(int)
    county["County"] = county["Region and County"].map(_normalise_county)
    county = county.loc[county["Year"].isin(YEARS)].copy()

    if not (county["UNIT"] == "000 Head").all():
        raise ValueError("AAA10 cattle input must use UNIT='000 Head'")

    numeric = ["Total cattle", "Dairy cows", "Other cows", *AAA_AGE_SEX_COLS]
    for column in numeric:
        values = pd.to_numeric(county[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"AAA10 contains invalid values in {column}")
        county[column] = values
        county[f"{column}__HEAD"] = np.rint(values * 1000.0).astype(np.int64)

    return county


def _load_cso_ed_2010(path) -> pd.DataFrame:
    """Load the 2010 ED cattle anchor while preserving published blanks."""

    ed = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = ["CSOED", "County", *SPATIAL_COMPONENTS, "TOTAL_CATTLE"]
    _require_columns(ed, required, "2010 ED cattle data")

    ed["_ED_KEY"] = ed["CSOED"].map(canonical_ed_key)
    if ed["_ED_KEY"].duplicated().any():
        raise AssertionError("2010 ED cattle data contain duplicate canonical ED keys")

    for column in (*SPATIAL_COMPONENTS, "TOTAL_CATTLE"):
        text = ed[column].astype(str).str.strip()
        blank = text.eq("")
        values = pd.to_numeric(text.mask(blank), errors="raise")
        if (values.dropna() < 0).any():
            raise ValueError(f"2010 ED cattle data contain negative values in {column}")
        ed[column] = values.astype(float)

    return ed


def _spatial_weight_mode(config: SpatialConfig) -> str:
    """Return the configured historical cattle spatial-weight rule."""

    value = str(
        config.raw.get("cattle", {}).get("spatial_weights", "fixed_2020")
    ).strip()
    if value not in SPATIAL_WEIGHT_MODES:
        raise ValueError(
            "cattle.spatial_weights must be one of "
            + ", ".join(sorted(SPATIAL_WEIGHT_MODES))
        )
    return value


def _dairy_anchor_mode(config: SpatialConfig) -> str:
    """Return the configured 2020 dairy-cow reconciliation rule."""

    value = str(
        config.raw.get("cattle", {}).get(
            "dairy_anchor_prior", "positive_proportional"
        )
    ).strip()
    if value not in DAIRY_ANCHOR_MODES:
        raise ValueError(
            "cattle.dairy_anchor_prior must be one of "
            + ", ".join(sorted(DAIRY_ANCHOR_MODES))
        )
    return value


def _bounded_weighted_allocate(weights, capacities, target: int) -> np.ndarray:
    """Allocate an integer residual by weights without exceeding capacities."""

    weights = np.asarray(weights, dtype=float)
    capacities = np.asarray(capacities, dtype=np.int64)
    target = int(target)

    if len(weights) != len(capacities):
        raise ValueError("weights and capacities must have equal length")
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("residual weights must be finite and non-negative")
    if (capacities < 0).any():
        raise ValueError("residual capacities must be non-negative")
    if target < 0 or target > int(capacities.sum()):
        raise ValueError("residual target exceeds available capacity")
    if target == 0:
        return np.zeros(len(capacities), dtype=np.int64)

    fractional = np.zeros(len(capacities), dtype=float)
    active = capacities > 0
    remaining = float(target)

    while remaining > 1e-10:
        indices = np.where(active)[0]
        if len(indices) == 0:
            raise RuntimeError("residual allocation exhausted capacity")

        available = capacities[indices].astype(float) - fractional[indices]
        current_weights = weights[indices].copy()
        if float(current_weights.sum()) <= 0:
            current_weights = available.copy()
        if float(current_weights.sum()) <= 0:
            raise RuntimeError("residual allocation has no positive capacity")

        proposal = remaining * current_weights / current_weights.sum()
        saturated = proposal >= available - 1e-12

        if not saturated.any():
            fractional[indices] += proposal
            remaining = 0.0
        else:
            hit = indices[saturated]
            fractional[hit] = capacities[hit]
            active[hit] = False
            remaining = float(target - fractional.sum())

    allocation = np.floor(fractional + 1e-12).astype(np.int64)
    left = target - int(allocation.sum())
    if left:
        remainder = fractional - allocation
        eligible = allocation < capacities
        order = np.argsort(-np.where(eligible, remainder, -1.0), kind="stable")
        for index in order:
            if left == 0:
                break
            if allocation[index] < capacities[index]:
                allocation[index] += 1
                left -= 1

    if left != 0:
        raise RuntimeError("residual allocation could not close integer target")
    if int(allocation.sum()) != target:
        raise AssertionError("residual allocation target closure failed")
    if (allocation < 0).any() or (allocation > capacities).any():
        raise AssertionError("residual allocation violated capacity")
    return allocation


def _build_aim_dairy_anchor_signal(ed_frame: pd.DataFrame, dafm_path) -> pd.DataFrame:
    """Map AIM broad dairy-type composition to the 2020 CSO ED frame.

    The signal is used only to place the county dairy-cow residual that exists
    between the published ED dairy-cow sum and the authoritative AAA10 county
    dairy-cow total. AIM counts are June/December averages and are not treated
    as dairy-cow counts themselves.
    """

    required_ed = ["County", "ED"]
    _require_columns(ed_frame, required_ed, "2020 ED cattle baseline")

    dafm = pd.read_csv(dafm_path)
    required = [
        "AVERAGE_YEAR",
        "COUNTY",
        "ELECTORAL_DIVISION",
        "AVERAGE_NUMBER_CATTLE",
        "AVERAGE_CATTLE_DAIRY",
    ]
    _require_columns(dafm, required, "DAFM cattle type profile")

    years = pd.to_numeric(dafm["AVERAGE_YEAR"], errors="raise").astype(int)
    if set(years.unique()) != {2020}:
        raise ValueError("DAFM cattle type profile must contain only 2020")

    for column in ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]:
        values = pd.to_numeric(dafm[column], errors="raise").astype(float)
        if (values < 0).any() or not np.isfinite(values).all():
            raise ValueError(f"DAFM cattle type profile has invalid values in {column}")
        dafm[column] = values

    dafm["County"] = dafm["COUNTY"].map(_normalise_county)
    dafm["_NAME_KEY"] = dafm["ELECTORAL_DIVISION"].map(_normalise_ed_name)

    county = dafm.groupby("County")[
        ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]
    ].sum()

    low_herd = dafm["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )
    local = (
        dafm.loc[~low_herd]
        .groupby(["County", "_NAME_KEY"])[
            ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]
        ]
        .sum()
    )

    signal = pd.DataFrame(index=ed_frame.index)
    signal["AIM_DAIRY_MATCHED"] = False
    signal["AIM_DAIRY_TYPE_HEAD"] = 0.0
    signal["AIM_TOTAL_HEAD"] = 0.0
    signal["AIM_COUNTY_DAIRY_TYPE_HEAD"] = np.nan

    for county_name, idx in ed_frame.groupby("County").groups.items():
        if county_name not in county.index:
            raise ValueError(f"DAFM cattle type profile missing county {county_name}")
        county_dairy = float(county.loc[county_name, "AVERAGE_CATTLE_DAIRY"])
        if county_dairy <= 0:
            raise ValueError(f"DAFM county dairy-type total is zero: {county_name}")
        signal.loc[idx, "AIM_COUNTY_DAIRY_TYPE_HEAD"] = county_dairy

        for i in idx:
            keys = {
                _normalise_ed_name(part)
                for part in str(ed_frame.at[i, "ED"]).split("/")
                if _normalise_ed_name(part)
            }
            local_total = 0.0
            local_dairy = 0.0
            matched = False
            for key in keys:
                lookup = (county_name, key)
                if lookup in local.index:
                    values = local.loc[lookup]
                    local_total += float(values["AVERAGE_NUMBER_CATTLE"])
                    local_dairy += float(values["AVERAGE_CATTLE_DAIRY"])
                    matched = True
            if matched:
                signal.at[i, "AIM_DAIRY_MATCHED"] = True
                signal.at[i, "AIM_DAIRY_TYPE_HEAD"] = local_dairy
                signal.at[i, "AIM_TOTAL_HEAD"] = local_total

    if signal["AIM_COUNTY_DAIRY_TYPE_HEAD"].isna().any():
        raise AssertionError("AIM dairy anchor signal has missing county totals")
    return signal


def _allocate_dairy_anchor_residual(
    published_dairy: np.ndarray,
    reconciled_total: np.ndarray,
    reconciled_other_cows: np.ndarray,
    target: int,
    aim_dairy_head: np.ndarray,
    aim_county_dairy_head: float,
    matched: np.ndarray,
) -> np.ndarray:
    """Preserve published ED dairy counts and allocate only the county gap.

    The county target remains AAA10. Published ED dairy counts are lower
    bounds. AIM broad dairy-type geography supplies the untuned spatial prior
    for the positive county residual. The residual weight is the positive
    difference between the county-scaled AIM dairy-type expectation and the
    published dairy count. If that signal is exhausted, direct AIM dairy-type
    head and then remaining physical capacity provide deterministic fallbacks.
    """

    published = np.asarray(published_dairy, dtype=np.int64)
    total = np.asarray(reconciled_total, dtype=np.int64)
    other_cows = np.asarray(reconciled_other_cows, dtype=np.int64)
    aim_dairy = np.asarray(aim_dairy_head, dtype=float)
    matched = np.asarray(matched, dtype=bool)
    target = int(target)

    gap = target - int(published.sum())
    if gap < 0:
        raise AssertionError("AAA10 dairy target is below published ED dairy sum")
    capacity = total - other_cows - published
    if (capacity < 0).any():
        raise AssertionError("published dairy cows exceed reconciled cattle capacity")

    # Preserve genuine no-adult-cow receiver/rearing EDs. AIM dairy-type cattle
    # in such EDs may be followers and are not evidence of resident dairy cows.
    adult_cow_support = (published > 0) | (other_cows > 0)
    capacity = np.where(adult_cow_support, capacity, 0).astype(np.int64)

    if gap > int(capacity.sum()):
        raise AssertionError("county dairy gap exceeds eligible reconciled cattle capacity")
    if gap == 0:
        return published.copy()

    county_aim = float(aim_county_dairy_head)
    if not np.isfinite(county_aim) or county_aim <= 0:
        raise ValueError("AIM county dairy-type total must be positive")

    expected = np.zeros(len(published), dtype=float)
    expected[matched] = target * aim_dairy[matched] / county_aim
    weights = np.maximum(0.0, expected - published.astype(float))
    weights[~matched] = 0.0
    weights[~adult_cow_support] = 0.0

    if float(weights.sum()) <= 0:
        weights = np.where(matched & adult_cow_support, aim_dairy, 0.0)
    if float(weights.sum()) <= 0:
        weights = np.where(adult_cow_support, published.astype(float), 0.0)

    addition = _bounded_weighted_allocate(weights, capacity, gap)
    reconciled = published + addition

    if int(reconciled.sum()) != target:
        raise AssertionError("AIM dairy residual reconciliation failed county closure")
    if (reconciled < published).any():
        raise AssertionError("AIM dairy residual reconciliation reduced a published count")
    if (reconciled + other_cows > total).any():
        raise AssertionError("AIM dairy residual reconciliation exceeded total cattle")
    return reconciled


def _age_sex_prior_mode(config: SpatialConfig) -> str:
    """Return the configured ED age-sex prior rule."""

    value = str(
        config.raw.get("cattle", {}).get("age_sex_prior", "flat_county")
    ).strip()
    if value not in AGE_SEX_PRIOR_MODES:
        raise ValueError(
            "cattle.age_sex_prior must be one of "
            + ", ".join(sorted(AGE_SEX_PRIOR_MODES))
        )
    return value


def _age_sex_logit_epsilon(config: SpatialConfig) -> float:
    value = float(
        config.raw.get("cattle", {}).get(
            "dafm_logit_epsilon", DEFAULT_LOGIT_EPSILON
        )
    )
    if not 0.0 < value < 0.5:
        raise ValueError("cattle.dafm_logit_epsilon must lie in (0, 0.5)")
    return value


def _build_historical_spatial_weights(
    anchor_2020: pd.DataFrame,
    ed_2010: pd.DataFrame,
) -> pd.DataFrame:
    """Build component-specific 2010 and 2020 within-county ED shares.

    Published 2010 zeroes remain zeroes. A blank 2010 component carries no
    component-specific information, so that ED retains its reconciled 2020
    within-county share for that component. The published 2010 values in the
    county are rescaled over the remaining share so each county closes to one.
    """

    anchor = anchor_2020.copy()
    anchor["_ED_KEY"] = anchor["CSOED"].map(canonical_ed_key)
    if anchor["_ED_KEY"].duplicated().any():
        raise AssertionError("2020 cattle anchor contains duplicate canonical ED keys")

    source = ed_2010.set_index("_ED_KEY")
    missing = sorted(set(anchor["_ED_KEY"]) - set(source.index))
    if missing:
        raise AssertionError(
            f"2010 cattle input is missing {len(missing)} EDs from the 2020 model frame"
        )

    weights = anchor[["County", "CSOED", "_ED_KEY"]].copy()

    for component in SPATIAL_COMPONENTS:
        v2010 = anchor["_ED_KEY"].map(source[component])
        s2010 = pd.Series(0.0, index=anchor.index, dtype=float)
        s2020 = pd.Series(0.0, index=anchor.index, dtype=float)

        for county_name, idx in anchor.groupby("County").groups.items():
            total_2020 = float(anchor.loc[idx, component].sum())
            if total_2020 <= 0:
                raise AssertionError(
                    f"{county_name}: zero 2020 support for {component}"
                )

            county_s2020 = anchor.loc[idx, component].astype(float) / total_2020
            s2020.loc[idx] = county_s2020

            county_v2010 = v2010.loc[idx]
            blank = county_v2010.isna()
            published = county_v2010.loc[~blank]

            if float(published.sum()) <= 0:
                s2010.loc[idx] = county_s2020
                continue

            blank_index = county_v2010.index[blank]
            published_index = published.index
            s2010.loc[blank_index] = county_s2020.loc[blank_index]

            remaining_share = 1.0 - float(county_s2020.loc[blank_index].sum())
            if remaining_share < -1e-12:
                raise AssertionError(
                    f"{county_name}: 2010 blank-share rule exceeded one for {component}"
                )
            s2010.loc[published_index] = (
                published.astype(float) / float(published.sum())
            ) * max(0.0, remaining_share)

        weights[f"{component}_SHARE_2010"] = s2010
        weights[f"{component}_SHARE_2020"] = s2020

        sums_2010 = weights.groupby("County")[f"{component}_SHARE_2010"].sum()
        sums_2020 = weights.groupby("County")[f"{component}_SHARE_2020"].sum()
        if float((sums_2010 - 1.0).abs().max()) > 1e-9:
            raise AssertionError(f"2010 {component} shares do not close within county")
        if float((sums_2020 - 1.0).abs().max()) > 1e-9:
            raise AssertionError(f"2020 {component} shares do not close within county")

    return weights


def _weights_for_year(
    historical_weights: pd.DataFrame,
    idx,
    component: str,
    year: int,
) -> np.ndarray:
    """Return time-weighted 2010-2020 ED shares for one component and year."""

    if not 2010 <= int(year) <= 2020:
        raise ValueError("two-anchor weights are defined only for 2010-2020")

    lambda_2020 = (int(year) - 2010) / 10.0
    s2010 = historical_weights.loc[idx, f"{component}_SHARE_2010"].to_numpy(
        dtype=float
    )
    s2020 = historical_weights.loc[idx, f"{component}_SHARE_2020"].to_numpy(
        dtype=float
    )
    return (1.0 - lambda_2020) * s2010 + lambda_2020 * s2020


def _build_2020_baseline(
    ed_source,
    county: pd.DataFrame,
    expected_eds: int,
    age_sex_mode: str = "flat_county",
    dafm_path=None,
    logit_epsilon: float = DEFAULT_LOGIT_EPSILON,
    dairy_anchor_mode: str = "positive_proportional",
) -> pd.DataFrame:
    """Reconcile the fixed 2020 ED cattle baseline to AAA10 county controls."""

    ed = pd.read_csv(ed_source)
    required = [
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED",
        *MAIN_CATTLE_COLS,
    ]
    _require_columns(ed, required, "2020 ED cattle baseline")

    ed["County"] = ed["County"].map(_normalise_county)
    ed = ed.sort_values(["County", "CSOED"], kind="stable").reset_index(drop=True)
    _as_nonnegative_integer(ed, MAIN_CATTLE_COLS, "2020 ED cattle baseline")

    if len(ed) != expected_eds or ed["CSOED"].nunique() != expected_eds:
        raise AssertionError(f"expected {expected_eds:,} unique EDs in 2020 baseline")
    if ed["CSOED"].duplicated().any():
        raise AssertionError("duplicate CSOED values in 2020 baseline")

    initial_identity = (
        ed["TOTAL_CATTLE"] - ed["DAIRY_COW"] - ed["OTHER_COW"] - ed["OTHER_CATTLE"]
    )
    if int(initial_identity.abs().max()) != 0:
        raise AssertionError("input 2020 cattle identity does not close")

    county_2020 = county.loc[county["Year"] == 2020].copy()
    if len(county_2020) != 26 or county_2020["County"].duplicated().any():
        raise AssertionError("AAA10 2020 must contain one row for each of 26 counties")

    ed_counties = set(ed["County"].unique())
    if set(county_2020["County"].unique()) != ed_counties:
        raise AssertionError("county coverage differs between ED baseline and AAA10")

    if dairy_anchor_mode not in DAIRY_ANCHOR_MODES:
        raise ValueError(
            "dairy_anchor_mode must be one of "
            + ", ".join(sorted(DAIRY_ANCHOR_MODES))
        )

    published_dairy = ed["DAIRY_COW"].to_numpy(dtype=np.int64).copy()
    aim_dairy_signal = None
    if dairy_anchor_mode == "aim_residual":
        if dafm_path is None:
            raise ValueError("AIM residual dairy anchor requires a DAFM profile path")
        aim_dairy_signal = _build_aim_dairy_anchor_signal(ed, dafm_path)

    controls = {
        "OTHER_COW": "Other cows__HEAD",
        "TOTAL_CATTLE": "Total cattle__HEAD",
    }

    for county_name in sorted(ed_counties):
        idx = ed.index[ed["County"] == county_name]
        source = county_2020.loc[county_2020["County"] == county_name].iloc[0]

        for ed_column, target_column in controls.items():
            weights = ed.loc[idx, ed_column].to_numpy(dtype=float)
            target = int(source[target_column])
            if target > 0 and float(weights.sum()) <= 0:
                raise ValueError(
                    f"{county_name}: positive {ed_column} target with zero ED support"
                )
            ed.loc[idx, ed_column] = hamilton_allocate(weights, target)

        dairy_target = int(source["Dairy cows__HEAD"])
        if dairy_anchor_mode == "positive_proportional":
            weights = published_dairy[idx].astype(float)
            if dairy_target > 0 and float(weights.sum()) <= 0:
                raise ValueError(
                    f"{county_name}: positive DAIRY_COW target with zero ED support"
                )
            dairy = hamilton_allocate(weights, dairy_target)
        else:
            county_signal = aim_dairy_signal.loc[idx]
            dairy = _allocate_dairy_anchor_residual(
                published_dairy[idx],
                ed.loc[idx, "TOTAL_CATTLE"].to_numpy(dtype=np.int64),
                ed.loc[idx, "OTHER_COW"].to_numpy(dtype=np.int64),
                dairy_target,
                county_signal["AIM_DAIRY_TYPE_HEAD"].to_numpy(dtype=float),
                float(county_signal["AIM_COUNTY_DAIRY_TYPE_HEAD"].iloc[0]),
                county_signal["AIM_DAIRY_MATCHED"].to_numpy(dtype=bool),
            )
        ed.loc[idx, "DAIRY_COW"] = dairy

    ed["OTHER_CATTLE"] = (
        ed["TOTAL_CATTLE"] - ed["DAIRY_COW"] - ed["OTHER_COW"]
    ).astype(np.int64)
    if (ed["OTHER_CATTLE"] < 0).any():
        raise AssertionError("2020 reconciliation produced negative OTHER_CATTLE")

    for output_column in AGE_SEX_COLS:
        ed[output_column] = 0

    age_signal = None
    if age_sex_mode == "dafm_log_odds":
        if dafm_path is None:
            raise ValueError("DAFM log-odds age-sex mode requires a DAFM profile path")
        age_signal = build_dafm_age_signal(ed, dafm_path)

    for county_name in sorted(ed_counties):
        idx = ed.index[ed["County"] == county_name]
        row_totals = ed.loc[idx, "OTHER_CATTLE"].to_numpy(dtype=np.int64)
        source = county_2020.loc[county_2020["County"] == county_name].iloc[0]

        components = np.array(
            [source[f"{column}__HEAD"] for column in AAA_AGE_SEX_COLS],
            dtype=float,
        )
        if float(components.sum()) <= 0:
            raise AssertionError(f"{county_name}: zero AAA10 age-sex component sum")

        if age_signal is None:
            allocation, _ = allocate_age_sex(
                row_totals,
                components,
                mode="flat_county",
                epsilon=logit_epsilon,
            )
        else:
            allocation, _ = allocate_age_sex(
                row_totals,
                components,
                mode=age_sex_mode,
                local_q=age_signal.loc[idx, "DAFM_Q_LOCAL"].to_numpy(dtype=float),
                county_q=float(age_signal.loc[idx, "DAFM_Q_COUNTY"].iloc[0]),
                epsilon=logit_epsilon,
            )
        for j, output_column in enumerate(AGE_SEX_COLS):
            ed.loc[idx, output_column] = allocation[:, j]

    _as_nonnegative_integer(ed, MAIN_CATTLE_COLS + AGE_SEX_COLS, "2020 reconciled cattle")
    _validate_ed_cattle_accounting(ed, "2020 reconciled cattle")
    _validate_county_controls(ed, county_2020, 2020)

    return ed


def _validate_ed_cattle_accounting(frame: pd.DataFrame, label: str) -> None:
    other_difference = frame["OTHER_CATTLE"] - frame[AGE_SEX_COLS].sum(axis=1)
    total_difference = (
        frame["TOTAL_CATTLE"]
        - frame["DAIRY_COW"]
        - frame["OTHER_COW"]
        - frame["OTHER_CATTLE"]
    )
    if int(other_difference.abs().max()) != 0:
        raise AssertionError(f"{label}: OTHER_CATTLE age-sex closure failed")
    if int(total_difference.abs().max()) != 0:
        raise AssertionError(f"{label}: TOTAL_CATTLE identity failed")


def _validate_county_controls(frame: pd.DataFrame, county_year: pd.DataFrame, year: int) -> None:
    observed = (
        frame.groupby("County", as_index=False)
        .agg(
            DAIRY_COW=("DAIRY_COW", "sum"),
            OTHER_COW=("OTHER_COW", "sum"),
            OTHER_CATTLE=("OTHER_CATTLE", "sum"),
            TOTAL_CATTLE=("TOTAL_CATTLE", "sum"),
        )
    )
    target = county_year[
        ["County", "Total cattle__HEAD", "Dairy cows__HEAD", "Other cows__HEAD"]
    ].copy()
    target["OTHER_CATTLE_TARGET"] = (
        target["Total cattle__HEAD"]
        - target["Dairy cows__HEAD"]
        - target["Other cows__HEAD"]
    )
    check = observed.merge(target, on="County", how="left", validate="one_to_one")
    differences = np.column_stack(
        [
            check["DAIRY_COW"] - check["Dairy cows__HEAD"],
            check["OTHER_COW"] - check["Other cows__HEAD"],
            check["OTHER_CATTLE"] - check["OTHER_CATTLE_TARGET"],
            check["TOTAL_CATTLE"] - check["Total cattle__HEAD"],
        ]
    )
    if int(np.abs(differences).max()) != 0:
        raise AssertionError(f"{year}: county AAA10 cattle controls do not close")


def build_cattle_panel(config: SpatialConfig) -> pd.DataFrame:
    """Build the validated CSO-controlled annual cattle ED panel.

    The annual county population is fixed by AAA10. In two-anchor mode, 2015-2019
    within-county ED shares are jointly informed by the 2010 and 2020 census
    geographies, weighted by temporal proximity. The 2020 anchor is exact and
    2021-2025 retain its ED shares. Fixed-2020 mode remains available for
    reproducibility. Same-year other-cattle age-sex county margins close exactly.

    Returns
    -------
    pandas.DataFrame
        2,857 EDs x 11 years for the Ireland 2015-2025 configuration.
    """

    ed_path = config.files["cso_ed_2020"]
    county_path = config.files["cso_cattle_county"]
    if not ed_path.exists():
        raise FileNotFoundError(ed_path)
    if not county_path.exists():
        raise FileNotFoundError(county_path)

    weight_mode = _spatial_weight_mode(config)
    dairy_anchor_mode = _dairy_anchor_mode(config)
    age_sex_mode = _age_sex_prior_mode(config)
    logit_epsilon = _age_sex_logit_epsilon(config)
    dafm_path = config.files.get("dafm_aim_ed_cattle_profile_2020")
    if age_sex_mode == "dafm_log_odds" or dairy_anchor_mode == "aim_residual":
        if dafm_path is None or not dafm_path.exists():
            raise FileNotFoundError(dafm_path)

    county = _load_aaa10(county_path)
    baseline = _build_2020_baseline(
        ed_path,
        county,
        config.expected_eds,
        age_sex_mode=age_sex_mode,
        dafm_path=dafm_path,
        logit_epsilon=logit_epsilon,
        dairy_anchor_mode=dairy_anchor_mode,
    )
    expected_counties = set(baseline["County"].unique())
    age_signal = (
        build_dafm_age_signal(baseline, dafm_path)
        if age_sex_mode == "dafm_log_odds"
        else None
    )

    historical_weights: pd.DataFrame | None = None
    if weight_mode == "two_anchor_2010_2020":
        ed_2010_path = config.files.get("cso_ed_2010")
        if ed_2010_path is None or not ed_2010_path.exists():
            raise FileNotFoundError(ed_2010_path)
        ed_2010 = _load_cso_ed_2010(ed_2010_path)
        historical_weights = _build_historical_spatial_weights(baseline, ed_2010)

    if len(expected_counties) != 26:
        raise AssertionError("cattle baseline must contain exactly 26 counties")

    for year in YEARS:
        source = county.loc[county["Year"] == year]
        if len(source) != 26 or source["County"].duplicated().any():
            raise AssertionError(f"{year}: AAA10 county coverage is incomplete")
        if set(source["County"].unique()) != expected_counties:
            raise AssertionError(f"{year}: AAA10 county names differ from 2020 baseline")

    fixed_weights: dict[str, dict[str, object]] = {}
    for county_name in sorted(expected_counties):
        idx = baseline.index[baseline["County"] == county_name]
        fixed_weights[county_name] = {
            "index": idx,
            "DAIRY_COW": baseline.loc[idx, "DAIRY_COW"].to_numpy(dtype=np.int64),
            "OTHER_COW": baseline.loc[idx, "OTHER_COW"].to_numpy(dtype=np.int64),
            "OTHER_CATTLE": baseline.loc[idx, "OTHER_CATTLE"].to_numpy(dtype=np.int64),
        }

    annual: list[pd.DataFrame] = []

    for year in YEARS:
        frame = baseline.copy()
        frame.insert(0, "YEAR", year)
        frame.insert(1, "STATIC_CONTEXT_YEAR", config.base_year)

        if year == config.base_year:
            frame["LIVESTOCK_DATA_STATUS"] = "FIXED_2020_RECONCILED_ANCHOR"
        else:
            if weight_mode == "two_anchor_2010_2020" and year < config.base_year:
                frame["LIVESTOCK_DATA_STATUS"] = (
                    "RECONSTRUCTED_FROM_2010_2020_TIME_WEIGHTED_ED_SHARES_"
                    "AND_ANNUAL_AAA10_COUNTY_CONTROLS"
                )
            else:
                frame["LIVESTOCK_DATA_STATUS"] = (
                    "RECONSTRUCTED_FROM_2020_ED_WEIGHTS_AND_ANNUAL_AAA10_COUNTY_CONTROLS"
                )
            for column in MAIN_CATTLE_COLS + AGE_SEX_COLS:
                frame[column] = 0

            for county_name in sorted(expected_counties):
                support = fixed_weights[county_name]
                idx = support["index"]
                source = county.loc[
                    (county["Year"] == year) & (county["County"] == county_name)
                ].iloc[0]

                total_target = int(source["Total cattle__HEAD"])
                dairy_target = int(source["Dairy cows__HEAD"])
                other_cow_target = int(source["Other cows__HEAD"])
                other_cattle_target = total_target - dairy_target - other_cow_target
                if other_cattle_target < 0:
                    raise AssertionError(f"{county_name} {year}: negative OTHER_CATTLE target")

                if (
                    weight_mode == "two_anchor_2010_2020"
                    and year < config.base_year
                ):
                    if historical_weights is None:
                        raise AssertionError("two-anchor historical weights were not built")
                    dairy_weights = _weights_for_year(
                        historical_weights, idx, "DAIRY_COW", year
                    )
                    other_cow_weights = _weights_for_year(
                        historical_weights, idx, "OTHER_COW", year
                    )
                    other_cattle_weights = _weights_for_year(
                        historical_weights, idx, "OTHER_CATTLE", year
                    )
                else:
                    dairy_weights = support["DAIRY_COW"].astype(float)
                    other_cow_weights = support["OTHER_COW"].astype(float)
                    other_cattle_weights = support["OTHER_CATTLE"].astype(float)

                dairy = hamilton_allocate(dairy_weights, dairy_target)
                other_cows = hamilton_allocate(other_cow_weights, other_cow_target)
                other_cattle = hamilton_allocate(
                    other_cattle_weights, other_cattle_target
                )

                for label, allocation_values, allocation_weights in (
                    ("DAIRY_COW", dairy, dairy_weights),
                    ("OTHER_COW", other_cows, other_cow_weights),
                    ("OTHER_CATTLE", other_cattle, other_cattle_weights),
                ):
                    zero_support = np.asarray(allocation_weights, dtype=float) <= 1e-15
                    if (np.asarray(allocation_values)[zero_support] != 0).any():
                        raise AssertionError(
                            f"{year} {county_name}: spatial support rule failed for {label}"
                        )

                frame.loc[idx, "DAIRY_COW"] = dairy
                frame.loc[idx, "OTHER_COW"] = other_cows
                frame.loc[idx, "OTHER_CATTLE"] = other_cattle
                frame.loc[idx, "TOTAL_CATTLE"] = dairy + other_cows + other_cattle

                components = np.array(
                    [source[f"{column}__HEAD"] for column in AAA_AGE_SEX_COLS],
                    dtype=float,
                )
                if float(components.sum()) <= 0:
                    raise AssertionError(f"{county_name} {year}: zero age-sex component sum")

                if age_signal is None:
                    allocation, _ = allocate_age_sex(
                        other_cattle,
                        components,
                        mode="flat_county",
                        epsilon=logit_epsilon,
                    )
                else:
                    allocation, _ = allocate_age_sex(
                        other_cattle,
                        components,
                        mode=age_sex_mode,
                        local_q=age_signal.loc[idx, "DAFM_Q_LOCAL"].to_numpy(dtype=float),
                        county_q=float(age_signal.loc[idx, "DAFM_Q_COUNTY"].iloc[0]),
                        epsilon=logit_epsilon,
                    )
                for j, output_column in enumerate(AGE_SEX_COLS):
                    frame.loc[idx, output_column] = allocation[:, j]

        _as_nonnegative_integer(
            frame, MAIN_CATTLE_COLS + AGE_SEX_COLS, f"{year} cattle panel"
        )
        _validate_ed_cattle_accounting(frame, f"{year} cattle panel")
        _validate_county_controls(frame, county.loc[county["Year"] == year], year)

        annual.append(frame)

    panel = pd.concat(annual, ignore_index=True)
    expected_rows = config.expected_eds * len(YEARS)
    if len(panel) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} cattle ED-year rows")
    if panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED cattle rows")
    if panel["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("cattle ED coverage changed")
    if set(panel["YEAR"].unique()) != set(YEARS):
        raise AssertionError("cattle panel years are not exactly 2015-2025")

    # The 2020 panel must be an exact numeric copy of the reconciled baseline.
    p2020 = panel.loc[panel["YEAR"] == config.base_year].sort_values("CSOED").reset_index(drop=True)
    b2020 = baseline.sort_values("CSOED").reset_index(drop=True)
    for column in MAIN_CATTLE_COLS + AGE_SEX_COLS:
        if not np.array_equal(p2020[column].to_numpy(), b2020[column].to_numpy()):
            raise AssertionError(f"2020 cattle lock failed for {column}")

    return panel
