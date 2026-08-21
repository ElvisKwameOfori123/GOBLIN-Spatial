"""Precomputed 08B/08C soil controls for the principal scenario pipeline.

Heavy source tables are reduced once to compact ED profiles. Scenario runs only
attach these profiles. 08B is the agricultural-capability frame used by SC1
land-release capacity and SC2 class eligibility. 08C is an independent mapped
physical-soil context and never replaces 08B or ALL_GRASSLAND.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .overlay import canonical_csoed

CLASS_SHARE_COLUMNS = tuple(f"SOIL_USE_CLASS_{i}_SHARE" for i in range(1, 7))
GROUP_SHARE_COLUMNS = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3))
PHYSICAL_AREA_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
)
PHYSICAL_SHARE_COLUMNS = tuple(c.replace("_HA", "_SHARE") for c in PHYSICAL_AREA_COLUMNS)
MAP_SG_SHARE_COLUMNS = tuple(f"IFS_MAP_SG{i}_SHARE" for i in (1, 2, 3))

# Exact Colm package assumption documented in the source GeoPackage methods table.
COLM_FARMED_PEAT_FRACTION = 0.10


def _read(source):
    return source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source), low_memory=False)


def _weighted(values: pd.Series, weights: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    mask = v.notna() & w.gt(0)
    if not mask.any():
        return np.nan
    return float(np.average(v.loc[mask], weights=w.loc[mask]))


def _aggregate_08b(block: pd.DataFrame) -> dict[str, object]:
    uaa = pd.to_numeric(block["SOIL_SOURCE_UAA_HA"], errors="coerce").fillna(0.0)
    if float(uaa.sum()) <= 0:
        raise ValueError("08B aggregation requires positive source UAA")
    row: dict[str, object] = {
        "SOIL_SOURCE_UAA_HA": float(uaa.sum()),
        "SOIL_SOURCE_HOLDINGS": float(
            pd.to_numeric(block.get("SOIL_SOURCE_HOLDINGS", 0), errors="coerce")
            .fillna(0)
            .sum()
        ),
    }
    for col in (*CLASS_SHARE_COLUMNS, *GROUP_SHARE_COLUMNS):
        row[col] = _weighted(block[col], uaa)
    if "FOREST_YC_WEIGHTED_MEAN" in block.columns:
        yc_w = pd.to_numeric(
            block.get("FOREST_YC_SOURCE_UAA_HA", uaa), errors="coerce"
        ).fillna(0.0)
        row["FOREST_YC_SOURCE_UAA_HA"] = float(yc_w.sum())
        row["FOREST_YC_WEIGHTED_MEAN"] = _weighted(
            block["FOREST_YC_WEIGHTED_MEAN"], yc_w
        )
    else:
        row["FOREST_YC_SOURCE_UAA_HA"] = np.nan
        row["FOREST_YC_WEIGHTED_MEAN"] = np.nan
    if "IFS_PEAT_CUTOVER_UAA_SHARE" in block.columns:
        ifs_w = pd.to_numeric(
            block.get("IFS_SOIL_COVERED_UAA_HA", uaa), errors="coerce"
        ).fillna(0.0)
        row["IFS_SOIL_COVERED_UAA_HA"] = float(ifs_w.sum())
        row["IFS_PEAT_CUTOVER_UAA_SHARE"] = _weighted(
            block["IFS_PEAT_CUTOVER_UAA_SHARE"], ifs_w
        )
        row["IFS_PEAT_CUTOVER_UAA_HA"] = (
            row["IFS_SOIL_COVERED_UAA_HA"] * row["IFS_PEAT_CUTOVER_UAA_SHARE"]
            if np.isfinite(row["IFS_PEAT_CUTOVER_UAA_SHARE"])
            else np.nan
        )
    else:
        row["IFS_SOIL_COVERED_UAA_HA"] = np.nan
        row["IFS_PEAT_CUTOVER_UAA_HA"] = np.nan
        row["IFS_PEAT_CUTOVER_UAA_SHARE"] = np.nan
    row["IFS_SOIL_DOMINANT"] = pd.NA
    row["IFS_SOIL_DOMINANT_SHARE"] = np.nan
    return row


def _model_map(master: pd.DataFrame) -> pd.DataFrame:
    if not {"CSOED", "County"}.issubset(master.columns):
        raise ValueError("soil attachment requires CSOED and County")
    model = master[["CSOED", "County"]].drop_duplicates().copy()
    model["_KEY"] = model["CSOED"].map(canonical_csoed)
    if model["_KEY"].eq("").any() or model["_KEY"].duplicated().any():
        raise ValueError("model must contain one valid CSOED-to-county relationship")
    return model


def _component_to_county(model: pd.DataFrame) -> dict[str, str]:
    """Map ordinary and compound model-ED components to validated counties.

    Mature 08B county fallback is built from source ED components, not only from
    source keys that happen to equal a complete model key. This matters for model
    EDs such as ``08045/08046`` whose individual Cathal source components must
    still contribute to the correct county profile.
    """
    rows: list[dict[str, str]] = []
    for _original, county, key in model[["CSOED", "County", "_KEY"]].itertuples(
        index=False, name=None
    ):
        for component in (part for part in key.split("/") if part):
            rows.append({"SOURCE_COMPONENT_KEY": component, "County": str(county)})
    bridge = pd.DataFrame(rows)
    if bridge.empty:
        return {}
    counts = bridge.groupby("SOURCE_COMPONENT_KEY")["County"].nunique()
    if counts.gt(1).any():
        bad = counts[counts.gt(1)].index.tolist()[:10]
        raise ValueError(f"one ED component maps to multiple counties: {bad}")
    return (
        bridge.drop_duplicates("SOURCE_COMPONENT_KEY")
        .set_index("SOURCE_COMPONENT_KEY")["County"]
        .to_dict()
    )


def _resolve_08b(master: pd.DataFrame, profile: pd.DataFrame) -> pd.DataFrame:
    model = _model_map(master)
    component_to_county = _component_to_county(model)
    p = profile.copy()
    required = {
        "CSOED",
        "SOIL_SOURCE_UAA_HA",
        *CLASS_SHARE_COLUMNS,
        *GROUP_SHARE_COLUMNS,
    }
    missing = sorted(required - set(p.columns))
    if missing:
        raise ValueError(f"compact 08B profile missing columns: {missing}")
    p["_KEY"] = p["CSOED"].map(canonical_csoed)
    if p["_KEY"].eq("").any() or p["_KEY"].duplicated().any():
        raise ValueError("compact 08B profile must contain unique canonical CSOED keys")
    by = p.set_index("_KEY", drop=False)

    direct: list[dict[str, object]] = []
    unresolved: list[tuple[str, str]] = []
    for _original, county, key in model[["CSOED", "County", "_KEY"]].itertuples(
        index=False, name=None
    ):
        if key in by.index:
            rec = by.loc[key].to_dict()
            rec["_MODEL_KEY"] = key
            rec["SOIL_PROFILE_SOURCE"] = "ED"
            direct.append(rec)
            continue
        parts = [x for x in key.split("/") if x]
        if len(parts) > 1 and all(x in by.index for x in parts):
            rec = _aggregate_08b(by.loc[parts].copy())
            rec["_MODEL_KEY"] = key
            rec["SOIL_PROFILE_SOURCE"] = "COMPOUND_COMPONENTS"
            direct.append(rec)
            continue
        unresolved.append((key, str(county)))

    # Reproduce the mature 08B county profile exactly: assign each source ED to
    # its county through the model component bridge, including components of
    # compound model EDs.
    source_county = p.copy()
    source_county["_SOURCE_COUNTY"] = source_county["_KEY"].map(component_to_county)
    county_profiles = {
        str(county): _aggregate_08b(block)
        for county, block in source_county.dropna(subset=["_SOURCE_COUNTY"]).groupby(
            "_SOURCE_COUNTY", sort=False
        )
        if float(
            pd.to_numeric(block["SOIL_SOURCE_UAA_HA"], errors="coerce")
            .fillna(0)
            .sum()
        )
        > 0
    }
    national = _aggregate_08b(p)
    fallback: list[dict[str, object]] = []
    for key, county in unresolved:
        rec = dict(county_profiles.get(county, national))
        rec["_MODEL_KEY"] = key
        rec["SOIL_PROFILE_SOURCE"] = (
            "COUNTY_FALLBACK" if county in county_profiles else "NATIONAL_FALLBACK"
        )
        fallback.append(rec)
    resolved = pd.DataFrame([*direct, *fallback])
    if len(resolved) != len(model) or resolved["_MODEL_KEY"].duplicated().any():
        raise AssertionError("08B resolution did not create exactly one profile per model ED")
    return resolved


def add_principal_08b_context(master, profile):
    """Attach precomputed 08B capability, preserving authoritative baseline hectares."""
    out = master.copy()
    if "ALL_GRASSLAND" not in out.columns:
        raise ValueError("08B attachment requires ALL_GRASSLAND")
    p = _read(profile)
    resolved = _resolve_08b(out, p)
    out["_08B_KEY"] = out["CSOED"].map(canonical_csoed)
    keep = [
        "_MODEL_KEY",
        "SOIL_PROFILE_SOURCE",
        "SOIL_SOURCE_HOLDINGS",
        "SOIL_SOURCE_UAA_HA",
        *CLASS_SHARE_COLUMNS,
        *GROUP_SHARE_COLUMNS,
        "FOREST_YC_SOURCE_UAA_HA",
        "FOREST_YC_WEIGHTED_MEAN",
        "IFS_SOIL_COVERED_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_HA",
        "IFS_PEAT_CUTOVER_UAA_SHARE",
        "IFS_SOIL_DOMINANT",
        "IFS_SOIL_DOMINANT_SHARE",
    ]
    for col in keep:
        if col not in resolved.columns:
            resolved[col] = np.nan
    out = out.merge(
        resolved[keep].rename(columns={"_MODEL_KEY": "_08B_KEY"}),
        on="_08B_KEY",
        how="left",
        validate="many_to_one",
    )
    class_sum = (
        out[list(CLASS_SHARE_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .sum(axis=1)
        .to_numpy(float)
    )
    group_sum = (
        out[list(GROUP_SHARE_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .sum(axis=1)
        .to_numpy(float)
    )
    if not np.allclose(class_sum, 1.0, atol=1e-8) or not np.allclose(
        group_sum, 1.0, atol=1e-8
    ):
        raise AssertionError("08B class/group shares do not close to one")
    grass = pd.to_numeric(out["ALL_GRASSLAND"], errors="raise").to_numpy(float)
    for i, col in enumerate(CLASS_SHARE_COLUMNS, start=1):
        out[f"SOIL_USE_CLASS_{i}_GRASSLAND_HA"] = grass * pd.to_numeric(
            out[col], errors="raise"
        ).to_numpy(float)
    for i, col in enumerate(GROUP_SHARE_COLUMNS, start=1):
        out[f"GOBLIN_SOIL_G{i}_GRASSLAND_HA"] = grass * pd.to_numeric(
            out[col], errors="raise"
        ).to_numpy(float)
    if not np.allclose(
        out[[f"SOIL_USE_CLASS_{i}_GRASSLAND_HA" for i in range(1, 7)]].sum(axis=1),
        grass,
        atol=1e-7,
    ):
        raise AssertionError("08B Class1-6 grassland capacity does not close to ALL_GRASSLAND")
    if not np.allclose(
        out[[f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in (1, 2, 3)]].sum(axis=1),
        grass,
        atol=1e-7,
    ):
        raise AssertionError("08B G1-G3 grassland capacity does not close to ALL_GRASSLAND")
    out["SOIL_CONTEXT_08B_PRECOMPUTED"] = True
    return out.drop(columns="_08B_KEY")


def _aggregate_08c(block: pd.DataFrame) -> dict[str, object]:
    """Derive one Colm mapped-soil profile from physical mapped areas."""
    row = {
        col: float(pd.to_numeric(block[col], errors="coerce").fillna(0).sum())
        for col in PHYSICAL_AREA_COLUMNS
    }
    row["IFS_MAP_AG_SOIL_HA"] = float(sum(row[col] for col in PHYSICAL_AREA_COLUMNS))
    denom = row["IFS_MAP_AG_SOIL_HA"]
    for ac, sc in zip(PHYSICAL_AREA_COLUMNS, PHYSICAL_SHARE_COLUMNS, strict=True):
        row[sc] = row[ac] / denom if denom > 0 else 0.0
    row["IFS_MAP_SOURCE_PEAT_SHARE"] = row["IFS_MAP_PEAT_HA"] / denom if denom > 0 else 0.0
    row["IFS_MAP_PARENT_MATERIAL_DOM"] = pd.NA
    row["IFS_MAP_PEAT_FARMED_FRACTION"] = COLM_FARMED_PEAT_FRACTION
    row["IFS_MAP_EFFECTIVE_FARMED_PEAT_HA"] = (
        COLM_FARMED_PEAT_FRACTION * row["IFS_MAP_PEAT_HA"]
    )
    row["IFS_MAP_SG1_EFFECTIVE_HA"] = (
        row["IFS_MAP_DEEP_WELL_DRAINED_HA"]
        + 0.5 * row["IFS_MAP_SHALLOW_WELL_DRAINED_HA"]
    )
    row["IFS_MAP_SG2_EFFECTIVE_HA"] = (
        0.5 * row["IFS_MAP_SHALLOW_WELL_DRAINED_HA"]
        + row["IFS_MAP_POORLY_DRAINED_HA"]
        + 0.5 * row["IFS_MAP_POORLY_DRAINED_PEATY_HA"]
        + row["IFS_MAP_ALLUVIUM_HA"]
    )
    row["IFS_MAP_SG3_EFFECTIVE_HA"] = (
        0.5 * row["IFS_MAP_POORLY_DRAINED_PEATY_HA"]
        + row["IFS_MAP_EFFECTIVE_FARMED_PEAT_HA"]
        + row["IFS_MAP_MISCELLANEOUS_HA"]
    )
    row["IFS_MAP_SG_EFFECTIVE_DENOM_HA"] = sum(
        row[f"IFS_MAP_SG{i}_EFFECTIVE_HA"] for i in (1, 2, 3)
    )
    d = row["IFS_MAP_SG_EFFECTIVE_DENOM_HA"]
    for i in (1, 2, 3):
        row[f"IFS_MAP_SG{i}_SHARE"] = row[f"IFS_MAP_SG{i}_EFFECTIVE_HA"] / d if d > 0 else 0.0
    shares = [row[f"IFS_MAP_SG{i}_SHARE"] for i in (1, 2, 3)]
    row["IFS_MAP_DOMINANT_SG"] = int(np.argmax(shares) + 1) if d > 0 else 0
    row["IFS_MAP_DOMINANT_SG_SHARE"] = float(max(shares)) if d > 0 else 0.0
    row["IFS_MAP_SOURCE"] = "Colm soil-group-package / component ED aggregation"
    return row


def _prepare_08c_source(profile: pd.DataFrame) -> pd.DataFrame:
    """Normalise a compact 08C source from its mapped physical-area columns.

    The compact runtime control may retain the full mature 08C profile or only
    the seven physical mapped-area fields. Derived shares are therefore
    reproduced here from the documented Colm crosswalk rather than assumed to
    have been persisted in the compact file.
    """
    required = {"CSOED", *PHYSICAL_AREA_COLUMNS}
    missing = sorted(required - set(profile.columns))
    if missing:
        raise ValueError(f"compact 08C profile missing columns: {missing}")

    rows: list[dict[str, object]] = []
    for source_row in profile.itertuples(index=False):
        block = pd.DataFrame(
            [{col: getattr(source_row, col) for col in PHYSICAL_AREA_COLUMNS}]
        )
        record = _aggregate_08c(block)
        record["CSOED"] = getattr(source_row, "CSOED")
        if "IFS_MAP_PARENT_MATERIAL_DOM" in profile.columns:
            record["IFS_MAP_PARENT_MATERIAL_DOM"] = getattr(
                source_row, "IFS_MAP_PARENT_MATERIAL_DOM"
            )
        if "IFS_MAP_SOURCE" in profile.columns:
            record["IFS_MAP_SOURCE"] = getattr(source_row, "IFS_MAP_SOURCE")
        else:
            record["IFS_MAP_SOURCE"] = "Colm soil-group-package / ed_soil_shares.csv"
        rows.append(record)

    out = pd.DataFrame(rows)
    out["_KEY"] = out["CSOED"].map(canonical_csoed)
    if out["_KEY"].eq("").any() or out["_KEY"].duplicated().any():
        raise ValueError("compact 08C profile must have unique canonical CSOED keys")
    return out


def add_principal_08c_context(master, profile):
    """Attach independent mapped 08C soil with no synthetic spatial fallback.

    Colm's source is itself an ED-level spatial map. The mature 08C contract
    therefore permits only a direct ED match or reconstruction of a compound
    model ED from all of its mapped component EDs. Missing mapped EDs are an ED
    bridge/data problem and must be surfaced, not filled using county or national
    average soil.
    """
    out = master.copy()
    model = _model_map(out)
    p = _prepare_08c_source(_read(profile))
    by = p.set_index("_KEY", drop=False)

    resolved_rows: list[dict[str, object]] = []
    unresolved: list[tuple[object, str]] = []
    for original, _county, key in model[["CSOED", "County", "_KEY"]].itertuples(
        index=False, name=None
    ):
        if key in by.index:
            record = by.loc[key].to_dict()
            record["_MODEL_KEY"] = key
            record["IFS_MAP_PROFILE_SOURCE"] = "ED"
        else:
            parts = [x for x in key.split("/") if x]
            if len(parts) > 1 and all(x in by.index for x in parts):
                component_block = by.loc[parts].copy()
                if isinstance(component_block, pd.Series):
                    component_block = component_block.to_frame().T
                record = _aggregate_08c(component_block)
                record["_MODEL_KEY"] = key
                record["IFS_MAP_PROFILE_SOURCE"] = "COMPOUND_COMPONENTS"
            else:
                unresolved.append((original, key))
                continue
        resolved_rows.append(record)

    if unresolved:
        examples = "; ".join(
            f"{original!r}->{key}" for original, key in unresolved[:10]
        )
        raise ValueError(
            f"{len(unresolved)} model EDs have no Colm mapped-soil record. "
            "08C does not invent county/national fallback soil; investigate the ED bridge. "
            f"Examples: {examples}"
        )

    resolved = pd.DataFrame(resolved_rows)
    if len(resolved) != len(model) or resolved["_MODEL_KEY"].duplicated().any():
        raise AssertionError("08C resolution did not create exactly one mapped profile per model ED")

    out["_08C_KEY"] = out["CSOED"].map(canonical_csoed)
    keep = [c for c in resolved.columns if c not in {"CSOED", "_KEY"}]
    out = out.merge(
        resolved[keep].rename(columns={"_MODEL_KEY": "_08C_KEY"}),
        on="_08C_KEY",
        how="left",
        validate="many_to_one",
    )
    physical = (
        out[list(PHYSICAL_SHARE_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(float)
    )
    sg = (
        out[list(MAP_SG_SHARE_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(float)
    )
    if not np.allclose(physical.sum(axis=1), 1.0, atol=1e-8):
        raise AssertionError("08C physical shares do not close to one")
    if not np.allclose(sg.sum(axis=1), 1.0, atol=1e-8):
        raise AssertionError("08C mapped SG shares do not close to one")
    out["SOIL_CONTEXT_08C_PRECOMPUTED"] = True
    out["SOIL_CONTEXT_08C_ROLE"] = "INDEPENDENT_PHYSICAL_CONTEXT_NOT_SC1_RELEASE_DRIVER"
    return out.drop(columns="_08C_KEY")
