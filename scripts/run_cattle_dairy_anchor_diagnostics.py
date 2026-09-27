#!/usr/bin/env python
"""Compare the legacy and AIM-informed 2020 dairy-anchor reconciliations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.age_sex import _normalise_ed_name
from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.cattle.panel import _normalise_county, build_cattle_panel
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/validation/historical"

FOLDS = {
    1: ["Clare", "Cork", "Longford", "Louth", "Wicklow"],
    2: ["Donegal", "Galway", "Laois", "Monaghan", "Waterford"],
    3: ["Carlow", "Limerick", "Meath", "Sligo", "Westmeath"],
    4: ["Dublin", "Kerry", "Mayo", "Offaly", "Tipperary"],
    5: ["Cavan", "Kildare", "Kilkenny", "Leitrim", "Roscommon", "Wexford"],
}

AGE_SEX = [
    "BULLS",
    "CATTLE_MALE_UNDER_1",
    "CATTLE_FEMALE_UNDER_1",
    "CATTLE_MALE_1_2",
    "CATTLE_FEMALE_1_2",
    "CATTLE_MALE_2_PLUS",
    "CATTLE_FEMALE_2_PLUS",
]


def _config_variant(
    cfg,
    *,
    spatial_mode: str | None = None,
    dairy_mode: str | None = None,
    age_mode: str | None = None,
    exclude_2010_zero: bool | None = None,
    min_new_herd: int | None = None,
):
    raw = deepcopy(cfg.raw)
    cattle = raw.setdefault("cattle", {})
    if spatial_mode is not None:
        cattle["spatial_weights"] = spatial_mode
    if dairy_mode is not None:
        cattle["dairy_anchor_prior"] = dairy_mode
    if age_mode is not None:
        cattle["age_sex_prior"] = age_mode
    if exclude_2010_zero is not None:
        cattle["dairy_anchor_exclude_2010_zero"] = bool(exclude_2010_zero)
    if min_new_herd is not None:
        cattle["dairy_anchor_min_new_herd"] = int(min_new_herd)
    return replace(cfg, raw=raw)


def _eligible(frame: pd.DataFrame) -> pd.Series:
    lsu_max = (
        frame["DAIRY_COW"]
        + 0.8 * frame["OTHER_COW"]
        + frame["OTHER_CATTLE"]
        + 0.1 * frame["TOTAL_SHEEP"]
    )
    return (
        frame["TOTAL_CATTLE"].gt(0)
        & frame["LSU"].gt(0)
        & frame["LSU"].le(lsu_max + 1.0)
    )


def _lsu_residual(frame: pd.DataFrame) -> pd.Series:
    modelled = (
        frame["DAIRY_COW"]
        + 0.8 * frame["OTHER_COW"]
        + frame["BULLS"]
        + 0.4 * (frame["CATTLE_MALE_UNDER_1"] + frame["CATTLE_FEMALE_UNDER_1"])
        + 0.7 * (frame["CATTLE_MALE_1_2"] + frame["CATTLE_FEMALE_1_2"])
        + frame["CATTLE_MALE_2_PLUS"]
        + 0.8 * frame["CATTLE_FEMALE_2_PLUS"]
        + 0.1 * frame["TOTAL_SHEEP"]
    )
    return frame["LSU"] - modelled


def _aim_type_frame(cfg, published: pd.DataFrame) -> pd.DataFrame:
    dafm = pd.read_csv(cfg.files["dafm_aim_ed_cattle_profile_2020"])
    dafm["County"] = dafm["COUNTY"].map(_normalise_county)
    dafm["_KEY"] = dafm["ELECTORAL_DIVISION"].map(_normalise_ed_name)
    low = dafm["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )
    local = (
        dafm.loc[~low]
        .groupby(["County", "_KEY"])[
            ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]
        ]
        .sum()
    )

    rows = []
    for _, row in published.iterrows():
        county = _normalise_county(row["County"])
        keys = {
            _normalise_ed_name(part)
            for part in str(row["ED"]).split("/")
            if _normalise_ed_name(part)
        }
        total = 0.0
        dairy = 0.0
        matched = False
        for key in keys:
            lookup = (county, key)
            if lookup in local.index:
                values = local.loc[lookup]
                total += float(values["AVERAGE_NUMBER_CATTLE"])
                dairy += float(values["AVERAGE_CATTLE_DAIRY"])
                matched = True
        rows.append(
            {
                "CSOED": row["CSOED"],
                "AIM_MATCHED": matched,
                "AIM_TOTAL": total,
                "AIM_DAIRY": dairy,
                "AIM_DAIRY_SHARE": dairy / total if matched and total > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("CSOED")


def _anchor_metrics(
    label: str,
    panel: pd.DataFrame,
    published: pd.DataFrame,
    aim: pd.DataFrame,
    dairy_2010: pd.Series,
) -> tuple[dict[str, object], pd.DataFrame]:
    y = panel.loc[panel["YEAR"].eq(2020)].set_index("CSOED").copy()
    pub = published.set_index("CSOED")
    idx = y.index.intersection(pub.index)

    published_dairy = pub.loc[idx, "DAIRY_COW"].astype(int)
    reconciled = y.loc[idx, "DAIRY_COW"].astype(int)
    addition = reconciled - published_dairy

    if (addition < 0).any():
        raise AssertionError(f"{label}: a published dairy count was reduced")
    if int(addition.sum()) != 187_716:
        raise AssertionError(f"{label}: dairy county-gap total changed")
    if (y["OTHER_CATTLE"] < 0).any():
        raise AssertionError(f"{label}: negative OTHER_CATTLE")

    pub_positive = published_dairy.gt(0)
    ratios = (
        reconciled.loc[pub_positive].astype(float)
        / published_dairy.loc[pub_positive].astype(float)
    )

    zero_added = published_dairy.eq(0) & reconciled.gt(0)
    dairy2010_aligned = pd.Series(
        [dairy_2010.get(canonical_ed_key(value), np.nan) for value in idx],
        index=idx,
        dtype=float,
    )
    zero_2010 = dairy2010_aligned.eq(0)
    added_to_2010_zero = published_dairy.eq(0) & zero_2010 & reconciled.gt(0)
    token_added = published_dairy.eq(0) & reconciled.between(1, 9)

    no_adult = (
        y["DAIRY_COW"].eq(0)
        & y["OTHER_COW"].eq(0)
        & y["OTHER_CATTLE"].gt(0)
    )

    positive_add = addition.loc[addition.gt(0)].sort_values(ascending=False)
    top1_n = max(1, int(np.ceil(0.01 * len(addition))))
    top5_n = max(1, int(np.ceil(0.05 * len(addition))))

    matched_ids = aim.index[aim["AIM_MATCHED"] & aim["AIM_DAIRY_SHARE"].notna()]
    common = y.index.intersection(matched_ids)
    model_share = y.loc[common, "DAIRY_COW"] / y.loc[common, "TOTAL_CATTLE"]
    broad_share = aim.loc[common, "AIM_DAIRY_SHARE"]
    rho = float(model_share.corr(broad_share, method="spearman"))

    metric = {
        "MODEL": label,
        "PUBLISHED_DAIRY_SUM": int(published_dairy.sum()),
        "RECONCILED_DAIRY_SUM": int(reconciled.sum()),
        "TOTAL_GAP_ADDED": int(addition.sum()),
        "PUBLISHED_ZERO_EDS_GAINING_DAIRY": int(zero_added.sum()),
        "GAP_HEAD_TO_PUBLISHED_ZERO_EDS": int(addition.loc[zero_added].sum()),
        "GAP_SHARE_TO_PUBLISHED_ZERO_EDS": float(
            addition.loc[zero_added].sum() / addition.sum()
        ),
        "PUBLISHED_ZERO_2010_ZERO_EDS_GAINING_DAIRY": int(
            added_to_2010_zero.sum()
        ),
        "GAP_HEAD_TO_2010_PUBLISHED_ZERO_EDS": int(
            addition.loc[added_to_2010_zero].sum()
        ),
        "PUBLISHED_ZERO_EDS_RECEIVING_1_TO_9_COWS": int(token_added.sum()),
        "NO_ADULT_COW_RECEIVER_EDS": int(no_adult.sum()),
        "MAX_POSITIVE_ED_SCALE_FACTOR": float(ratios.max()),
        "P95_POSITIVE_ED_SCALE_FACTOR": float(ratios.quantile(0.95)),
        "TOP_1PCT_GAP_SHARE": float(positive_add.head(top1_n).sum() / addition.sum()),
        "TOP_5PCT_GAP_SHARE": float(positive_add.head(top5_n).sum() / addition.sum()),
        "AIM_BROAD_DAIRY_SHARE_SPEARMAN": rho,
    }

    detail = pd.DataFrame(
        {
            "CSOED": idx,
            "County": y.loc[idx, "County"].to_numpy(),
            "ED": y.loc[idx, "ED"].to_numpy(),
            "PUBLISHED_DAIRY_COW": published_dairy.to_numpy(),
            f"{label}_DAIRY_COW": reconciled.to_numpy(),
            f"{label}_ADDITION": addition.to_numpy(),
            "TOTAL_CATTLE": y.loc[idx, "TOTAL_CATTLE"].to_numpy(),
            "OTHER_COW": y.loc[idx, "OTHER_COW"].to_numpy(),
            "OTHER_CATTLE": y.loc[idx, "OTHER_CATTLE"].to_numpy(),
        }
    )
    return metric, detail


def _age_lsu_metrics(cfg) -> pd.DataFrame:
    rows = []
    for age_mode in ("flat_county", "dafm_log_odds"):
        panel = build_cattle_panel(
            _config_variant(
                cfg,
                spatial_mode="two_anchor_2010_2020",
                dairy_mode="aim_residual",
                age_mode=age_mode,
                exclude_2010_zero=False,
                min_new_herd=10,
            )
        )
        y = panel.loc[panel["YEAR"].eq(2020)].copy()
        eligible = _eligible(y)
        diagnostic = y["TOTAL_CATTLE"].gt(0) & y["LSU"].gt(0)
        rows.append(
            {
                "AGE_MODE": age_mode,
                "SCOPE": "POOLED",
                "ELIGIBLE_N": int(eligible.sum()),
                "DIAGNOSTIC_N": int(diagnostic.sum()),
                "ELIGIBLE_SHARE": float(eligible.sum() / diagnostic.sum()),
                "MEDIAN_ABS_LSU_RESIDUAL": float(
                    _lsu_residual(y.loc[eligible]).abs().median()
                ),
            }
        )
        for fold, counties in FOLDS.items():
            mask = eligible & y["County"].isin(counties)
            rows.append(
                {
                    "AGE_MODE": age_mode,
                    "SCOPE": f"FOLD_{fold}",
                    "ELIGIBLE_N": int(mask.sum()),
                    "DIAGNOSTIC_N": int(
                        (diagnostic & y["County"].isin(counties)).sum()
                    ),
                    "ELIGIBLE_SHARE": float(
                        mask.sum()
                        / max(1, int((diagnostic & y["County"].isin(counties)).sum()))
                    ),
                    "MEDIAN_ABS_LSU_RESIDUAL": float(
                        _lsu_residual(y.loc[mask]).abs().median()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _spatial_difference(
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
    label: str,
) -> pd.DataFrame:
    """Return fraction of each national component placed in different EDs."""

    keys = ["YEAR", "CSOED"]
    components = ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]
    merged = reference[keys + components].merge(
        candidate[keys + components],
        on=keys,
        suffixes=("_REF", "_CAND"),
        validate="one_to_one",
    )
    rows = []
    for year, frame in merged.groupby("YEAR"):
        for component in components:
            ref = frame[f"{component}_REF"].to_numpy(dtype=float)
            cand = frame[f"{component}_CAND"].to_numpy(dtype=float)
            total = float(ref.sum())
            displaced = (
                float(np.abs(cand - ref).sum()) / (2.0 * total)
                if total > 0
                else 0.0
            )
            rows.append(
                {
                    "VARIANT": label,
                    "YEAR": int(year),
                    "COMPONENT": component,
                    "DISPLACED_SHARE_VS_NULL": displaced,
                    "NATIONAL_TOTAL_DIFFERENCE": int(round(cand.sum() - ref.sum())),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_config(CONFIG)
    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["DAIRY_COW"] = pd.to_numeric(
        published["DAIRY_COW"], errors="raise"
    ).astype(int)

    null = build_cattle_panel(
        _config_variant(
            cfg,
            spatial_mode="fixed_2020",
            dairy_mode="positive_proportional",
            exclude_2010_zero=False,
            min_new_herd=0,
        )
    )
    two_anchor_legacy = build_cattle_panel(
        _config_variant(
            cfg,
            spatial_mode="two_anchor_2010_2020",
            dairy_mode="positive_proportional",
            exclude_2010_zero=False,
            min_new_herd=0,
        )
    )
    aim_residual = build_cattle_panel(
        _config_variant(
            cfg,
            spatial_mode="two_anchor_2010_2020",
            dairy_mode="aim_residual",
            exclude_2010_zero=False,
            min_new_herd=10,
        )
    )
    aim_residual_2010_zero = build_cattle_panel(
        _config_variant(
            cfg,
            spatial_mode="two_anchor_2010_2020",
            dairy_mode="aim_residual",
            exclude_2010_zero=True,
            min_new_herd=10,
        )
    )
    aim = _aim_type_frame(cfg, published)

    source_2010 = pd.read_csv(
        cfg.files["cso_ed_2010"], dtype=str, keep_default_na=False
    )
    dairy_2010_text = source_2010["DAIRY_COW"].astype(str).str.strip()
    dairy_2010_values = pd.to_numeric(
        dairy_2010_text.mask(dairy_2010_text.eq("")), errors="raise"
    )
    dairy_2010 = pd.Series(
        dairy_2010_values.to_numpy(dtype=float),
        index=source_2010["CSOED"].map(canonical_ed_key),
    )

    null_metric, null_detail = _anchor_metrics(
        "NULL_FIXED_2020_LEGACY", null, published, aim, dairy_2010
    )
    aim_metric, aim_detail = _anchor_metrics(
        "AIM_RESIDUAL", aim_residual, published, aim, dairy_2010
    )
    sensitivity_metric, _ = _anchor_metrics(
        "AIM_RESIDUAL_EXCLUDE_2010_ZERO",
        aim_residual_2010_zero,
        published,
        aim,
        dairy_2010,
    )
    summary = pd.DataFrame([null_metric, aim_metric, sensitivity_metric])

    detail = null_detail.merge(
        aim_detail[
            [
                "CSOED",
                "AIM_RESIDUAL_DAIRY_COW",
                "AIM_RESIDUAL_ADDITION",
            ]
        ],
        on="CSOED",
        how="left",
        validate="one_to_one",
    ).join(aim[["AIM_MATCHED", "AIM_TOTAL", "AIM_DAIRY", "AIM_DAIRY_SHARE"]], on="CSOED")

    lsu = _age_lsu_metrics(cfg)

    # Hard acceptance checks for the candidate.
    candidate = summary.loc[summary["MODEL"].eq("AIM_RESIDUAL")].iloc[0]
    null_row = summary.loc[summary["MODEL"].eq("NULL_FIXED_2020_LEGACY")].iloc[0]
    if int(candidate["NO_ADULT_COW_RECEIVER_EDS"]) != 51:
        raise AssertionError("AIM dairy anchor changed the 51 no-adult receiver EDs")
    if int(candidate["PUBLISHED_ZERO_EDS_RECEIVING_1_TO_9_COWS"]) != 0:
        raise AssertionError("AIM dairy anchor created a sub-10-cow token dairy herd")
    if float(candidate["MAX_POSITIVE_ED_SCALE_FACTOR"]) >= float(
        null_row["MAX_POSITIVE_ED_SCALE_FACTOR"]
    ):
        raise AssertionError("AIM dairy anchor did not reduce maximum positive-ED inflation")

    a0 = lsu.loc[(lsu["AGE_MODE"] == "flat_county") & (lsu["SCOPE"] == "POOLED")].iloc[0]
    a1 = lsu.loc[(lsu["AGE_MODE"] == "dafm_log_odds") & (lsu["SCOPE"] == "POOLED")].iloc[0]
    if float(a1["ELIGIBLE_SHARE"]) < float(a0["ELIGIBLE_SHARE"]) - 0.01:
        raise AssertionError("AIM dairy anchor causes A1 to fail the LSU eligibility gate")
    if float(a1["MEDIAN_ABS_LSU_RESIDUAL"]) >= float(a0["MEDIAN_ABS_LSU_RESIDUAL"]):
        raise AssertionError("A1 no longer improves pooled LSU residual under AIM dairy anchor")

    for fold in range(1, 6):
        f0 = lsu.loc[
            (lsu["AGE_MODE"] == "flat_county") & (lsu["SCOPE"] == f"FOLD_{fold}")
        ].iloc[0]
        f1 = lsu.loc[
            (lsu["AGE_MODE"] == "dafm_log_odds") & (lsu["SCOPE"] == f"FOLD_{fold}")
        ].iloc[0]
        if float(f1["MEDIAN_ABS_LSU_RESIDUAL"]) >= float(
            f0["MEDIAN_ABS_LSU_RESIDUAL"]
        ):
            raise AssertionError(f"A1 fails LSU fold {fold} under AIM dairy anchor")

    refinements = pd.concat(
        [
            _spatial_difference(null, two_anchor_legacy, "TWO_ANCHOR_ONLY"),
            _spatial_difference(null, aim_residual, "TWO_ANCHOR_PLUS_AIM_DAIRY"),
        ],
        ignore_index=True,
    )
    # All refinements must preserve the same annual national totals as the null.
    if not refinements["NATIONAL_TOTAL_DIFFERENCE"].eq(0).all():
        raise AssertionError("baseline refinement changed an annual national cattle total")

    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / "cattle_dairy_anchor_comparison.csv", index=False)
    detail.to_csv(OUT / "cattle_dairy_anchor_ed_2020.csv", index=False)
    lsu.to_csv(OUT / "cattle_dairy_anchor_lsu.csv", index=False)
    refinements.to_csv(
        OUT / "cattle_baseline_refinement_comparison.csv", index=False
    )

    focus = detail.loc[
        detail["ED"].isin(["Carrigallen East", "Rockhill", "Hopestown"])
    ].copy()

    print("Cattle dairy-anchor comparison")
    print(summary.to_string(index=False))
    print("\nBaseline refinement displacement versus frozen null")
    print(
        refinements.loc[
            refinements["COMPONENT"].eq("TOTAL_CATTLE")
            | refinements["COMPONENT"].eq("DAIRY_COW")
        ].to_string(index=False)
    )
    print("\nLSU comparison under AIM-residual dairy anchor")
    print(lsu.to_string(index=False))
    print("\nKnown high-inflation EDs")
    print(
        focus[
            [
                "County",
                "ED",
                "PUBLISHED_DAIRY_COW",
                "NULL_FIXED_2020_LEGACY_DAIRY_COW",
                "AIM_RESIDUAL_DAIRY_COW",
                "AIM_DAIRY",
                "AIM_TOTAL",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
