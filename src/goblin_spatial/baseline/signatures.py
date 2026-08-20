"""Stage 09 ED livestock dependency signatures.

Stage 09 is the final historical-baseline stage. It freezes the 2020 ED cattle
cohort relationships that a later scenario may consume, but it does not run a
scenario and it does not depend on scenario modules.

The signatures are accounting relationships inferred from the reconstructed ED
livestock structure. They are not observations of animal movements.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import SpatialConfig


DXD_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
FOLLOWER_COHORTS = tuple(
    c for c in FINAL_21_COHORTS if c not in {"dairy_cows", "suckler_cows"}
)


def _integer_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8:
        raise AssertionError(f"{column} must contain integer animal counts")
    if (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative animal counts")
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
    """Describe the baseline ED-to-adult relationship for one cattle cohort."""

    base_adults = np.asarray(base_adults, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)
    counties = np.asarray(counties, dtype=object)

    n = len(base_adults)
    if len(cohort_base) != n or len(counties) != n:
        raise ValueError("adult, cohort and county arrays must have equal length")
    if (base_adults < 0).any() or (cohort_base < 0).any():
        raise ValueError("adult and cohort counts must be non-negative")
    if pd.isna(counties).any():
        raise ValueError("County is required for Stage 09 signature accounting")

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


def build_signatures(
    baseline: pd.DataFrame,
    config: SpatialConfig,
    *,
    year: int | None = None,
) -> pd.DataFrame:
    """Freeze the ED cattle dependency profile for the baseline year.

    The final Stage 09 table contains one row per ED and follower cohort. Dairy
    origin cohorts are related to local/county dairy cows, BxB cohorts to
    local/county suckler cows, and bulls to the combined adult-cow population.
    """

    baseline_year = int(config.base_year if year is None else year)
    required = {"YEAR", "CSOED", "County", "DAIRY_COW", "OTHER_COW", *FINAL_21_COHORTS}
    missing = sorted(required - set(baseline.columns))
    if missing:
        raise ValueError(f"Stage 09 signature construction missing columns: {missing}")

    years = pd.to_numeric(baseline["YEAR"], errors="raise").astype(int)
    selected = baseline.loc[years == baseline_year].copy()
    selected = selected.sort_values("CSOED", kind="stable").reset_index(drop=True)

    if len(selected) != config.expected_eds:
        raise AssertionError(
            f"expected {config.expected_eds:,} EDs in signature year {baseline_year}; "
            f"found {len(selected):,}"
        )
    if selected["CSOED"].duplicated().any():
        raise AssertionError("Stage 09 baseline contains duplicate CSOED rows")

    dairy = _integer_array(selected, "DAIRY_COW")
    suckler = _integer_array(selected, "OTHER_COW")
    adults = dairy + suckler
    counties = selected["County"].astype(str).to_numpy(dtype=object)

    rows: list[pd.DataFrame] = []
    for cohort in FOLLOWER_COHORTS:
        cohort_base = _integer_array(selected, cohort)
        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            origin_adults = dairy
        elif origin == "SUCKLER":
            origin_adults = suckler
        else:
            origin_adults = adults

        parts = _relationship_components(origin_adults, cohort_base, counties)
        rows.append(
            pd.DataFrame(
                {
                    "YEAR": baseline_year,
                    "CSOED": selected["CSOED"].astype(str),
                    "County": selected["County"].astype(str),
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
        )

    signatures = pd.concat(rows, ignore_index=True)
    expected_followers = 19
    expected_rows = config.expected_eds * expected_followers
    if len(FOLLOWER_COHORTS) != expected_followers:
        raise AssertionError("Stage 09 expects 19 cattle follower cohorts")
    if len(signatures) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows:,} Stage 09 signature rows; found {len(signatures):,}"
        )
    if signatures[["CSOED", "COHORT"]].duplicated().any():
        raise AssertionError("Stage 09 contains duplicate CSOED-cohort rows")

    return signatures.sort_values(["CSOED", "COHORT"], kind="stable").reset_index(drop=True)
