"""Fixed-2020 Standard Output enrichment for the historical baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.standard_output import add_baseline_standard_output


SO_REQUIRED = [
    "FADN_REGION",
    "FADN_REGION_LABEL",
    "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR",
    "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR",
    "SO_LIVESTOCK_2020_EUR",
    "SO_CEREALS_2020_EUR",
    "SO_OTHER_CROPS_2020_EUR",
    "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
    "SO_OTHER_CROPS_IMPUTED_HA",
    "SO_COVERED_TOTAL_2020_EUR",
    "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
]
SO_VALUE_COLUMNS = [
    column for column in SO_REQUIRED if column.startswith("SO_")
]


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return frame[columns].apply(pd.to_numeric, errors="raise")


def validate_standard_output(
    protected: pd.DataFrame,
    valued: pd.DataFrame,
) -> None:
    """Validate Stage-08 identities and prove that activity data are unchanged."""

    if len(valued) != len(protected):
        raise AssertionError("Standard Output stage changed the baseline row count")

    missing = [column for column in SO_REQUIRED if column not in valued.columns]
    if missing:
        raise AssertionError(f"Standard Output stage missing required fields: {missing}")

    # Stage 08 is enrichment only. Every pre-existing value, including the
    # YEAR x CSOED spine, livestock, land and socioeconomic fields, is immutable.
    common = [column for column in protected.columns if column in valued.columns]
    if not protected[common].equals(valued[common]):
        changed = [
            column
            for column in common
            if not protected[column].equals(valued[column])
        ]
        raise AssertionError(
            "Standard Output stage changed pre-existing baseline fields: "
            + ", ".join(changed[:20])
        )

    if {"YEAR", "CSOED"}.issubset(valued.columns):
        if valued[["YEAR", "CSOED"]].duplicated().any():
            raise AssertionError("Standard Output stage created duplicate YEAR-CSOED rows")

    regions = set(valued["FADN_REGION"].astype(str).unique())
    if not regions.issubset({"381", "382"}) or not regions:
        raise AssertionError(f"unexpected Standard Output regions: {sorted(regions)}")
    if valued["FADN_REGION_LABEL"].isna().any():
        raise AssertionError("Standard Output region labels contain missing values")

    values = _numeric(valued, SO_VALUE_COLUMNS)
    matrix = values.to_numpy(dtype=float)
    if (~np.isfinite(matrix)).any():
        raise AssertionError("Standard Output contains non-finite required values")
    if (matrix < -1e-9).any():
        raise AssertionError("Standard Output contains negative required values")

    livestock_components = (
        values["SO_DAIRY_COWS_2020_EUR"]
        + values["SO_SUCKLER_COWS_2020_EUR"]
        + values["SO_BULLS_2020_EUR"]
        + values["SO_FOLLOWERS_2020_EUR"]
        + values["SO_SHEEP_2020_EUR"]
    )
    if not np.allclose(
        livestock_components.to_numpy(dtype=float),
        values["SO_LIVESTOCK_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    ):
        raise AssertionError("Standard Output livestock components do not close")

    covered = (
        values["SO_LIVESTOCK_2020_EUR"]
        + values["SO_CEREALS_2020_EUR"]
        + values["SO_OTHER_CROPS_2020_EUR"]
    )
    if not np.allclose(
        covered.to_numpy(dtype=float),
        values["SO_COVERED_TOTAL_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    ):
        raise AssertionError("Standard Output covered total does not close")

    covered_conservative = (
        values["SO_LIVESTOCK_2020_EUR"]
        + values["SO_CEREALS_2020_EUR"]
        + values["SO_OTHER_CROPS_CONSERVATIVE_2020_EUR"]
    )
    if not np.allclose(
        covered_conservative.to_numpy(dtype=float),
        values["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"].to_numpy(dtype=float),
        atol=1e-7,
        rtol=1e-12,
    ):
        raise AssertionError("conservative Standard Output covered total does not close")

    if "AGRICULTURAL_HOLDINGS" in valued.columns:
        holdings = pd.to_numeric(
            valued["AGRICULTURAL_HOLDINGS"], errors="raise"
        ).to_numpy(dtype=float)
        for total_column, per_holding_column in (
            ("SO_COVERED_TOTAL_2020_EUR", "SO_COVERED_PER_HOLDING_2020_EUR"),
            (
                "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
                "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
            ),
        ):
            if per_holding_column not in valued.columns:
                raise AssertionError(
                    f"Standard Output stage missing {per_holding_column}"
                )
            observed = pd.to_numeric(
                valued[per_holding_column], errors="coerce"
            ).to_numpy(dtype=float)
            total = pd.to_numeric(
                valued[total_column], errors="raise"
            ).to_numpy(dtype=float)
            positive = holdings > 0
            if positive.any() and not np.allclose(
                observed[positive],
                total[positive] / holdings[positive],
                atol=1e-7,
                rtol=1e-12,
            ):
                raise AssertionError(
                    f"{per_holding_column} is inconsistent with holdings"
                )
            if (~positive).any() and np.isfinite(observed[~positive]).any():
                raise AssertionError(
                    f"{per_holding_column} must be missing where holdings are zero"
                )


def add_standard_output(
    baseline: pd.DataFrame,
    config: SpatialConfig,
) -> pd.DataFrame:
    """Attach Stage-08 production-value exposure without changing activities.

    Fixed 2020 coefficients are applied to all historical years. The result is
    a production-value exposure measure, not farm income, profit or welfare.
    """

    mapping = config.files.get("standard_output_mapping")
    if mapping is None:
        raise KeyError("configuration is missing standard_output_mapping")
    if not mapping.exists():
        raise FileNotFoundError(mapping)

    audit = config.files.get("standard_output_coefficients")
    audit_path = str(audit) if audit is not None and audit.exists() else None

    protected = baseline.copy()
    out = add_baseline_standard_output(
        baseline,
        mapping_path=str(mapping),
        coefficient_path=audit_path,
    )
    validate_standard_output(protected, out)
    return out
