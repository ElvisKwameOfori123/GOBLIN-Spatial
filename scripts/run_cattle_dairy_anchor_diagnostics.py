#!/usr/bin/env python
"""Compare the legacy and AIM-informed 2020 dairy-anchor reconciliations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.age_sex import _normalise_ed_name
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


def _config_with_anchor(cfg, mode: str, age_mode: str | None = None):
    raw = deepcopy(cfg.raw)
    raw.setdefault("cattle", {})["dairy_anchor_prior"] = mode
    if age_mode is not None:
        raw["cattle"]["age_sex_prior"] = age_mode
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
            _config_with_anchor(cfg, "aim_residual", age_mode=age_mode)
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


def main() -> None:
    cfg = load_config(CONFIG)
    published = pd.read_csv(cfg.files["cso_ed_2020"])
    published["DAIRY_COW"] = pd.to_numeric(
        published["DAIRY_COW"], errors="raise"
    ).astype(int)

    legacy = build_cattle_panel(_config_with_anchor(cfg, "positive_proportional"))
    aim_residual = build_cattle_panel(_config_with_anchor(cfg, "aim_residual"))
    aim = _aim_type_frame(cfg, published)

    legacy_metric, legacy_detail = _anchor_metrics(
        "LEGACY_POSITIVE_ONLY", legacy, published, aim
    )
    aim_metric, aim_detail = _anchor_metrics(
        "AIM_RESIDUAL", aim_residual, published, aim
    )
    summary = pd.DataFrame([legacy_metric, aim_metric])

    detail = legacy_detail.merge(
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
    legacy_row = summary.loc[summary["MODEL"].eq("LEGACY_POSITIVE_ONLY")].iloc[0]
    if int(candidate["NO_ADULT_COW_RECEIVER_EDS"]) != 51:
        raise AssertionError("AIM dairy anchor changed the 51 no-adult receiver EDs")
    if float(candidate["MAX_POSITIVE_ED_SCALE_FACTOR"]) >= float(
        legacy_row["MAX_POSITIVE_ED_SCALE_FACTOR"]
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

    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / "cattle_dairy_anchor_comparison.csv", index=False)
    detail.to_csv(OUT / "cattle_dairy_anchor_ed_2020.csv", index=False)
    lsu.to_csv(OUT / "cattle_dairy_anchor_lsu.csv", index=False)

    focus = detail.loc[
        detail["ED"].isin(["Carrigallen East", "Rockhill", "Hopestown"])
    ].copy()

    print("Cattle dairy-anchor comparison")
    print(summary.to_string(index=False))
    print("\nLSU comparison under AIM-residual dairy anchor")
    print(lsu.to_string(index=False))
    print("\nKnown high-inflation EDs")
    print(
        focus[
            [
                "County",
                "ED",
                "PUBLISHED_DAIRY_COW",
                "LEGACY_POSITIVE_ONLY_DAIRY_COW",
                "AIM_RESIDUAL_DAIRY_COW",
                "AIM_DAIRY",
                "AIM_TOTAL",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
