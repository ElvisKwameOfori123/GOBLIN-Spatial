"""Versioned evidence-backed Colm eligibility control loader.

No scientific default is supplied. A production rule table must explicitly
cover every Stage-A future use and all seven Colm physical-soil categories.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.land.sc2_colm_direct import (
    COLM_PHYSICAL_CATEGORIES,
    COLM_STAGE_A_USES,
    validate_colm_eligibility_rules,
)

REQUIRED_COLUMNS = (
    "USE",
    "CATEGORY",
    "ELIGIBILITY_COEFFICIENT",
    "RULE_VERSION",
    "EVIDENCE_NOTE",
)


def load_colm_eligibility_control(
    source: str | Path | pd.DataFrame,
) -> tuple[dict[str, dict[str, float]], str, str]:
    """Load a complete Stage-A use x Colm-soil eligibility control."""

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source))
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Colm eligibility control missing columns: {missing_columns}")

    frame = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["USE"] = frame["USE"].astype(str).str.strip().str.upper()
    frame["CATEGORY"] = frame["CATEGORY"].astype(str).str.strip().str.upper()
    frame["RULE_VERSION"] = frame["RULE_VERSION"].astype(str).str.strip()
    frame["EVIDENCE_NOTE"] = frame["EVIDENCE_NOTE"].astype(str).str.strip()
    frame["ELIGIBILITY_COEFFICIENT"] = pd.to_numeric(
        frame["ELIGIBILITY_COEFFICIENT"], errors="raise"
    )

    if frame[["USE", "CATEGORY"]].duplicated().any():
        raise ValueError("Colm eligibility control contains duplicate use/category rows")
    if frame["RULE_VERSION"].eq("").any() or frame["EVIDENCE_NOTE"].eq("").any():
        raise ValueError("every Colm eligibility row requires rule version and evidence note")
    versions = frame["RULE_VERSION"].unique().tolist()
    if len(versions) != 1:
        raise ValueError(f"Colm eligibility control must contain one rule version; found={versions}")

    expected_pairs = {
        (use, category)
        for use in COLM_STAGE_A_USES
        for category in COLM_PHYSICAL_CATEGORIES
    }
    actual_pairs = set(zip(frame["USE"], frame["CATEGORY"], strict=False))
    missing = sorted(expected_pairs - actual_pairs)
    extra = sorted(actual_pairs - expected_pairs)
    if missing or extra:
        raise ValueError(
            "Colm eligibility control must cover the complete Stage-A use x soil matrix; "
            f"missing={missing}, extra={extra}"
        )

    rules: dict[str, dict[str, float]] = {}
    for use in COLM_STAGE_A_USES:
        block = frame.loc[frame["USE"].eq(use)]
        rules[use] = {
            str(row.CATEGORY): float(row.ELIGIBILITY_COEFFICIENT)
            for row in block.itertuples(index=False)
        }
    rules = validate_colm_eligibility_rules(rules, allowed_uses=COLM_STAGE_A_USES)
    if set(rules) != set(COLM_STAGE_A_USES):
        raise AssertionError("validated Colm eligibility matrix lost a Stage-A use")

    evidence_summary = " | ".join(
        sorted({note for note in frame["EVIDENCE_NOTE"].tolist() if note})
    )
    return rules, str(versions[0]), evidence_summary
