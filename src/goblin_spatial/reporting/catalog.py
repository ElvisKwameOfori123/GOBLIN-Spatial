"""Run catalogue and frozen-output discovery for GOBLIN-Spatial reporting.

This module only identifies and validates result artefacts that already exist.
It does not invoke the scientific model.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import json
from typing import Iterable


@dataclass(frozen=True)
class FrozenRun:
    run_id: str
    path: str
    scenario_id: str
    baseline_year: int
    allocation_rule: str
    through_stage: str
    model_commit: str | None = None

    def as_record(self) -> dict:
        return asdict(self)


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 digest of an existing file."""
    p = Path(path)
    h = sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_run_registry(runs: Iterable[FrozenRun], output_path: str | Path) -> Path:
    """Write a deterministic JSON registry for frozen runs.

    Parquet materialisation is handled by the report-data builder; JSON is kept
    as a human-readable provenance sidecar.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    records = sorted((r.as_record() for r in runs), key=lambda x: x["run_id"])
    out.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
