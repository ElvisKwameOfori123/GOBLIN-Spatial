"""Fetch and verify the datasets required by GOBLIN-Spatial.

The manifest is the reproducibility contract between the GitHub software
package and external research-data records such as Zenodo. Small controls can
remain local to the repository, while raw/binary datasets are downloaded into
``data/raw`` and checked against pinned SHA256 hashes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pooch
import yaml


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA256 checksum of *path*."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | Path = "data_manifest.yaml") -> tuple[Path, dict[str, Any]]:
    """Load a data manifest and return ``(project_root, manifest)``."""

    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}

    if "datasets" not in manifest:
        raise ValueError("data manifest must contain a 'datasets' mapping")

    return manifest_path.parent, manifest


def _resolved_path(project_root: Path, info: dict[str, Any]) -> Path:
    if info.get("source") == "local":
        value = info.get("path")
        if not value:
            raise ValueError("local dataset entry is missing 'path'")
    else:
        value = info.get("destination")
        if not value:
            raise ValueError("external dataset entry is missing 'destination'")

    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _verify_one(name: str, path: Path, expected_sha256: str | None) -> tuple[bool, str]:
    if not path.exists():
        return False, f"MISSING  {name}: {path}"

    if not expected_sha256:
        return False, f"NO HASH  {name}: manifest has no SHA256"

    actual = sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        return (
            False,
            f"BAD HASH {name}: expected {expected_sha256}, got {actual}",
        )

    return True, f"OK       {name}: {path}"


def fetch_data(
    manifest_path: str | Path = "data_manifest.yaml",
    *,
    verify_only: bool = False,
) -> dict[str, Path]:
    """Fetch or verify all datasets declared in the manifest.

    Parameters
    ----------
    manifest_path:
        Path to ``data_manifest.yaml``.
    verify_only:
        If ``True``, never download. Existing local files are checked against
        the pinned SHA256 values and missing required inputs cause failure.

    Returns
    -------
    dict
        Mapping from dataset key to the resolved local file path.

    Notes
    -----
    During development, an external entry may have ``url: null`` while the
    first Zenodo record is being prepared. In that case the canonical file can
    be placed manually at its declared destination and ``--verify-only`` can be
    used to prove that it is the expected file.
    """

    project_root, manifest = load_manifest(manifest_path)
    datasets: dict[str, dict[str, Any]] = manifest["datasets"]
    resolved: dict[str, Path] = {}
    failures: list[str] = []

    for name, info in datasets.items():
        path = _resolved_path(project_root, info)
        resolved[name] = path
        expected = info.get("sha256")
        required = bool(info.get("required", True))

        ok, message = _verify_one(name, path, expected)
        if ok:
            print(message)
            continue

        if info.get("source") == "local" or verify_only:
            print(message)
            if required:
                failures.append(message)
            continue

        url = info.get("url")
        if not url:
            message = (
                f"NO URL   {name}: place the canonical file at {path} or "
                "populate its Zenodo/official URL in data_manifest.yaml"
            )
            print(message)
            if required:
                failures.append(message)
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"DOWNLOAD {name}: {url}")
        pooch.retrieve(
            url=url,
            known_hash=f"sha256:{expected}" if expected else None,
            path=path.parent,
            fname=path.name,
            progressbar=False,
        )

        ok, message = _verify_one(name, path, expected)
        print(message)
        if not ok and required:
            failures.append(message)

    if failures:
        joined = "\n".join(f"  - {item}" for item in failures)
        raise RuntimeError(
            "GOBLIN-Spatial data verification failed for required inputs:\n"
            f"{joined}"
        )

    return resolved
