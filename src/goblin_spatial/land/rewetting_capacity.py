"""Validated external rewetting-capacity control for Colm-direct SC3.

Mapped peat is not equivalent to drained agricultural organic soil. This module
therefore accepts rewetting capacity only from an explicit, versioned control
whose provenance/evidence is supplied by the caller. No national stock or peat
fraction is invented here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.sc2_colm_direct import COLM_PHYSICAL_CATEGORIES
from goblin_spatial.soil.overlay import canonical_csoed

CAPACITY_PREFIX = "REWETTING_CAPACITY_"
CAPACITY_SUFFIX = "_HA"
REQUIRED_META = ("CAPACITY_VERSION", "EVIDENCE_NOTE")


def _column_for(category: str) -> str:
    return f"{CAPACITY_PREFIX}{category}{CAPACITY_SUFFIX}"


def load_rewetting_capacity_control(
    source: str | Path | pd.DataFrame,
    *,
    expected_eds: int | None = None,
) -> tuple[pd.DataFrame, dict[str, str], str, str]:
    """Read one ED-level validated rewetting capacity control.

    At least one Colm category-specific capacity column must be present. Missing
    categories are interpreted as structurally unavailable for rewetting, not as
    unknown positive capacity. The control must carry one version and non-empty
    evidence notes.
    """

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source))
    if "CSOED" not in frame.columns:
        raise ValueError("rewetting capacity control requires CSOED")
    missing_meta = sorted(set(REQUIRED_META) - set(frame.columns))
    if missing_meta:
        raise ValueError(f"rewetting capacity control missing metadata: {missing_meta}")

    out = frame.copy()
    out["CSOED"] = out["CSOED"].map(canonical_csoed)
    if out["CSOED"].eq("").any() or out["CSOED"].duplicated().any():
        raise ValueError("rewetting capacity control requires unique non-empty ED keys")
    if expected_eds is not None and len(out) != int(expected_eds):
        raise ValueError(
            f"rewetting capacity rows={len(out):,}; expected={int(expected_eds):,}"
        )

    versions = out["CAPACITY_VERSION"].astype(str).str.strip().unique().tolist()
    if len(versions) != 1 or not versions[0]:
        raise ValueError("rewetting capacity control must contain one non-empty version")
    evidence = out["EVIDENCE_NOTE"].astype(str).str.strip()
    if evidence.eq("").any():
        raise ValueError("every rewetting capacity row requires EVIDENCE_NOTE")

    mapping: dict[str, str] = {}
    for category in COLM_PHYSICAL_CATEGORIES:
        column = _column_for(category)
        if column not in out.columns:
            continue
        values = pd.to_numeric(out[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(values)).any() or (values < -1e-10).any():
            raise ValueError(f"{column} must be finite and non-negative")
        out[column] = np.maximum(values, 0.0)
        mapping[category] = column
    if not mapping:
        raise ValueError(
            "rewetting capacity control contains no category-specific capacity columns"
        )

    keep = ["CSOED", *mapping.values(), *REQUIRED_META]
    evidence_summary = " | ".join(sorted(set(evidence.tolist())))
    return (
        out[keep].sort_values("CSOED", kind="stable").reset_index(drop=True),
        mapping,
        str(versions[0]),
        evidence_summary,
    )


def attach_rewetting_capacity(
    frame: pd.DataFrame,
    control: pd.DataFrame,
) -> pd.DataFrame:
    """Attach validated rewetting capacity one-to-one without changing release."""

    if "CSOED" not in frame.columns:
        raise ValueError("rewetting capacity attachment requires CSOED")
    left = frame.copy()
    left["_REWET_KEY"] = left["CSOED"].map(canonical_csoed)
    right = control.copy()
    right["_REWET_KEY"] = right["CSOED"].map(canonical_csoed)
    available = set(right["_REWET_KEY"])
    required = set(left["_REWET_KEY"])
    missing = sorted(required - available)
    if missing:
        raise ValueError(
            f"rewetting capacity control is missing {len(missing)} model EDs; "
            f"examples={missing[:10]}"
        )
    attach = right.drop(columns="CSOED")
    out = left.merge(attach, on="_REWET_KEY", how="left", validate="many_to_one")
    return out.drop(columns="_REWET_KEY")
