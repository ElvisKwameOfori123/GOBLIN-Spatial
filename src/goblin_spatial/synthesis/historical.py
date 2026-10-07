"""Historical-results synthesis for the validated GOBLIN-Spatial baseline.

This module reads frozen historical outputs and derives manuscript-facing
summaries. It never changes livestock, land, Standard Output, or spatial
allocation. The authoritative scientific state remains the ED x year baseline.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


DXD = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
PRE_ADULT_FOLLOWERS = (*DXD, *DXB, *BXB)
UNDER1_FOLLOWERS = tuple(c for c in PRE_ADULT_FOLLOWERS if "_calves_" in c)
UPLAND_SHEEP = tuple(c for c in GOBLIN_SHEEP_10 if c.startswith("Upland "))
SO_COMPONENTS = (
    "SO_DAIRY_COWS_2020_EUR",
    "SO_SUCKLER_COWS_2020_EUR",
    "SO_BULLS_2020_EUR",
    "SO_FOLLOWERS_2020_EUR",
    "SO_SHEEP_2020_EUR",
    "SO_CEREALS_2020_EUR",
    "SO_OTHER_CROPS_2020_EUR",
)
SIGNATURE_METRICS = (
    "DAIRY_SHARE_ADULT_PCT",
    "DXD_SHARE_FOLLOWERS_PCT",
    "DXB_SHARE_FOLLOWERS_PCT",
    "BXB_SHARE_FOLLOWERS_PCT",
    "UNDER1_SHARE_FOLLOWERS_PCT",
    "FOLLOWER_TO_ADULT_RATIO",
    "CATTLE_PER_FARMED_HA",
    "SHEEP_PER_FARMED_HA",
    "GRASSLAND_SHARE_FARMED_PCT",
    "CEREAL_SHARE_FARMED_PCT",
    "SO_PER_FARMED_HA",
    "UPLAND_SHARE_SHEEP_PCT",
)


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"missing historical-results column: {column}")
    return pd.to_numeric(frame[column], errors="raise").astype(float)


def _safe_ratio(num: pd.Series, den: pd.Series, scale: float = 1.0) -> pd.Series:
    n = pd.to_numeric(num, errors="coerce").astype(float)
    d = pd.to_numeric(den, errors="coerce").astype(float)
    out = pd.Series(np.nan, index=n.index, dtype=float)
    ok = d > 0
    out.loc[ok] = scale * n.loc[ok] / d.loc[ok]
    return out


def add_signature_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Add transparent livestock-system signature metrics to additive states."""

    out = frame.copy()
    out["ADULT_COWS"] = _num(out, "dairy_cows") + _num(out, "suckler_cows")
    out["DXD_FOLLOWERS"] = out[list(DXD)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    out["DXB_FOLLOWERS"] = out[list(DXB)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    out["BXB_FOLLOWERS"] = out[list(BXB)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    out["FOLLOWER_TOTAL"] = (
        out["DXD_FOLLOWERS"] + out["DXB_FOLLOWERS"] + out["BXB_FOLLOWERS"]
    )
    out["UNDER1_FOLLOWERS"] = out[list(UNDER1_FOLLOWERS)].apply(
        pd.to_numeric, errors="raise"
    ).sum(axis=1)
    out["UPLAND_SHEEP"] = out[list(UPLAND_SHEEP)].apply(
        pd.to_numeric, errors="raise"
    ).sum(axis=1)

    out["DAIRY_SHARE_ADULT_PCT"] = _safe_ratio(
        _num(out, "dairy_cows"), out["ADULT_COWS"], 100.0
    )
    out["DXD_SHARE_FOLLOWERS_PCT"] = _safe_ratio(
        out["DXD_FOLLOWERS"], out["FOLLOWER_TOTAL"], 100.0
    )
    out["DXB_SHARE_FOLLOWERS_PCT"] = _safe_ratio(
        out["DXB_FOLLOWERS"], out["FOLLOWER_TOTAL"], 100.0
    )
    out["BXB_SHARE_FOLLOWERS_PCT"] = _safe_ratio(
        out["BXB_FOLLOWERS"], out["FOLLOWER_TOTAL"], 100.0
    )
    out["UNDER1_SHARE_FOLLOWERS_PCT"] = _safe_ratio(
        out["UNDER1_FOLLOWERS"], out["FOLLOWER_TOTAL"], 100.0
    )
    out["FOLLOWER_TO_ADULT_RATIO"] = _safe_ratio(
        out["FOLLOWER_TOTAL"], out["ADULT_COWS"]
    )
    out["CATTLE_PER_FARMED_HA"] = _safe_ratio(
        _num(out, "TOTAL_CATTLE"), _num(out, "AREA_FARMED")
    )
    out["SHEEP_PER_FARMED_HA"] = _safe_ratio(
        _num(out, "TOTAL_SHEEP"), _num(out, "AREA_FARMED")
    )
    out["GRASSLAND_SHARE_FARMED_PCT"] = _safe_ratio(
        _num(out, "ALL_GRASSLAND"), _num(out, "AREA_FARMED"), 100.0
    )
    out["CEREAL_SHARE_FARMED_PCT"] = _safe_ratio(
        _num(out, "TOTAL_CEREALS"), _num(out, "AREA_FARMED"), 100.0
    )
    out["SO_PER_FARMED_HA"] = _safe_ratio(
        _num(out, "SO_COVERED_TOTAL_2020_EUR"), _num(out, "AREA_FARMED")
    )
    out["UPLAND_SHARE_SHEEP_PCT"] = _safe_ratio(
        out["UPLAND_SHEEP"], _num(out, "TOTAL_SHEEP"), 100.0
    )
    return out


def _additive_columns(frame: pd.DataFrame) -> list[str]:
    candidates = [
        "DAIRY_COW", "OTHER_COW", "BULLS", "TOTAL_CATTLE", "TOTAL_SHEEP",
        "AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA",
        "AGRICULTURAL_HOLDINGS",
        *FINAL_21_COHORTS,
        *GOBLIN_SHEEP_10,
        *SO_COMPONENTS,
        "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR",
        "SO_OTHER_CROPS_IMPUTED_HA",
        "SO_LIVESTOCK_2020_EUR",
        "SO_COVERED_TOTAL_2020_EUR",
        "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
    ]
    return list(dict.fromkeys(c for c in candidates if c in frame.columns))


def aggregate_state(
    master: pd.DataFrame,
    by: list[str],
) -> pd.DataFrame:
    """Aggregate additive state, then derive signatures and structure metrics.

    Average holding size is AREA_FARMED / AGRICULTURAL_HOLDINGS after
    aggregation. Average holder age is holdings-weighted. Median holder age is
    intentionally not propagated because ED medians cannot recover a valid
    higher-level median.
    """

    cols = _additive_columns(master)
    work = master.copy()
    include_age = (
        "AVERAGE_AGE_OF_HOLDER" in work.columns
        and "AGRICULTURAL_HOLDINGS" in work.columns
    )
    temp_cols: list[str] = []
    if include_age:
        holdings = _num(work, "AGRICULTURAL_HOLDINGS")
        age = pd.to_numeric(
            work["AVERAGE_AGE_OF_HOLDER"], errors="coerce"
        ).astype(float)
        valid = age.notna()
        work["_AGE_HOLDING_NUM"] = np.where(valid, age * holdings, 0.0)
        work["_AGE_HOLDING_DEN"] = np.where(valid, holdings, 0.0)
        temp_cols = ["_AGE_HOLDING_NUM", "_AGE_HOLDING_DEN"]

    grouped = work.groupby(by, as_index=False, sort=True)[[*cols, *temp_cols]].sum()

    if {"AREA_FARMED", "AGRICULTURAL_HOLDINGS"}.issubset(grouped.columns):
        grouped["AVERAGE_SIZE_OF_HOLDINGS"] = _safe_ratio(
            grouped["AREA_FARMED"], grouped["AGRICULTURAL_HOLDINGS"]
        )

    if include_age:
        grouped["AVERAGE_AGE_OF_HOLDER"] = _safe_ratio(
            grouped["_AGE_HOLDING_NUM"], grouped["_AGE_HOLDING_DEN"]
        )
        grouped = grouped.drop(columns=temp_cols)

    if "AGRICULTURAL_HOLDINGS" in grouped.columns:
        for total_column, per_holding_column in (
            ("SO_COVERED_TOTAL_2020_EUR", "SO_COVERED_PER_HOLDING_2020_EUR"),
            (
                "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR",
                "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR",
            ),
        ):
            if total_column in grouped.columns:
                grouped[per_holding_column] = _safe_ratio(
                    grouped[total_column], grouped["AGRICULTURAL_HOLDINGS"]
                )

    return add_signature_metrics(grouped)


def build_anchor_reconciliation(
    ed_anchor_path: str | Path,
    county_control_path: str | Path,
) -> pd.DataFrame:
    """Quantify 2020 adjustment from raw ED census sums to county cattle controls."""

    ed = pd.read_csv(ed_anchor_path)
    ctl = pd.read_csv(county_control_path)
    ctl["Year"] = pd.to_numeric(ctl["Year"], errors="raise").astype(int)
    ctl = ctl.loc[ctl["Year"] == 2020].copy()

    mapping = {
        "TOTAL_CATTLE": "Total cattle",
        "DAIRY_COW": "Dairy cows",
        "OTHER_COW": "Other cows",
    }
    rows: list[dict[str, object]] = []
    for ed_col, control_col in mapping.items():
        raw = (
            ed.groupby("County", as_index=False)[ed_col]
            .sum()
            .rename(columns={ed_col: "RAW_ED_TOTAL"})
        )
        control = ctl[["Region and County", control_col]].rename(
            columns={"Region and County": "County", control_col: "CONTROL_000_HEAD"}
        )
        control["CONTROL_TOTAL"] = pd.to_numeric(
            control["CONTROL_000_HEAD"], errors="raise"
        ) * 1000.0
        merged = raw.merge(
            control[["County", "CONTROL_TOTAL"]],
            on="County",
            how="inner",
            validate="one_to_one",
        )
        merged["DIFF_HEAD"] = merged["CONTROL_TOTAL"] - merged["RAW_ED_TOTAL"]
        merged["PCT_OF_RAW"] = np.where(
            merged["RAW_ED_TOTAL"] != 0,
            100.0 * merged["DIFF_HEAD"] / merged["RAW_ED_TOTAL"],
            np.nan,
        )
        raw_nat = float(merged["RAW_ED_TOTAL"].sum())
        control_nat = float(merged["CONTROL_TOTAL"].sum())
        rows.append(
            {
                "VARIABLE": ed_col,
                "RAW_ED_NATIONAL": raw_nat,
                "CONTROL_NATIONAL": control_nat,
                "NATIONAL_ADJUSTMENT_HEAD": control_nat - raw_nat,
                "NATIONAL_ADJUSTMENT_PCT_OF_RAW": (
                    100.0 * (control_nat - raw_nat) / raw_nat if raw_nat else np.nan
                ),
                "MEAN_ABS_COUNTY_ADJUSTMENT_HEAD": float(
                    merged["DIFF_HEAD"].abs().mean()
                ),
                "MAX_ABS_COUNTY_ADJUSTMENT_PCT_OF_RAW": float(
                    merged["PCT_OF_RAW"].abs().max()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_so_decomposition(
    master: pd.DataFrame,
    start_year: int = 2015,
    end_year: int = 2025,
) -> pd.DataFrame:
    """Decompose fixed-coefficient covered-SO change into all reported components."""

    cols = [*SO_COMPONENTS, "SO_COVERED_TOTAL_2020_EUR"]
    missing = [c for c in cols if c not in master.columns]
    if missing:
        raise ValueError(f"SO decomposition missing columns: {missing}")
    totals = master.groupby("YEAR", as_index=False)[cols].sum().set_index("YEAR")
    if start_year not in totals.index or end_year not in totals.index:
        raise ValueError("SO decomposition endpoint years are missing")

    rows = []
    for column in cols:
        start = float(totals.loc[start_year, column])
        end = float(totals.loc[end_year, column])
        rows.append(
            {
                "COMPONENT": column,
                "START_YEAR": start_year,
                "END_YEAR": end_year,
                "START_EUR": start,
                "END_EUR": end,
                "CHANGE_EUR": end - start,
                "CHANGE_PCT": 100.0 * (end - start) / start if start else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    component_change = float(
        out.loc[out["COMPONENT"].isin(SO_COMPONENTS), "CHANGE_EUR"].sum()
    )
    total_change = float(
        out.loc[out["COMPONENT"] == "SO_COVERED_TOTAL_2020_EUR", "CHANGE_EUR"].iloc[0]
    )
    if not np.isclose(component_change, total_change, rtol=0, atol=1e-5):
        raise AssertionError(
            "SO components do not close to covered-total change: "
            f"components={component_change}, total={total_change}"
        )
    return out


def build_validation_summary(validation_dir: str | Path) -> pd.DataFrame:
    """Create one manuscript-facing validation table from frozen diagnostics."""

    root = Path(validation_dir)
    rows: list[dict[str, object]] = []

    overview = pd.read_csv(root / "historical_validation_overview.csv")
    accounting = overview.loc[
        overview["VALIDATION_FAMILY"] == "ACCOUNTING_VERIFICATION"
    ]
    for _, r in accounting.iterrows():
        rows.append(
            {
                "EVIDENCE": "Internal accounting",
                "SCOPE": str(r["METRIC"]),
                "METRIC": str(r["METRIC"]),
                "VALUE": float(r["VALUE"]),
                "UNIT": "native",
            }
        )

    holdout = pd.read_csv(root / "sheep_composition_holdout_2022_summary.csv")
    for _, r in holdout.iterrows():
        rows.extend(
            [
                {
                    "EVIDENCE": "2022 sheep-composition holdout",
                    "SCOPE": str(r["BREED_GROUP"]),
                    "METRIC": "MAE",
                    "VALUE": float(r["MAE_PP"]),
                    "UNIT": "percentage points",
                },
                {
                    "EVIDENCE": "2022 sheep-composition holdout",
                    "SCOPE": str(r["BREED_GROUP"]),
                    "METRIC": "Spearman rho",
                    "VALUE": float(r["SPEARMAN_RHO"]),
                    "UNIT": "rho",
                },
            ]
        )

    lsu_path = root / "cattle_lsu_age_prior_summary.csv"
    if lsu_path.exists():
        lsu = pd.read_csv(lsu_path)
        for _, r in lsu.iterrows():
            rows.extend(
                [
                    {
                        "EVIDENCE": "2020 ED livestock-unit age-prior plausibility",
                        "SCOPE": str(r["AGE_PRIOR"]),
                        "METRIC": "Median absolute residual",
                        "VALUE": float(r["median_abs_residual"]),
                        "UNIT": "LSU",
                    },
                    {
                        "EVIDENCE": "2020 ED livestock-unit age-prior plausibility",
                        "SCOPE": str(r["AGE_PRIOR"]),
                        "METRIC": "Eligible EDs",
                        "VALUE": float(r["eligible_eds"]),
                        "UNIT": "EDs",
                    },
                    {
                        "EVIDENCE": "2020 ED livestock-unit age-prior plausibility",
                        "SCOPE": str(r["AGE_PRIOR"]),
                        "METRIC": "Median published ED LSU",
                        "VALUE": float(r["median_published_lsu"]),
                        "UNIT": "LSU",
                    },
                ]
            )

    dafm = pd.read_csv(root / "dafm_county_sheep_summary.csv")
    for _, r in dafm.iterrows():
        mean_observed_county = float(r["OBSERVED_TOTAL"]) / float(r["N"])
        rows.extend(
            [
                {
                    "EVIDENCE": "DAFM county sheep pattern fidelity",
                    "SCOPE": str(int(r["YEAR"])),
                    "METRIC": "MAE",
                    "VALUE": float(r["MAE"]),
                    "UNIT": "head",
                },
                {
                    "EVIDENCE": "DAFM county sheep pattern fidelity",
                    "SCOPE": str(int(r["YEAR"])),
                    "METRIC": "MAE / mean observed county",
                    "VALUE": 100.0 * float(r["MAE"]) / mean_observed_county,
                    "UNIT": "%",
                },
                {
                    "EVIDENCE": "DAFM county sheep pattern fidelity",
                    "SCOPE": str(int(r["YEAR"])),
                    "METRIC": "Spearman rho",
                    "VALUE": float(r["SPEARMAN_RHO"]),
                    "UNIT": "rho",
                },
            ]
        )

    achill = pd.read_csv(root / "achill_ed_2020_summary.csv")
    for _, r in achill.iterrows():
        rows.append(
            {
                "EVIDENCE": "Achill North livestock reproduction",
                "SCOPE": str(r["VARIABLE"]),
                "METRIC": "MAE",
                "VALUE": float(r["MAE"]),
                "UNIT": "head",
            }
        )

    achill_land = pd.read_csv(root / "achill_land_2020_summary.csv")
    for _, r in achill_land.iterrows():
        rows.append(
            {
                "EVIDENCE": "Achill North land reproduction",
                "SCOPE": str(r["VARIABLE"]),
                "METRIC": "MAE",
                "VALUE": float(r["MAE"]),
                "UNIT": "native",
            }
        )

    transfer = overview.loc[
        overview["VALIDATION_FAMILY"] == "ACHILL_SPATIAL_TRANSFER"
    ]
    for _, r in transfer.iterrows():
        rows.append(
            {
                "EVIDENCE": "Achill North spatial transfer",
                "SCOPE": str(r["SCOPE"]),
                "METRIC": "Maximum absolute rounding difference",
                "VALUE": float(r["VALUE"]),
                "UNIT": "head",
            }
        )

    stability = pd.read_csv(root / "temporal_rank_stability_summary.csv")
    for _, r in stability.iterrows():
        rows.append(
            {
                "EVIDENCE": "Adjacent-year continuity",
                "SCOPE": str(r["INDICATOR"]),
                "METRIC": "Minimum Spearman rho",
                "VALUE": float(r["MIN_RHO"]),
                "UNIT": "rho",
            }
        )
    return pd.DataFrame(rows)


def information_geography(
    ed_state: pd.DataFrame,
    metrics: tuple[str, ...] = SIGNATURE_METRICS,
) -> pd.DataFrame:
    """Return between-county share of ED variance for selected metrics."""

    rows = []
    for metric in metrics:
        work = ed_state[["County", metric]].dropna().copy()
        if len(work) < 2:
            continue
        overall = float(work[metric].mean())
        total_ss = float(((work[metric] - overall) ** 2).sum())
        grouped = work.groupby("County")[metric].agg(["mean", "size"])
        between_ss = float(
            (grouped["size"] * (grouped["mean"] - overall) ** 2).sum()
        )
        rows.append(
            {
                "METRIC": metric,
                "N_ED": int(len(work)),
                "BETWEEN_COUNTY_SHARE_RB": (
                    between_ss / total_ss if total_ss > 0 else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def signature_ranges(
    states: dict[str, pd.DataFrame],
    year: int = 2020,
) -> pd.DataFrame:
    """Summarise comparable signature ranges across reporting geographies."""

    rows = []
    for geography, frame in states.items():
        part = frame.loc[pd.to_numeric(frame["YEAR"], errors="raise").astype(int) == year]
        for metric in SIGNATURE_METRICS:
            x = pd.to_numeric(part[metric], errors="coerce").dropna()
            if x.empty:
                continue
            rows.append(
                {
                    "YEAR": year,
                    "GEOGRAPHY": geography,
                    "METRIC": metric,
                    "N": int(len(x)),
                    "MIN": float(x.min()),
                    "P05": float(x.quantile(0.05)),
                    "MEDIAN": float(x.median()),
                    "P95": float(x.quantile(0.95)),
                    "MAX": float(x.max()),
                }
            )
    return pd.DataFrame(rows)


def concentration_summary(ed_state: pd.DataFrame, year: int = 2020) -> pd.DataFrame:
    """Land-normalised upper-decile concentration for central livestock groups."""

    part = ed_state.loc[pd.to_numeric(ed_state["YEAR"], errors="raise").astype(int) == year].copy()
    part = part.loc[_num(part, "AREA_FARMED") > 0].copy()
    groups = {
        "TOTAL_CATTLE": _num(part, "TOTAL_CATTLE"),
        "DAIRY_COWS": _num(part, "dairy_cows"),
        "SUCKLER_COWS": _num(part, "suckler_cows"),
        "FOLLOWERS": _num(part, "FOLLOWER_TOTAL"),
        "TOTAL_SHEEP": _num(part, "TOTAL_SHEEP"),
    }
    rows = []
    n_top = max(1, int(np.ceil(0.10 * len(part))))
    total_land = float(_num(part, "AREA_FARMED").sum())
    for label, values in groups.items():
        density = values / _num(part, "AREA_FARMED")
        ranked = part.assign(_VALUE=values, _DENSITY=density).sort_values(
            "_DENSITY", ascending=False, kind="stable"
        )
        top = ranked.head(n_top)
        total_value = float(ranked["_VALUE"].sum())
        rows.append(
            {
                "YEAR": year,
                "POPULATION": label,
                "TOP_DECILE_EDS": n_top,
                "POPULATION_SHARE_PCT": (
                    100.0 * float(top["_VALUE"].sum()) / total_value
                    if total_value > 0 else np.nan
                ),
                "FARMED_AREA_SHARE_PCT": (
                    100.0 * float(top["AREA_FARMED"].sum()) / total_land
                    if total_land > 0 else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def build_matched_pairs(ed_state: pd.DataFrame, year: int = 2020) -> pd.DataFrame:
    """Find within-county pairs with near-identical cattle totals and contrasting signatures."""

    part = ed_state.loc[pd.to_numeric(ed_state["YEAR"], errors="raise").astype(int) == year].copy()
    part = part.loc[
        (_num(part, "TOTAL_CATTLE") >= 500)
        & (_num(part, "ADULT_COWS") >= 200)
    ].copy()
    vars_ = [
        "DAIRY_SHARE_ADULT_PCT",
        "FOLLOWER_TO_ADULT_RATIO",
        "UNDER1_SHARE_FOLLOWERS_PCT",
        "DXD_SHARE_FOLLOWERS_PCT",
    ]
    for v in vars_:
        sd = float(pd.to_numeric(part[v], errors="coerce").std(ddof=0))
        mean = float(pd.to_numeric(part[v], errors="coerce").mean())
        part[f"_Z_{v}"] = (part[v] - mean) / sd if sd > 0 else 0.0

    rows = []
    for county, group in part.groupby("County", sort=True):
        recs = list(group.to_dict("records"))
        for a, b in combinations(recs, 2):
            pair_mean = (float(a["TOTAL_CATTLE"]) + float(b["TOTAL_CATTLE"])) / 2.0
            if pair_mean <= 0:
                continue
            pct_gap = 100.0 * abs(float(a["TOTAL_CATTLE"]) - float(b["TOTAL_CATTLE"])) / pair_mean
            if pct_gap > 2.0:
                continue
            dist = float(np.sqrt(sum(
                (float(a[f"_Z_{v}"]) - float(b[f"_Z_{v}"])) ** 2 for v in vars_
            )))
            rows.append(
                {
                    "YEAR": year,
                    "County": county,
                    "ED_A": a.get("EDNAME", a.get("ED", a["CSOED"])),
                    "CSOED_A": str(a["CSOED"]),
                    "ED_B": b.get("EDNAME", b.get("ED", b["CSOED"])),
                    "CSOED_B": str(b["CSOED"]),
                    "TOTAL_CATTLE_A": float(a["TOTAL_CATTLE"]),
                    "TOTAL_CATTLE_B": float(b["TOTAL_CATTLE"]),
                    "CATTLE_GAP_PCT_PAIR_MEAN": pct_gap,
                    "SIGNATURE_DISTANCE": dist,
                    "DAIRY_SHARE_A_PCT": float(a["DAIRY_SHARE_ADULT_PCT"]),
                    "DAIRY_SHARE_B_PCT": float(b["DAIRY_SHARE_ADULT_PCT"]),
                    "FOLLOWER_ADULT_A": float(a["FOLLOWER_TO_ADULT_RATIO"]),
                    "FOLLOWER_ADULT_B": float(b["FOLLOWER_TO_ADULT_RATIO"]),
                    "UNDER1_SHARE_A_PCT": float(a["UNDER1_SHARE_FOLLOWERS_PCT"]),
                    "UNDER1_SHARE_B_PCT": float(b["UNDER1_SHARE_FOLLOWERS_PCT"]),
                    "DXD_SHARE_A_PCT": float(a["DXD_SHARE_FOLLOWERS_PCT"]),
                    "DXD_SHARE_B_PCT": float(b["DXD_SHARE_FOLLOWERS_PCT"]),
                    "CATTLE_PER_FARMED_HA_A": float(a["CATTLE_PER_FARMED_HA"]),
                    "CATTLE_PER_FARMED_HA_B": float(b["CATTLE_PER_FARMED_HA"]),
                    "SO_PER_FARMED_HA_A": float(a["SO_PER_FARMED_HA"]),
                    "SO_PER_FARMED_HA_B": float(b["SO_PER_FARMED_HA"]),
                }
            )
    if not rows:
        return pd.DataFrame()
    candidates = pd.DataFrame(rows).sort_values(
        ["SIGNATURE_DISTANCE", "County"], ascending=[False, True], kind="stable"
    )
    best = candidates.groupby("County", as_index=False, sort=True).head(1)
    return best.sort_values("SIGNATURE_DISTANCE", ascending=False, kind="stable").reset_index(drop=True)


def stable_ed_sensitivity(
    ed_state: pd.DataFrame,
    start_year: int = 2015,
    end_year: int = 2020,
) -> pd.DataFrame:
    """Summarise change within stability bands over the two-anchor spatial period.

    The default ends in 2020 because 2015-2019 ED shares move along the
    2010-to-2020 census path. After 2020 the within-county ED support pattern
    is deliberately held, so combining 2015-2025 would mix two spatial regimes.
    """

    cols = [
        "CSOED", "YEAR", "TOTAL_CATTLE",
        "DAIRY_SHARE_ADULT_PCT", "DXB_SHARE_FOLLOWERS_PCT",
        "BXB_SHARE_FOLLOWERS_PCT", "SO_PER_FARMED_HA",
    ]
    work = ed_state[cols].copy()
    a = work.loc[work["YEAR"] == start_year].set_index("CSOED")
    b = work.loc[work["YEAR"] == end_year].set_index("CSOED")
    both = a.add_suffix(f"_{start_year}").join(b.add_suffix(f"_{end_year}"), how="inner")
    both["CATTLE_CHANGE_PCT"] = 100.0 * (
        both[f"TOTAL_CATTLE_{end_year}"] - both[f"TOTAL_CATTLE_{start_year}"]
    ) / both[f"TOTAL_CATTLE_{start_year}"].replace(0, np.nan)

    for metric in ("DAIRY_SHARE_ADULT_PCT", "DXB_SHARE_FOLLOWERS_PCT", "BXB_SHARE_FOLLOWERS_PCT"):
        both[f"ABS_{metric}_CHANGE_PP"] = (
            both[f"{metric}_{end_year}"] - both[f"{metric}_{start_year}"]
        ).abs()

    both["SO_INTENSITY_CHANGE_PCT"] = 100.0 * (
        both[f"SO_PER_FARMED_HA_{end_year}"] - both[f"SO_PER_FARMED_HA_{start_year}"]
    ) / both[f"SO_PER_FARMED_HA_{start_year}"].replace(0, np.nan)

    rows = []
    n_total = int(len(both))
    for band in (2.5, 5.0, 10.0):
        s = both.loc[both["CATTLE_CHANGE_PCT"].abs() <= band].copy()
        row: dict[str, object] = {
            "START_YEAR": start_year,
            "END_YEAR": end_year,
            "STABILITY_BAND_PCT": band,
            "N_ED": int(len(s)),
            "PCT_OF_ALL_ED": 100.0 * len(s) / n_total if n_total else np.nan,
        }
        for short, metric in (
            ("DAIRY", "DAIRY_SHARE_ADULT_PCT"),
            ("DXB", "DXB_SHARE_FOLLOWERS_PCT"),
            ("BXB", "BXB_SHARE_FOLLOWERS_PCT"),
        ):
            x = s[f"ABS_{metric}_CHANGE_PP"].dropna()
            row[f"MEDIAN_ABS_{short}_CHANGE_PP"] = float(x.median()) if len(x) else np.nan
            row[f"P90_ABS_{short}_CHANGE_PP"] = float(x.quantile(0.90)) if len(x) else np.nan
            row[f"PCT_{short}_CHANGE_GE_10PP"] = (
                100.0 * float((x >= 10.0).mean()) if len(x) else np.nan
            )
        so = s["SO_INTENSITY_CHANGE_PCT"].abs().dropna()
        row["PCT_ABS_SO_INTENSITY_CHANGE_GE_10PCT"] = (
            100.0 * float((so >= 10.0).mean()) if len(so) else np.nan
        )
        rows.append(row)
    return pd.DataFrame(rows)


def select_multiscale_example(
    ed_state: pd.DataFrame,
    county_state: pd.DataFrame,
    catchment_state: pd.DataFrame,
    crosswalk: pd.DataFrame,
    year: int = 2020,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pre-specify one multiscale example from maximum within-county dairy heterogeneity.

    County selection maximises the adult-cow-weighted mean absolute deviation of
    ED dairy share from the county dairy share. The ED example is the eligible
    (>=200 adult cows) ED with the largest absolute deviation inside that county.
    Its WFD catchment is the catchment receiving the largest intersection weight
    for that ED. County and catchment are alternative reporting geographies, not
    a nested hierarchy.
    """

    ed = ed_state.loc[ed_state["YEAR"] == year].copy()
    county = county_state.loc[county_state["YEAR"] == year].copy()
    county_share = county.set_index("County")["DAIRY_SHARE_ADULT_PCT"].to_dict()
    rows = []
    for name, g in ed.loc[ed["ADULT_COWS"] > 0].groupby("County", sort=True):
        if name not in county_share:
            continue
        weights = _num(g, "ADULT_COWS")
        dev = (g["DAIRY_SHARE_ADULT_PCT"] - float(county_share[name])).abs()
        rows.append(
            {
                "County": name,
                "WEIGHTED_MAD_DAIRY_SHARE_PP": float((weights * dev).sum() / weights.sum()),
                "N_ED_WITH_ADULT_COWS": int(len(g)),
            }
        )
    scores = pd.DataFrame(rows).sort_values(
        ["WEIGHTED_MAD_DAIRY_SHARE_PP", "County"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    if scores.empty:
        raise AssertionError("could not select multiscale county example")
    selected_county = str(scores.iloc[0]["County"])

    eligible = ed.loc[
        (ed["County"] == selected_county) & (ed["ADULT_COWS"] >= 200)
    ].copy()
    if eligible.empty:
        raise AssertionError("selected county has no ED with at least 200 adult cows")
    eligible["_ABS_DEV"] = (
        eligible["DAIRY_SHARE_ADULT_PCT"] - float(county_share[selected_county])
    ).abs()
    selected_ed = eligible.sort_values(
        ["_ABS_DEV", "CSOED"], ascending=[False, True], kind="stable"
    ).iloc[0]
    selected_csoed = str(selected_ed["CSOED"])

    xw = crosswalk.copy()
    xw["CSOED"] = xw["CSOED"].astype(str)
    ed_xw = xw.loc[xw["CSOED"] == selected_csoed].sort_values(
        ["ED_CATCHMENT_WEIGHT", "WFD_CATCHMENT_ID"],
        ascending=[False, True],
        kind="stable",
    )
    if ed_xw.empty:
        raise AssertionError("selected ED missing from WFD crosswalk")
    wfd_id = str(ed_xw.iloc[0]["WFD_CATCHMENT_ID"])
    wfd_name = str(ed_xw.iloc[0]["WFD_CATCHMENT"])

    catch = catchment_state.loc[
        (catchment_state["YEAR"] == year)
        & (catchment_state["WFD_CATCHMENT_ID"].astype(str) == wfd_id)
    ]
    if len(catch) != 1:
        raise AssertionError("selected WFD catchment state is not unique")

    national = aggregate_state(ed_state.loc[ed_state["YEAR"] == year], ["YEAR"]).iloc[0]
    county_row = county.loc[county["County"] == selected_county].iloc[0]
    catch_row = catch.iloc[0]

    common = [
        "TOTAL_CATTLE", "DAIRY_SHARE_ADULT_PCT", "DXD_SHARE_FOLLOWERS_PCT",
        "DXB_SHARE_FOLLOWERS_PCT", "BXB_SHARE_FOLLOWERS_PCT",
        "FOLLOWER_TO_ADULT_RATIO", "CATTLE_PER_FARMED_HA", "SO_PER_FARMED_HA",
    ]
    output = []
    for geography, label, row in (
        ("NATIONAL", "Ireland", national),
        ("COUNTY", selected_county, county_row),
        ("WFD_CATCHMENT", wfd_name, catch_row),
        ("ED", str(selected_ed.get("EDNAME", selected_ed.get("ED", selected_csoed))), selected_ed),
    ):
        rec = {"YEAR": year, "GEOGRAPHY": geography, "NAME": label}
        for col in common:
            rec[col] = float(row[col]) if pd.notna(row[col]) else np.nan
        if geography == "ED":
            rec["CSOED"] = selected_csoed
        output.append(rec)
    return pd.DataFrame(output), scores


def build_historical_result_tables(
    master: pd.DataFrame,
    wfd_catchment: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    ed_anchor_path: str | Path,
    cattle_control_path: str | Path,
    validation_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    """Build the canonical baseline result bundle from frozen outputs."""

    ed = add_signature_metrics(master)
    county = aggregate_state(master, ["YEAR", "County"])
    national = aggregate_state(master, ["YEAR"])
    catchment = add_signature_metrics(wfd_catchment)

    example, county_scores = select_multiscale_example(
        ed, county, catchment, crosswalk
    )

    tables = {
        "ed_year": ed,
        "county_year": county,
        "wfd_catchment_year": catchment,
        "national_year": national,
        "validation_summary": build_validation_summary(validation_dir),
        "anchor_reconciliation_2020": build_anchor_reconciliation(
            ed_anchor_path, cattle_control_path
        ),
        "so_change_2015_2025": build_so_decomposition(master),
        "signature_ranges_2020": signature_ranges(
            {
                "ED": ed,
                "COUNTY": county,
                "WFD_CATCHMENT": catchment,
                "NATIONAL": national,
            }
        ),
        "information_geography_2020": information_geography(
            ed.loc[ed["YEAR"] == 2020]
        ),
        "concentration_2020": concentration_summary(ed),
        "matched_pairs_2020": build_matched_pairs(ed),
        "stable_ed_sensitivity": stable_ed_sensitivity(ed),
        "multiscale_example_2020": example,
        "multiscale_county_selection_scores_2020": county_scores,
    }
    return tables
