#!/usr/bin/env python
"""Code 2 diagnostics: two-anchor 2010->2020 cattle spatial reconstruction.

This script compares the frozen Code 1 null (fixed 2020 ED shares applied to
every AAA10 county year) with Code 2 (2010->2020 time-weighted ED shares for
2015-2019, exact 2020 anchor, fixed 2020 shares thereafter).

Only the four main cattle quantities are evaluated:
DAIRY_COW, OTHER_COW, OTHER_CATTLE and TOTAL_CATTLE.
No AIM evidence, age-sex result or genetic result is used in the comparison.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.panel import (
    SPATIAL_COMPONENTS,
    _load_aaa10,
    build_cattle_panel,
)
from goblin_spatial.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/validation/historical"

MAIN = ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]


def _variant(cfg, spatial_mode: str):
    raw = deepcopy(cfg.raw)
    cattle = raw.setdefault("cattle", {})
    cattle["spatial_weights"] = spatial_mode

    # Code 2 is a population-stage comparison only. The age-sex layer is not
    # part of the test, so use the flat county prior to avoid bringing AIM into
    # this diagnostic.
    cattle["age_sex_prior"] = "flat_county"
    return replace(cfg, raw=raw)


def _county_closure(panel: pd.DataFrame, county: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in range(2015, 2026):
        observed = (
            panel.loc[panel["YEAR"].eq(year)]
            .groupby("County")[MAIN]
            .sum()
            .sort_index()
        )
        target = county.loc[county["Year"].eq(year)].set_index("County").sort_index()
        other_target = (
            target["Total cattle__HEAD"]
            - target["Dairy cows__HEAD"]
            - target["Other cows__HEAD"]
        )
        expected = pd.DataFrame(
            {
                "DAIRY_COW": target["Dairy cows__HEAD"].astype(int),
                "OTHER_COW": target["Other cows__HEAD"].astype(int),
                "OTHER_CATTLE": other_target.astype(int),
                "TOTAL_CATTLE": target["Total cattle__HEAD"].astype(int),
            }
        ).loc[observed.index]

        diff = observed - expected
        for county_name in observed.index:
            rows.append(
                {
                    "YEAR": year,
                    "County": county_name,
                    "MAX_ABS_DIFFERENCE": int(diff.loc[county_name].abs().max()),
                }
            )
    return pd.DataFrame(rows)


def _displacement(null: pd.DataFrame, code2: pd.DataFrame) -> pd.DataFrame:
    merged = null[["YEAR", "CSOED", *MAIN]].merge(
        code2[["YEAR", "CSOED", *MAIN]],
        on=["YEAR", "CSOED"],
        suffixes=("_N0", "_N1"),
        validate="one_to_one",
    )

    rows = []
    for year, frame in merged.groupby("YEAR"):
        for component in MAIN:
            x = frame[f"{component}_N0"].to_numpy(dtype=float)
            y = frame[f"{component}_N1"].to_numpy(dtype=float)
            total = float(x.sum())
            rows.append(
                {
                    "YEAR": int(year),
                    "COMPONENT": component,
                    "DISPLACED_HEAD": int(round(np.abs(y - x).sum() / 2.0)),
                    "DISPLACED_SHARE": (
                        float(np.abs(y - x).sum() / (2.0 * total))
                        if total > 0
                        else 0.0
                    ),
                    "NATIONAL_TOTAL_N0": int(round(x.sum())),
                    "NATIONAL_TOTAL_N1": int(round(y.sum())),
                    "NATIONAL_TOTAL_DIFFERENCE": int(round(y.sum() - x.sum())),
                    "MAX_ED_ABS_DIFFERENCE": int(round(np.abs(y - x).max())),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_config(CONFIG)
    county = _load_aaa10(cfg.files["cso_cattle_county"])

    n0 = build_cattle_panel(_variant(cfg, "fixed_2020"))
    n1 = build_cattle_panel(_variant(cfg, "two_anchor_2010_2020"))

    # Fundamental panel contract.
    for label, panel in [("N0", n0), ("N1", n1)]:
        if len(panel) != 31_427:
            raise AssertionError(f"{label}: expected 31,427 rows")
        counts = panel.groupby("YEAR")["CSOED"].nunique()
        if not counts.eq(2_857).all():
            raise AssertionError(f"{label}: expected 2,857 EDs per year")
        if (panel[MAIN] < 0).any().any():
            raise AssertionError(f"{label}: negative cattle count")
        identity = (
            panel["DAIRY_COW"]
            + panel["OTHER_COW"]
            + panel["OTHER_CATTLE"]
            - panel["TOTAL_CATTLE"]
        )
        if int(identity.abs().max()) != 0:
            raise AssertionError(f"{label}: D + S + O != T")

    closure_n0 = _county_closure(n0, county)
    closure_n1 = _county_closure(n1, county)
    if int(closure_n0["MAX_ABS_DIFFERENCE"].max()) != 0:
        raise AssertionError("N0 does not close exactly to AAA10 county controls")
    if int(closure_n1["MAX_ABS_DIFFERENCE"].max()) != 0:
        raise AssertionError("N1 does not close exactly to AAA10 county controls")

    displacement = _displacement(n0, n1)

    # Code 2 should affect only the pre-2020 historical reconstruction.
    post = displacement.loc[displacement["YEAR"].between(2020, 2025)]
    if not post["DISPLACED_HEAD"].eq(0).all():
        raise AssertionError("Code 2 changed 2020-2025 values relative to the null")

    total_pre = displacement.loc[
        (displacement["COMPONENT"].eq("TOTAL_CATTLE"))
        & displacement["YEAR"].between(2015, 2019)
    ].sort_values("YEAR")
    if not np.all(np.diff(total_pre["DISPLACED_SHARE"].to_numpy()) < 0):
        raise AssertionError("Code 2 total-cattle displacement does not converge to 2020")

    if not displacement["NATIONAL_TOTAL_DIFFERENCE"].eq(0).all():
        raise AssertionError("Code 2 changed an annual national cattle total")

    OUT.mkdir(parents=True, exist_ok=True)
    displacement.to_csv(
        OUT / "cattle_code2_two_anchor_vs_null.csv",
        index=False,
    )
    closure_n1.to_csv(
        OUT / "cattle_code2_county_closure.csv",
        index=False,
    )

    national = (
        n1.groupby("YEAR")[MAIN]
        .sum()
        .reset_index()
    )
    national.to_csv(
        OUT / "cattle_code2_national_totals.csv",
        index=False,
    )

    print("Code 2: two-anchor cattle reconstruction versus frozen null")
    print(
        displacement.loc[
            displacement["COMPONENT"].eq("TOTAL_CATTLE")
        ][
            [
                "YEAR",
                "DISPLACED_HEAD",
                "DISPLACED_SHARE",
                "NATIONAL_TOTAL_N1",
                "NATIONAL_TOTAL_DIFFERENCE",
            ]
        ].to_string(index=False)
    )

    print("\nMain-cattle displacement, 2015-2019")
    print(
        displacement.loc[
            displacement["YEAR"].between(2015, 2019)
        ][
            [
                "YEAR",
                "COMPONENT",
                "DISPLACED_HEAD",
                "DISPLACED_SHARE",
                "MAX_ED_ABS_DIFFERENCE",
            ]
        ].to_string(index=False)
    )

    print("\nCounty closure maximum absolute difference:")
    print(int(closure_n1["MAX_ABS_DIFFERENCE"].max()))


if __name__ == "__main__":
    main()
