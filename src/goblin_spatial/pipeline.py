"""Top-level one-command GOBLIN-Spatial build pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.export import export_clean_workbook
from goblin_spatial.land import add_land
from goblin_spatial.se import add_se
from goblin_spatial.sheep import add_sheep_cohorts, build_sheep_panel
from goblin_spatial.validation import validate_master


MERGE_KEYS = ["YEAR", "CSOED"]
SHARED_IDENTIFIERS = {
    "ELECTORAL_DIVISIONS",
    "ED",
    "County",
    "EDID",
    "CSOED_RAW",
    "EDNAME",
    "COUNTYNAME",
}


def merge_livestock(
    cattle: pd.DataFrame, sheep: pd.DataFrame
) -> pd.DataFrame:
    """Merge independently constructed cattle and sheep ED panels.

    Cattle supplies the shared ED/static baseline context. If a sheep field also
    exists on the cattle-side copy of the 2020 baseline, the sheep module is
    authoritative and replaces that stale/static field.

    ``LSU`` is intentionally removed here. In the historical ED source it is a
    static 2020 context field copied into annual cattle rows, whereas the frozen
    validated final 2015-2025 master does not treat it as an annual reconstructed
    indicator. A future pressure/LSU module can calculate scenario-consistent LSU
    explicitly rather than carrying the 2020 value through time.
    """

    for label, frame in (("cattle", cattle), ("sheep", sheep)):
        missing = [key for key in MERGE_KEYS if key not in frame.columns]
        if missing:
            raise ValueError(f"{label} panel missing merge keys: {missing}")
        if frame[MERGE_KEYS].duplicated().any():
            raise ValueError(
                f"{label} panel contains duplicate YEAR-CSOED rows"
            )

    overlap = (
        set(cattle.columns).intersection(sheep.columns) - set(MERGE_KEYS)
    )
    replace_from_sheep = sorted(overlap - SHARED_IDENTIFIERS)
    cattle_base = cattle.drop(
        columns=[*replace_from_sheep, "LSU"], errors="ignore"
    )
    sheep_keep = [
        column
        for column in sheep.columns
        if column in MERGE_KEYS or column not in SHARED_IDENTIFIERS
    ]
    sheep_keep = list(dict.fromkeys(sheep_keep))

    merged = cattle_base.merge(
        sheep[sheep_keep],
        on=MERGE_KEYS,
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(cattle) or len(merged) != len(sheep):
        raise AssertionError(
            "cattle/sheep merge did not preserve the complete panel"
        )
    if "LSU" in merged.columns:
        raise AssertionError("stale baseline LSU survived livestock merge")
    return merged


def _output_path(
    config: SpatialConfig, key: str, default: str
) -> Path:
    value = config.raw.get("outputs", {}).get(key, default)
    path = Path(value)
    return path if path.is_absolute() else config.project_root / path


def build(config: str | Path | SpatialConfig) -> pd.DataFrame:
    """Run the complete GOBLIN-Spatial data-generation workflow.

    One call executes cattle, sheep, livestock merge, land, SE, validation and
    final export. The scientific modules remain callable independently for
    development, while normal users need only ``goblin-spatial build``.
    """

    cfg = (
        load_config(config)
        if not isinstance(config, SpatialConfig)
        else config
    )

    cfg.interim_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    cattle = add_cattle_cohorts(build_cattle_panel(cfg), cfg)
    sheep = add_sheep_cohorts(build_sheep_panel(cfg), cfg)
    master = merge_livestock(cattle, sheep)
    master = add_land(master, cfg)
    master = add_se(master, cfg)

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

    print(f"Validated master: {master_path}")
    print(f"Clean workbook: {workbook_path}")
    print(f"Validation summary: {validation_path}")

    return master
