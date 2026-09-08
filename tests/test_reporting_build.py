from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from goblin_spatial.reporting.build import build_report_data
from goblin_spatial.reporting.figure_data import export_figure_data


def _write_run(root: Path, rule: str, ed1: float, ed2: float) -> None:
    run_dir = root / f"BE_SG_{rule}"
    run_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "CSOED": ["ED1", "ED2"],
            "PATHWAY_NAME": ["BE_SG", "BE_SG"],
            "PATHWAY_ALLOCATION_RULE": [rule, rule],
            "BASE_TOTAL_CATTLE": [100.0, 100.0],
            "CUMULATIVE_REDUCTION_TOTAL_CATTLE": [ed1, ed2],
            "BASE_SO_LIVESTOCK_2020_EUR": [1000.0, 1000.0],
            "SO_LIVESTOCK_EXPOSURE_2020_EUR": [10.0 * ed1, 10.0 * ed2],
            "GOBLIN_RELEASED_GRASSLAND_HA": [ed1 / 2.0, ed2 / 2.0],
        }
    ).to_csv(run_dir / "sc1_ed_results.csv", index=False)
    pd.DataFrame(
        [
            {
                "SCENARIO_ID": "BE_SG",
                "RUN_START_YEAR": 2020,
                "TARGET_YEAR": 2050,
                "ALLOCATION_POLICY": rule,
                "PROTECTION_STRENGTH_LAMBDA": 0.5,
            }
        ]
    ).to_csv(run_dir / "sc1_control_summary.csv", index=False)
    pd.DataFrame([{"SCENARIO_ID": "BE_SG", "ED_COUNT": 2}]).to_csv(
        run_dir / "sc1_national_metrics.csv", index=False
    )


def test_report_data_builder_materialises_frozen_csv_contract(tmp_path: Path) -> None:
    principal = tmp_path / "principal"
    _write_run(principal, "PRORATA", 20.0, 10.0)
    _write_run(principal, "DAIRY_PROTECTION", 10.0, 20.0)

    result = build_report_data(
        principal,
        tmp_path / "reporting" / "report_data",
        project_root=tmp_path,
        expected_eds=2,
        parquet=False,
        csv=True,
        model_commit="abc123",
    )

    assert len(result.run_registry) == 2
    assert set(result.source_files["FILENAME"]) == {
        "sc1_control_summary.csv",
        "sc1_ed_results.csv",
        "sc1_national_metrics.csv",
    }
    assert (result.output_root / "sc1" / "ed_results.csv").exists()
    assert (result.output_root / "sc1" / "comparison_ed.csv").exists()
    assert (result.output_root / "sc1" / "redistribution.csv").exists()
    assert (result.output_root / "sc1" / "robust_exposure.csv").exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["MODEL_COMMIT"] == "abc123"
    assert manifest["RUN_COUNT"] == 2
    assert manifest["BOUNDARY"].startswith("REPORTING_READS_FROZEN_RESULTS")


def test_figure_data_export_selects_existing_values_only(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "CSOED": ["ED2", "ED1"],
            "VALUE": [2.0, 1.0],
            "UNUSED": [99, 99],
        }
    )
    csv_path, manifest_path = export_figure_data(
        frame,
        tmp_path / "fig03.csv",
        required_columns=["CSOED", "VALUE"],
        sort_by=["CSOED"],
        figure_id="FIG03",
        source_tables=["sc1/ed_results"],
    )
    exported = pd.read_csv(csv_path)
    assert exported.columns.tolist() == ["CSOED", "VALUE"]
    assert exported["CSOED"].tolist() == ["ED1", "ED2"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["FIGURE_ID"] == "FIG03"
    assert manifest["SCIENTIFIC_RECALCULATION"] is False
