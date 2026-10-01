"""Verify repository-contained GOBLIN-Spatial historical-baseline datasets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

LOCAL_SOURCES = {"git", "local"}


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    if not path.is_file():
        raise ValueError(f"checksum target must be a file: {path}")
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    return file_hash(path, "sha256", chunk_size)


def load_manifest(path: str | Path = "data_manifest.yaml") -> tuple[Path, dict[str, Any]]:
    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}
    if "datasets" not in manifest:
        raise ValueError("data manifest must contain a 'datasets' mapping")
    return manifest_path.parent, manifest


def _resolved_path(project_root: Path, info: dict[str, Any]) -> Path:
    source = str(info.get("source", "local")).lower()
    if source not in LOCAL_SOURCES:
        raise ValueError(f"unsupported data source {source!r}; production manifest is repository/local only")
    value = info.get("path")
    if not value:
        raise ValueError(f"{source} dataset entry is missing 'path'")
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _known_hash(info: dict[str, Any]) -> tuple[str, str] | None:
    known = info.get("known_hash")
    if known:
        text = str(known).strip()
        if ":" in text:
            return tuple(text.split(":", 1))
        return "sha256", text
    if info.get("sha256"):
        return "sha256", str(info["sha256"])
    if info.get("md5"):
        return "md5", str(info["md5"])
    return None


def _verify_one(name: str, path: Path, expected_hash, *, git_tracked: bool):
    if not path.exists():
        return False, f"MISSING  {name}: {path}"
    if path.is_dir():
        return (True, f"OK       {name}: {path} [Git-tracked directory]") if git_tracked and expected_hash is None else (False, f"NO FILE HASH {name}: directory entries must be declared individually")
    if expected_hash is None:
        return (True, f"OK       {name}: {path} [Git-tracked]") if git_tracked else (False, f"NO HASH  {name}: manifest has no checksum")
    algorithm, expected = expected_hash
    actual = file_hash(path, algorithm)
    if actual.lower() != expected.lower():
        return False, f"BAD HASH {name}: expected {algorithm}:{expected}, got {algorithm}:{actual}"
    return True, f"OK       {name}: {path} [{algorithm}]"


def fetch_data(
    manifest_path: str | Path = "data_manifest.yaml",
    *,
    verify_only: bool = True,
    tracked_only: bool = True,
) -> dict[str, Path]:
    """Verify all declared repository/local historical-baseline inputs; never download data."""
    del verify_only, tracked_only
    project_root, manifest = load_manifest(manifest_path)
    resolved: dict[str, Path] = {}
    failures: list[str] = []
    for name, info in manifest["datasets"].items():
        source = str(info.get("source", "local")).lower()
        if source not in LOCAL_SOURCES:
            failures.append(f"UNSUPPORTED SOURCE {name}: {source}")
            continue
        path = _resolved_path(project_root, info)
        required = bool(info.get("required", True))
        git_tracked = bool(info.get("git_tracked", source == "git"))
        ok, message = _verify_one(name, path, _known_hash(info), git_tracked=git_tracked)
        print(message)
        if not ok:
            if required:
                failures.append(message)
            continue
        resolved[name] = path
    if failures:
        joined = "\n".join(f"  - {item}" for item in failures)
        raise RuntimeError("GOBLIN-Spatial repository data verification failed:\n" + joined)
    return resolved
