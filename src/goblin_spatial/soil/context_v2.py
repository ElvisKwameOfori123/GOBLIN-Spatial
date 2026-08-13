"""Improved ED agricultural-soil context for downstream opportunity analysis.

This module keeps the validated GOBLIN-Spatial land accounting untouched while
fixing two limitations of the first soil attachment layer:

* model CSOED identifiers, including compound identifiers such as
  ``08045/08046``, are preserved rather than coerced to integers; and
* a compound model ED can be assembled from its component source-soil profiles
  before falling back to county or national averages.

The holding-linked source remains an aggregation source only.  ``fsizuaa`` is a
weight, never the authoritative ED land total.  ``ALL_GRASSLAND`` remains the
controlling grassland hectares and is partitioned by the resulting G1/G2/G3
shares only after the livestock baseline is solved.

A continuous source-UAA-weighted peat/cutover share is also derived from the
Irish Forest Soil field.  This replaces the need to infer rewetting opportunity
solely from the single dominant IFS class when the richer source is available.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .agricultural import (
    build_ed_agricultural_soil_profile as _build_v1,
    read_ed_agricultural_soil_profile as _read_v1,
)
from .overlay import canonical_csoed


GOBLIN_SHARE_COLUMNS = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3))


def _read_source(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    return source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source), low_memory=False)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    mask = values.notna() & weights.gt(0)
    if not mask.any():
        return np.nan
    return float(np.average(values.loc[mask], weights=weights.loc[mask]))


def _add_continuous_ifs_context(profile: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    out = profile.copy()
    out["CSOED_CANONICAL"] = out["CSOED"].map(canonical_csoed)

    if "ifs_soil" not in raw.columns:
        out["IFS_SOIL_COVERED_UAA_HA"] = np.nan
        out["IFS_PEAT_CUTOVER_UAA_HA"] = np.nan
        out["IFS_PEAT_CUTOVER_UAA_SHARE"] = np.nan
        return out

    required = {"cso_ed", "fsizuaa"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"agricultural soil source missing columns: {missing}")

    work = pd.DataFrame(index=raw.index)
    work["CSOED_CANONICAL"] = raw["cso_ed"].map(canonical_csoed)
    work["SOURCE_UAA_HA"] = pd.to_numeric(raw["fsizuaa"], errors="coerce")
    work["IFS_SOIL"] = raw["ifs_soil"].astype("string").str.strip()
    work = work.loc[
        work["CSOED_CANONICAL"].ne("")
        & work["SOURCE_UAA_HA"].gt(0)
        & work["IFS_SOIL"].notna()
        & work["IFS_SOIL"].ne("")
    ].copy()

    if work.empty:
        out["IFS_SOIL_COVERED_UAA_HA"] = np.nan
        out["IFS_PEAT_CUTOVER_UAA_HA"] = np.nan
        out["IFS_PEAT_CUTOVER_UAA_SHARE"] = np.nan
        return out

    upper = work["IFS_SOIL"].str.upper()
    work["IS_PEAT_CUTOVER"] = upper.str.endswith("PT") | upper.eq("CUT")
    grouped = (
        work.groupby("CSOED_CANONICAL", as_index=False)
        .agg(
            IFS_SOIL_COVERED_UAA_HA=("SOURCE_UAA_HA", "sum"),
            IFS_PEAT_CUTOVER_UAA_HA=(
                "SOURCE_UAA_HA",
                lambda values: float(values.loc[work.loc[values.index, "IS_PEAT_CUTOVER"]].sum()),
            ),
        )
    )
    grouped["IFS_PEAT_CUTOVER_UAA_SHARE"] = np.divide(
        grouped["IFS_PEAT_CUTOVER_UAA_HA"],
        grouped["IFS_SOIL_COVERED_UAA_HA"],
        out=np.zeros(len(grouped), dtype=float),
        where=grouped["IFS_SOIL_COVERED_UAA_HA"].to_numpy(dtype=float) > 0,
    )
    return out.merge(grouped, on="CSOED_CANONICAL", how="left", validate="one_to_one")


def build_ed_agricultural_soil_profile(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Build the compact ED soil profile with a continuous peat/cutover share."""

    raw = _read_source(source)
    profile = _build_v1(raw)
    return _add_continuous_ifs_context(profile, raw)


def read_ed_agricultural_soil_profile(path: str | Path) -> pd.DataFrame:
    """Read either the original compact soil profile or the enriched v2 profile."""

    profile = _read_v1(path)
    if "CSOED_CANONICAL" not in profile.columns:
        profile["CSOED_CANONICAL"] = profile["CSOED"].map(canonical_csoed)
    for column in (
        "IFS_SOIL_COVERED_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_SHARE",
    ):
        if column not in profile.columns:
            profile[column] = np.nan
    if profile["CSOED_CANONICAL"].eq("").any() or profile["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("ED soil profile must contain one valid canonical CSOED per row")
    return profile


def _aggregate_profiles(block: pd.DataFrame) -> dict[str, object]:
    weights = pd.to_numeric(block["SOIL_SOURCE_UAA_HA"], errors="coerce").fillna(0.0)
    if weights.sum() <= 0:
        raise ValueError("cannot aggregate soil profiles without positive source UAA")

    row: dict[str, object] = {
        "SOIL_SOURCE_HOLDINGS": float(pd.to_numeric(block.get("SOIL_SOURCE_HOLDINGS", 0), errors="coerce").fillna(0).sum()),
        "SOIL_SOURCE_UAA_HA": float(weights.sum()),
    }
    for share in GOBLIN_SHARE_COLUMNS:
        row[share] = _weighted_mean(block[share], weights)

    if "FOREST_YC_WEIGHTED_MEAN" in block.columns:
        forest_weights = (
            pd.to_numeric(block["FOREST_YC_SOURCE_UAA_HA"], errors="coerce").fillna(0.0)
            if "FOREST_YC_SOURCE_UAA_HA" in block.columns
            else weights
        )
        row["FOREST_YC_WEIGHTED_MEAN"] = _weighted_mean(
            block["FOREST_YC_WEIGHTED_MEAN"], forest_weights
        )
    else:
        row["FOREST_YC_WEIGHTED_MEAN"] = np.nan

    if "IFS_PEAT_CUTOVER_UAA_SHARE" in block.columns:
        ifs_weights = (
            pd.to_numeric(block["IFS_SOIL_COVERED_UAA_HA"], errors="coerce").fillna(0.0)
            if "IFS_SOIL_COVERED_UAA_HA" in block.columns
            else weights
        )
        row["IFS_PEAT_CUTOVER_UAA_SHARE"] = _weighted_mean(
            block["IFS_PEAT_CUTOVER_UAA_SHARE"], ifs_weights
        )
        row["IFS_SOIL_COVERED_UAA_HA"] = float(ifs_weights.sum())
        if np.isfinite(row["IFS_PEAT_CUTOVER_UAA_SHARE"]):
            row["IFS_PEAT_CUTOVER_UAA_HA"] = (
                row["IFS_SOIL_COVERED_UAA_HA"] * row["IFS_PEAT_CUTOVER_UAA_SHARE"]
            )
        else:
            row["IFS_PEAT_CUTOVER_UAA_HA"] = np.nan
    else:
        row["IFS_PEAT_CUTOVER_UAA_SHARE"] = np.nan
        row["IFS_SOIL_COVERED_UAA_HA"] = np.nan
        row["IFS_PEAT_CUTOVER_UAA_HA"] = np.nan

    row["IFS_SOIL_DOMINANT"] = pd.NA
    row["IFS_SOIL_DOMINANT_SHARE"] = np.nan
    return row


def _resolved_model_profile(master: pd.DataFrame, soil: pd.DataFrame) -> pd.DataFrame:
    model = master[["CSOED", "County"]].drop_duplicates().copy()
    model["CSOED_CANONICAL"] = model["CSOED"].map(canonical_csoed)
    if model["CSOED_CANONICAL"].eq("").any() or model["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("model must contain one valid CSOED-to-county relationship")

    soil = soil.copy()
    if "CSOED_CANONICAL" not in soil.columns:
        soil["CSOED_CANONICAL"] = soil["CSOED"].map(canonical_csoed)
    if soil["CSOED_CANONICAL"].duplicated().any():
        raise ValueError("soil profile contains duplicate canonical CSOED rows")
    by_key = soil.set_index("CSOED_CANONICAL", drop=False)

    direct_or_compound: list[dict[str, object]] = []
    unresolved: list[tuple[str, str, object]] = []
    for row in model.itertuples(index=False):
        key = row.CSOED_CANONICAL
        if key in by_key.index:
            source = by_key.loc[key]
            record = source.to_dict()
            record["MODEL_CSOED_CANONICAL"] = key
            record["SOIL_PROFILE_SOURCE"] = "ED"
            direct_or_compound.append(record)
            continue

        components = [part for part in key.split("/") if part]
        if len(components) > 1 and all(part in by_key.index for part in components):
            component_block = by_key.loc[components].copy()
            record = _aggregate_profiles(component_block)
            record["MODEL_CSOED_CANONICAL"] = key
            record["SOIL_PROFILE_SOURCE"] = "COMPOUND_COMPONENTS"
            direct_or_compound.append(record)
            continue

        unresolved.append((key, str(row.County), row.CSOED))

    resolved = pd.DataFrame(direct_or_compound)
    if "MODEL_CSOED_CANONICAL" not in resolved.columns:
        resolved = pd.DataFrame(columns=["MODEL_CSOED_CANONICAL", "SOIL_PROFILE_SOURCE"])

    source_county = soil[["CSOED_CANONICAL", *[c for c in soil.columns if c != "CSOED_CANONICAL"]]].copy()
    source_county = source_county.merge(
        model[["CSOED_CANONICAL", "County"]],
        on="CSOED_CANONICAL",
        how="left",
        validate="one_to_one",
    )
    county_profiles: dict[str, dict[str, object]] = {}
    for county, block in source_county.dropna(subset=["County"]).groupby("County", sort=False):
        if pd.to_numeric(block["SOIL_SOURCE_UAA_HA"], errors="coerce").fillna(0).sum() > 0:
            county_profiles[str(county)] = _aggregate_profiles(block)
    national = _aggregate_profiles(soil)

    fallback_rows: list[dict[str, object]] = []
    for key, county, _original in unresolved:
        if county in county_profiles:
            record = dict(county_profiles[county])
            record["SOIL_PROFILE_SOURCE"] = "COUNTY_FALLBACK"
        else:
            record = dict(national)
            record["SOIL_PROFILE_SOURCE"] = "NATIONAL_FALLBACK"
        record["MODEL_CSOED_CANONICAL"] = key
        fallback_rows.append(record)

    all_rows = pd.concat([resolved, pd.DataFrame(fallback_rows)], ignore_index=True, sort=False)
    if len(all_rows) != len(model) or all_rows["MODEL_CSOED_CANONICAL"].duplicated().any():
        raise AssertionError("soil resolution did not create exactly one profile per model ED")
    return all_rows


def add_ed_agricultural_soil(
    master: pd.DataFrame,
    profile: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Attach compound-aware soil context without changing the model CSOED field."""

    required = {"CSOED", "County", "ALL_GRASSLAND"}
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"master missing soil attachment columns: {missing}")

    if isinstance(profile, pd.DataFrame):
        soil = profile.copy()
        if "CSOED_CANONICAL" not in soil.columns:
            soil["CSOED_CANONICAL"] = soil["CSOED"].map(canonical_csoed)
        for column in (
            "IFS_SOIL_COVERED_UAA_HA",
            "IFS_PEAT_CUTOVER_UAA_HA",
            "IFS_PEAT_CUTOVER_UAA_SHARE",
        ):
            if column not in soil.columns:
                soil[column] = np.nan
    else:
        soil = read_ed_agricultural_soil_profile(profile)

    original_csoed = master["CSOED"].copy()
    out = master.copy()
    out["_SOIL_CSOED_KEY"] = out["CSOED"].map(canonical_csoed)
    resolved = _resolved_model_profile(out, soil)

    keep = [
        "MODEL_CSOED_CANONICAL",
        "SOIL_PROFILE_SOURCE",
        "SOIL_SOURCE_HOLDINGS",
        "SOIL_SOURCE_UAA_HA",
        *GOBLIN_SHARE_COLUMNS,
        "FOREST_YC_WEIGHTED_MEAN",
        "IFS_SOIL_DOMINANT",
        "IFS_SOIL_DOMINANT_SHARE",
        "IFS_SOIL_COVERED_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_SHARE",
    ]
    for column in keep:
        if column not in resolved.columns:
            resolved[column] = np.nan

    out = out.merge(
        resolved[keep].rename(columns={"MODEL_CSOED_CANONICAL": "_SOIL_CSOED_KEY"}),
        on="_SOIL_CSOED_KEY",
        how="left",
        validate="many_to_one",
    )
    if out[list(GOBLIN_SHARE_COLUMNS)].isna().any().any():
        raise AssertionError("soil attachment left unresolved G1/G2/G3 shares")
    if not np.allclose(
        out[list(GOBLIN_SHARE_COLUMNS)].sum(axis=1).to_numpy(dtype=float), 1.0, atol=1e-8
    ):
        raise AssertionError("attached GOBLIN soil-group shares do not close to one")

    grass = pd.to_numeric(out["ALL_GRASSLAND"], errors="coerce")
    for group, share in enumerate(GOBLIN_SHARE_COLUMNS, start=1):
        out[f"GOBLIN_SOIL_G{group}_GRASSLAND_HA"] = grass * out[share]
    grass_columns = [f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in (1, 2, 3)]
    if not np.allclose(
        out[grass_columns].fillna(0.0).sum(axis=1).to_numpy(dtype=float),
        grass.fillna(0.0).to_numpy(dtype=float),
        atol=1e-7,
    ):
        raise AssertionError("soil-group grassland hectares do not close to ALL_GRASSLAND")

    out["CSOED"] = original_csoed.to_numpy()
    return out.drop(columns="_SOIL_CSOED_KEY")
