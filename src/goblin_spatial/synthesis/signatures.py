"""Multiscale livestock signatures for the frozen signature years (2020, 2025).

Four products, all derived from the finished baseline without changing it:

livestock_signature
    One row per geography unit and signature year (ED, county, WFD catchment,
    Colm catchment, national): the full 21-cohort cattle state, adult and
    follower totals, and the signature ratios. Aggregate rows sum the additive
    populations first and then derive the ratios; ED ratios are never averaged.

livestock_signature_long
    The same ratios in tidy form, each with the numerator and denominator it is
    computed from, so a user can re-aggregate correctly.

parent_follower_relationship_ed
    One row per ED, follower cohort and signature year: parent population,
    parent and follower head, follower-per-parent ratio and relationship class
    (LOCAL_ED, COUNTY_RECEIVER, NATIONAL_ORPHAN, NONE).

parent_follower_relationship_shares
    For every geography unit: follower head by parental-origin group split by
    ED relationship class. The class is an ED property; aggregates report only
    how much of their follower stock sits in each class.

WFD and Colm catchments use the frozen ED-catchment area weights.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import build_signatures
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import SpatialConfig
from goblin_spatial.synthesis.historical import add_signature_metrics

SIGNATURE_YEARS = (2020, 2025)
RELATIONSHIP_CLASSES = ("LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN")
ORIGIN_GROUPS = {"DxD": "DAIRY", "DxB": "DAIRY", "BxB": "SUCKLER", "bulls": "ADULT_COWS"}

STATE_COLUMNS = (
    "DAIRY_COW",
    "OTHER_COW",
    *FINAL_21_COHORTS,
    "ADULT_COWS",
    "DXD_FOLLOWERS",
    "DXB_FOLLOWERS",
    "BXB_FOLLOWERS",
    "FOLLOWER_TOTAL",
    "TOTAL_CATTLE",
    "TOTAL_SHEEP",
    "UPLAND_SHEEP",
    "AREA_FARMED",
    "ALL_GRASSLAND",
    "TOTAL_CEREALS",
    "SO_COVERED_TOTAL_2020_EUR",
)

# signature -> (numerator, denominator, scale)
SIGNATURE_DEFINITIONS = {
    "DAIRY_SHARE_ADULT_PCT": ("dairy_cows", "ADULT_COWS", 100.0),
    "DXD_SHARE_FOLLOWERS_PCT": ("DXD_FOLLOWERS", "FOLLOWER_TOTAL", 100.0),
    "DXB_SHARE_FOLLOWERS_PCT": ("DXB_FOLLOWERS", "FOLLOWER_TOTAL", 100.0),
    "BXB_SHARE_FOLLOWERS_PCT": ("BXB_FOLLOWERS", "FOLLOWER_TOTAL", 100.0),
    "FOLLOWER_TO_ADULT_RATIO": ("FOLLOWER_TOTAL", "ADULT_COWS", 1.0),
    "CATTLE_PER_FARMED_HA": ("TOTAL_CATTLE", "AREA_FARMED", 1.0),
    "SHEEP_PER_FARMED_HA": ("TOTAL_SHEEP", "AREA_FARMED", 1.0),
    "GRASSLAND_SHARE_FARMED_PCT": ("ALL_GRASSLAND", "AREA_FARMED", 100.0),
    "CEREAL_SHARE_FARMED_PCT": ("TOTAL_CEREALS", "AREA_FARMED", 100.0),
    "SO_PER_FARMED_HA": ("SO_COVERED_TOTAL_2020_EUR", "AREA_FARMED", 1.0),
    "UPLAND_SHARE_SHEEP_PCT": ("UPLAND_SHEEP", "TOTAL_SHEEP", 100.0),
}

GEOGRAPHY_TYPES = ("ED", "COUNTY", "WFD_CATCHMENT", "COLM_CATCHMENT", "NATIONAL")


def _frame(
    table: pd.DataFrame, geography: str, geo_id: str | None, geo_name: str | None, county: str | None
) -> pd.DataFrame:
    work = add_signature_metrics(table.loc[table["YEAR"].isin(SIGNATURE_YEARS)].copy())
    out = pd.DataFrame(
        {
            "GEOGRAPHY_TYPE": geography,
            "GEOGRAPHY_ID": work[geo_id].astype(str) if geo_id else "IE",
            "GEOGRAPHY_NAME": work[geo_name].astype(str) if geo_name else "Ireland",
            "COUNTY": work[county].astype(str) if county else "",
            "YEAR": work["YEAR"].astype(int),
        }
    )
    missing = [c for c in (*STATE_COLUMNS, *SIGNATURE_DEFINITIONS) if c not in work.columns]
    if missing:
        raise ValueError(f"{geography} table lacks signature fields: {missing}")
    for column in (*STATE_COLUMNS, *SIGNATURE_DEFINITIONS):
        out[column] = work[column].to_numpy()
    return out


def build_livestock_signature(
    ed: pd.DataFrame,
    county: pd.DataFrame,
    wfd: pd.DataFrame,
    colm: pd.DataFrame,
    national: pd.DataFrame,
) -> pd.DataFrame:
    parts = [
        _frame(ed, "ED", "CSOED", "EDNAME" if "EDNAME" in ed.columns else "ED", "County"),
        _frame(county, "COUNTY", "County", "County", "County"),
        _frame(wfd, "WFD_CATCHMENT", "WFD_CATCHMENT_ID", "WFD_CATCHMENT", None),
        _frame(colm, "COLM_CATCHMENT", "COLM_CATCHMENT", "COLM_CATCHMENT", None),
        _frame(national, "NATIONAL", None, None, None),
    ]
    signature = pd.concat(parts, ignore_index=True)

    # Aggregates must equal ED sums (catchments within rounding of the area weights).
    ed_rows = signature.loc[signature["GEOGRAPHY_TYPE"] == "ED"]
    for geography in GEOGRAPHY_TYPES[1:]:
        rows = signature.loc[signature["GEOGRAPHY_TYPE"] == geography]
        for year in SIGNATURE_YEARS:
            ed_total = ed_rows.loc[ed_rows["YEAR"] == year, "TOTAL_CATTLE"].sum()
            total = rows.loc[rows["YEAR"] == year, "TOTAL_CATTLE"].sum()
            if abs(total - ed_total) > 1e-6 * max(ed_total, 1):
                raise AssertionError(f"{geography} {year}: cattle {total} differ from ED sum {ed_total}")
    return signature


def build_signature_long(signature: pd.DataFrame) -> pd.DataFrame:
    keys = ["GEOGRAPHY_TYPE", "GEOGRAPHY_ID", "GEOGRAPHY_NAME", "YEAR"]
    frames = []
    for name, (numerator, denominator, scale) in SIGNATURE_DEFINITIONS.items():
        part = signature[keys].copy()
        part["SIGNATURE"] = name
        part["NUMERATOR_COLUMN"] = numerator
        part["DENOMINATOR_COLUMN"] = denominator
        part["NUMERATOR"] = signature[numerator].astype(float)
        part["DENOMINATOR"] = signature[denominator].astype(float)
        part["SCALE"] = scale
        part["VALUE"] = signature[name].astype(float)
        frames.append(part)
    long = pd.concat(frames, ignore_index=True)
    defined = long["DENOMINATOR"] > 0
    recomputed = long.loc[defined, "NUMERATOR"] / long.loc[defined, "DENOMINATOR"] * long.loc[defined, "SCALE"]
    if not np.allclose(recomputed, long.loc[defined, "VALUE"], rtol=1e-9, atol=1e-9, equal_nan=True):
        raise AssertionError("signature values do not equal numerator / denominator x scale")
    if long.loc[~defined, "VALUE"].notna().any():
        raise AssertionError("signatures with a zero denominator must be undefined, not zero")
    return long


def _weighted_quantile(values: pd.Series, weights: pd.Series, q: float) -> float:
    """Weighted quantile used to describe ED heterogeneity inside catchments."""

    value = pd.to_numeric(values, errors="coerce").astype(float)
    weight = pd.to_numeric(weights, errors="coerce").astype(float)
    keep = value.notna() & weight.notna() & (weight > 0)
    if not keep.any():
        return np.nan
    value = value.loc[keep].to_numpy()
    weight = weight.loc[keep].to_numpy()
    order = np.argsort(value)
    value = value[order]
    weight = weight[order]
    cumulative = np.cumsum(weight)
    return float(np.interp(q * cumulative[-1], cumulative, value))


def build_wfd_signature_spread(
    signature_long: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    """Pair each WFD catchment signature with the weighted ED distribution inside it.

    The catchment value is the accounting representation: additive numerators
    and denominators are transferred with the frozen ED-catchment weights and
    the ratio is then recomputed. The ED quantiles are the structural
    representation: each intersecting ED retains its own signature and is
    weighted by the share of the signature denominator assigned to the
    catchment. No majority-inside rule is used in the calculation.
    """

    required = {"CSOED", "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "ED_CATCHMENT_WEIGHT"}
    missing = sorted(required - set(crosswalk.columns))
    if missing:
        raise ValueError(f"catchment crosswalk lacks fields: {missing}")

    ed = signature_long.loc[signature_long["GEOGRAPHY_TYPE"] == "ED"].copy()
    wfd = signature_long.loc[signature_long["GEOGRAPHY_TYPE"] == "WFD_CATCHMENT"].copy()
    ed["CSOED"] = ed["GEOGRAPHY_ID"].astype(str)
    xw = crosswalk[list(required)].copy()
    xw["CSOED"] = xw["CSOED"].astype(str)
    xw["WFD_CATCHMENT_ID"] = xw["WFD_CATCHMENT_ID"].astype(str)

    joined = ed.merge(xw, on="CSOED", how="inner", validate="many_to_many")
    joined["ED_CATCHMENT_WEIGHT"] = pd.to_numeric(
        joined["ED_CATCHMENT_WEIGHT"], errors="raise"
    ).astype(float)
    joined["DISTRIBUTION_WEIGHT"] = (
        pd.to_numeric(joined["DENOMINATOR"], errors="coerce").astype(float)
        * joined["ED_CATCHMENT_WEIGHT"]
    )

    rows: list[dict[str, object]] = []
    group_cols = ["YEAR", "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "SIGNATURE"]
    for keys, group in joined.groupby(group_cols, sort=True):
        year, catchment_id, catchment_name, metric = keys
        valid = group["VALUE"].notna() & (group["DISTRIBUTION_WEIGHT"] > 0)
        rows.append(
            {
                "YEAR": int(year),
                "WFD_CATCHMENT_ID": str(catchment_id),
                "WFD_CATCHMENT": str(catchment_name),
                "SIGNATURE": metric,
                "ED_WEIGHTED_P10": _weighted_quantile(
                    group.loc[valid, "VALUE"], group.loc[valid, "DISTRIBUTION_WEIGHT"], 0.10
                ),
                "ED_WEIGHTED_P50": _weighted_quantile(
                    group.loc[valid, "VALUE"], group.loc[valid, "DISTRIBUTION_WEIGHT"], 0.50
                ),
                "ED_WEIGHTED_P90": _weighted_quantile(
                    group.loc[valid, "VALUE"], group.loc[valid, "DISTRIBUTION_WEIGHT"], 0.90
                ),
                "INTERSECTING_EDS": int(group.loc[valid, "CSOED"].nunique()),
                "DISTRIBUTION_DENOMINATOR": float(
                    group.loc[valid, "DISTRIBUTION_WEIGHT"].sum()
                ),
                "DENOMINATOR_COLUMN": (
                    str(group["DENOMINATOR_COLUMN"].iloc[0]) if len(group) else ""
                ),
            }
        )
    spread = pd.DataFrame(rows)
    if spread.empty:
        return spread
    spread["ED_WEIGHTED_P90_P10"] = (
        spread["ED_WEIGHTED_P90"] - spread["ED_WEIGHTED_P10"]
    )

    catchment = wfd[
        ["YEAR", "GEOGRAPHY_ID", "GEOGRAPHY_NAME", "SIGNATURE", "VALUE"]
    ].rename(
        columns={
            "GEOGRAPHY_ID": "WFD_CATCHMENT_ID",
            "GEOGRAPHY_NAME": "WFD_CATCHMENT",
            "VALUE": "CATCHMENT_VALUE",
        }
    )
    catchment["WFD_CATCHMENT_ID"] = catchment["WFD_CATCHMENT_ID"].astype(str)
    out = catchment.merge(
        spread,
        on=["YEAR", "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "SIGNATURE"],
        how="left",
        validate="one_to_one",
    )
    return out.sort_values(["YEAR", "SIGNATURE", "WFD_CATCHMENT_ID"]).reset_index(drop=True)


def build_relationship_ed(master: pd.DataFrame, cfg: SpatialConfig) -> pd.DataFrame:
    frames = [build_signatures(master, cfg, year=year) for year in SIGNATURE_YEARS]
    return pd.concat(frames, ignore_index=True)


def _origin_group(cohort: str) -> str:
    return "bulls" if cohort == "bulls" else cohort[:3]


def build_relationship_shares(
    relationship: pd.DataFrame, crosswalk: pd.DataFrame
) -> pd.DataFrame:
    work = relationship.copy()
    work["ORIGIN_GROUP"] = work["COHORT"].map(_origin_group)
    work["PARENT"] = work["ORIGIN_GROUP"].map(ORIGIN_GROUPS)
    work["CSOED"] = work["CSOED"].astype(str)

    def summarise(frame: pd.DataFrame, geography: str, key: str | None, weight: str | None) -> pd.DataFrame:
        head = frame["BASE_COHORT_HEAD"].astype(float) * (frame[weight] if weight else 1.0)
        frame = frame.assign(_HEAD=head, GEOGRAPHY_ID=frame[key].astype(str) if key else "IE")
        table = (
            frame.groupby(["GEOGRAPHY_ID", "YEAR", "ORIGIN_GROUP", "PARENT", "COHORT_SPATIAL_ROLE"])["_HEAD"]
            .sum()
            .unstack("COHORT_SPATIAL_ROLE", fill_value=0.0)
        )
        for role in RELATIONSHIP_CLASSES:
            if role not in table.columns:
                table[role] = 0.0
        table = table[list(RELATIONSHIP_CLASSES)].rename(columns=lambda r: f"{r}_HEAD")
        table["FOLLOWER_HEAD"] = table.sum(axis=1)
        for role in RELATIONSHIP_CLASSES:
            table[f"{role}_PCT"] = np.where(
                table["FOLLOWER_HEAD"] > 0, 100.0 * table[f"{role}_HEAD"] / table["FOLLOWER_HEAD"], np.nan
            )
        table = table.reset_index()
        table.insert(0, "GEOGRAPHY_TYPE", geography)
        return table

    weights = crosswalk[["CSOED", "WFD_CATCHMENT_ID", "COLM_CATCHMENT", "ED_CATCHMENT_WEIGHT"]].copy()
    weights["CSOED"] = weights["CSOED"].astype(str)
    weighted = work.merge(weights, on="CSOED", how="left", validate="many_to_many")
    if weighted["ED_CATCHMENT_WEIGHT"].isna().any():
        raise AssertionError("EDs without catchment weights in the relationship table")

    shares = pd.concat(
        [
            summarise(work, "ED", "CSOED", None),
            summarise(work, "COUNTY", "County", None),
            summarise(weighted, "WFD_CATCHMENT", "WFD_CATCHMENT_ID", "ED_CATCHMENT_WEIGHT"),
            summarise(weighted, "COLM_CATCHMENT", "COLM_CATCHMENT", "ED_CATCHMENT_WEIGHT"),
            summarise(work, "NATIONAL", None, None),
        ],
        ignore_index=True,
    )
    national = shares.loc[shares["GEOGRAPHY_TYPE"] == "NATIONAL"].set_index(["YEAR", "ORIGIN_GROUP"])["FOLLOWER_HEAD"]
    for geography in GEOGRAPHY_TYPES[:-1]:
        total = shares.loc[shares["GEOGRAPHY_TYPE"] == geography].groupby(["YEAR", "ORIGIN_GROUP"])["FOLLOWER_HEAD"].sum()
        if not np.allclose(total.sort_index().to_numpy(), national.sort_index().to_numpy(), rtol=1e-8):
            raise AssertionError(f"{geography} relationship shares do not sum to the national follower head")
    return shares


def build_relationship_by_year(master: pd.DataFrame, cfg: SpatialConfig) -> pd.DataFrame:
    """National follower head by relationship class for every baseline year.

    Diagnostic: shows how the ED relationship classes depend on the year's
    parent geography. COUNTY_RECEIVER is a support classification only: the
    follower cohort is present in the ED, the corresponding parent cows are
    absent locally, and parent cows are present elsewhere in the county. Under
    the corrected reconstruction, published 2020 adult-cow support is retained
    after 2020, so this class can persist in reconstructed years.
    """

    rows = []
    for year in sorted(int(y) for y in master["YEAR"].unique()):
        rel = build_signatures(master, cfg, year=year)
        rel["ORIGIN_GROUP"] = rel["COHORT"].map(_origin_group)
        table = rel.groupby(["ORIGIN_GROUP", "COHORT_SPATIAL_ROLE"])["BASE_COHORT_HEAD"].sum().unstack(fill_value=0)
        for group, values in table.iterrows():
            total = float(values.sum())
            row = {"YEAR": year, "ORIGIN_GROUP": group, "PARENT": ORIGIN_GROUPS[group], "FOLLOWER_HEAD": total}
            for role in RELATIONSHIP_CLASSES:
                head = float(values.get(role, 0.0))
                row[f"{role}_HEAD"] = head
                row[f"{role}_PCT"] = 100.0 * head / total if total > 0 else np.nan
            rows.append(row)
    return pd.DataFrame(rows)
