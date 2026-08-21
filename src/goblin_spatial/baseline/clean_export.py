"""Stage-07 clean historical export interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.export import export_clean_workbook


def export_core_baseline(
    baseline: pd.DataFrame,
    path: str | Path,
    *,
    base_year: int = 2020,
) -> Path:
    """Write the validated clean baseline workbook without changing values."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    export_clean_workbook(baseline, target, base_year=base_year)
    return target
