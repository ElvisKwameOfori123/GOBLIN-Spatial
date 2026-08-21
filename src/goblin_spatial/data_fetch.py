"""Locate, fetch, verify and unpack declared GOBLIN-Spatial datasets.

Compact runtime inputs are tracked directly in Git. Large first-principles
spatial reconstruction sources may be stored in a versioned external release,
downloaded only when explicitly requested, checksum-verified and unpacked into
gitignored data directories.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pooch
import yaml


LOCAL_SOURCES = {"git", "local"}


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """Return a hexadecimal checksum for one file using *algorithm*."""

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

    if path.is_dir():
        if git_tracked and not expected_hash:
            return True, f"OK       {name}: {path} [Git-tracked directory]"
        return False, f"NO FILE HASH {name}: directory requires its dedicated validator"

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


def _verify_logical_repository_control(
    name: str,
    path: Path,
    info: dict[str, Any],
) -> tuple[bool, str] | None:
    """Verify a repository directory whose checksum describes a logical object.

    ``ED_Land_Context_2020`` is stored as transparent text shards but is one
    scientific CSV object. Merely checking that its directory exists would let
    an incomplete transfer pass the ordinary repository-data gate, so its
    reconstructed bytes and full scientific contract are validated here.
    """

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
        from goblin_spatial.land.context import (
            land_context_sha256,
            read_land_context_table,
        )

        actual = land_context_sha256(path).lower()
        if actual != logical_sha:
            return (
                False,
                f"BAD LOGICAL HASH {name}: expected sha256:{logical_sha}, "
                f"got sha256:{actual}",
            )
        frame = read_land_context_table(path, verify_sha256=False)
    except Exception as exc:
        return False, f"INVALID  {name}: {exc}"

    expected_rows = info.get("expected_rows")
    expected_columns = info.get("expected_columns")
    if expected_rows is not None and len(frame) != int(expected_rows):
        return False, f"BAD ROW COUNT {name}: expected {expected_rows}, got {len(frame)}"
    if expected_columns is not None and len(frame.columns) != int(expected_columns):
        return (
            False,
            f"BAD COLUMN COUNT {name}: expected {expected_columns}, got {len(frame.columns)}",
        )
    return (
        True,
        f"OK       {name}: {path} [logical sha256:{actual}; "
        f"rows={len(frame):,}; columns={len(frame.columns)}]",
    )


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


def _canonicalise_shapefile_bundle(
    extract_dir: Path,
    primary: Path,
    *,
    expected_sha256: str | None = None,
) -> bool:
    """Copy a pinned extracted shapefile bundle to its canonical local stem."""

    if primary.suffix.lower() != ".shp" or primary.exists():
        return False
    candidates = [
        path
        for path in extract_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".shp"
    ]

    selected: Path | None = None
    if expected_sha256:
        expected = str(expected_sha256).lower()
        matches = [path for path in candidates if sha256_file(path).lower() == expected]
        if len(matches) == 1:
            selected = matches[0]
    elif len(candidates) == 1:
        selected = candidates[0]
    if selected is None:
        return False

    primary.parent.mkdir(parents=True, exist_ok=True)
    copied = False
    for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        source = selected.with_suffix(suffix)
        target = primary.with_suffix(suffix)
        if source.exists() and source.resolve() != target.resolve():
            shutil.copy2(source, target)
            copied = True
    return copied


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
    primary = _project_path(project_root, primary_value) if primary_value else archive_path

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

    canonicalised = False
    if extract and missing:
        _safe_extract_zip(archive_path, extract_dir)
        canonicalised = _canonicalise_shapefile_bundle(
            extract_dir,
            primary,
            expected_sha256=info.get("primary_sha256"),
        )
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
                f"BAD PRIMARY HASH {name}: expected sha256:{primary_sha256}, got sha256:{actual}",
                primary,
            )

    action = "UNPACKED/CANONICALISED" if canonicalised else "UNPACKED"
    return True, f"{action} {name}: {extract_dir}", primary


def fetch_data(
    manifest_path: str | Path = "data_manifest.yaml",
    *,
    verify_only: bool = False,
    tracked_only: bool = False,
) -> dict[str, Path]:
    """Locate, optionally download, verify and unpack declared datasets.

    External datasets are downloaded only when explicitly included by the call.
    ``tracked_only=True`` limits verification to Git/local inputs and is the
    appropriate mode for routine repository CI.
    """

    project_root, manifest = load_manifest(manifest_path)
    datasets: dict[str, dict[str, Any]] = manifest["datasets"]
    resolved: dict[str, Path] = {}
    failures: list[str] = []

    for name, info in datasets.items():
        source = str(info.get("source", "local")).lower()
        if source not in LOCAL_SOURCES and not info.get("url"):
            raise ValueError(f"unsupported or incomplete source for {name}: {source}")

        if tracked_only and source not in LOCAL_SOURCES:
            print(f"SKIP     {name}: optional external reconstruction source")
            continue

        archive_path = _resolved_path(project_root, info)
        expected = _known_hash(info)
        required = bool(info.get("required", True))
        git_tracked = bool(info.get("git_tracked", source == "git"))

        logical_result = _verify_logical_repository_control(name, archive_path, info)
        if logical_result is not None:
            ok, message = logical_result
        else:
            ok, message = _verify_one(
                name,
                archive_path,
                expected,
                git_tracked=git_tracked,
            )

        if not ok and source not in LOCAL_SOURCES and not verify_only:
            url = info.get("url")
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
            except Exception as exc:
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
            "GOBLIN-Spatial data verification failed for required inputs:\n" + joined
        )
    return resolved