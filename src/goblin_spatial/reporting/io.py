"""Typed report-data writers.

Parquet is the canonical machine-readable reporting format. CSV is written as a
human-readable companion.  Neither format is an authoritative scientific input.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class ReportingDependencyError(ImportError):
    """Raised when an optional reporting dependency is unavailable."""


def _require_parquet_engine() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on optional environment
        raise ReportingDependencyError(
            "Parquet reporting requires pyarrow. Install with: "
            "pip install 'goblin-spatial[reporting]'"
        ) from exc


def write_report_table(
    frame: pd.DataFrame,
    base_path: str | Path,
    *,
    parquet: bool = True,
    csv: bool = True,
) -> dict[str, Path]:
    """Write one report-data table without altering its scientific values.

    ``base_path`` is supplied without a file extension. The function creates the
    parent directory and writes deterministic row order exactly as provided by
    the caller.
    """

    if not parquet and not csv:
        raise ValueError("at least one report-data format must be requested")

    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    if parquet:
        _require_parquet_engine()
        path = base.with_suffix(".parquet")
        frame.to_parquet(path, index=False, engine="pyarrow")
        written["parquet"] = path

    if csv:
        path = base.with_suffix(".csv")
        frame.to_csv(path, index=False)
        written["csv"] = path

    return written
