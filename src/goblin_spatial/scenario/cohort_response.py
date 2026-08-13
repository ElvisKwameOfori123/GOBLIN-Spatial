"""Propagate adult destocking into the 21 GOBLIN cattle cohorts spatially.

National biology and spatial incidence are deliberately separated:

* GOBLIN/COHORTS supplies the adult-to-pre-adult biological relationship.
* GOBLIN-Spatial starts from the selected ED cohort baseline and allocates only
  the implied reduction across EDs.
* Breeding EDs respond through their own adult-to-cohort relationship.
* EDs carrying more young stock than their local adult base can biologically
  support are treated as mixed breeding/receiver locations for that cohort.
* Pure receiver/rearing/finishing EDs inherit the reduction signal from breeding
  activity within the same county.
* National fallback is reserved for sparse orphan cases where a cohort exists
  in a county with no corresponding adult breeding stock at all.

The spatial dependency split is derived from the same type of herd coefficient
used by Henn et al. (2023): pre-adult cohort numbers relative to the relevant
adult cow population.  For each cohort k, the selected baseline implies a
national coefficient beta_k = cohort_k / origin_adults.  In each ED, up to
beta_k * local_origin_adults is treated as locally supported.  Any observed
cohort stock above that amount is treated as receiver/rearing dependence.  This
is a transparent spatial proxy for cattle movement, not a claim that individual
animals have been traced between EDs.
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


def _dependency_components(
    base_adults: np.ndarray,
    cohort_base: np.ndarray,
    counties: np.ndarray,
) -> dict[str, np.ndarray | float]:
    """Decompose one cohort into local-support and receiver-dependent shares.

    The national cohort/adult coefficient is used only as a biological reference
    for the selected baseline.  It does not change the observed ED cohort count.
    An ED can therefore be:

    * ``LOCAL_ED``: all observed cohort stock is supportable by its local adults;
    * ``MIXED_ED_COUNTY``: some stock is local and some is receiver/rearing stock;
    * ``COUNTY_RECEIVER``: cohort stock exists with no corresponding local adults;
    * ``NATIONAL_ORPHAN``: receiver stock exists in a county with no origin adults;
    * ``NONE``: the ED contains none of the cohort.
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
        raise ValueError("county is required for cohort dependency decomposition")

    national_adults = int(base_adults.sum())
    national_cohort = int(cohort_base.sum())
    coefficient = (
        float(national_cohort) / float(national_adults)
        if national_adults > 0
        else 0.0
    )

    local_capacity = coefficient * base_adults.astype(float)
    local_supported = np.minimum(cohort_base.astype(float), local_capacity)
    receiver_dependent = np.maximum(0.0, cohort_base.astype(float) - local_supported)
    local_share = np.divide(
        local_supported,
        cohort_base,
        out=np.zeros(n, dtype=float),
        where=cohort_base > 0,
    )
    receiver_share = np.divide(
        receiver_dependent,
        cohort_base,
        out=np.zeros(n, dtype=float),
        where=cohort_base > 0,
    )

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

    source = np.full(n, "NONE", dtype=object)
    has_cohort = cohort_base > 0
    active = base_adults > 0
    local_only = has_cohort & active & (receiver_share <= 1e-12)
    mixed = has_cohort & active & (receiver_share > 1e-12)
    receiver = has_cohort & (~active) & (county_adults > 0)
    orphan = has_cohort & (~active) & (county_adults <= 0)
    source[local_only] = "LOCAL_ED"
    source[mixed] = "MIXED_ED_COUNTY"
    source[receiver] = "COUNTY_RECEIVER"
    source[orphan] = "NATIONAL_ORPHAN"

    return {
        "coefficient": coefficient,
        "local_supported": local_supported,
        "receiver_dependent": receiver_dependent,
        "local_share": np.clip(local_share, 0.0, 1.0),
        "receiver_share": np.clip(receiver_share, 0.0, 1.0),
        "county_adults": county_adults,
        "county_cohort": county_cohort,
        "source": source,
    }


def _reduction_signal(
    base_adults: np.ndarray,
    adult_reductions: np.ndarray,
    cohort_base: np.ndarray,
    counties: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return an ED-local / county-receiver blended reduction signal.

    A pure breeding ED uses its own realised adult reduction rate. A pure
    receiver/rearing/finishing ED uses the reduction rate of origin adults in
    its county. A mixed ED blends the two rates according to the baseline share
    of that cohort that can be supported by local adults versus the share that
    is inferred to depend on cattle coming from elsewhere in the county.

    No fixed 30%, 50% or other spillover factor is imposed. The dependency share
    is inferred from the selected baseline cohort/adult relationship itself.
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
        raise ValueError("county is required for receiver/rearing cohort propagation")

    parts = _dependency_components(base_adults, cohort_base, counties)
    local_share = np.asarray(parts["local_share"], dtype=float)
    receiver_share = np.asarray(parts["receiver_share"], dtype=float)
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
    receiver_rate = np.where(county_base > 0, county_rate, national_rate)

    signal = local_share * local_rate + receiver_share * receiver_rate
    signal = np.where(cohort_base > 0, signal, 0.0)
    return np.clip(signal, 0.0, 1.0), source


def _cohort_origin(cohort: str) -> str:
    if cohort in DXD_COHORTS or cohort in DXB_COHORTS:
        return "DAIRY"
    if cohort in BXB_COHORTS:
        return "SUCKLER"
    if cohort == "bulls":
        return "ADULT_COWS"
    raise ValueError(f"cannot identify adult origin for cohort {cohort}")


def build_ed_cohort_dependency_profile(baseline: pd.DataFrame) -> pd.DataFrame:
    """Return a publication/audit table of ED adult-to-cohort dependence.

    The output is long-form: one row per ED and follower cohort. It is designed
    to make the spatial herd structure visible before any scenario is applied.
    ``COUNTY_DEPENDENCY_SHARE`` is an inferred dependence proxy, not observed
    animal movement data.
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

        parts = _dependency_components(origin_adults, cohort_base, counties)
        block = pd.DataFrame(
            {
                "CSOED": frame["CSOED"].astype(str),
                "County": frame["County"].astype(str),
                "COHORT": cohort,
                "ADULT_ORIGIN": origin,
                "BASE_ORIGIN_ADULTS": origin_adults,
                "BASE_COHORT_HEAD": cohort_base,
                "COHORT_PER_ADULT_COEFFICIENT": float(parts["coefficient"]),
                "LOCALLY_SUPPORTED_HEAD_EQUIV": np.asarray(
                    parts["local_supported"], dtype=float
                ),
                "COUNTY_DEPENDENT_HEAD_EQUIV": np.asarray(
                    parts["receiver_dependent"], dtype=float
                ),
                "LOCAL_SUPPORT_SHARE": np.asarray(parts["local_share"], dtype=float),
                "COUNTY_DEPENDENCY_SHARE": np.asarray(
                    parts["receiver_share"], dtype=float
                ),
                "COUNTY_ORIGIN_ADULT_TOTAL": np.asarray(
                    parts["county_adults"], dtype=float
                ),
                "COUNTY_COHORT_TOTAL": np.asarray(parts["county_cohort"], dtype=float),
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
    """Subtract GOBLIN/COHORTS cohort reductions from the ED cohort baseline.

    This function represents one milestone/endpoint. Adult reductions and
    follower reductions belong to the same herd state. Breeding EDs are linked
    directly through their own adult reduction rate. Mixed and receiver/rearing
    EDs also inherit the relevant same-county breeding signal before any national
    orphan fallback is allowed.

    ``national_cohort_targets`` remains authoritative for national biology. ED
    and county relationships determine spatial incidence only.
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
