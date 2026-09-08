"""Frozen publication extracts for figures and tables."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def export_figure_data(
    frame: pd.DataFrame,
    output_csv: str | Path,
    *,
    required_columns: Iterable[str],
    sort_by: Iterable[str] | None = None,
    figure_id: str | None = None,
    source_tables: Iterable[str] = (),
) -> tuple[Path, Path]:
    """Write the exact tabular extract behind one publication figure.

    The function selects and orders existing columns only. It performs no
    scientific derivation. A JSON sidecar records the extract hash and sources.
    """

    columns = list(required_columns)
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"figure-data extract missing columns: {missing}")

    data = frame.loc[:, columns].copy()
    if sort_by is not None:
        keys = list(sort_by)
        unknown = sorted(set(keys) - set(data.columns))
        if unknown:
            raise ValueError(f"figure-data sort columns missing from extract: {unknown}")
        data = data.sort_values(keys, kind="stable").reset_index(drop=True)

    path = Path(output_csv)
    if path.suffix.lower() != ".csv":
        raise ValueError("publication figure-data extracts must use a .csv path")
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False)

    digest = sha256(path.read_bytes()).hexdigest()
    manifest = {
        "FIGURE_ID": figure_id or path.stem,
        "DATA_FILE": str(path),
        "SHA256": digest,
        "ROWS": int(len(data)),
        "COLUMNS": columns,
        "SOURCE_TABLES": list(source_tables),
        "SCIENTIFIC_RECALCULATION": False,
    }
    sidecar = path.with_suffix(".manifest.json")
    sidecar.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, sidecar
