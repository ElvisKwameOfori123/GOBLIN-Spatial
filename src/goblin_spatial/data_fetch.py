"""Locate, fetch, verify and unpack datasets required by GOBLIN-Spatial.

Compact working inputs can be tracked directly in Git. Large spatial inputs
are stored externally (for example in a versioned Zenodo record), downloaded
on demand, checksum-verified, and unpacked into gitignored data directories.
The scientific modules consume verified local paths and remain independent of
where the files were hosted.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import pooch
import yaml


LOCAL_SOURCES = {"git", "local"}


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """Return a hexadecimal checksum for *path* using *algorithm*."""

    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Backward-compatible SHA256 helper."""

    return file_hash(path, "sha256", chunk_size)


def load_manifest(path: str | Path = "data_manifest.yaml") -> tuple[Path, dict[str, Any]]:
    """Load the data manifest and return ``(project_root, manifest)``."""

    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}

    if "datasets" not in manifest:
        raise ValueError("data manifest must contain a 'datasets' mapping")

    return manifest_path.parent, manifest


def _resolved_path(project_root: Path, info: dict[str, Any]) -> Path:
    source = str(info.get("source", "local")).lower()

    if source in LOCAL_SOURCES:
        value = info.get("path")
        if not value:
            raise ValueError(f"{source} dataset entry is missing 'path'")
    else:
        value = info.get("destination")
        if not value:
            raise ValueError("external dataset entry is missing 'destination'")

    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _known_hash(info: dict[str, Any]) -> str | None:
    """Return a Pooch-style ``algorithm:hex`` checksum from one manifest entry."""

    known = info.get("known_hash")
    if known:
        text = str(known).strip()
        return text if ":" in text else f"sha256:{text}"

    if info.get("sha256"):
        return f"sha256:{info['sha256']}"
    if info.get("md5"):
        return f"md5:{info['md5']}"
    return None


def _verify_one(
    name: str,
    path: Path,
    expected_hash: str | None,
    *,
    git_tracked: bool = False,
) -> tuple[bool, str]:
    if not path.exists():
        return False, f"MISSING  {name}: {path}"

    if not expected_hash:
        if git_tracked:
            return True, f"OK       {name}: {path} [Git-tracked]"
        return False, f"NO HASH  {name}: manifest has no checksum"

    algorithm, expected = expected_hash.split(":", 1)
    actual = file_hash(path, algorithm)
    if actual.lower() != expected.lower():
        return (
            False,
            f"BAD HASH {name}: expected {algorithm}:{expected}, got {algorithm}:{actual}",
        )

    return True, f"OK       {name}: {path} [{algorithm}]"


def _project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _safe_extract_zip(archive_path: Path, extract_dir: Path) -> None:
    """Extract a ZIP while rejecting paths that escape *extract_dir*."""

    extract_dir.mkdir(parents=True, exist_ok=True)
    root = extract_dir.resolve()

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            candidate = (extract_dir / member.filename).resolve()
            if candidate != root and root not in candidate.parents:
                raise ValueError(
                    f"Unsafe ZIP member in {archive_path.name}: {member.filename}"
                )
        archive.extractall(extract_dir)


def _postprocess_archive(
    name: str,
    info: dict[str, Any],
    project_root: Path,
    archive_path: Path,
    *,
    extract: bool,
) -> tuple[bool, str, Path]:
    """Unpack and validate one declared archive, returning its primary path."""

    archive_type = str(info.get("archive", "")).lower()
    primary_value = info.get("primary_path")
    primary = (
        _project_path(project_root, primary_value)
        if primary_value
        else archive_path
    )

    if not archive_type:
        return True, "", primary
    if archive_type != "zip":
        return False, f"UNSUPPORTED ARCHIVE {name}: {archive_type}", primary

    extract_value = info.get("extract_to")
    if not extract_value:
        return False, f"NO EXTRACT PATH {name}: manifest is missing extract_to", primary
    extract_dir = _project_path(project_root, extract_value)

    required_values = info.get("required_members", []) or []
    required = [_project_path(project_root, value) for value in required_values]
    missing = [path for path in required if not path.exists()]

    if extract and missing:
        _safe_extract_zip(archive_path, extract_dir)
        missing = [path for path in required if not path.exists()]

    if missing:
        return (
            False,
            f"MISSING EXTRACTED {name}: " + ", ".join(str(path) for path in missing),
            primary,
        )

    primary_sha256 = info.get("primary_sha256")
    if primary_sha256 and primary.exists():
        actual = sha256_file(primary)
        if actual.lower() != str(primary_sha256).lower():
            return (
                False,
                f"BAD PRIMARY HASH {name}: expected sha256:{primary_sha256}, "
                f"got sha256:{actual}",
                primary,
            )

    return True, f"UNPACKED {name}: {extract_dir}", primary


def fetch_data(
    manifest_path: str | Path = "data_manifest.yaml",
    *,
    verify_only: bool = False,
    tracked_only: bool = False,
) -> dict[str, Path]:
    """Locate, download where necessary, verify and unpack declared datasets.

    External datasets are fetched to their manifest ``destination``. Versioned
    repository URLs (for example Zenodo record-specific file URLs) should be
    used when scientific reproducibility requires an immutable research input.
    """

    project_root, manifest = load_manifest(manifest_path)
    datasets: dict[str, dict[str, Any]] = manifest["datasets"]
    resolved: dict[str, Path] = {}
    failures: list[str] = []

    for name, info in datasets.items():
        source = str(info.get("source", "local")).lower()

        if tracked_only and source not in LOCAL_SOURCES:
            print(f"SKIP     {name}: external input")
            continue

        archive_path = _resolved_path(project_root, info)
        expected = _known_hash(info)
        required = bool(info.get("required", True))
        git_tracked = bool(info.get("git_tracked", source == "git"))

        ok, message = _verify_one(
            name,
            archive_path,
            expected,
            git_tracked=git_tracked,
        )

        if not ok and source not in LOCAL_SOURCES and not verify_only:
            url = info.get("url")
            if url:
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"DOWNLOAD {name}: {url}")
                try:
                    pooch.retrieve(
                        url=str(url),
                        known_hash=expected,
                        path=archive_path.parent,
                        fname=archive_path.name,
                        progressbar=False,
                    )
                except Exception as exc:  # network/remote errors are reported cleanly
                    message = f"DOWNLOAD FAILED {name}: {exc}"
                    print(message)
                    if required:
                        failures.append(message)
                    continue

                ok, message = _verify_one(
                    name,
                    archive_path,
                    expected,
                    git_tracked=False,
                )
            else:
                message = (
                    f"NO URL   {name}: place the canonical file at {archive_path} or "
                    "populate its external URL in data_manifest.yaml"
                )

        print(message)
        if not ok:
            if required:
                failures.append(message)
            continue

        archive_ok, archive_message, primary = _postprocess_archive(
            name,
            info,
            project_root,
            archive_path,
            extract=not verify_only,
        )
        if archive_message:
            print(archive_message)
        if not archive_ok:
            if required:
                failures.append(archive_message)
            continue

        resolved[name] = primary

    if failures:
        joined = "\n".join(f"  - {item}" for item in failures)
        raise RuntimeError(
            "GOBLIN-Spatial data verification failed for required inputs:\n"
            f"{joined}"
        )

    return resolved
