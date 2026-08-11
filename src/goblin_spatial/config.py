"""Configuration loading and repository-relative paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SpatialConfig:
    """Resolved configuration for one GOBLIN-Spatial build."""

    project_root: Path
    raw_dir: Path
    controls_dir: Path
    interim_dir: Path
    processed_dir: Path
    start_year: int
    end_year: int
    base_year: int
    expected_eds: int
    files: dict[str, Path]
    raw: dict[str, Any]


def load_config(path: str | Path) -> SpatialConfig:
    """Load YAML and resolve all data paths relative to the repository root."""

    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    project_root = config_path.parent.parent
    paths = raw.get("paths", {})
    study = raw.get("study", {})

    raw_dir = project_root / paths.get("raw", "data/raw")
    controls_dir = project_root / paths.get("controls", "data/controls")
    interim_dir = project_root / paths.get("interim", "data/interim")
    processed_dir = project_root / paths.get("processed", "data/processed")

    file_config = raw.get("files", {})
    files: dict[str, Path] = {}
    for key, value in file_config.items():
        value_path = Path(value)
        files[key] = value_path if value_path.is_absolute() else project_root / value_path

    return SpatialConfig(
        project_root=project_root,
        raw_dir=raw_dir,
        controls_dir=controls_dir,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
        start_year=int(study.get("start_year", 2015)),
        end_year=int(study.get("end_year", 2025)),
        base_year=int(study.get("base_year", 2020)),
        expected_eds=int(study.get("expected_eds", 2857)),
        files=files,
        raw=raw,
    )
