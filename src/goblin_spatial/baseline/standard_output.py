"""Fixed-2020 Standard Output enrichment for the historical baseline."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.standard_output import add_baseline_standard_output


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

    common = [column for column in protected.columns if column in out.columns]
    if not protected[common].equals(out[common]):
        raise AssertionError("Standard Output stage changed a pre-existing baseline value")
    if len(out) != len(baseline):
        raise AssertionError("Standard Output stage changed the baseline row count")

    return out
