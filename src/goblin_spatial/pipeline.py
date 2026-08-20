"""Top-level orchestration for the GOBLIN-Spatial historical baseline.

Scientific calculations live in the baseline modules. This file controls only
stage order, validation and output persistence.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.baseline import (
    add_land_farm_structure,
    add_standard_output,
    build_cattle_baseline,
    build_sheep_baseline,
    merge_livestock,
)
from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.export import export_clean_workbook
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
    """Build the Stage-07 compatible historical baseline.

    This function remains the compatibility entry point while v1 regression
    migration is in progress. It now orchestrates the new baseline module
    boundaries but preserves the legacy pre-Standard-Output return contract.
    """

    cfg = _config(config)
    cfg.interim_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    cattle = build_cattle_baseline(cfg)
    sheep = build_sheep_baseline(cfg)
    livestock = merge_livestock(cattle, sheep)
    master = add_land_farm_structure(livestock, cfg)
    master = _canonical_order(master)

    validation = validate_master(master, cfg)

    master_path = _output_path(
        cfg,
        "enriched_master",
        "data/processed/goblin_spatial_master_2015_2025.csv",
    )
    workbook_path = _output_path(
        cfg,
        "clean_workbook",
        "data/processed/GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx",
    )
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(master_path, index=False)
    export_clean_workbook(master, workbook_path, base_year=cfg.base_year)

    validation_path = cfg.processed_dir / "validation_summary.csv"
    pd.DataFrame([validation]).to_csv(validation_path, index=False)

    print(f"Validated historical core baseline: {master_path}")
    print(f"Clean baseline workbook: {workbook_path}")
    print(f"Validation summary: {validation_path}")

    return master


def run_baseline(config: str | Path | SpatialConfig) -> pd.DataFrame:
    """Build the complete v1 core baseline through fixed-2020 Standard Output.

    The sequence is cattle -> sheep -> merge -> land/farm structure -> clean
    validation/export -> Standard Output. Soil is deliberately excluded here;
    08B/08C and frozen signatures form the subsequent scenario-ready enrichment
    layer.
    """

    cfg = _config(config)
    core = build(cfg)
    valued = add_standard_output(core, cfg)
    valued = _canonical_order(valued)

    output = _output_path(
        cfg,
        "standard_output_master",
        "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    valued.to_csv(output, index=False)

    print(f"Baseline through Standard Output: {output}")
    return valued
