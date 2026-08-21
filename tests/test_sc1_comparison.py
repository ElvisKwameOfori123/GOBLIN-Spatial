from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.scenario.comparison import (
    build_sc1_robust_exposure,
    compare_sc1_to_prorata,
    summarise_sc1_redistribution,
)


def _runs() -> pd.DataFrame:
    rows = []
    # Same two EDs under two pathways x two allocation rules.
    specs = {
        ("SI_SG", "PRORATA"): [(40, 400.0), (60, 600.0)],
        ("SI_SG", "DAIRY_PROTECTION"): [(30, 300.0), (70, 700.0)],
        ("BE_SG", "PRORATA"): [(50, 500.0), (50, 500.0)],
        ("BE_SG", "DAIRY_PROTECTION"): [(35, 350.0), (65, 650.0)],
    }
    for (scenario, rule), values in specs.items():
        for idx, (cattle_loss, so_loss) in enumerate(values, start=1):
            rows.append(
                {
                    "CSOED": str(idx),
                    "PATHWAY_NAME": scenario,
                    "PATHWAY_ALLOCATION_RULE": rule,
                    "BASE_TOTAL_CATTLE": 100,
                    "CUMULATIVE_REDUCTION_TOTAL_CATTLE": cattle_loss,
                    "BASE_SO_LIVESTOCK_2020_EUR": 1000.0,
                    "SO_LIVESTOCK_EXPOSURE_2020_EUR": so_loss,
                    "GOBLIN_RELEASED_GRASSLAND_HA": float(cattle_loss),
                }
            )
    return pd.DataFrame(rows)


def test_protection_and_displacement_are_measured_against_same_scenario_prorata() -> None:
    compared = compare_sc1_to_prorata(_runs())
    si = compared.loc[
        compared["PATHWAY_NAME"].eq("SI_SG")
        & compared["PATHWAY_ALLOCATION_RULE"].eq("DAIRY_PROTECTION")
    ].sort_values("CSOED")

    assert si["PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_HEAD"].tolist() == [10.0, 0.0]
    assert si["DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_HEAD"].tolist() == [0.0, 10.0]
    assert np.isclose(
        si["SIGNED_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD"].sum(),
        0.0,
    )


def test_redistribution_summary_closes_for_physical_reduction() -> None:
    compared = compare_sc1_to_prorata(_runs())
    summary = summarise_sc1_redistribution(compared)
    alt = summary.loc[
        summary["PATHWAY_NAME"].eq("SI_SG")
        & summary["PATHWAY_ALLOCATION_RULE"].eq("DAIRY_PROTECTION")
    ].iloc[0]
    assert alt["TOTAL_PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_HEAD"] == 10.0
    assert alt["TOTAL_DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_HEAD"] == 10.0
    assert np.isclose(alt["NET_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD"], 0.0)


def test_robust_exposure_reports_lower_bound_and_sensitivity_without_invented_threshold() -> None:
    robust = build_sc1_robust_exposure(_runs()).set_index("CSOED")

    assert robust.loc["1", "RUN_COUNT"] == 4
    assert robust.loc["1", "ROBUST_MIN_CATTLE_REDUCTION_PCT"] == 30.0
    assert robust.loc["2", "ROBUST_MIN_CATTLE_REDUCTION_PCT"] == 50.0
    assert robust.loc["1", "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT"] == 10.0
    assert robust.loc["1", "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT"] == 15.0
    assert "ROBUSTLY_EXPOSED_CATTLE" not in robust.columns


def test_robust_classification_requires_explicit_threshold() -> None:
    robust = build_sc1_robust_exposure(
        _runs(),
        cattle_reduction_pct_threshold=40.0,
        so_loss_pct_threshold=40.0,
    ).set_index("CSOED")

    assert not bool(robust.loc["1", "ROBUSTLY_EXPOSED_CATTLE"])
    assert bool(robust.loc["2", "ROBUSTLY_EXPOSED_CATTLE"])
    assert not bool(robust.loc["1", "ROBUSTLY_EXPOSED_SO"])
    assert bool(robust.loc["2", "ROBUSTLY_EXPOSED_SO"])
