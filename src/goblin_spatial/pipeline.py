"""Top-level one-command GOBLIN-Spatial build pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.land import add_land
from goblin_spatial.se import add_se
from goblin_spatial.sheep import add_sheep_cohorts, build_sheep_panel


MERGE_KEYS = ["YEAR", "CSOED"]


def merge_livestock(cattle: pd.DataFrame, sheep: pd.DataFrame) -> pd.DataFrame:
    """Merge independently constructed cattle and sheep ED panels."""

    for label, frame in (("cattle", cattle), ("sheep", sheep)):
        missing = [key for key in MERGE_KEYS if key not in frame.columns]
        if missing:
            raise ValueError(f"{label} panel missing merge keys: {missing}")
        if frame[MERGE_KEYS].duplicated().any():
            raise ValueError(f"{label} panel contains duplicate YEAR-CSOED rows")

    overlapping = [
        column
        for column in cattle.columns
        if column in sheep.columns and column not in MERGE_KEYS
    ]

    # Shared identifiers are retained from cattle. Sheep-specific substantive
    # indicators are appended. Conflicting substantive column names are not
    # silently accepted.
    allowed_shared = {
        "ELECTORAL_DIVISIONS",
        "ED",
        "County",
        "EDID",
        "CSOED_RAW",
        "EDNAME",
        "COUNTYNAME",
    }
    conflicts = [column for column in overlapping if column not in allowed_shared]
    if conflicts:
        raise ValueError(f"cattle/sheep merge has unexpected shared columns: {conflicts}")

    sheep_keep = [
        column
        for column in sheep.columns
        if column in MERGE_KEYS or column not in overlapping
    ]

    merged = cattle.merge(
        sheep[sheep_keep],
        on=MERGE_KEYS,
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(cattle) or len(merged) != len(sheep):
        raise AssertionError("cattle/sheep merge did not preserve the complete panel")

    return merged


def build(config: str | Path | SpatialConfig) -> pd.DataFrame:
    """Run the complete GOBLIN-Spatial data-generation workflow.

    One call executes the four scientific modules in dependency order:

    1. cattle
    2. sheep
    3. land
    4. SE (social-economic)

    Cattle and sheep are developed independently, then merged. Land and SE are
    added to the merged livestock master. Each module is responsible for its
    own accounting constraints and may also be run independently by developers.
    """

    cfg = load_config(config) if not isinstance(config, SpatialConfig) else config

    cfg.interim_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    cattle = build_cattle_panel(cfg)
    cattle = add_cattle_cohorts(cattle, cfg)

    sheep = build_sheep_panel(cfg)
    sheep = add_sheep_cohorts(sheep, cfg)

    master = merge_livestock(cattle, sheep)
    master = add_land(master, cfg)
    master = add_se(master, cfg)

    return master
