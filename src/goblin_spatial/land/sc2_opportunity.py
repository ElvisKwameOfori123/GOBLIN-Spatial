"""Mature SC2 v3.1 released-land opportunity science.

This module ports the scientific rules from the frozen standalone
``SC2_GOBLIN_Spatial_Dual_Soil_Land_Opportunity_v3_1_20260820.py`` into the
package without changing their mathematics.

Boundary
--------
SC1 decides cattle geography and the authoritative ED released-land budget,
including its 08B G1/G2/G3 composition. SC2 preserves that result exactly,
adds baseline-matched LPIS and independent 08C physical-soil context, then
produces opportunity scores and SC3-ready physical eligibility quantities.

``PotentialRelease != Opportunity != RealisedConversion``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


SC2_VERSION = "3.1.0"
AVAIL_NOT_REPRESENTED = "NOT_REPRESENTED_IN_SOURCE"

NFS_CLASSES = (1, 2, 3, 4, 5, 6)
CLASS_SHARE_COLUMNS = tuple(f"SOIL_USE_CLASS_{c}_SHARE" for c in NFS_CLASSES)
CLASS_GRASSLAND_COLUMNS = tuple(
    f"SOIL_USE_CLASS_{c}_GRASSLAND_HA" for c in NFS_CLASSES
)
RELEASED_CLASS_COLUMNS = tuple(f"RELEASED_CLASS_{c}_HA" for c in NFS_CLASSES)

RELEASED_ELIGIBILITY_COLUMNS = (
    "RELEASED_ORGANIC_WEIGHT_HA",
    "RELEASED_MINERAL_INDICATIVE_HA",
    "RELEASED_TILLAGE_ELIGIBLE_HA",
    "RELEASED_TILLAGE_STRICT_ELIGIBLE_HA",
    "RELEASED_FOREST_ELIGIBLE_HA",
    "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
    "RELEASED_WILLOW_ELIGIBLE_HA",
    "RELEASED_WILLOW_WIDE_ELIGIBLE_HA",
    "RELEASED_REWETTING_ELIGIBLE_WEIGHT_HA",
)

OPPORTUNITY_COLUMNS = (
    "FORESTRY_OPPORTUNITY_SCORE",
    "REWETTING_OPPORTUNITY_SCORE",
    "AD_GRASS_OPPORTUNITY_SCORE",
    "WILLOW_OPPORTUNITY_SCORE",
    "ENERGY_GRASS_OPPORTUNITY_SCORE",
    "NATURE_OPPORTUNITY_SCORE",
)

IFS_MAP_SG_SHARE_COLUMNS = (
    "IFS_MAP_SG1_SHARE",
    "IFS_MAP_SG2_SHARE",
    "IFS_MAP_SG3_SHARE",
)
IFS_MAP_PHYSICAL_SHARE_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_SHARE",
    "IFS_MAP_SHALLOW_WELL_DRAINED_SHARE",
    "IFS_MAP_POORLY_DRAINED_SHARE",
    "IFS_MAP_POORLY_DRAINED_PEATY_SHARE",
    "IFS_MAP_ALLUVIUM_SHARE",
    "IFS_MAP_PEAT_SHARE",
    "IFS_MAP_MISCELLANEOUS_SHARE",
)


def _availability_column(area_column: str) -> str:
    return f"{area_column}_AVAILABILITY"


def _area_represented(frame: pd.DataFrame, area_column: str) -> bool:
    """Distinguish source absence from a genuine observed zero when possible."""

    availability = _availability_column(area_column)
    if availability not in frame.columns:
        return area_column in frame.columns and pd.to_numeric(
            frame[area_column], errors="coerce"
        ).notna().any()
    states = set(frame[availability].dropna().astype(str).unique())
    return states != {AVAIL_NOT_REPRESENTED}


def _share(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        return np.zeros(len(frame), dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    return np.clip(np.nan_to_num(values, nan=0.0), 0.0, 1.0)


def score_band(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return pd.Series(
        np.select(
            [numeric.ge(2.0 / 3.0), numeric.ge(1.0 / 3.0)],
            ["HIGH", "MEDIUM"],
            default="LOW",
        ),
        index=values.index,
        dtype="string",
    )


def opportunity_method_strings(frame: pd.DataFrame) -> tuple[str, str]:
    terms: list[str] = []
    if _area_represented(frame, "LPIS_LOW_INPUT_GRASS_HA"):
        terms.append("LOW_INPUT_GRASS")
    if _area_represented(frame, "LPIS_PEAT_GRASS_HA"):
        terms.append("PEAT_GRASS")
    if _area_represented(frame, "LPIS_RIPARIAN_GRASS_HA"):
        terms.append("RIPARIAN_GRASS")
    sensitive = " + ".join(terms) if terms else "NO_LPIS_SENSITIVE_GRASS_TERM"

    rewetting = "CATHAL_IFS_PEAT"
    if _area_represented(frame, "LPIS_PEAT_GRASS_HA"):
        rewetting += " + LPIS_PEAT_GRASS"
    return sensitive, rewetting


def add_ed_land_opportunity_scores_v2(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the mature repository Opportunity-v2 score equations exactly."""

    out = frame.copy()
    required_soil = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3))
    missing = sorted(set(required_soil) - set(out.columns))
    if missing:
        raise ValueError(f"SC2 missing Cathal/NFS soil fields: {missing}")

    g = out[list(required_soil)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if (g < 0).any() or not np.allclose(g.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("GOBLIN G1/G2/G3 shares must be non-negative and close to one")
    g1, g2, g3 = g[:, 0], g[:, 1], g[:, 2]

    # Public GOBLIN production-soil relative-yield ordering retained from the
    # mature SC2 v3.1 implementation.
    productivity_index = 0.85 * g1 + 0.80 * g2 + 0.70 * g3
    productivity_score = np.clip(
        (productivity_index - 0.70) / (0.85 - 0.70),
        0.0,
        1.0,
    )
    if "GOBLIN_SOIL_PRODUCTIVITY_INDEX" in out.columns:
        existing = pd.to_numeric(
            out["GOBLIN_SOIL_PRODUCTIVITY_INDEX"], errors="raise"
        ).to_numpy(float)
        if not np.allclose(
            existing,
            productivity_index,
            rtol=1e-10,
            atol=1e-10,
            equal_nan=True,
        ):
            raise AssertionError(
                "SC1 GOBLIN_SOIL_PRODUCTIVITY_INDEX is incompatible with mature SC2"
            )
        out["SC2_RECOMPUTED_GOBLIN_SOIL_PRODUCTIVITY_INDEX"] = productivity_index
    else:
        out["GOBLIN_SOIL_PRODUCTIVITY_INDEX"] = productivity_index
        out["SC2_RECOMPUTED_GOBLIN_SOIL_PRODUCTIVITY_INDEX"] = productivity_index
    out["GOBLIN_SOIL_PRODUCTIVITY_SCORE"] = productivity_score

    if "FOREST_YC_WEIGHTED_MEAN" in out.columns:
        yc = pd.to_numeric(
            out["FOREST_YC_WEIGHTED_MEAN"], errors="coerce"
        ).to_numpy(float)
        forest_base = np.where(
            np.isfinite(yc),
            np.clip((yc - 14.0) / 10.0, 0.0, 1.0),
            0.0,
        )
    else:
        forest_base = np.zeros(len(out), dtype=float)
    out["FORESTRY_BASE_YC_SCORE"] = forest_base

    if "IFS_PEAT_CUTOVER_UAA_SHARE" in out.columns:
        peat = pd.to_numeric(
            out["IFS_PEAT_CUTOVER_UAA_SHARE"], errors="coerce"
        ).to_numpy(float)
        soil_peat = np.where(np.isfinite(peat), np.clip(peat, 0.0, 1.0), 0.0)
        soil_peat_method = np.where(
            np.isfinite(peat), "IFS_FULL_SHARE", "NO_IFS_FULL_SHARE"
        )
    elif "IFS_SOIL_DOMINANT" in out.columns:
        code = out["IFS_SOIL_DOMINANT"].astype("string").fillna("").str.upper()
        is_peat = code.str.endswith("PT") | code.eq("CUT")
        if "IFS_SOIL_DOMINANT_SHARE" in out.columns:
            dominant = pd.to_numeric(
                out["IFS_SOIL_DOMINANT_SHARE"], errors="coerce"
            ).fillna(0.0).to_numpy(float)
            dominant = np.clip(dominant, 0.0, 1.0)
        else:
            dominant = np.ones(len(out), dtype=float)
        soil_peat = np.where(is_peat.to_numpy(), dominant, 0.0)
        soil_peat_method = np.full(len(out), "IFS_DOMINANT_FALLBACK", dtype=object)
    else:
        soil_peat = np.zeros(len(out), dtype=float)
        soil_peat_method = np.full(len(out), "NO_IFS_PEAT_SIGNAL", dtype=object)

    if "LPIS_GRASS_CONTEXT_AVAILABLE" in out.columns:
        lpis_available = (
            out["LPIS_GRASS_CONTEXT_AVAILABLE"].fillna(False).astype(bool).to_numpy()
        )
    else:
        lpis_available = np.zeros(len(out), dtype=bool)

    low_input = _share(out, "LPIS_LOW_INPUT_GRASS_SHARE")
    peat_grass = _share(out, "LPIS_PEAT_GRASS_SHARE")
    riparian = _share(out, "LPIS_RIPARIAN_GRASS_SHARE")
    low_input_represented = _area_represented(out, "LPIS_LOW_INPUT_GRASS_HA")
    peat_grass_represented = _area_represented(out, "LPIS_PEAT_GRASS_HA")
    riparian_represented = _area_represented(out, "LPIS_RIPARIAN_GRASS_HA")

    sensitive = np.zeros(len(out), dtype=float)
    if low_input_represented:
        sensitive += low_input
    if peat_grass_represented:
        sensitive += peat_grass
    if riparian_represented:
        sensitive += riparian
    sensitive = np.where(lpis_available, np.clip(sensitive, 0.0, 1.0), 0.0)
    productive_context = np.where(lpis_available, 1.0 - sensitive, 1.0)

    out["FORESTRY_OPPORTUNITY_SCORE"] = np.clip(
        forest_base * productive_context, 0.0, 1.0
    )
    out["REWETTING_OPPORTUNITY_SCORE"] = np.clip(
        np.maximum(
            soil_peat,
            np.where(
                lpis_available & peat_grass_represented,
                peat_grass,
                0.0,
            ),
        ),
        0.0,
        1.0,
    )
    biomass = np.clip(productivity_score * productive_context, 0.0, 1.0)
    out["AD_GRASS_OPPORTUNITY_SCORE"] = biomass
    out["WILLOW_OPPORTUNITY_SCORE"] = biomass
    out["ENERGY_GRASS_OPPORTUNITY_SCORE"] = biomass
    out["NATURE_OPPORTUNITY_SCORE"] = np.clip(
        np.maximum.reduce(
            [
                out["REWETTING_OPPORTUNITY_SCORE"].to_numpy(float),
                np.where(lpis_available & low_input_represented, low_input, 0.0),
                np.where(lpis_available & riparian_represented, riparian, 0.0),
                1.0 - productivity_score,
            ]
        ),
        0.0,
        1.0,
    )

    out["LPIS_SENSITIVE_GRASS_SHARE"] = np.where(lpis_available, sensitive, np.nan)
    out["LPIS_PRODUCTIVE_GRASS_CONTEXT_SHARE"] = np.where(
        lpis_available, productive_context, np.nan
    )
    out["OPPORTUNITY_LPIS_CONTEXT_USED"] = lpis_available
    out["OPPORTUNITY_SOIL_PEAT_METHOD"] = soil_peat_method
    out["OPPORTUNITY_SCREEN_VERSION"] = SC2_VERSION
    sensitive_method, rewetting_method = opportunity_method_strings(out)
    out["SENSITIVE_GRASS_DEFINITION_IN_FORCE"] = sensitive_method
    out["REWETTING_EVIDENCE_IN_FORCE"] = rewetting_method

    out["SC2_PRODUCTIVITY_EVIDENCE"] = productivity_score
    out["SC2_SENSITIVE_GRASS_EVIDENCE"] = np.where(
        lpis_available, sensitive, np.nan
    )
    out["SC2_SOIL_PEAT_EVIDENCE"] = soil_peat
    out["SC2_LPIS_PEAT_GRASS_EVIDENCE"] = (
        np.where(lpis_available, peat_grass, np.nan)
        if peat_grass_represented
        else np.full(len(out), np.nan)
    )
    out["SC2_LOW_INPUT_GRASS_EVIDENCE"] = (
        np.where(lpis_available, low_input, np.nan)
        if low_input_represented
        else np.full(len(out), np.nan)
    )
    out["SC2_RIPARIAN_GRASS_EVIDENCE"] = (
        np.where(lpis_available, riparian, np.nan)
        if riparian_represented
        else np.full(len(out), np.nan)
    )

    for column in (
        "LPIS_COMMONAGE_GRASS_SHARE",
        "LPIS_ANC_GRASS_SHARE",
        "LPIS_ENV_SCHEME_GRASS_SHARE",
        "LPIS_ORGANIC_GRASS_SHARE",
    ):
        if column not in out.columns:
            out[column] = np.nan

    for score in OPPORTUNITY_COLUMNS:
        out[score.replace("_SCORE", "_BAND")] = score_band(out[score])
    return out


def add_dual_soil_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Add descriptive Cathal/NFS vs Colm/IFS diagnostics without score blending."""

    out = frame.copy()
    cathal_cols = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3))
    required = (*cathal_cols, *IFS_MAP_SG_SHARE_COLUMNS, *IFS_MAP_PHYSICAL_SHARE_COLUMNS)
    missing = sorted(set(required) - set(out.columns))
    if missing:
        raise ValueError(f"SC2 v3.1 dual-soil context missing fields: {missing}")

    cathal = out[list(cathal_cols)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    mapped = out[list(IFS_MAP_SG_SHARE_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(float)
    physical = out[list(IFS_MAP_PHYSICAL_SHARE_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(float)
    for label, values in (
        ("Cathal/NFS G1-G3", cathal),
        ("Colm/IFS mapped G1-G3", mapped),
        ("Colm/IFS physical categories", physical),
    ):
        if (~np.isfinite(values)).any() or (values < -1e-10).any():
            raise AssertionError(f"{label} contains invalid shares")
        closure = float(np.max(np.abs(values.sum(axis=1) - 1.0)))
        if closure > 1e-8:
            raise AssertionError(f"{label} does not close to one: {closure:.3e}")

    delta = cathal - mapped
    for i, group in enumerate((1, 2, 3)):
        out[f"SOIL_G{group}_SHARE_DIFFERENCE_CATHAL_MINUS_IFS_MAP"] = delta[:, i]
    divergence = 0.5 * np.abs(delta).sum(axis=1)
    out["SOIL_REPRESENTATION_DIVERGENCE"] = np.clip(divergence, 0.0, 1.0)
    out["SOIL_REPRESENTATION_DIVERGENCE_BAND"] = pd.Series(
        np.select(
            [divergence <= 0.10, divergence <= 0.25],
            ["LOW_DIVERGENCE", "MODERATE_DIVERGENCE"],
            default="HIGH_DIVERGENCE",
        ),
        index=out.index,
        dtype="string",
    )
    cathal_dom = np.array([f"G{i + 1}" for i in np.argmax(cathal, axis=1)], object)
    mapped_dom = np.array([f"G{i + 1}" for i in np.argmax(mapped, axis=1)], object)
    out["SOIL_DOMINANT_GROUP_CATHAL"] = cathal_dom
    out["SOIL_DOMINANT_GROUP_IFS_MAP"] = mapped_dom
    out["SOIL_DOMINANT_GROUP_AGREEMENT"] = cathal_dom == mapped_dom

    deep = out["IFS_MAP_DEEP_WELL_DRAINED_SHARE"].to_numpy(float)
    shallow = out["IFS_MAP_SHALLOW_WELL_DRAINED_SHARE"].to_numpy(float)
    poor = out["IFS_MAP_POORLY_DRAINED_SHARE"].to_numpy(float)
    poor_peaty = out["IFS_MAP_POORLY_DRAINED_PEATY_SHARE"].to_numpy(float)
    peat = out["IFS_MAP_PEAT_SHARE"].to_numpy(float)
    well_drained = np.clip(deep + shallow, 0.0, 1.0)
    poor_drainage = np.clip(poor + poor_peaty, 0.0, 1.0)
    wet_or_peat = np.clip(poor + poor_peaty + peat, 0.0, 1.0)
    out["IFS_MAP_WELL_DRAINED_SHARE"] = well_drained
    out["IFS_MAP_POOR_DRAINAGE_SHARE"] = poor_drainage
    out["IFS_MAP_WET_OR_PEAT_CONTEXT_SHARE"] = wet_or_peat
    out["SC2_IFS_MAP_PRODUCTIVE_DRAINAGE_EVIDENCE"] = well_drained
    out["SC2_IFS_MAP_WET_PEAT_EVIDENCE"] = wet_or_peat
    out["SC2_DUAL_SOIL_PRINCIPAL_SCORES_CHANGED"] = False
    out["SC2_DUAL_SOIL_METHOD"] = (
        "CATHAL_NFS_CAPABILITY_PLUS_INDEPENDENT_COLM_IFS_PHYSICAL_CONTEXT_NO_BLEND"
    )
    return out


def add_released_land_physical_quantities(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | str]]:
    """Port the mature SC2 v3.1 Class1-6 and organic/mineral eligibility solve."""

    out = frame.copy()
    release = pd.to_numeric(
        out["GOBLIN_RELEASED_GRASSLAND_HA"], errors="raise"
    ).to_numpy(float)
    release_g_cols = tuple(f"GOBLIN_RELEASED_G{i}_HA" for i in (1, 2, 3))
    required = {*release_g_cols, "ALL_GRASSLAND"}
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"SC2 physical quantities missing frozen SC1 fields: {missing}")

    have_hectares = all(c in out.columns for c in CLASS_GRASSLAND_COLUMNS)
    have_shares = all(c in out.columns for c in CLASS_SHARE_COLUMNS)
    if not (have_hectares or have_shares):
        raise ValueError("SC2 v3.1 requires preserved 08B Class1-6 fields")

    grass = pd.to_numeric(out["ALL_GRASSLAND"], errors="raise").to_numpy(float)
    if have_hectares:
        class_capacity = out[list(CLASS_GRASSLAND_COLUMNS)].apply(
            pd.to_numeric, errors="raise"
        ).to_numpy(float)
    else:
        shares = out[list(CLASS_SHARE_COLUMNS)].apply(
            pd.to_numeric, errors="raise"
        ).to_numpy(float)
        class_capacity = shares * grass[:, None]
    if (~np.isfinite(class_capacity)).any() or (class_capacity < -1e-9).any():
        raise AssertionError("08B Class1-6 capacities contain invalid values")
    class_capacity = np.maximum(class_capacity, 0.0)
    if not np.allclose(class_capacity.sum(axis=1), grass, atol=1e-7):
        raise AssertionError("08B Class1-6 capacities do not close to ALL_GRASSLAND")

    released_g = out[list(release_g_cols)].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(float)
    if not np.allclose(released_g.sum(axis=1), release, atol=1e-7):
        raise AssertionError("SC1 G1/G2/G3 release does not close to total release")

    released_class = np.zeros((len(out), 6), dtype=float)
    pairs = {1: (0, 1), 2: (2, 3), 3: (4, 5)}
    g_errors: list[np.ndarray] = []
    for group, (i, j) in pairs.items():
        cap_pair = class_capacity[:, [i, j]]
        denom = cap_pair.sum(axis=1)
        group_release = released_g[:, group - 1]
        impossible = (group_release > 1e-8) & (denom <= 1e-12)
        if impossible.any():
            raise AssertionError(
                f"SC1 releases G{group} in EDs with zero Class-{2*group-1}/{2*group} capacity"
            )
        share_i = np.divide(
            cap_pair[:, 0],
            denom,
            out=np.zeros(len(out)),
            where=denom > 1e-12,
        )
        released_class[:, i] = group_release * share_i
        released_class[:, j] = group_release - released_class[:, i]
        g_errors.append(released_class[:, i] + released_class[:, j] - group_release)

    for idx, klass in enumerate(NFS_CLASSES):
        out[f"RELEASED_CLASS_{klass}_HA"] = released_class[:, idx]
        if (released_class[:, idx] - class_capacity[:, idx] > 1e-6).any():
            raise AssertionError(f"RELEASED_CLASS_{klass}_HA exceeds 08B capacity")

    class_error = float(np.max(np.abs(released_class.sum(axis=1) - release)))
    group_error = float(max(np.max(np.abs(x)) for x in g_errors))
    if class_error > 1e-7 or group_error > 1e-7:
        raise AssertionError(
            f"SC2 class release closure failed: class={class_error:.3e}, group={group_error:.3e}"
        )

    if "IFS_PEAT_CUTOVER_UAA_SHARE" not in out.columns:
        raise ValueError("SC2 v3.1 requires IFS_PEAT_CUTOVER_UAA_SHARE for SC3 eligibility")
    organic_share = pd.to_numeric(
        out["IFS_PEAT_CUTOVER_UAA_SHARE"], errors="coerce"
    ).to_numpy(float)
    valid = np.isfinite(organic_share)
    if not valid.all():
        raise ValueError(
            "principal SC2/SC3 requires an organic-soil weight for every ED after 08B fallback"
        )
    if ((organic_share < -1e-9) | (organic_share > 1.0 + 1e-9)).any():
        raise AssertionError("IFS_PEAT_CUTOVER_UAA_SHARE must lie in [0,1]")
    organic_share = np.clip(organic_share, 0.0, 1.0)
    organic_weight = release * organic_share
    mineral_fraction = 1.0 - organic_share
    released_class_mineral = released_class * mineral_fraction[:, None]

    out["RELEASED_ORGANIC_WEIGHT_HA"] = organic_weight
    out["RELEASED_MINERAL_INDICATIVE_HA"] = release * mineral_fraction
    out["RELEASED_REWETTING_ELIGIBLE_WEIGHT_HA"] = organic_weight

    def mineral_sum(classes: tuple[int, ...]) -> np.ndarray:
        return np.nansum(
            released_class_mineral[:, [c - 1 for c in classes]], axis=1
        )

    out["RELEASED_TILLAGE_ELIGIBLE_HA"] = mineral_sum((1, 2, 3))
    out["RELEASED_TILLAGE_STRICT_ELIGIBLE_HA"] = mineral_sum((1, 2))
    out["RELEASED_FOREST_ELIGIBLE_HA"] = mineral_sum((1, 2, 3, 4, 5))
    out["RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA"] = mineral_sum((1, 2, 3, 4))
    out["RELEASED_WILLOW_ELIGIBLE_HA"] = mineral_sum((1, 2, 3))
    out["RELEASED_WILLOW_WIDE_ELIGIBLE_HA"] = mineral_sum((1, 2, 3, 4))

    max_exceed = max(
        float(np.max(pd.to_numeric(out[c], errors="raise").to_numpy(float) - release))
        for c in RELEASED_ELIGIBILITY_COLUMNS
    )
    if max_exceed > 1e-7:
        raise AssertionError("SC2 eligibility exceeds ED released-land budget")

    out["RELEASED_ORGANIC_IS_SCALED_TO_PATHWAY_STOCK"] = False
    out["RELEASED_CLASS_PARTITION_AVAILABLE"] = True
    out["RELEASED_CLASS_PARTITION_METHOD"] = (
        "SC1_G1_G2_G3_RELEASE_SPLIT_WITHIN_G_BY_08B_CLASS_CAPACITY"
    )
    out["RELEASED_ORGANIC_METHOD"] = (
        "IFS_PEAT_CUTOVER_UAA_SHARE_AS_UNSCALED_ED_WEIGHT"
    )
    return out, {
        "CLASS_PARTITION_AVAILABLE": "YES",
        "CLASS_PARTITION_CLOSURE_MAX_ABS_HA": class_error,
        "CLASS_TO_SC1_G_CLOSURE_MAX_ABS_HA": group_error,
        "MAX_ELIGIBLE_QUANTITY_MINUS_RELEASE_HA": max(0.0, max_exceed),
    }


def build_sc2_opportunity(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | str]]:
    """Run the mature SC2 v3.1 post-context science in its validated order."""

    before = frame.copy()
    out = add_ed_land_opportunity_scores_v2(frame)
    out = add_dual_soil_context(out)
    out, qa = add_released_land_physical_quantities(out)

    # SC2 may append columns only. Original SC1/context fields must be invariant.
    for column in before.columns:
        left = before[column]
        right = out[column]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            same = np.allclose(
                pd.to_numeric(left, errors="coerce").to_numpy(float),
                pd.to_numeric(right, errors="coerce").to_numpy(float),
                rtol=1e-12,
                atol=1e-10,
                equal_nan=True,
            )
        else:
            same = np.array_equal(
                left.astype("string").fillna("<NA>").to_numpy(str),
                right.astype("string").fillna("<NA>").to_numpy(str),
            )
        if not same:
            raise AssertionError(f"SC2 changed pre-existing field: {column}")
    return out, qa
