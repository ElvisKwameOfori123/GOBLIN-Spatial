"""Diagnostics for the final cattle genetics disaggregation.

The script compares the legacy cow-support G0 allocator with the production
AIM-hierarchical G1 allocator. It checks exact accounting, receiver/rearing
behaviour, concentration and agreement with the DAFM/AIM broad cattle-type
composition. Because G1 uses AIM cattle type as a prior, the G1 AIM comparison
is a calibration/coherence diagnostic rather than independent validation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.cattle.age_sex import _normalise_county, _normalise_ed_name
from goblin_spatial.cattle.cohorts import (
    CONTAINERS,
    FINAL_21_COHORTS,
    GENETICS,
    _build_aim_genetic_signature,
    _build_biological_controls,
    _build_ed_genetic_support,
    _load_goblin,
)
from goblin_spatial.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUTPUT_DIR = ROOT / "data/processed/validation/historical"


def _sum_columns(mapping_key: str) -> list[str]:
    if mapping_key == "dairy_origin":
        return [
            mapping[genetic]
            for mapping in CONTAINERS.values()
            for genetic in ("DxD", "DxB")
        ]
    if mapping_key == "bxb":
        return [mapping["BxB"] for mapping in CONTAINERS.values()]
    raise ValueError(mapping_key)


def _top_share(values: pd.Series, fraction: float) -> float:
    values = pd.to_numeric(values, errors="raise").astype(float)
    total = float(values.sum())
    if total <= 0:
        return 0.0
    n = max(1, int(np.ceil(len(values) * fraction)))
    return float(values.nlargest(n).sum() / total)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="raise").astype(float)
    denominator = pd.to_numeric(denominator, errors="raise").astype(float)
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    positive = denominator > 0
    out.loc[positive] = numerator.loc[positive] / denominator.loc[positive]
    return out



def _build_dafm_type_signal(ed_frame: pd.DataFrame, dafm_path) -> pd.DataFrame:
    """Map unused DAFM beef/dairy composition to the 2020 model EDs.

    This is validation evidence only. The DAFM beef/dairy fields do not alter
    CSO cattle totals, age-sex controls or GOBLIN genetic margins.
    """

    dafm = pd.read_csv(dafm_path)
    required = [
        "COUNTY",
        "ELECTORAL_DIVISION",
        "AVERAGE_NUMBER_CATTLE",
        "AVERAGE_CATTLE_BEEF",
        "AVERAGE_CATTLE_DAIRY",
    ]
    missing = [column for column in required if column not in dafm.columns]
    if missing:
        raise ValueError(f"DAFM cattle type profile missing required columns: {missing}")

    for column in required[2:]:
        dafm[column] = pd.to_numeric(dafm[column], errors="raise").astype(float)
        if (dafm[column] < 0).any():
            raise ValueError(f"DAFM cattle type profile has negative values in {column}")

    dafm["County"] = dafm["COUNTY"].map(_normalise_county)
    dafm["_NAME_KEY"] = dafm["ELECTORAL_DIVISION"].map(_normalise_ed_name)
    low_herd = dafm["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )
    local = (
        dafm.loc[~low_herd]
        .groupby(["County", "_NAME_KEY"])[
            ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_BEEF", "AVERAGE_CATTLE_DAIRY"]
        ]
        .sum()
    )

    signal = pd.DataFrame(index=ed_frame.index)
    signal["DAFM_TYPE_MATCHED"] = False
    signal["DAFM_TYPE_TOTAL"] = np.nan
    signal["DAFM_DAIRY_COUNT"] = np.nan
    signal["DAFM_BEEF_COUNT"] = np.nan

    for county_name, idx in ed_frame.groupby("County").groups.items():
        for i in idx:
            keys = {
                _normalise_ed_name(part)
                for part in str(ed_frame.at[i, "ED"]).split("/")
                if _normalise_ed_name(part)
            }
            total = 0.0
            dairy = 0.0
            beef = 0.0
            matched = False
            for key in keys:
                lookup = (county_name, key)
                if lookup in local.index:
                    values = local.loc[lookup]
                    total += float(values["AVERAGE_NUMBER_CATTLE"])
                    dairy += float(values["AVERAGE_CATTLE_DAIRY"])
                    beef += float(values["AVERAGE_CATTLE_BEEF"])
                    matched = True
            if matched and total > 0:
                signal.at[i, "DAFM_TYPE_MATCHED"] = True
                signal.at[i, "DAFM_TYPE_TOTAL"] = total
                signal.at[i, "DAFM_DAIRY_COUNT"] = dairy
                signal.at[i, "DAFM_BEEF_COUNT"] = beef

    signal["DAFM_DAIRY_SHARE"] = np.divide(
        signal["DAFM_DAIRY_COUNT"],
        signal["DAFM_TYPE_TOTAL"],
        out=np.full(len(signal), np.nan, dtype=float),
        where=signal["DAFM_TYPE_TOTAL"].to_numpy(dtype=float) > 0,
    )
    return signal


def _config_with_genetics_mode(config, mode: str):
    raw = deepcopy(config.raw)
    raw.setdefault("cattle", {})["genetics_prior"] = mode
    return replace(config, raw=raw)


def _dafm_type_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, float, float, float]:
    matched = frame.loc[
        frame["DAFM_TYPE_MATCHED"]
        & frame["MODEL_DAIRY_TYPE_SHARE"].notna()
        & frame["DAFM_DAIRY_SHARE"].notna()
    ].copy()
    if matched.empty:
        raise AssertionError("no DAFM beef/dairy composition matches available")
    spearman = float(
        matched["MODEL_DAIRY_TYPE_SHARE"].corr(
            matched["DAFM_DAIRY_SHARE"], method="spearman"
        )
    )
    mae_pp = float(
        100.0
        * np.average(
            matched["DAFM_DAIRY_SHARE_RESIDUAL"].abs(),
            weights=matched["DAFM_TYPE_TOTAL"],
        )
    )
    cattle_share = float(matched["TOTAL_CATTLE"].sum() / frame["TOTAL_CATTLE"].sum())
    return matched, spearman, mae_pp, cattle_share


def run() -> None:
    config = load_config(CONFIG)
    panel = build_cattle_panel(config)
    cattle = add_cattle_cohorts(panel, config)
    g0 = add_cattle_cohorts(
        panel,
        _config_with_genetics_mode(config, "cow_support"),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Hard accounting checks.
    if not (
        cattle[FINAL_21_COHORTS].sum(axis=1).astype(np.int64)
        == cattle["TOTAL_CATTLE"].astype(np.int64)
    ).all():
        raise AssertionError("21-cohort cattle total does not close to TOTAL_CATTLE")

    for container, mapping in CONTAINERS.items():
        columns = [mapping[g] for g in GENETICS]
        if not (
            cattle[columns].sum(axis=1).astype(np.int64)
            == cattle[container].astype(np.int64)
        ).all():
            raise AssertionError(f"{container}: genetic rows do not close")

    goblin = _load_goblin(config.files["goblin_cohorts"])
    targets, _ = _build_biological_controls(cattle, goblin)
    dairy_support, bxb_support, _, _ = _build_ed_genetic_support(cattle, targets)
    aim_signature, q_national = _build_aim_genetic_signature(
        panel,
        config.files["dafm_aim_ed_cattle_profile_2020"],
        epsilon=float(config.raw.get("cattle", {}).get("dafm_logit_epsilon", 1.0e-6)),
    )

    national_rows: list[dict] = []
    for year in sorted(cattle["YEAR"].unique()):
        year_frame = cattle.loc[cattle["YEAR"] == year]
        for container, mapping in CONTAINERS.items():
            target = targets[(int(year), container)]
            observed = np.array(
                [int(year_frame[mapping[g]].sum()) for g in GENETICS], dtype=np.int64
            )
            if not np.array_equal(observed, target):
                raise AssertionError(
                    f"{year} {container}: genetic national margin does not close"
                )
            for j, genetic in enumerate(GENETICS):
                national_rows.append(
                    {
                        "YEAR": int(year),
                        "CONTAINER": container,
                        "GENETIC": genetic,
                        "OBSERVED": int(observed[j]),
                        "TARGET": int(target[j]),
                        "DIFF": int(observed[j] - target[j]),
                    }
                )

    national = pd.DataFrame(national_rows)
    national.to_csv(OUTPUT_DIR / "cattle_genetics_national_margins.csv", index=False)

    y2020 = cattle.loc[cattle["YEAR"] == 2020].copy()
    g0_2020 = g0.loc[g0["YEAR"] == 2020].copy()
    dxd_cols = [mapping["DxD"] for mapping in CONTAINERS.values()]
    dxb_cols = [mapping["DxB"] for mapping in CONTAINERS.values()]
    bxb_cols = [mapping["BxB"] for mapping in CONTAINERS.values()]
    dairy_cols = dxd_cols + dxb_cols

    y2020["DXD_YOUNG"] = y2020[dxd_cols].sum(axis=1)
    y2020["DXB_YOUNG"] = y2020[dxb_cols].sum(axis=1)
    y2020["DAIRY_ORIGIN_YOUNG"] = y2020[dairy_cols].sum(axis=1)
    y2020["BXB_YOUNG"] = y2020[bxb_cols].sum(axis=1)
    y2020["IS_DAIRY_SUPPORT_G0"] = y2020["CSOED"].isin(dairy_support)
    y2020["IS_BXB_SUPPORT_G0"] = y2020["CSOED"].isin(bxb_support)
    y2020["NO_ADULT_RECEIVER"] = (
        y2020["DAIRY_COW"].eq(0)
        & y2020["OTHER_COW"].eq(0)
        & y2020["OTHER_CATTLE"].gt(0)
    )
    y2020["ZERO_DAIRY_WITH_DAIRY_ORIGIN"] = (
        y2020["DAIRY_COW"].eq(0) & y2020["DAIRY_ORIGIN_YOUNG"].gt(0)
    )
    y2020["ZERO_SUCKLER_WITH_BXB"] = (
        y2020["OTHER_COW"].eq(0) & y2020["BXB_YOUNG"].gt(0)
    )

    bxb_calves = (
        y2020["BxB_calves_m"].astype(float)
        + y2020["BxB_calves_f"].astype(float)
    )
    y2020["BXB_CALVES_PER_SUCKLER_COW"] = _safe_ratio(
        bxb_calves, y2020["OTHER_COW"]
    )
    dairy_calves = (
        y2020["DxD_calves_m"].astype(float)
        + y2020["DxD_calves_f"].astype(float)
        + y2020["DxB_calves_m"].astype(float)
        + y2020["DxB_calves_f"].astype(float)
    )
    y2020["DAIRY_ORIGIN_CALVES_PER_DAIRY_COW"] = _safe_ratio(
        dairy_calves, y2020["DAIRY_COW"]
    )

    dafm_type = _build_dafm_type_signal(
        y2020[["County", "ED"]], config.files["dafm_aim_ed_cattle_profile_2020"]
    )
    y2020 = y2020.join(dafm_type)
    # DAFM broad dairy cattle are compared with DxD, not with all
    # dairy-origin cattle. DxB are beef-cross cattle and therefore belong with
    # BxB in the broad beef-type comparison.
    y2020["MODEL_DAIRY_TYPE_COUNT"] = y2020["DAIRY_COW"] + y2020["DXD_YOUNG"]
    y2020["MODEL_BEEF_TYPE_COUNT"] = (
        y2020["OTHER_COW"] + y2020["DXB_YOUNG"] + y2020["BXB_YOUNG"]
    )
    y2020["MODEL_TYPE_TOTAL"] = (
        y2020["MODEL_DAIRY_TYPE_COUNT"] + y2020["MODEL_BEEF_TYPE_COUNT"]
    )
    y2020["MODEL_DAIRY_TYPE_SHARE"] = np.divide(
        y2020["MODEL_DAIRY_TYPE_COUNT"],
        y2020["MODEL_TYPE_TOTAL"],
        out=np.full(len(y2020), np.nan, dtype=float),
        where=y2020["MODEL_TYPE_TOTAL"].to_numpy(dtype=float) > 0,
    )
    y2020["DAFM_DAIRY_SHARE_RESIDUAL"] = (
        y2020["MODEL_DAIRY_TYPE_SHARE"] - y2020["DAFM_DAIRY_SHARE"]
    )
    matched_type, type_spearman, type_mae_pp, matched_model_cattle_share = (
        _dafm_type_metrics(y2020)
    )

    g0_2020 = g0_2020.join(
        dafm_type[
            [
                "DAFM_TYPE_MATCHED",
                "DAFM_TYPE_TOTAL",
                "DAFM_DAIRY_SHARE",
            ]
        ]
    )
    g0_2020["DXD_YOUNG"] = g0_2020[dxd_cols].sum(axis=1)
    g0_2020["DXB_YOUNG"] = g0_2020[dxb_cols].sum(axis=1)
    g0_2020["BXB_YOUNG"] = g0_2020[bxb_cols].sum(axis=1)
    g0_2020["MODEL_DAIRY_TYPE_COUNT"] = (
        g0_2020["DAIRY_COW"] + g0_2020["DXD_YOUNG"]
    )
    g0_2020["MODEL_BEEF_TYPE_COUNT"] = (
        g0_2020["OTHER_COW"] + g0_2020["DXB_YOUNG"] + g0_2020["BXB_YOUNG"]
    )
    g0_2020["MODEL_TYPE_TOTAL"] = (
        g0_2020["MODEL_DAIRY_TYPE_COUNT"] + g0_2020["MODEL_BEEF_TYPE_COUNT"]
    )
    g0_2020["MODEL_DAIRY_TYPE_SHARE"] = np.divide(
        g0_2020["MODEL_DAIRY_TYPE_COUNT"],
        g0_2020["MODEL_TYPE_TOTAL"],
        out=np.full(len(g0_2020), np.nan, dtype=float),
        where=g0_2020["MODEL_TYPE_TOTAL"].to_numpy(dtype=float) > 0,
    )
    g0_2020["DAFM_DAIRY_SHARE_RESIDUAL"] = (
        g0_2020["MODEL_DAIRY_TYPE_SHARE"] - g0_2020["DAFM_DAIRY_SHARE"]
    )
    _, g0_type_spearman, g0_type_mae_pp, _ = _dafm_type_metrics(g0_2020)

    ed_columns = [
        "CSOED",
        "County",
        "ED",
        "DAIRY_COW",
        "OTHER_COW",
        "OTHER_CATTLE",
        "DXD_YOUNG",
        "DXB_YOUNG",
        "DAIRY_ORIGIN_YOUNG",
        "BXB_YOUNG",
        "IS_DAIRY_SUPPORT_G0",
        "IS_BXB_SUPPORT_G0",
        "NO_ADULT_RECEIVER",
        "ZERO_DAIRY_WITH_DAIRY_ORIGIN",
        "ZERO_SUCKLER_WITH_BXB",
        "BXB_CALVES_PER_SUCKLER_COW",
        "DAIRY_ORIGIN_CALVES_PER_DAIRY_COW",
        "DAFM_TYPE_MATCHED",
        "DAFM_TYPE_TOTAL",
        "DAFM_DAIRY_COUNT",
        "DAFM_BEEF_COUNT",
        "DAFM_DAIRY_SHARE",
        "MODEL_DAIRY_TYPE_SHARE",
        "DAFM_DAIRY_SHARE_RESIDUAL",
    ]
    y2020[ed_columns].to_csv(
        OUTPUT_DIR / "cattle_genetics_ed_2020.csv", index=False
    )
    matched_type.sort_values(
        "DAFM_DAIRY_SHARE_RESIDUAL",
        key=lambda s: s.abs(),
        ascending=False,
    )[
        [
            "CSOED",
            "County",
            "ED",
            "TOTAL_CATTLE",
            "DAIRY_COW",
            "OTHER_COW",
            "OTHER_CATTLE",
            "DAIRY_ORIGIN_YOUNG",
            "BXB_YOUNG",
            "DAFM_TYPE_TOTAL",
            "DAFM_DAIRY_SHARE",
            "MODEL_DAIRY_TYPE_SHARE",
            "DAFM_DAIRY_SHARE_RESIDUAL",
        ]
    ].to_csv(OUTPUT_DIR / "cattle_genetics_dafm_type_check_2020.csv", index=False)

    suckler_ratio = y2020.loc[
        y2020["OTHER_COW"] > 0, "BXB_CALVES_PER_SUCKLER_COW"
    ].dropna()
    dairy_ratio = y2020.loc[
        y2020["DAIRY_COW"] > 0, "DAIRY_ORIGIN_CALVES_PER_DAIRY_COW"
    ].dropna()

    total_dairy_origin = float(y2020["DAIRY_ORIGIN_YOUNG"].sum())
    total_bxb = float(y2020["BXB_YOUNG"].sum())
    no_adult = y2020["NO_ADULT_RECEIVER"]

    summary = pd.DataFrame(
        [
            {"METRIC": "ed_count_2020", "VALUE": len(y2020)},
            {"METRIC": "g0_dairy_support_ed_count", "VALUE": len(dairy_support)},
            {
                "METRIC": "aim_genetic_signature_matched_ed_count",
                "VALUE": int(aim_signature["AIM_TYPE_MATCHED"].sum()),
            },
            {
                "METRIC": "aim_genetic_signature_local_valid_ed_count",
                "VALUE": int(aim_signature["AIM_LOCAL_SIGNAL_VALID"].sum()),
            },
            {
                "METRIC": "aim_genetic_signature_county_fallback_ed_count",
                "VALUE": int((~aim_signature["AIM_LOCAL_SIGNAL_VALID"]).sum()),
            },
            {
                "METRIC": "aim_genetic_signature_q_national",
                "VALUE": float(q_national),
            },
            {
                "METRIC": "dafm_type_matched_ed_count",
                "VALUE": int(matched_type.shape[0]),
            },
            {
                "METRIC": "dafm_type_matched_model_cattle_share",
                "VALUE": matched_model_cattle_share,
            },
            {
                "METRIC": "g0_dafm_type_model_spearman_rho",
                "VALUE": g0_type_spearman,
            },
            {
                "METRIC": "g0_dafm_type_weighted_mae_percentage_points",
                "VALUE": g0_type_mae_pp,
            },
            {
                "METRIC": "g1_dafm_type_model_spearman_rho",
                "VALUE": type_spearman,
            },
            {
                "METRIC": "g1_dafm_type_weighted_mae_percentage_points",
                "VALUE": type_mae_pp,
            },
            {"METRIC": "g0_bxb_support_ed_count", "VALUE": len(bxb_support)},
            {
                "METRIC": "no_adult_receiver_ed_count",
                "VALUE": int(no_adult.sum()),
            },
            {
                "METRIC": "zero_dairy_ed_with_dairy_origin_count",
                "VALUE": int(y2020["ZERO_DAIRY_WITH_DAIRY_ORIGIN"].sum()),
            },
            {
                "METRIC": "zero_suckler_ed_with_bxb_count",
                "VALUE": int(y2020["ZERO_SUCKLER_WITH_BXB"].sum()),
            },
            {
                "METRIC": "dxd_share_in_zero_dairy_eds",
                "VALUE": (
                    float(y2020.loc[y2020["DAIRY_COW"].eq(0), "DXD_YOUNG"].sum())
                    / float(y2020["DXD_YOUNG"].sum())
                    if float(y2020["DXD_YOUNG"].sum()) > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "dxb_share_in_suckler_only_eds",
                "VALUE": (
                    float(
                        y2020.loc[
                            y2020["DAIRY_COW"].eq(0) & y2020["OTHER_COW"].gt(0),
                            "DXB_YOUNG",
                        ].sum()
                    )
                    / float(y2020["DXB_YOUNG"].sum())
                    if float(y2020["DXB_YOUNG"].sum()) > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "dairy_origin_share_in_zero_dairy_eds",
                "VALUE": (
                    float(
                        y2020.loc[
                            y2020["DAIRY_COW"].eq(0), "DAIRY_ORIGIN_YOUNG"
                        ].sum()
                    )
                    / total_dairy_origin
                    if total_dairy_origin > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_share_in_zero_suckler_eds",
                "VALUE": (
                    float(y2020.loc[y2020["OTHER_COW"].eq(0), "BXB_YOUNG"].sum())
                    / total_bxb
                    if total_bxb > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "dairy_origin_share_in_no_adult_receivers",
                "VALUE": (
                    float(y2020.loc[no_adult, "DAIRY_ORIGIN_YOUNG"].sum())
                    / total_dairy_origin
                    if total_dairy_origin > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_share_in_no_adult_receivers",
                "VALUE": (
                    float(y2020.loc[no_adult, "BXB_YOUNG"].sum())
                    / total_bxb
                    if total_bxb > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_calves_per_suckler_median",
                "VALUE": float(suckler_ratio.median()),
            },
            {
                "METRIC": "bxb_calves_per_suckler_p95",
                "VALUE": float(suckler_ratio.quantile(0.95)),
            },
            {
                "METRIC": "bxb_calves_per_suckler_p99",
                "VALUE": float(suckler_ratio.quantile(0.99)),
            },
            {
                "METRIC": "bxb_calves_per_suckler_max",
                "VALUE": float(suckler_ratio.max()),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_median",
                "VALUE": float(dairy_ratio.median()),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_p95",
                "VALUE": float(dairy_ratio.quantile(0.95)),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_p99",
                "VALUE": float(dairy_ratio.quantile(0.99)),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_max",
                "VALUE": float(dairy_ratio.max()),
            },
            {
                "METRIC": "dairy_origin_top_1pct_share",
                "VALUE": _top_share(y2020["DAIRY_ORIGIN_YOUNG"], 0.01),
            },
            {
                "METRIC": "dairy_origin_top_5pct_share",
                "VALUE": _top_share(y2020["DAIRY_ORIGIN_YOUNG"], 0.05),
            },
            {
                "METRIC": "bxb_top_1pct_share",
                "VALUE": _top_share(y2020["BXB_YOUNG"], 0.01),
            },
            {
                "METRIC": "bxb_top_5pct_share",
                "VALUE": _top_share(y2020["BXB_YOUNG"], 0.05),
            },
        ]
    )
    summary.to_csv(OUTPUT_DIR / "cattle_genetics_summary.csv", index=False)

    # EDs with other cattle but no adult cows (none in the Stage 00 inputs; 50
    # in v1.1, all suppressed cells stored as zero; the count is reported in
    # the summary) may carry both origins, but genetics must never create
    # cattle outside OTHER_CATTLE.
    if (
        y2020.loc[no_adult, "DAIRY_ORIGIN_YOUNG"] > y2020.loc[no_adult, "OTHER_CATTLE"]
    ).any():
        raise AssertionError("receiver dairy-origin allocation exceeds OTHER_CATTLE")
    if (
        y2020.loc[no_adult, "BXB_YOUNG"] > y2020.loc[no_adult, "OTHER_CATTLE"]
    ).any():
        raise AssertionError("receiver BxB allocation exceeds OTHER_CATTLE")

    print("Cattle genetics diagnostics")
    print(summary.to_string(index=False))
    print("National genetic margin max absolute difference:", int(national["DIFF"].abs().max()))
    print("G1 DAFM type calibration comparison, worst 15 absolute share residuals")
    print(
        matched_type.assign(
            ABS_RESIDUAL=matched_type["DAFM_DAIRY_SHARE_RESIDUAL"].abs()
        )
        .nlargest(15, "ABS_RESIDUAL")[
            [
                "CSOED",
                "County",
                "ED",
                "TOTAL_CATTLE",
                "DAIRY_COW",
                "OTHER_COW",
                "OTHER_CATTLE",
                "DAFM_DAIRY_SHARE",
                "MODEL_DAIRY_TYPE_SHARE",
                "DAFM_DAIRY_SHARE_RESIDUAL",
            ]
        ]
        .to_string(index=False)
    )
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_summary.csv")
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_ed_2020.csv")
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_national_margins.csv")
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_dafm_type_check_2020.csv")


if __name__ == "__main__":
    run()
