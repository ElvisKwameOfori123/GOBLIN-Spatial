"""Validation gates for downstream reporting data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


FORBIDDEN_REPORT_OUTPUT_PARENTS = (
    Path("src"),
    Path("data/inputs"),
    Path("data/controls"),
)


def validate_ed_table(
    frame: pd.DataFrame,
    *,
    key: str = "CSOED",
    expected_eds: int | None = 2857,
) -> None:
    """Require a unique, complete ED table before spatial reporting."""

    if key not in frame.columns:
        raise ValueError(f"ED reporting table missing key column: {key}")
    if frame[key].isna().any():
        raise ValueError(f"ED reporting key contains missing values: {key}")
    if frame[key].astype(str).duplicated().any():
        raise ValueError(f"ED reporting table contains duplicate {key} values")
    if expected_eds is not None and len(frame) != int(expected_eds):
        raise ValueError(
            f"ED reporting table has {len(frame)} rows, expected {int(expected_eds)}"
        )


def validate_reporting_root(project_root: str | Path, output_root: str | Path) -> Path:
    """Prevent generated reporting artefacts from entering scientific input trees."""

    root = Path(project_root).resolve()
    output = Path(output_root)
    output = output if output.is_absolute() else root / output
    resolved = output.resolve()

    for relative in FORBIDDEN_REPORT_OUTPUT_PARENTS:
        forbidden = (root / relative).resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise ValueError(
                f"reporting output cannot be written inside scientific source/input tree: {resolved}"
            )
    return resolved
