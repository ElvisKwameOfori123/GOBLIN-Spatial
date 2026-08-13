"""Propagate adult-cow reductions into the 21 GOBLIN cattle cohorts spatially.

The rule is deliberately simple and auditable.

For every follower cohort, the selected 2020 or 2025 ED baseline records the
relationship between the relevant adult cows and the cohort already present in
that ED.  If the ED has the relevant adult cows, its follower cohort responds to
that ED's realised adult-cow reduction rate.  Algebraically::

    cohort_reduction_e = adult_reduction_e * (cohort_e / adult_e)
                       = cohort_e * adult_reduction_rate_e

This preserves each ED's observed adult-to-cohort relationship during a
reduction scenario.

Some EDs contain young stock but no corresponding adult cows.  These are
receiver/orphan EDs for that cohort.  Their young stock is assumed to depend on
breeding activity elsewhere in the same county, so their reduction follows the
same-county adult reduction rate::

    orphan_reduction_e = county_adult_reduction
                         * (orphan_cohort_e / county_adults)
                       = orphan_cohort_e * county_adult_reduction_rate

Only if a cohort exists in a county with no corresponding adult cows at all is a
national fallback used.  No mixed-ED decomposition and no arbitrary 30%, 50% or
other spillover factor is imposed.

GOBLIN/COHORTS remains authoritative for the national biological target of each
cohort.  The ED and county relationships determine only where that required
cohort reduction falls.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.allocation import _bounded_integer_allocate


DXD_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
FOLLOWER_COHORTS = tuple(
    c for c in FINAL_21_COHORTS if c not in {"dairy_cows", "suckler_cows"}
)


def _integer_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def _cohort_origin(cohort: str) -> str:
    if cohort in DXD_COHORTS or cohort in DXB_COHORTS:
        return "DAIRY"
    if cohort in BXB_COHORTS:
        return "SUCKLER"
    if cohort == "bulls":
        return "ADULT_COWS"
    raise ValueError(f"cannot identify adult origin for cohort {cohort}")


def _relationship_components(
    base_adults: np.ndarray,
    cohort_base: np.ndarray,
    counties: np.ndarray,
) -> dict[str, np.ndarray]:
    """Describe the simple ED relationship used by the scenario ripple.

    ``LOCAL_ED`` means the ED contains both the relevant parent adults and the
    follower cohort. ``COUNTY_RECEIVER`` means the cohort exists but the ED has
    no corresponding adults, so the cohort is linked to the county adult pool.
    ``NATIONAL_ORPHAN`` is reserved for the rare case where the county itself has
    no corresponding adults. ``NONE`` means the cohort is absent in the ED.
    """

    base_adults = np.asarray(base_adults, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)
    counties = np.asarray(counties, dtype=object)
    n = len(base_adults)
    if len(cohort_base) != n or len(counties) != n:
        raise ValueError("adult, cohort and county arrays must have equal length")
    if (base_adults < 0).any() or (cohort_base < 0).any():
        raise ValueError("adult and cohort counts must be non-negative")
    if pd.isna(counties).any():
        raise ValueError("county is required for cohort relationship accounting")

    network = pd.DataFrame(
        {
            "County": counties,
            "BASE_ADULTS": base_adults,
            "BASE_COHORT": cohort_base,
        }
    )
    county_adults = (
        network.groupby("County", sort=False)["BASE_ADULTS"]
        .transform("sum")
        .to_numpy(dtype=float)
    )
    county_cohort = (
        network.groupby("County", sort=False)["BASE_COHORT"]
        .transform("sum")
        .to_numpy(dtype=float)
    )

    ed_ratio = np.divide(
        cohort_base.astype(float),
        base_adults.astype(float),
        out=np.zeros(n, dtype=float),
        where=base_adults > 0,
    )
    orphan_ratio_to_county_adults = np.divide(
        cohort_base.astype(float),
        county_adults,
        out=np.zeros(n, dtype=float),
        where=(base_adults == 0) & (cohort_base > 0) & (county_adults > 0),
    )
    orphan_share_of_county_cohort = np.divide(
        cohort_base.astype(float),
        county_cohort,
        out=np.zeros(n, dtype=float),
        where=(base_adults == 0) & (cohort_base > 0) & (county_cohort > 0),
    )

    source = np.full(n, "NONE", dtype=object)
    has_cohort = cohort_base > 0
    local = has_cohort & (base_adults > 0)
    receiver = has_cohort & (base_adults == 0) & (county_adults > 0)
    national_orphan = has_cohort & (base_adults == 0) & (county_adults <= 0)
    source[local] = "LOCAL_ED"
    source[receiver] = "COUNTY_RECEIVER"
    source[national_orphan] = "NATIONAL_ORPHAN"

    return {
        "ed_ratio": ed_ratio,
        "county_adults": county_adults,
        "county_cohort": county_cohort,
        "orphan_ratio_to_county_adults": orphan_ratio_to_county_adults,
        "orphan_share_of_county_cohort": orphan_share_of_county_cohort,
        "source": source,
    }


def _reduction_signal(
    base_adults: np.ndarray,
    adult_reductions: np.ndarray,
    cohort_base: np.ndarray,
    counties: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the local-parent or county-parent cohort reduction rate.

    An ED with parent adults uses its own realised adult reduction rate.  An ED
    with the cohort but no parent adults uses the realised reduction rate of the
    relevant adults in its county.  A national rate is used only when the county
    has none of the relevant parent adults.
    """

    base_adults = np.asarray(base_adults, dtype=np.int64)
    adult_reductions = np.asarray(adult_reductions, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)
    counties = np.asarray(counties, dtype=object)

    n = len(base_adults)
    if any(len(x) != n for x in (adult_reductions, cohort_base, counties)):
        raise ValueError("adult, cohort and county arrays must have equal length")
    if (base_adults < 0).any() or (adult_reductions < 0).any() or (cohort_base < 0).any():
        raise ValueError("adult, reduction and cohort counts must be non-negative")
    if (adult_reductions > base_adults).any():
        raise AssertionError("adult reduction exceeds adult baseline")
    if pd.isna(counties).any():
        raise ValueError("county is required for receiver/orphan cohort propagation")

    parts = _relationship_components(base_adults, cohort_base, counties)
    county_base = np.asarray(parts["county_adults"], dtype=float)
    source = np.asarray(parts["source"], dtype=object)

    local_rate = np.divide(
        adult_reductions.astype(float),
        base_adults.astype(float),
        out=np.zeros(n, dtype=float),
        where=base_adults > 0,
    )

    network = pd.DataFrame(
        {
            "County": counties,
            "ADULT_REDUCTION": adult_reductions,
        }
    )
    county_reduction = (
        network.groupby("County", sort=False)["ADULT_REDUCTION"]
        .transform("sum")
        .to_numpy(dtype=float)
    )
    county_rate = np.divide(
        county_reduction,
        county_base,
        out=np.zeros(n, dtype=float),
        where=county_base > 0,
    )

    national_base = int(base_adults.sum())
    national_reduction = int(adult_reductions.sum())
    national_rate = national_reduction / national_base if national_base > 0 else 0.0

    signal = np.zeros(n, dtype=float)
    local = source == "LOCAL_ED"
    receiver = source == "COUNTY_RECEIVER"
    orphan = source == "NATIONAL_ORPHAN"
    signal[local] = local_rate[local]
    signal[receiver] = county_rate[receiver]
    signal[orphan] = national_rate
    return np.clip(signal, 0.0, 1.0), source


def build_ed_cohort_dependency_profile(baseline: pd.DataFrame) -> pd.DataFrame:
    """Record each ED's adult-to-cohort relationship before scenarios.

    The output is long-form, one row per ED and follower cohort.  For a normal
    breeding ED, ``ED_COHORT_PER_ADULT_RATIO`` is the observed baseline cohort
    divided by the relevant parent adults in that ED.  For an orphan/receiver ED
    with no parent adults, ``ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO`` records its
    cohort relative to the relevant adult pool elsewhere in the county.  These
    are accounting relationships, not observed animal movement records.
    """

    required = {"CSOED", "County", "DAIRY_COW", "OTHER_COW", *FINAL_21_COHORTS}
    missing = sorted(required - set(baseline.columns))
    if missing:
        raise ValueError(f"cohort dependency profile missing columns: {missing}")
    if baseline["CSOED"].duplicated().any():
        raise AssertionError("cohort dependency profile requires one row per CSOED")

    frame = baseline.copy().sort_values("CSOED", kind="stable").reset_index(drop=True)
    dairy = _integer_array(frame, "DAIRY_COW")
    suckler = _integer_array(frame, "OTHER_COW")
    adults = dairy + suckler
    counties = frame["County"].astype(str).to_numpy(dtype=object)
    year_value = None
    if "YEAR" in frame.columns:
        years = pd.to_numeric(frame["YEAR"], errors="raise").astype(int).unique()
        if len(years) != 1:
            raise ValueError("cohort dependency profile requires a single baseline year")
        year_value = int(years[0])

    rows: list[pd.DataFrame] = []
    for cohort in FOLLOWER_COHORTS:
        cohort_base = _integer_array(frame, cohort)
        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            origin_adults = dairy
        elif origin == "SUCKLER":
            origin_adults = suckler
        else:
            origin_adults = adults

        parts = _relationship_components(origin_adults, cohort_base, counties)
        block = pd.DataFrame(
            {
                "CSOED": frame["CSOED"].astype(str),
                "County": frame["County"].astype(str),
                "COHORT": cohort,
                "ADULT_ORIGIN": origin,
                "BASE_ORIGIN_ADULTS": origin_adults,
                "BASE_COHORT_HEAD": cohort_base,
                "ED_COHORT_PER_ADULT_RATIO": np.asarray(parts["ed_ratio"], dtype=float),
                "COUNTY_ORIGIN_ADULT_TOTAL": np.asarray(parts["county_adults"], dtype=float),
                "COUNTY_COHORT_TOTAL": np.asarray(parts["county_cohort"], dtype=float),
                "ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO": np.asarray(
                    parts["orphan_ratio_to_county_adults"], dtype=float
                ),
                "ORPHAN_SHARE_OF_COUNTY_COHORT": np.asarray(
                    parts["orphan_share_of_county_cohort"], dtype=float
                ),
                "COHORT_SPATIAL_ROLE": np.asarray(parts["source"], dtype=object),
            }
        )
        if year_value is not None:
            block.insert(0, "YEAR", year_value)
        rows.append(block)

    return pd.concat(rows, ignore_index=True)


def allocate_cattle_cohort_response(
    adult_scenario: pd.DataFrame,
    national_cohort_targets: Mapping[str, int],
) -> pd.DataFrame:
    """Subtract the required national cohort reduction across existing ED stock.

    GOBLIN/COHORTS supplies the national target for each of the 21 cattle
    cohorts.  GOBLIN-Spatial allocates the implied reduction using the simple
    ripple rule: local parent reduction first, same-county parent reduction for
    receiver/orphan EDs, national fallback only for true county orphans.
    """

    out = adult_scenario.copy()
    if out["CSOED"].duplicated().any():
        raise AssertionError("cohort response requires one row per CSOED")

    required = [
        "CSOED",
        "County",
        "BASE_DAIRY_COW",
        "BASE_OTHER_COW",
        "BASE_ADULT_COWS",
        "REDUCTION_DAIRY_COW",
        "REDUCTION_OTHER_COW",
        "REDUCTION_ADULT_COWS",
        "SCENARIO_DAIRY_COW",
        "SCENARIO_OTHER_COW",
        *FINAL_21_COHORTS,
    ]
    missing = [column for column in required if column not in out.columns]
    if missing:
        raise ValueError(f"cattle cohort response missing required columns: {missing}")

    target_keys = set(national_cohort_targets)
    required_targets = set(FINAL_21_COHORTS)
    missing_targets = sorted(required_targets - target_keys)
    extra_targets = sorted(target_keys - required_targets)
    if missing_targets:
        raise ValueError(f"national cohort targets missing: {missing_targets}")
    if extra_targets:
        raise ValueError(f"unknown national cattle cohort targets: {extra_targets}")

    targets: dict[str, int] = {}
    for cohort in FINAL_21_COHORTS:
        value = int(national_cohort_targets[cohort])
        if value < 0:
            raise ValueError(f"negative national target for {cohort}")
        targets[cohort] = value

    adult_checks = {
        "dairy_cows": int(out["SCENARIO_DAIRY_COW"].sum()),
        "suckler_cows": int(out["SCENARIO_OTHER_COW"].sum()),
    }
    for cohort, expected in adult_checks.items():
        if targets[cohort] != expected:
            raise AssertionError(
                f"GOBLIN target for {cohort} ({targets[cohort]:,}) does not match "
                f"the adult scenario target ({expected:,})"
            )

    adult_mapping = {
        "dairy_cows": ("BASE_DAIRY_COW", "REDUCTION_DAIRY_COW", "SCENARIO_DAIRY_COW"),
        "suckler_cows": ("BASE_OTHER_COW", "REDUCTION_OTHER_COW", "SCENARIO_OTHER_COW"),
    }
    for cohort, (base_col, reduction_col, scenario_col) in adult_mapping.items():
        out[f"BASE_COHORT_{cohort}"] = _integer_array(out, base_col)
        out[f"REDUCTION_COHORT_{cohort}"] = _integer_array(out, reduction_col)
        out[f"SCENARIO_COHORT_{cohort}"] = _integer_array(out, scenario_col)

    base_dairy = _integer_array(out, "BASE_DAIRY_COW")
    base_suckler = _integer_array(out, "BASE_OTHER_COW")
    base_adults = _integer_array(out, "BASE_ADULT_COWS")
    red_dairy = _integer_array(out, "REDUCTION_DAIRY_COW")
    red_suckler = _integer_array(out, "REDUCTION_OTHER_COW")
    red_adults = _integer_array(out, "REDUCTION_ADULT_COWS")
    counties = out["County"].astype(str).to_numpy(dtype=object)

    for cohort in FOLLOWER_COHORTS:
        base = _integer_array(out, cohort)
        base_total = int(base.sum())
        target_total = targets[cohort]
        if target_total > base_total:
            raise ValueError(
                f"reduction-only cohort response cannot expand {cohort}: "
                f"baseline={base_total:,}, target={target_total:,}"
            )
        reduction_total = base_total - target_total

        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            signal, source = _reduction_signal(base_dairy, red_dairy, base, counties)
        elif origin == "SUCKLER":
            signal, source = _reduction_signal(base_suckler, red_suckler, base, counties)
        else:
            signal, source = _reduction_signal(base_adults, red_adults, base, counties)

        # base * signal is exactly the simple adult-to-cohort ripple before the
        # integer closure needed to hit the authoritative national cohort target.
        cut_weights = base.astype(float) * (signal + 1e-12)
        reductions = _bounded_integer_allocate(cut_weights, base, reduction_total)
        scenario_values = base - reductions

        if int(reductions.sum()) != reduction_total:
            raise AssertionError(f"national cohort reduction failed for {cohort}")
        if int(scenario_values.sum()) != target_total:
            raise AssertionError(f"national cohort target failed for {cohort}")
        if not np.array_equal(base - reductions, scenario_values):
            raise AssertionError(f"baseline-minus-reduction failed for {cohort}")

        out[f"BASE_COHORT_{cohort}"] = base
        out[f"REDUCTION_SIGNAL_{cohort}"] = signal
        out[f"REDUCTION_SIGNAL_SOURCE_{cohort}"] = source
        out[f"REDUCTION_COHORT_{cohort}"] = reductions
        out[f"SCENARIO_COHORT_{cohort}"] = scenario_values
        out[f"REDUCTION_PCT_COHORT_{cohort}"] = np.divide(
            100.0 * reductions.astype(float),
            base.astype(float),
            out=np.zeros(len(base), dtype=float),
            where=base > 0,
        )

    scenario_columns = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]
    reduction_columns = [f"REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS]
    base_columns = [f"BASE_COHORT_{c}" for c in FINAL_21_COHORTS]

    out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_columns].sum(axis=1)
    out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[reduction_columns].sum(axis=1)
    out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_columns].sum(axis=1)

    if not np.array_equal(
        out["BASE_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64)
        - out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("21-cohort ED scenario is not baseline minus reduction")

    expected_national = sum(targets.values())
    if int(out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].sum()) != expected_national:
        raise AssertionError("21-cohort national scenario total failed exact closure")

    return out
