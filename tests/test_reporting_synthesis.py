from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from goblin_spatial.synthesis.sc1_crossrun import (
    build_sc1_crossrun_synthesis,
    discover_sc1_runs,
    load_sc1_ensemble,
)


def _write_run(
    root: Path,
    *,
    scenario: str,
    rule: str,
    cattle: tuple[float, float],
    so_loss: tuple[float, float],
    release: tuple[float, float],
) -> None:
    run_dir = root / f"{scenario}_{rule}"
    run_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "CSOED": ["ED1", "ED2"],
            "PATHWAY_NAME": [scenario, scenario],
            "PATHWAY_ALLOCATION_RULE": [rule, rule],
            "BASE_TOTAL_CATTLE": [100.0, 100.0],
            "CUMULATIVE_REDUCTION_TOTAL_CATTLE": list(cattle),
            "BASE_SO_LIVESTOCK_2020_EUR": [1000.0, 1000.0],
            "SO_LIVESTOCK_EXPOSURE_2020_EUR": list(so_loss),
            "GOBLIN_RELEASED_GRASSLAND_HA": list(release),
        }
    ).to_csv(run_dir / "sc1_ed_results.csv", index=False)
    pd.DataFrame(
        [
            {
                "SCENARIO_ID": scenario,
                "RUN_START_YEAR": 2020,
                "TARGET_YEAR": 2050,
                "ALLOCATION_POLICY": rule,
                "PROTECTION_STRENGTH_LAMBDA": 0.5,
            }
        ]
    ).to_csv(run_dir / "sc1_control_summary.csv", index=False)


def _ensemble_root(tmp_path: Path) -> Path:
    root = tmp_path / "principal"
    _write_run(root, scenario="A", rule="PRORATA", cattle=(20, 10), so_loss=(200, 100), release=(12, 8))
    _write_run(root, scenario="A", rule="SOCIAL_VULNERABILITY_PROTECTION", cattle=(10, 20), so_loss=(100, 200), release=(7, 13))
    _write_run(root, scenario="B", rule="PRORATA", cattle=(30, 20), so_loss=(300, 200), release=(18, 12))
    _write_run(root, scenario="B", rule="SOCIAL_VULNERABILITY_PROTECTION", cattle=(20, 30), so_loss=(200, 300), release=(13, 17))
    return root


def test_frozen_sc1_runs_are_discovered_from_control_identity(tmp_path: Path) -> None:
    root = _ensemble_root(tmp_path)
    runs = discover_sc1_runs(root)
    assert {run.run_id for run in runs} == {
        "A__2020__PRORATA",
        "A__2020__SOCIAL_VULNERABILITY_PROTECTION",
        "B__2020__PRORATA",
        "B__2020__SOCIAL_VULNERABILITY_PROTECTION",
    }
    assert all(run.through_stage == "SC1" for run in runs)


def test_sc1_crossrun_synthesis_delegates_existing_scientific_diagnostics(tmp_path: Path) -> None:
    root = _ensemble_root(tmp_path)
    ensemble = load_sc1_ensemble(discover_sc1_runs(root), expected_eds=2)
    result = build_sc1_crossrun_synthesis(ensemble)

    assert len(result.ensemble) == 8
    assert len(result.robust_exposure) == 2

    robust = result.robust_exposure.set_index("CSOED")
    assert robust.loc["ED1", "ROBUST_MIN_CATTLE_REDUCTION_PCT"] == pytest.approx(10.0)
    assert robust.loc["ED2", "ROBUST_MIN_CATTLE_REDUCTION_PCT"] == pytest.approx(10.0)
    assert robust.loc["ED1", "ROBUST_MIN_SO_LOSS_PCT"] == pytest.approx(10.0)
    assert robust.loc["ED1", "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT"] == pytest.approx(10.0)
    assert robust.loc["ED1", "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT"] == pytest.approx(10.0)

    redistribution = result.redistribution
    alt = redistribution.loc[
        (redistribution["PATHWAY_NAME"] == "A")
        & (redistribution["PATHWAY_ALLOCATION_RULE"] == "SOCIAL_VULNERABILITY_PROTECTION")
    ].iloc[0]
    assert alt["TOTAL_PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_HEAD"] == pytest.approx(10.0)
    assert alt["TOTAL_DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_HEAD"] == pytest.approx(10.0)
    assert alt["NET_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD"] == pytest.approx(0.0)
