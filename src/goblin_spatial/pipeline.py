"""Top-level orchestration for the GOBLIN-Spatial historical baseline.

Scientific calculations live in the baseline modules. This file controls only
stage order, validation and output persistence for the historical model.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.baseline import (
    add_land_farm_structure,
    add_standard_output,
    build_cattle_baseline,
    build_sheep_baseline,
    build_signatures,
    merge_livestock,
)
from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.export import export_clean_workbook
from goblin_spatial.export.livestock_panels import (
    project_enriched_livestock_panels,
    run_checks as run_livestock_panel_checks,
)
from goblin_spatial.validation import validate_master


def _canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def _output_path(config: SpatialConfig, key: str, default: str) -> Path:
    value = config.raw.get("outputs", {}).get(key, default)
    path = Path(value)
    return path if path.is_absolute() else config.project_root / path


def _config(config: str | Path | SpatialConfig) -> SpatialConfig:
    return load_config(config) if not isinstance(config, SpatialConfig) else config


def build(config: str | Path | SpatialConfig) -> pd.DataFrame:
    """Build the historical reconstruction through land and farm structure."""
    cfg = _config(config)
    cfg.interim_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    cattle = build_cattle_baseline(cfg)
    sheep = build_sheep_baseline(cfg)
    ed_anchor = pd.read_csv(cfg.files["cso_ed_2020"], dtype={"CSOED": str})
    livestock = merge_livestock(cattle, sheep, ed_anchor=ed_anchor)
    master = _canonical_order(add_land_farm_structure(livestock, cfg))
    validation = validate_master(master, cfg)

    panel13, panel31 = project_enriched_livestock_panels(master)
    livestock_checks = run_livestock_panel_checks(panel13, panel31, cfg)
    if not livestock_checks["PASS"].all():
        failed = livestock_checks.loc[~livestock_checks["PASS"], "CHECK"].tolist()
        raise AssertionError(f"canonical livestock panel checks failed: {failed}")

    cso13_path = _output_path(
        cfg,
        "cso_13_cohort_panel",
        "data/interim/CSO_13_Cohort_Annual_Panel_2015_2025.csv",
    )
    goblin31_path = _output_path(
        cfg,
        "goblin_31_cohort_panel",
        "data/interim/GOBLIN_31_Cohort_Annual_Panel_2015_2025.csv",
    )
    for path, frame in ((cso13_path, panel13), (goblin31_path, panel31)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    master_path = _output_path(cfg, "enriched_master", "data/processed/goblin_spatial_master_2015_2025.csv")
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(master_path, index=False)
    validation_path = cfg.processed_dir / "validation_summary.csv"
    pd.DataFrame([validation]).to_csv(validation_path, index=False)

    print(f"CSO 13 cohort annual panel: {cso13_path}")
    print(f"GOBLIN 31 cohort annual panel: {goblin31_path}")
    print(f"Validated historical reconstruction: {master_path}")
    print(f"Validation summary: {validation_path}")
    return master


def run_baseline(config: str | Path | SpatialConfig) -> pd.DataFrame:
    """Build the complete historical baseline through ED cohort signatures."""
    cfg = _config(config)
    core = build(cfg)
    valued = _canonical_order(add_standard_output(core, cfg))

    output = _output_path(cfg, "standard_output_master", "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    valued.to_csv(output, index=False)

    workbook_path = _output_path(
        cfg,
        "clean_workbook",
        "data/processed/GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx",
    )
    export_clean_workbook(valued, workbook_path, base_year=cfg.base_year)

    signatures = build_signatures(valued, cfg)
    signature_output = _output_path(cfg, "ed_signatures", "data/processed/09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv")
    signature_output.parent.mkdir(parents=True, exist_ok=True)
    signatures.to_csv(signature_output, index=False)

    print(f"Baseline through Standard Output: {output}")
    print(f"Final clean workbook through Standard Output: {workbook_path}")
    print(f"ED cohort signatures: {signature_output}")
    return valued
