"""ED-level agricultural soil profiles derived from holding-linked soil records.

The production soil layer deliberately collapses holding-level source records to
Electoral Division (ED) shares before they enter GOBLIN-Spatial. Individual
holdings are not modelling units. The source data are used only to estimate the
composition of agricultural area within each ED.

Agricultural use-range classes are mapped to the three soil groups used by the
GOBLIN grassland-production model:

- classes 1-2 -> GOBLIN soil group 1
- classes 3-4 -> GOBLIN soil group 2
- classes 5-6 -> GOBLIN soil group 3

Source UAA is used only as an aggregation weight. The authoritative hectares in
GOBLIN-Spatial remain ``ALL_GRASSLAND`` from the validated ED baseline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


SOIL_CLASS_TO_GOBLIN_GROUP = {
    1: 1,
    2: 1,
    3: 2,
    4: 2,
    5: 3,
    6: 3,
}
FOREST_YIELD_CLASSES = (14, 18, 20, 24)


def _canonical_csoed(values: pd.Series) -> pd.Series:
    """Return nullable integer CSO ED identifiers."""

    return pd.to_numeric(values, errors="coerce").astype("Int64")


def _weighted_share_table(
    frame: pd.DataFrame,
    category: str,
    categories: tuple[int, ...],
    *,
    prefix: str,
) -> pd.DataFrame:
    """Return one UAA-weighted share column per category and ED."""

    grouped = (
        frame.groupby(["CSOED", category], observed=True)["SOURCE_UAA_HA"]
        .sum()
        .unstack(fill_value=0.0)
    )
    grouped = grouped.reindex(columns=list(categories), fill_value=0.0)
    totals = grouped.sum(axis=1)
    shares = grouped.div(totals.replace(0.0, np.nan), axis=0)
    shares.columns = [
        f"{prefix}{int(value)}_SHARE" for value in shares.columns
    ]
    return shares


def build_ed_agricultural_soil_profile(
    source: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate holding-linked soil records to one production profile per ED.

    Parameters
    ----------
    source:
        Cathal/NFS-derived source table or a path to that CSV. Required source
        fields are ``cso_ed``, ``fsizuaa`` and ``soil_code_nfs``. ``yc``,
        ``ifs_soil`` and ``herd_no`` are used when available for downstream
        forestry context and diagnostics.

    Returns
    -------
    pandas.DataFrame
        One row per ED. The three ``GOBLIN_SOIL_G*_SHARE`` fields sum to one.
        Source UAA and holding counts are diagnostics only; they never replace
        validated ED land totals.
    """

    if isinstance(source, pd.DataFrame):
        raw = source.copy()
    else:
        raw = pd.read_csv(Path(source), low_memory=False)

    required = {"cso_ed", "fsizuaa", "soil_code_nfs"}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"agricultural soil source missing columns: {missing}")

    work = pd.DataFrame(index=raw.index)
    work["CSOED"] = _canonical_csoed(raw["cso_ed"])
    work["SOURCE_UAA_HA"] = pd.to_numeric(raw["fsizuaa"], errors="coerce")
    work["SOIL_USE_CLASS"] = pd.to_numeric(
        raw["soil_code_nfs"], errors="coerce"
    ).astype("Int64")
    work["GOBLIN_SOIL_GROUP"] = work["SOIL_USE_CLASS"].map(
        SOIL_CLASS_TO_GOBLIN_GROUP
    ).astype("Int64")

    if "herd_no" in raw.columns:
        work["HERD_NO"] = raw["herd_no"]
    else:
        work["HERD_NO"] = pd.NA

    if "yc" in raw.columns:
        work["FOREST_YC"] = pd.to_numeric(raw["yc"], errors="coerce")
    else:
        work["FOREST_YC"] = np.nan

    if "ifs_soil" in raw.columns:
        work["IFS_SOIL"] = raw["ifs_soil"].astype("string")
    else:
        work["IFS_SOIL"] = pd.Series(
            pd.NA, index=work.index, dtype="string"
        )

    valid = work[
        work["CSOED"].notna()
        & work["SOURCE_UAA_HA"].gt(0)
        & work["GOBLIN_SOIL_GROUP"].notna()
    ].copy()
    if valid.empty:
        raise ValueError(
            "agricultural soil source has no usable ED/UAA/soil rows"
        )

    profile = (
        valid.groupby("CSOED", sort=True)
        .agg(
            SOIL_SOURCE_HOLDINGS=("HERD_NO", "count"),
            SOIL_SOURCE_UAA_HA=("SOURCE_UAA_HA", "sum"),
        )
        .sort_index()
    )

    class_shares = _weighted_share_table(
        valid,
        "SOIL_USE_CLASS",
        (1, 2, 3, 4, 5, 6),
        prefix="SOIL_USE_CLASS_",
    )
    group_shares = _weighted_share_table(
        valid,
        "GOBLIN_SOIL_GROUP",
        (1, 2, 3),
        prefix="GOBLIN_SOIL_G",
    )
    profile = profile.join(class_shares, how="left").join(
        group_shares, how="left"
    )

    yc_valid = valid[valid["FOREST_YC"].isin(FOREST_YIELD_CLASSES)].copy()
    if not yc_valid.empty:
        yc_shares = _weighted_share_table(
            yc_valid,
            "FOREST_YC",
            FOREST_YIELD_CLASSES,
            prefix="FOREST_YC_",
        )
        profile = profile.join(yc_shares, how="left")
        weighted_yc = (
            yc_valid.assign(
                _YC_WEIGHT=(
                    yc_valid["SOURCE_UAA_HA"] * yc_valid["FOREST_YC"]
                )
            )
            .groupby("CSOED")
            .agg(
                _YC_WEIGHT=("_YC_WEIGHT", "sum"),
                FOREST_YC_SOURCE_UAA_HA=("SOURCE_UAA_HA", "sum"),
            )
        )
        weighted_yc["FOREST_YC_WEIGHTED_MEAN"] = (
            weighted_yc["_YC_WEIGHT"]
            / weighted_yc["FOREST_YC_SOURCE_UAA_HA"]
        )
        profile = profile.join(
            weighted_yc[
                ["FOREST_YC_SOURCE_UAA_HA", "FOREST_YC_WEIGHTED_MEAN"]
            ],
            how="left",
        )

    ifs_valid = valid[valid["IFS_SOIL"].notna()].copy()
    if not ifs_valid.empty:
        by_ifs = (
            ifs_valid.groupby(
                ["CSOED", "IFS_SOIL"], observed=True
            )["SOURCE_UAA_HA"]
            .sum()
            .reset_index()
        )
        by_ifs["_IFS_TOTAL"] = by_ifs.groupby("CSOED")[
            "SOURCE_UAA_HA"
        ].transform("sum")
        by_ifs["_IFS_SHARE"] = (
            by_ifs["SOURCE_UAA_HA"] / by_ifs["_IFS_TOTAL"]
        )
        dominant = (
            by_ifs.sort_values(
                ["CSOED", "SOURCE_UAA_HA", "IFS_SOIL"],
                ascending=[True, False, True],
                kind="stable",
            )
            .drop_duplicates("CSOED")
            .set_index("CSOED")
        )
        nclasses = by_ifs.groupby("CSOED")["IFS_SOIL"].nunique()
        profile["IFS_SOIL_DOMINANT"] = dominant["IFS_SOIL"]
        profile["IFS_SOIL_DOMINANT_SHARE"] = dominant["_IFS_SHARE"]
        profile["IFS_SOIL_N_CLASSES"] = nclasses.astype("Int64")

    share_columns = [
        f"GOBLIN_SOIL_G{group}_SHARE" for group in (1, 2, 3)
    ]
    profile[share_columns] = profile[share_columns].fillna(0.0)
    share_sum = profile[share_columns].sum(axis=1)
    if not np.allclose(share_sum.to_numpy(), 1.0, atol=1e-10):
        raise AssertionError(
            "GOBLIN soil-group shares do not close to one within ED"
        )

    for column in [
        *(f"FOREST_YC_{yc}_SHARE" for yc in FOREST_YIELD_CLASSES),
        "FOREST_YC_SOURCE_UAA_HA",
        "FOREST_YC_WEIGHTED_MEAN",
        "IFS_SOIL_DOMINANT_SHARE",
    ]:
        if column not in profile.columns:
            profile[column] = np.nan

    return profile.reset_index()


def read_ed_agricultural_soil_profile(path: str | Path) -> pd.DataFrame:
    """Read and validate a compact ED soil-profile control table."""

    profile = pd.read_csv(Path(path), low_memory=False)
    required = {
        "CSOED",
        "SOIL_SOURCE_HOLDINGS",
        "SOIL_SOURCE_UAA_HA",
        "GOBLIN_SOIL_G1_SHARE",
        "GOBLIN_SOIL_G2_SHARE",
        "GOBLIN_SOIL_G3_SHARE",
    }
    missing = sorted(required.difference(profile.columns))
    if missing:
        raise ValueError(f"ED soil profile missing columns: {missing}")
    profile["CSOED"] = _canonical_csoed(profile["CSOED"])
    if profile["CSOED"].isna().any() or profile["CSOED"].duplicated().any():
        raise ValueError("ED soil profile must contain one valid row per CSOED")
    shares = profile[
        [f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3)]
    ].apply(pd.to_numeric, errors="coerce")
    if shares.isna().any().any() or not np.allclose(
        shares.sum(axis=1).to_numpy(), 1.0, atol=1e-8
    ):
        raise ValueError("ED soil profile G1/G2/G3 shares must close to one")
    profile[
        [f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3)]
    ] = shares
    return profile


def add_ed_agricultural_soil(
    master: pd.DataFrame,
    profile: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Attach static ED soil shares and soil-scaled grass hectares to a panel.

    The compact ED profile supplies *shares*. ``ALL_GRASSLAND`` remains the
    authoritative hectare total and is partitioned by those shares. If a
    baseline ED is absent from the source profile, shares fall back to a
    source-UAA-weighted county profile and then to the national profile. The
    chosen level is recorded in ``SOIL_PROFILE_SOURCE``.
    """

    required_master = {"CSOED", "County", "ALL_GRASSLAND"}
    missing = sorted(required_master.difference(master.columns))
    if missing:
        raise ValueError(f"master missing soil attachment columns: {missing}")

    if isinstance(profile, pd.DataFrame):
        soil = profile.copy()
        soil["CSOED"] = _canonical_csoed(soil["CSOED"])
    else:
        soil = read_ed_agricultural_soil_profile(profile)

    if soil["CSOED"].duplicated().any():
        raise ValueError("ED soil profile contains duplicate CSOED rows")

    result = master.copy()
    result["CSOED"] = _canonical_csoed(result["CSOED"])

    ed_county = result[["CSOED", "County"]].drop_duplicates()
    if ed_county["CSOED"].duplicated().any():
        raise ValueError("one CSOED is associated with multiple counties")

    shares = [f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3)]
    keep = [
        column
        for column in soil.columns
        if column == "CSOED"
        or column.startswith("SOIL_")
        or column.startswith("GOBLIN_SOIL_")
        or column.startswith("FOREST_YC_")
        or column.startswith("IFS_SOIL_")
    ]
    soil = soil[keep].merge(
        ed_county, on="CSOED", how="left", validate="one_to_one"
    )

    weight = pd.to_numeric(
        soil["SOIL_SOURCE_UAA_HA"], errors="coerce"
    ).fillna(0.0)
    county_rows: list[dict[str, object]] = []
    for county, group in soil.dropna(subset=["County"]).groupby(
        "County", sort=False
    ):
        group_weight = pd.to_numeric(
            group["SOIL_SOURCE_UAA_HA"], errors="coerce"
        ).fillna(0.0)
        if group_weight.sum() <= 0:
            continue
        row: dict[str, object] = {"County": county}
        for share in shares:
            row[share] = np.average(group[share], weights=group_weight)
        if "FOREST_YC_WEIGHTED_MEAN" in group.columns:
            values = pd.to_numeric(
                group["FOREST_YC_WEIGHTED_MEAN"], errors="coerce"
            )
            mask = values.notna() & group_weight.gt(0)
            row["FOREST_YC_WEIGHTED_MEAN"] = (
                np.average(values[mask], weights=group_weight[mask])
                if mask.any()
                else np.nan
            )
        county_rows.append(row)
    county_profile = (
        pd.DataFrame(county_rows).set_index("County")
        if county_rows
        else pd.DataFrame()
    )

    national_weight = weight.where(weight.gt(0), 0.0)
    national_shares = {
        share: float(np.average(soil[share], weights=national_weight))
        for share in shares
    }
    if "FOREST_YC_WEIGHTED_MEAN" in soil.columns:
        forest_values = pd.to_numeric(
            soil["FOREST_YC_WEIGHTED_MEAN"], errors="coerce"
        )
        mask = forest_values.notna() & national_weight.gt(0)
        national_forest_yc = (
            float(
                np.average(
                    forest_values[mask], weights=national_weight[mask]
                )
            )
            if mask.any()
            else np.nan
        )
    else:
        national_forest_yc = np.nan

    result = result.merge(
        soil.drop(columns="County"),
        on="CSOED",
        how="left",
        validate="many_to_one",
    )
    source = pd.Series("ED", index=result.index, dtype="string")
    missing_ed = result[shares].isna().any(axis=1)

    if missing_ed.any() and not county_profile.empty:
        for share in shares:
            result.loc[missing_ed, share] = result.loc[
                missing_ed, "County"
            ].map(county_profile[share])
        if (
            "FOREST_YC_WEIGHTED_MEAN" in result.columns
            and "FOREST_YC_WEIGHTED_MEAN" in county_profile.columns
        ):
            result.loc[
                missing_ed, "FOREST_YC_WEIGHTED_MEAN"
            ] = result.loc[missing_ed, "County"].map(
                county_profile["FOREST_YC_WEIGHTED_MEAN"]
            )
        county_filled = missing_ed & result[shares].notna().all(axis=1)
        source.loc[county_filled] = "COUNTY_FALLBACK"

    missing_after_county = result[shares].isna().any(axis=1)
    if missing_after_county.any():
        for share, value in national_shares.items():
            result.loc[missing_after_county, share] = value
        if "FOREST_YC_WEIGHTED_MEAN" in result.columns:
            result.loc[
                missing_after_county, "FOREST_YC_WEIGHTED_MEAN"
            ] = national_forest_yc
        source.loc[missing_after_county] = "NATIONAL_FALLBACK"

    result["SOIL_PROFILE_SOURCE"] = source
    if not np.allclose(
        result[shares].sum(axis=1).to_numpy(), 1.0, atol=1e-8
    ):
        raise AssertionError(
            "attached GOBLIN soil-group shares do not close to one"
        )

    grassland = pd.to_numeric(result["ALL_GRASSLAND"], errors="coerce")
    for group, share in enumerate(shares, start=1):
        result[f"GOBLIN_SOIL_G{group}_GRASSLAND_HA"] = (
            grassland * result[share]
        )

    grass_columns = [
        f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in (1, 2, 3)
    ]
    expected = grassland.fillna(0.0).to_numpy()
    actual = result[grass_columns].fillna(0.0).sum(axis=1).to_numpy()
    if not np.allclose(actual, expected, atol=1e-7):
        raise AssertionError(
            "soil-group grassland hectares do not close to ALL_GRASSLAND"
        )

    return result
