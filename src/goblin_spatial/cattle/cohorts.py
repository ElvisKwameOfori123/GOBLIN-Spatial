"""GOBLIN cattle cohort disaggregation of the CSO ED cattle panel.

The CSO ED panel is the controlling livestock population. GOBLIN cohort data
supply national biological relationships used only to subdivide the six
existing CSO pre-adult age-sex containers into DxD, DxB and BxB cohorts.

Genetic support is ED-informed. Dairy cows support dairy-origin DxD/DxB
cohorts and other/suckler cows support BxB cohorts. A sparse set of
receiver/rearing EDs is admitted where the ED's own young-stock-to-adult-cow
structure indicates bought-in cattle and where that support is required to
reproduce the national GOBLIN cohort margins. County context is not used to
make every ED eligible for every genetic cohort.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate


YEARS = tuple(range(2015, 2026))
GENETICS = ("DxD", "DxB", "BxB")

CONTAINERS = {
    "CATTLE_MALE_UNDER_1": {
        "DxD": "DxD_calves_m",
        "DxB": "DxB_calves_m",
        "BxB": "BxB_calves_m",
    },
    "CATTLE_FEMALE_UNDER_1": {
        "DxD": "DxD_calves_f",
        "DxB": "DxB_calves_f",
        "BxB": "BxB_calves_f",
    },
    "CATTLE_FEMALE_1_2": {
        "DxD": "DxD_heifers_less_2_yr",
        "DxB": "DxB_heifers_less_2_yr",
        "BxB": "BxB_heifers_less_2_yr",
    },
    "CATTLE_MALE_1_2": {
        "DxD": "DxD_steers_less_2_yr",
        "DxB": "DxB_steers_less_2_yr",
        "BxB": "BxB_steers_less_2_yr",
    },
    "CATTLE_FEMALE_2_PLUS": {
        "DxD": "DxD_heifers_more_2_yr",
        "DxB": "DxB_heifers_more_2_yr",
        "BxB": "BxB_heifers_more_2_yr",
    },
    "CATTLE_MALE_2_PLUS": {
        "DxD": "DxD_steers_more_2_yr",
        "DxB": "DxB_steers_more_2_yr",
        "BxB": "BxB_steers_more_2_yr",
    },
}

FINAL_21_COHORTS = [
    "dairy_cows",
    "suckler_cows",
    "DxD_calves_m",
    "DxD_calves_f",
    "DxB_calves_m",
    "DxB_calves_f",
    "BxB_calves_m",
    "BxB_calves_f",
    "DxD_heifers_less_2_yr",
    "DxD_steers_less_2_yr",
    "DxB_heifers_less_2_yr",
    "DxB_steers_less_2_yr",
    "BxB_heifers_less_2_yr",
    "BxB_steers_less_2_yr",
    "DxD_heifers_more_2_yr",
    "DxD_steers_more_2_yr",
    "DxB_heifers_more_2_yr",
    "DxB_steers_more_2_yr",
    "BxB_heifers_more_2_yr",
    "BxB_steers_more_2_yr",
    "bulls",
]

CATTLE_CONTROL_COLS = [
    "DAIRY_COW",
    "OTHER_COW",
    "BULLS",
    *CONTAINERS.keys(),
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
]


def _load_goblin(path) -> pd.DataFrame:
    goblin = pd.read_csv(path)
    goblin.columns = [str(column).strip() for column in goblin.columns]

    cohort_columns = [column for column in goblin.columns if column.lower() == "cohorts"]
    if len(cohort_columns) != 1:
        raise ValueError("could not uniquely identify the GOBLIN Cohorts column")
    if cohort_columns[0] != "Cohorts":
        goblin = goblin.rename(columns={cohort_columns[0]: "Cohorts"})

    goblin["Cohorts"] = goblin["Cohorts"].astype(str).str.strip()
    for year in range(2012, 2021):
        column = str(year)
        if column not in goblin.columns:
            raise ValueError(f"GOBLIN cohort data missing year {year}")
        goblin[column] = pd.to_numeric(goblin[column], errors="raise")

    required = {"dairy_cows", "suckler_cows", "bulls"}
    for mapping in CONTAINERS.values():
        required.update(mapping.values())

    available = set(goblin["Cohorts"])
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"GOBLIN cohort data missing required cattle cohorts: {missing}")

    counts = goblin.loc[goblin["Cohorts"].isin(required), "Cohorts"].value_counts()
    if (counts != 1).any():
        raise AssertionError("required GOBLIN cattle cohort rows are not unique")

    return goblin


def _goblin_value(goblin: pd.DataFrame, cohort: str, year: int) -> float:
    row = goblin.loc[goblin["Cohorts"] == cohort]
    if len(row) != 1:
        raise AssertionError(f"expected one GOBLIN row for {cohort}")
    value = float(row.iloc[0][str(year)])
    if not np.isfinite(value) or value < 0:
        raise AssertionError(f"invalid GOBLIN value for {cohort}, {year}")
    return value


def _build_biological_controls(
    cattle: pd.DataFrame, goblin: pd.DataFrame
) -> tuple[dict[tuple[int, str], np.ndarray], dict[tuple[int, str], np.ndarray]]:
    """Return exact national genetic targets and cow-to-cohort coefficients."""

    targets: dict[tuple[int, str], np.ndarray] = {}
    coefficients: dict[tuple[int, str], np.ndarray] = {}

    for year in YEARS:
        source_year = year if year <= 2020 else 2020
        goblin_dairy = _goblin_value(goblin, "dairy_cows", source_year)
        goblin_suckler = _goblin_value(goblin, "suckler_cows", source_year)
        if goblin_dairy <= 0 or goblin_suckler <= 0:
            raise AssertionError(f"{source_year}: non-positive GOBLIN adult cow population")

        year_frame = cattle.loc[cattle["YEAR"] == year]
        cso_dairy = int(year_frame["DAIRY_COW"].sum())
        cso_suckler = int(year_frame["OTHER_COW"].sum())

        for container, mapping in CONTAINERS.items():
            coeff = np.array(
                [
                    _goblin_value(goblin, mapping["DxD"], source_year) / goblin_dairy,
                    _goblin_value(goblin, mapping["DxB"], source_year) / goblin_dairy,
                    _goblin_value(goblin, mapping["BxB"], source_year) / goblin_suckler,
                ],
                dtype=float,
            )
            if (coeff < 0).any():
                raise AssertionError(f"{year} {container}: negative biological coefficient")

            raw_expectation = np.array(
                [
                    coeff[0] * cso_dairy,
                    coeff[1] * cso_dairy,
                    coeff[2] * cso_suckler,
                ],
                dtype=float,
            )
            if float(raw_expectation.sum()) <= 0:
                raise AssertionError(f"{year} {container}: zero GOBLIN expectation")

            container_total = int(year_frame[container].sum())
            targets[(year, container)] = hamilton_allocate(raw_expectation, container_total)
            coefficients[(year, container)] = coeff

    return targets, coefficients


def _support_has_capacity(
    cattle: pd.DataFrame,
    support_ids: set,
    national_targets: dict[tuple[int, str], np.ndarray],
    origin: str,
) -> bool:
    """Check whether a fixed ED support set can carry every annual margin."""

    if origin not in {"dairy", "bxb"}:
        raise ValueError("origin must be 'dairy' or 'bxb'")

    for year in YEARS:
        year_frame = cattle.loc[cattle["YEAR"] == year]
        supported = year_frame["CSOED"].isin(support_ids).to_numpy()

        for container in CONTAINERS:
            row_totals = year_frame[container].to_numpy(dtype=np.int64)
            target = national_targets[(year, container)]
            required = int(target[0] + target[1]) if origin == "dairy" else int(target[2])
            if int(row_totals[supported].sum()) < required:
                return False

    return True


def _build_ed_genetic_support(
    cattle: pd.DataFrame,
    national_targets: dict[tuple[int, str], np.ndarray],
) -> tuple[set, set, dict, dict]:
    """Build fixed ED support for dairy-origin and BxB young-stock cohorts.

    The 2020 adult-cow footprint is the primary spatial signal. EDs with dairy
    cows support DxD/DxB; EDs with other/suckler cows support BxB. EDs with no
    adult cows but with young stock are mandatory receiver/rearing exceptions.

    If additional support is required for exact national GOBLIN margins,
    zero-origin EDs are admitted in descending order of their own 2020
    young-stock-to-opposite-adult-cow ratio. This keeps exceptions sparse and
    ED-informed instead of using a county-wide positive fallback.
    """

    baseline = cattle.loc[cattle["YEAR"] == 2020].copy().sort_values("CSOED")
    if baseline["CSOED"].duplicated().any():
        raise AssertionError("2020 cattle support baseline contains duplicate EDs")

    max_other_cattle = cattle.groupby("CSOED")["OTHER_CATTLE"].max()
    has_young_stock = baseline["CSOED"].map(max_other_cattle).fillna(0).gt(0)
    no_adults = (baseline["DAIRY_COW"] == 0) & (baseline["OTHER_COW"] == 0)
    mandatory_receivers = set(baseline.loc[no_adults & has_young_stock, "CSOED"])

    def build_origin_support(origin: str) -> tuple[set, dict]:
        if origin == "dairy":
            adult_col = "DAIRY_COW"
            opposite_col = "OTHER_COW"
        elif origin == "bxb":
            adult_col = "OTHER_COW"
            opposite_col = "DAIRY_COW"
        else:
            raise ValueError("origin must be 'dairy' or 'bxb'")

        receiver_score = (
            baseline["OTHER_CATTLE"].astype(float)
            / (baseline[opposite_col].astype(float) + 1.0)
        )
        score_map = dict(zip(baseline["CSOED"], receiver_score))

        support = set(baseline.loc[baseline[adult_col] > 0, "CSOED"])
        support.update(mandatory_receivers)

        if not _support_has_capacity(cattle, support, national_targets, origin):
            candidates = baseline.loc[
                (baseline[adult_col] == 0)
                & (~baseline["CSOED"].isin(support))
                & has_young_stock
            ].copy()
            candidates["RECEIVER_SCORE"] = receiver_score.loc[candidates.index]
            candidates = candidates.sort_values(
                ["RECEIVER_SCORE", "OTHER_CATTLE", "CSOED"],
                ascending=[False, False, True],
                kind="stable",
            )

            for ed_id in candidates["CSOED"]:
                support.add(ed_id)
                if _support_has_capacity(cattle, support, national_targets, origin):
                    break

        if not _support_has_capacity(cattle, support, national_targets, origin):
            raise AssertionError(
                f"ED support is insufficient to place all {origin} GOBLIN cattle cohorts"
            )

        return support, score_map

    dairy_support, dairy_receiver_scores = build_origin_support("dairy")
    bxb_support, bxb_receiver_scores = build_origin_support("bxb")
    return dairy_support, bxb_support, dairy_receiver_scores, bxb_receiver_scores


def _bounded_weighted_allocate(weights, capacities, target: int) -> np.ndarray:
    """Allocate an integer target by weights without exceeding row capacities."""

    weights = np.asarray(weights, dtype=float)
    capacities = np.asarray(capacities, dtype=np.int64)
    target = int(target)

    if len(weights) != len(capacities):
        raise ValueError("weights and capacities must have equal length")
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("bounded allocation weights must be finite and non-negative")
    if (capacities < 0).any():
        raise ValueError("bounded allocation capacities must be non-negative")
    if target < 0 or target > int(capacities.sum()):
        raise ValueError("bounded allocation target exceeds available capacity")
    if target == 0:
        return np.zeros(len(capacities), dtype=np.int64)

    fractional = np.zeros(len(capacities), dtype=float)
    active = capacities > 0
    remaining = float(target)

    while remaining > 1e-10:
        indices = np.where(active)[0]
        if len(indices) == 0:
            raise RuntimeError("bounded allocation exhausted capacity")

        available = capacities[indices].astype(float) - fractional[indices]
        current_weights = weights[indices].copy()
        if float(current_weights.sum()) <= 0:
            current_weights = available.copy()
        if float(current_weights.sum()) <= 0:
            raise RuntimeError("bounded allocation has no positive weight or capacity")

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
    if left < 0:
        raise AssertionError("bounded allocation floor exceeded target")

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
        raise RuntimeError("bounded allocation could not close integer target")
    if int(allocation.sum()) != target:
        raise AssertionError("bounded allocation target closure failed")
    if (allocation < 0).any() or (allocation > capacities).any():
        raise AssertionError("bounded allocation violated capacity")

    return allocation


def _allocate_genetics(
    row_totals: np.ndarray,
    col_targets: np.ndarray,
    coeff: np.ndarray,
    dairy_support: np.ndarray,
    bxb_support: np.ndarray,
    dairy_score: np.ndarray,
    bxb_score: np.ndarray,
) -> np.ndarray:
    """Allocate one CSO age-sex container to DxD, DxB and BxB exactly."""

    row_totals = np.asarray(row_totals, dtype=np.int64)
    col_targets = np.asarray(col_targets, dtype=np.int64)
    dairy_support = np.asarray(dairy_support, dtype=bool)
    bxb_support = np.asarray(bxb_support, dtype=bool)
    dairy_score = np.asarray(dairy_score, dtype=float)
    bxb_score = np.asarray(bxb_score, dtype=float)

    if int(row_totals.sum()) != int(col_targets.sum()):
        raise AssertionError("age-sex row totals and genetic targets differ")
    if ((row_totals > 0) & ~(dairy_support | bxb_support)).any():
        raise AssertionError("positive ED age-sex row has no genetic support")

    bxb = np.zeros(len(row_totals), dtype=np.int64)
    bxb_only = bxb_support & ~dairy_support
    both = bxb_support & dairy_support
    bxb[bxb_only] = row_totals[bxb_only]

    remaining_bxb = int(col_targets[2] - bxb.sum())
    if remaining_bxb < 0:
        raise AssertionError("mandatory BxB-only EDs exceed national BxB target")
    if remaining_bxb > int(row_totals[both].sum()):
        raise AssertionError("shared ED support cannot carry national BxB target")

    if remaining_bxb:
        dairy_component = dairy_score * float(coeff[0] + coeff[1])
        bxb_component = bxb_score * float(coeff[2])
        denominator = dairy_component + bxb_component
        bxb_propensity = np.zeros(len(row_totals), dtype=float)
        positive = denominator > 0
        bxb_propensity[positive] = bxb_component[positive] / denominator[positive]
        desired_bxb = row_totals.astype(float) * bxb_propensity

        bxb[both] = _bounded_weighted_allocate(
            desired_bxb[both], row_totals[both], remaining_bxb
        )

    dairy_origin = row_totals - bxb
    dairy_target = int(col_targets[0] + col_targets[1])
    if int(dairy_origin.sum()) != dairy_target:
        raise AssertionError("dairy-origin residual does not match DxD + DxB target")
    if (dairy_origin[~dairy_support] != 0).any():
        raise AssertionError("dairy-origin cattle entered an unsupported ED")
    if (bxb[~bxb_support] != 0).any():
        raise AssertionError("BxB cattle entered an unsupported ED")

    dxd = hamilton_allocate(dairy_origin.astype(float), int(col_targets[0]))
    if (dxd > dairy_origin).any():
        raise AssertionError("DxD allocation exceeded dairy-origin row total")
    dxb = dairy_origin - dxd

    allocation = np.column_stack([dxd, dxb, bxb]).astype(np.int64)
    if not np.array_equal(allocation.sum(axis=1), row_totals):
        raise AssertionError("ED age-sex totals changed during genetic allocation")
    if not np.array_equal(allocation.sum(axis=0), col_targets):
        raise AssertionError("national genetic targets failed during allocation")

    return allocation


def add_cattle_cohorts(cattle_panel: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Express the fixed ED cattle population in the 21 GOBLIN cattle cohorts.

    The spatial distribution and age-sex structure are fixed by the CSO ED
    cattle panel. GOBLIN supplies national DxD/DxB/BxB biological margins.
    The ED's own adult-cow structure supplies genetic support, with sparse
    receiver/rearing exceptions inferred from ED young-stock structure. No ED,
    county or national cattle total is changed.
    """

    cattle = cattle_panel.copy()
    required = ["YEAR", "CSOED", *CATTLE_CONTROL_COLS]
    missing = [column for column in required if column not in cattle.columns]
    if missing:
        raise ValueError(f"cattle cohort module missing required columns: {missing}")

    expected_rows = config.expected_eds * len(YEARS)
    if len(cattle) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} cattle rows")
    if cattle[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED cattle rows")
    if cattle["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("cattle ED coverage changed before cohort disaggregation")
    if set(cattle["YEAR"].unique()) != set(YEARS):
        raise AssertionError("cattle years are not exactly 2015-2025")

    for column in CATTLE_CONTROL_COLS:
        values = pd.to_numeric(cattle[column], errors="raise")
        rounded = np.rint(values.to_numpy(dtype=float))
        if np.max(np.abs(values.to_numpy(dtype=float) - rounded)) > 1e-8:
            raise AssertionError(f"{column} contains non-integer cattle counts")
        if (rounded < 0).any():
            raise AssertionError(f"{column} contains negative cattle counts")
        cattle[column] = rounded.astype(np.int64)

    pre_adult = list(CONTAINERS)
    if int(
        (cattle["BULLS"] + cattle[pre_adult].sum(axis=1) - cattle["OTHER_CATTLE"])
        .abs()
        .max()
    ) != 0:
        raise AssertionError("input OTHER_CATTLE accounting does not close")
    if int(
        (
            cattle["DAIRY_COW"]
            + cattle["OTHER_COW"]
            + cattle["OTHER_CATTLE"]
            - cattle["TOTAL_CATTLE"]
        )
        .abs()
        .max()
    ) != 0:
        raise AssertionError("input TOTAL_CATTLE accounting does not close")

    original_controls = cattle[["YEAR", "CSOED", *CATTLE_CONTROL_COLS]].copy()

    goblin_path = config.files["goblin_cohorts"]
    if not goblin_path.exists():
        raise FileNotFoundError(goblin_path)
    goblin = _load_goblin(goblin_path)
    national_targets, coefficients = _build_biological_controls(cattle, goblin)
    (
        dairy_support_ids,
        bxb_support_ids,
        dairy_receiver_scores,
        bxb_receiver_scores,
    ) = _build_ed_genetic_support(cattle, national_targets)

    cattle["dairy_cows"] = cattle["DAIRY_COW"].astype(np.int64)
    cattle["suckler_cows"] = cattle["OTHER_COW"].astype(np.int64)
    cattle["bulls"] = cattle["BULLS"].astype(np.int64)
    for mapping in CONTAINERS.values():
        for cohort in mapping.values():
            cattle[cohort] = 0

    for year in YEARS:
        year_index = cattle.index[cattle["YEAR"] == year]
        year_frame = cattle.loc[year_index].copy()

        dairy_support = year_frame["CSOED"].isin(dairy_support_ids).to_numpy()
        bxb_support = year_frame["CSOED"].isin(bxb_support_ids).to_numpy()

        dairy_score = year_frame["DAIRY_COW"].to_numpy(dtype=float)
        bxb_score = year_frame["OTHER_COW"].to_numpy(dtype=float)

        dairy_receivers = (dairy_score == 0) & dairy_support
        if dairy_receivers.any():
            receiver_values = year_frame.loc[dairy_receivers, "CSOED"].map(
                dairy_receiver_scores
            )
            dairy_score[dairy_receivers] = np.maximum(
                receiver_values.to_numpy(dtype=float), 1e-9
            )

        bxb_receivers = (bxb_score == 0) & bxb_support
        if bxb_receivers.any():
            receiver_values = year_frame.loc[bxb_receivers, "CSOED"].map(
                bxb_receiver_scores
            )
            bxb_score[bxb_receivers] = np.maximum(
                receiver_values.to_numpy(dtype=float), 1e-9
            )

        dairy_score[~dairy_support] = 0.0
        bxb_score[~bxb_support] = 0.0

        for container, mapping in CONTAINERS.items():
            row_totals = year_frame[container].to_numpy(dtype=np.int64)
            col_targets = national_targets[(year, container)]
            coeff = coefficients[(year, container)]

            allocation = _allocate_genetics(
                row_totals,
                col_targets,
                coeff,
                dairy_support,
                bxb_support,
                dairy_score,
                bxb_score,
            )

            for j, genetic in enumerate(GENETICS):
                cattle.loc[year_index, mapping[genetic]] = allocation[:, j]

    for cohort in FINAL_21_COHORTS:
        cattle[cohort] = pd.to_numeric(cattle[cohort], errors="raise").astype(np.int64)
        if (cattle[cohort] < 0).any():
            raise AssertionError(f"negative GOBLIN cattle cohort: {cohort}")

    for container, mapping in CONTAINERS.items():
        cohort_columns = [mapping[genetic] for genetic in GENETICS]
        difference = cattle[cohort_columns].sum(axis=1) - cattle[container]
        if int(difference.abs().max()) != 0:
            raise AssertionError(f"GOBLIN cohorts do not close to {container}")

    cattle["GOBLIN_21_CATTLE_COHORT_TOTAL"] = cattle[FINAL_21_COHORTS].sum(axis=1)
    if int(
        (cattle["GOBLIN_21_CATTLE_COHORT_TOTAL"] - cattle["TOTAL_CATTLE"])
        .abs()
        .max()
    ) != 0:
        raise AssertionError("21 GOBLIN cattle cohorts do not reproduce TOTAL_CATTLE")

    post_controls = cattle[["YEAR", "CSOED", *CATTLE_CONTROL_COLS]]
    check = original_controls.merge(
        post_controls,
        on=["YEAR", "CSOED"],
        validate="one_to_one",
        suffixes=("_BEFORE", "_AFTER"),
    )
    for column in CATTLE_CONTROL_COLS:
        if not np.array_equal(
            check[f"{column}_BEFORE"].to_numpy(),
            check[f"{column}_AFTER"].to_numpy(),
        ):
            raise AssertionError(f"cohort disaggregation changed CSO control {column}")

    return cattle
