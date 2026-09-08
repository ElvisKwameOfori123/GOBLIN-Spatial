"""SC2 physical-resource and eligibility contract.

Scientific boundary
-------------------
1. SC1 supplies a frozen ED released-land vector.
2. Colm mapped physical-soil shares characterise that released resource
   proportionally within each ED.
3. LPIS and other downstream evidence may provide agricultural-use context but
   cannot change the frozen SC1 release.
4. Use-specific eligibility coefficients must be explicit, complete, versioned
   and evidence-backed. No coefficient is inferred here.
5. Rewetting is excluded from generic soil-only eligibility because mapped peat
   is not equivalent to drained agricultural organic soil.

Release != PhysicalResource != Eligibility != Opportunity != Allocation != Adoption.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

COLM_PHYSICAL_CATEGORIES = (
    "DEEP_WELL_DRAINED",
    "SHALLOW_WELL_DRAINED",
    "POORLY_DRAINED",
    "POORLY_DRAINED_PEATY",
    "ALLUVIUM",
    "PEAT",
    "MISCELLANEOUS",
)
COLM_PHYSICAL_SHARE_COLUMNS = tuple(
    f"IFS_MAP_{category}_SHARE" for category in COLM_PHYSICAL_CATEGORIES
)
COLM_RELEASED_AREA_COLUMNS = tuple(
    f"COLM_RELEASED_{category}_HA" for category in COLM_PHYSICAL_CATEGORIES
)
COLM_STAGE_A_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
)
SOIL_ONLY_FORBIDDEN_USES = {"REWETTING"}


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC2 missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def add_colm_released_soil_resource(
    frame: pd.DataFrame,
    *,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Characterise frozen ED release using Colm physical-soil shares."""

    out = frame.copy()
    missing = sorted(set(COLM_PHYSICAL_SHARE_COLUMNS) - set(out.columns))
    if missing:
        raise ValueError(f"SC2 missing physical-soil shares: {missing}")

    release = _numeric(out, release_column)
    if (release < -1e-9).any():
        raise ValueError("frozen SC1 release cannot be negative")
    release = np.maximum(release, 0.0)
    if "ALL_GRASSLAND" in out.columns:
        grass = _numeric(out, "ALL_GRASSLAND")
        if (release - grass > 1e-7).any():
            raise ValueError("frozen SC1 release exceeds ALL_GRASSLAND")

    shares = out[list(COLM_PHYSICAL_SHARE_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    if (~np.isfinite(shares)).any() or (shares < -1e-10).any():
        raise ValueError("Colm physical-soil shares contain invalid values")
    closure = float(np.max(np.abs(shares.sum(axis=1) - 1.0)))
    if closure > 1e-8:
        raise ValueError(
            f"Colm physical-soil shares do not close to one; max error={closure:.3e}"
        )
    shares = np.clip(shares, 0.0, 1.0)

    released = release[:, None] * shares
    for index, column in enumerate(COLM_RELEASED_AREA_COLUMNS):
        out[column] = released[:, index]
    if float(np.max(np.abs(released.sum(axis=1) - release))) > 1e-7:
        raise AssertionError("released-soil partition does not close to frozen SC1 release")

    out["COLM_RELEASED_SOIL_CONTEXT_HA"] = release
    out["COLM_RELEASED_SOIL_PARTITION_METHOD"] = (
        "FROZEN_SC1_RELEASE_X_COLM_ED_PHYSICAL_SOIL_SHARE"
    )
    out["COLM_RELEASED_SOIL_INTERPRETATION"] = (
        "PROPORTIONAL_WITHIN_ED_RESOURCE_CHARACTERISATION"
    )
    out["COLM_DIRECT_SC2_RULE_STATUS"] = "PHYSICAL_RESOURCE_ONLY"
    return out


def validate_colm_eligibility_rules(
    rules: Mapping[str, Mapping[str, float]],
    *,
    allowed_uses: tuple[str, ...] | None = None,
) -> dict[str, dict[str, float]]:
    """Validate complete explicit use-by-soil eligibility coefficients."""

    if not rules:
        raise ValueError("eligibility rules must contain at least one future use")
    validated: dict[str, dict[str, float]] = {}
    expected_categories = set(COLM_PHYSICAL_CATEGORIES)
    allowed = None if allowed_uses is None else {str(use).upper() for use in allowed_uses}

    for use, coefficients in rules.items():
        use_name = str(use).strip().upper()
        if not use_name:
            raise ValueError("future-use rule names must be non-empty")
        if use_name in SOIL_ONLY_FORBIDDEN_USES:
            raise ValueError(
                "REWETTING cannot be derived from Colm soil coefficients alone; "
                "supply a separately validated drained-organic agricultural capacity"
            )
        if allowed is not None and use_name not in allowed:
            raise ValueError(f"unsupported future use {use_name!r}; allowed={sorted(allowed)}")

        supplied = {str(key).strip().upper() for key in coefficients}
        missing = sorted(expected_categories - supplied)
        extra = sorted(supplied - expected_categories)
        if missing or extra:
            raise ValueError(
                f"{use_name} rule must explicitly cover all Colm categories; "
                f"missing={missing}, extra={extra}"
            )

        upper = {str(key).strip().upper(): value for key, value in coefficients.items()}
        row: dict[str, float] = {}
        for category in COLM_PHYSICAL_CATEGORIES:
            value = float(upper[category])
            if not np.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(
                    f"{use_name}/{category} eligibility coefficient must lie in [0,1]"
                )
            row[category] = value
        validated[use_name] = row
    return validated


def add_colm_direct_eligibility(
    frame: pd.DataFrame,
    *,
    rules: Mapping[str, Mapping[str, float]],
    rule_version: str,
    evidence_note: str,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Apply explicit physical-soil eligibility rules."""

    if not str(rule_version).strip():
        raise ValueError("rule_version is required")
    if not str(evidence_note).strip():
        raise ValueError("evidence_note is required")

    out = frame.copy()
    if not all(column in out.columns for column in COLM_RELEASED_AREA_COLUMNS):
        out = add_colm_released_soil_resource(out, release_column=release_column)

    validated = validate_colm_eligibility_rules(rules)
    released = out[list(COLM_RELEASED_AREA_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    total_release = _numeric(out, release_column)

    for use, coefficients in validated.items():
        weights = np.array(
            [coefficients[category] for category in COLM_PHYSICAL_CATEGORIES],
            dtype=float,
        )
        eligible = released @ weights
        if (eligible < -1e-9).any() or (eligible - total_release > 1e-7).any():
            raise AssertionError(f"{use} eligibility falls outside released-land budget")
        out[f"COLM_DIRECT_{use}_ELIGIBLE_HA"] = np.clip(eligible, 0.0, total_release)

    out["COLM_DIRECT_SC2_RULE_STATUS"] = "EXPLICIT_RULES_APPLIED"
    out["COLM_DIRECT_SC2_RULE_VERSION"] = str(rule_version)
    out["COLM_DIRECT_SC2_RULE_EVIDENCE"] = str(evidence_note)
    return out


def build_colm_direct_sc2_physical(
    frame: pd.DataFrame,
    *,
    rules: Mapping[str, Mapping[str, float]] | None = None,
    rule_version: str | None = None,
    evidence_note: str | None = None,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Build the physical-resource layer and optional eligibility."""

    out = add_colm_released_soil_resource(frame, release_column=release_column)
    if rules is None:
        return out
    return add_colm_direct_eligibility(
        out,
        rules=rules,
        rule_version=rule_version or "",
        evidence_note=evidence_note or "",
        release_column=release_column,
    )
