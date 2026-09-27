"""Full-data tests for the two-anchor historical cattle reconstruction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.cattle.panel import (
    SPATIAL_COMPONENTS,
    _build_2020_baseline,
    _build_historical_spatial_weights,
    _load_aaa10,
    _load_cso_ed_2010,
    _weights_for_year,
    build_cattle_panel,
)
from goblin_spatial.config import load_config


pytestmark = pytest.mark.full_data

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"


def _config_with_mode(mode: str):
    cfg = load_config(CONFIG)
    raw = deepcopy(cfg.raw)
    raw.setdefault("cattle", {})["spatial_weights"] = mode
    return replace(cfg, raw=raw)


def _anchors():
    cfg = _config_with_mode("two_anchor_2010_2020")
    county = _load_aaa10(cfg.files["cso_cattle_county"])
    anchor = _build_2020_baseline(
        cfg.files["cso_ed_2020"], county, cfg.expected_eds
    )
    ed_2010 = _load_cso_ed_2010(cfg.files["cso_ed_2010"])
    weights = _build_historical_spatial_weights(anchor, ed_2010)
    return cfg, county, anchor, ed_2010, weights


def test_two_anchor_county_controls_and_accounting() -> None:
    cfg = _config_with_mode("two_anchor_2010_2020")
    panel = build_cattle_panel(cfg)
    county = _load_aaa10(cfg.files["cso_cattle_county"])

    assert len(panel) == 31_427
    assert (panel[list(SPATIAL_COMPONENTS)] >= 0).all().all()
    assert (
        panel["TOTAL_CATTLE"] == panel[list(SPATIAL_COMPONENTS)].sum(axis=1)
    ).all()

    for year in range(2015, 2026):
        observed = panel.loc[panel["YEAR"] == year].groupby("County")[
            ["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]
        ].sum()
        target = county.loc[county["Year"] == year].set_index("County")
        other_target = (
            target["Total cattle__HEAD"]
            - target["Dairy cows__HEAD"]
            - target["Other cows__HEAD"]
        )
        assert np.array_equal(
            observed["DAIRY_COW"].to_numpy(),
            target.loc[observed.index, "Dairy cows__HEAD"].to_numpy(dtype=int),
        )
        assert np.array_equal(
            observed["OTHER_COW"].to_numpy(),
            target.loc[observed.index, "Other cows__HEAD"].to_numpy(dtype=int),
        )
        assert np.array_equal(
            observed["OTHER_CATTLE"].to_numpy(),
            other_target.loc[observed.index].to_numpy(dtype=int),
        )
        assert np.array_equal(
            observed["TOTAL_CATTLE"].to_numpy(),
            target.loc[observed.index, "Total cattle__HEAD"].to_numpy(dtype=int),
        )


def test_two_anchor_2020_to_2025_matches_fixed_2020_value_for_value() -> None:
    two_anchor = build_cattle_panel(_config_with_mode("two_anchor_2010_2020"))
    fixed = build_cattle_panel(_config_with_mode("fixed_2020"))

    columns = [*SPATIAL_COMPONENTS, "TOTAL_CATTLE"]
    left = two_anchor.loc[two_anchor["YEAR"] >= 2020, ["YEAR", "CSOED", *columns]]
    right = fixed.loc[fixed["YEAR"] >= 2020, ["YEAR", "CSOED", *columns]]
    left = left.sort_values(["YEAR", "CSOED"]).reset_index(drop=True)
    right = right.sort_values(["YEAR", "CSOED"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_two_anchor_shares_close_are_bounded_and_move_in_equal_steps() -> None:
    _, _, anchor, _, weights = _anchors()

    for component in SPATIAL_COMPONENTS:
        s10_col = f"{component}_SHARE_2010"
        s20_col = f"{component}_SHARE_2020"

        assert float(
            (weights.groupby("County")[s10_col].sum() - 1.0).abs().max()
        ) < 1e-9
        assert float(
            (weights.groupby("County")[s20_col].sum() - 1.0).abs().max()
        ) < 1e-9

        annual = []
        for year in range(2015, 2021):
            shares = np.zeros(len(weights), dtype=float)
            for _, idx in anchor.groupby("County").groups.items():
                shares[idx] = _weights_for_year(weights, idx, component, year)
            lower = np.minimum(weights[s10_col].to_numpy(), weights[s20_col].to_numpy())
            upper = np.maximum(weights[s10_col].to_numpy(), weights[s20_col].to_numpy())
            assert (shares >= lower - 1e-12).all()
            assert (shares <= upper + 1e-12).all()
            annual.append(shares)

        increments = np.diff(np.vstack(annual), axis=0)
        assert float(np.abs(increments - increments[0]).max()) < 1e-12


def test_two_anchor_blank_rule_and_zero_support() -> None:
    cfg, _, anchor, ed_2010, weights = _anchors()
    source = ed_2010.set_index("_ED_KEY")
    panel = build_cattle_panel(cfg)

    for component in SPATIAL_COMPONENTS:
        v2010 = weights["_ED_KEY"].map(source[component])
        blank = v2010.isna().to_numpy()
        s10 = weights[f"{component}_SHARE_2010"].to_numpy()
        s20 = weights[f"{component}_SHARE_2020"].to_numpy()
        assert np.allclose(s10[blank], s20[blank], atol=0.0, rtol=0.0)

        zero_both = (s10 == 0) & (s20 == 0)
        zero_ids = set(weights.loc[zero_both, "CSOED"])
        if zero_ids:
            assert (
                panel.loc[panel["CSOED"].isin(zero_ids), component] == 0
            ).all()


def test_two_anchor_hamilton_outputs_follow_interpolated_quota_within_one_head() -> None:
    cfg, county, anchor, _, weights = _anchors()
    panel = build_cattle_panel(cfg)

    target_columns = {
        "DAIRY_COW": "Dairy cows__HEAD",
        "OTHER_COW": "Other cows__HEAD",
    }

    for year in range(2015, 2020):
        county_year = county.loc[county["Year"] == year].set_index("County")
        observed_year = panel.loc[panel["YEAR"] == year].set_index("CSOED")

        for component in SPATIAL_COMPONENTS:
            for county_name, idx in anchor.groupby("County").groups.items():
                shares = _weights_for_year(weights, idx, component, year)
                if component == "OTHER_CATTLE":
                    row = county_year.loc[county_name]
                    target = int(
                        row["Total cattle__HEAD"]
                        - row["Dairy cows__HEAD"]
                        - row["Other cows__HEAD"]
                    )
                else:
                    target = int(county_year.loc[county_name, target_columns[component]])

                expected = shares * target
                ids = anchor.loc[idx, "CSOED"]
                actual = observed_year.loc[ids, component].to_numpy(dtype=float)
                assert (np.abs(actual - expected) < 1.0 + 1e-12).all()


def test_two_anchor_difference_from_fixed_2020_shrinks_toward_2020() -> None:
    two_anchor = build_cattle_panel(_config_with_mode("two_anchor_2010_2020"))
    fixed = build_cattle_panel(_config_with_mode("fixed_2020"))
    merged = two_anchor.merge(
        fixed[["YEAR", "CSOED", "TOTAL_CATTLE"]],
        on=["YEAR", "CSOED"],
        suffixes=("", "_FIXED"),
        validate="one_to_one",
    )

    differences = []
    for year in range(2015, 2020):
        frame = merged.loc[merged["YEAR"] == year]
        differences.append(
            float((frame["TOTAL_CATTLE"] - frame["TOTAL_CATTLE_FIXED"]).abs().sum())
            / (2.0 * float(frame["TOTAL_CATTLE"].sum()))
        )

    assert all(np.diff(differences) < 0)
    assert differences[-1] > 0


def test_two_anchor_provenance_labels() -> None:
    panel = build_cattle_panel(_config_with_mode("two_anchor_2010_2020"))

    assert set(
        panel.loc[panel["YEAR"].between(2015, 2019), "LIVESTOCK_DATA_STATUS"]
    ) == {
        "RECONSTRUCTED_FROM_2010_2020_TIME_WEIGHTED_ED_SHARES_AND_ANNUAL_AAA10_COUNTY_CONTROLS"
    }
    assert set(panel.loc[panel["YEAR"] == 2020, "LIVESTOCK_DATA_STATUS"]) == {
        "FIXED_2020_RECONCILED_ANCHOR"
    }
    assert set(
        panel.loc[panel["YEAR"].between(2021, 2025), "LIVESTOCK_DATA_STATUS"]
    ) == {
        "RECONSTRUCTED_FROM_2020_ED_WEIGHTS_AND_ANNUAL_AAA10_COUNTY_CONTROLS"
    }
