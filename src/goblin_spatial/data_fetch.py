"""Verify repository-contained GOBLIN-Spatial datasets.

The production model is self-contained. This module does not download data or
contact external services. First-principles reconstruction, if ever required,
is a separate local/manual activity using user-supplied source files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


LOCAL_SOURCES = {"git", "local"}


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """Return a hexadecimal checksum for one local file."""

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
    """Load the repository data manifest and return ``(project_root, manifest)``."""

    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}
    if "datasets" not in manifest:
        raise ValueError("data manifest must contain a 'datasets' mapping")
    return manifest_path.parent, manifest


def _resolved_path(project_root: Path, info: dict[str, Any]) -> Path:
    source = str(info.get("source", "local")).lower()
    if source not in LOCAL_SOURCES:
        raise ValueError(
            f"unsupported data source {source!r}; production manifest must be repository/local only"
        )
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
            algorithm, digest = text.split(":", 1)
            return algorithm, digest
        return "sha256", text
    if info.get("sha256"):
        return "sha256", str(info["sha256"])
    if info.get("md5"):
        return "md5", str(info["md5"])
    return None


def _verify_one(
    name: str,
    path: Path,
    expected_hash: tuple[str, str] | None,
    *,
    git_tracked: bool,
) -> tuple[bool, str]:
    if not path.exists():
        return False, f"MISSING  {name}: {path}"

    if path.is_dir():
        if git_tracked and expected_hash is None:
            return True, f"OK       {name}: {path} [Git-tracked directory]"
        return False, f"NO FILE HASH {name}: directory requires its dedicated validator"

    if expected_hash is None:
        if git_tracked:
            return True, f"OK       {name}: {path} [Git-tracked]"
        return False, f"NO HASH  {name}: manifest has no checksum"

    algorithm, expected = expected_hash
    actual = file_hash(path, algorithm)
    if actual.lower() != expected.lower():
        return (
            False,
            f"BAD HASH {name}: expected {algorithm}:{expected}, got {algorithm}:{actual}",
        )
    return True, f"OK       {name}: {path} [{algorithm}]"


def _verify_logical_repository_control(
    name: str,
    path: Path,
    info: dict[str, Any],
) -> tuple[bool, str] | None:
    """Verify repository directories that represent one scientific object."""

    logical_sha = str(info.get("logical_sha256", "")).strip().lower()
    if not logical_sha:
        return None
    if name != "ed_land_context_2020":
        return False, f"NO LOGICAL VALIDATOR {name}: logical_sha256 is declared"
    if not path.exists():
        return False, f"MISSING  {name}: {path}"
    if not path.is_dir():
        return False, f"INVALID  {name}: expected repository directory at {path}"

    try:
        from goblin_spatial.land.context import land_context_sha256, read_land_context_table

        actual = land_context_sha256(path).lower()
        if actual != logical_sha:
            return (
                False,
                f"BAD LOGICAL HASH {name}: expected sha256:{logical_sha}, got sha256:{actual}",
            )
        frame = read_land_context_table(path, verify_sha256=False)
    except Exception as exc:
        return False, f"INVALID  {name}: {exc}"

    expected_rows = info.get("expected_rows")
    expected_columns = info.get("expected_columns")
    if expected_rows is not None and len(frame) != int(expected_rows):
        return False, f"BAD ROW COUNT {name}: expected {expected_rows}, got {len(frame)}"
    if expected_columns is not None and len(frame.columns) != int(expected_columns):
        return False, f"BAD COLUMN COUNT {name}: expected {expected_columns}, got {len(frame.columns)}"

    return (
        True,
        f"OK       {name}: {path} [logical sha256:{actual}; rows={len(frame):,}; columns={len(frame.columns)}]",
    )


def fetch_data(
    manifest_path: str | Path = "data_manifest.yaml",
    *,
    verify_only: bool = True,
    tracked_only: bool = True,
) -> dict[str, Path]:
    """Verify all declared repository/local model inputs.

    The historical name ``fetch_data`` is retained for CLI/API stability, but
    the function performs verification only. It never downloads anything.
    ``verify_only`` and ``tracked_only`` remain accepted for backwards API
    compatibility and have no effect on the repository-only policy.
    """

    del verify_only, tracked_only
    project_root, manifest = load_manifest(manifest_path)
    datasets: dict[str, dict[str, Any]] = manifest["datasets"]
    resolved: dict[str, Path] = {}
    failures: list[str] = []

    for name, info in datasets.items():
        source = str(info.get("source", "local")).lower()
        if source not in LOCAL_SOURCES:
            failures.append(
                f"UNSUPPORTED SOURCE {name}: {source}; production manifest is repository/local only"
            )
            continue

        path = _resolved_path(project_root, info)
        required = bool(info.get("required", True))
        git_tracked = bool(info.get("git_tracked", source == "git"))

        logical_result = _verify_logical_repository_control(name, path, info)
        if logical_result is not None:
            ok, message = logical_result
        else:
            ok, message = _verify_one(
                name,
                path,
                _known_hash(info),
                git_tracked=git_tracked,
            )

        print(message)
        if not ok:
            if required:
                failures.append(message)
            continue
        resolved[name] = path

    if failures:
        joined = "\n".join(f"  - {item}" for item in failures)
        raise RuntimeError(
            "GOBLIN-Spatial repository data verification failed for required inputs:\n" + joined
        )
    return resolved
