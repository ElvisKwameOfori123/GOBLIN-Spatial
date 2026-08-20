"""Package the compact frozen historical inputs into GitHub.

The immutable source of record is the pinned Zenodo release in
``data_manifest.yaml``. This helper downloads only datasets whose manifest path
is under ``data/inputs/baseline/`` and whose source is ``git_pending`` or
``git``. Every byte is SHA256-verified before it replaces the local target.

It deliberately excludes 08B/08C soil, LPIS, ED geometry and SC1-SC3 inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen

import yaml


CHUNK_SIZE = 8 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _baseline_entries(manifest: dict) -> list[tuple[str, dict]]:
    entries: list[tuple[str, dict]] = []
    for key, spec in manifest.get("datasets", {}).items():
        path = str(spec.get("path", ""))
        source = str(spec.get("source", ""))
        if path.startswith("data/inputs/baseline/") and source in {"git_pending", "git"}:
            entries.append((str(key), spec))
    if not entries:
        raise RuntimeError("manifest contains no compact baseline packaging entries")
    return entries


def _record_id(manifest: dict) -> int:
    releases = manifest.get("external_releases", {})
    release = releases.get("goblin_spatial_frozen_inputs_v1", {})
    record_id = release.get("record_id")
    if record_id is None:
        raise KeyError("missing external_releases.goblin_spatial_frozen_inputs_v1.record_id")
    return int(record_id)


def _download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "GOBLIN-Spatial/1.0 baseline-packager"})

    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".download", dir=destination.parent, delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
        digest = hashlib.sha256()
        try:
            with urlopen(request, timeout=180) as response:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    digest.update(chunk)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    observed = digest.hexdigest()
    if observed != expected_sha256:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA256 mismatch for {destination.name}: expected {expected_sha256}, got {observed}"
        )

    os.replace(tmp_path, destination)


def package_baseline_inputs(root: Path, *, verify_only: bool = False) -> None:
    manifest_path = root / "data_manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    record_id = _record_id(manifest)
    entries = _baseline_entries(manifest)

    verified = 0
    downloaded = 0
    for key, spec in entries:
        relative = Path(str(spec["path"]))
        destination = root / relative
        expected = str(spec.get("sha256", "")).lower().strip()
        if len(expected) != 64:
            raise ValueError(f"{key}: missing/invalid SHA256 in data_manifest.yaml")

        if destination.exists():
            observed = _sha256(destination)
            if observed == expected:
                print(f"OK       {key}: {relative}")
                verified += 1
                continue
            if verify_only:
                raise RuntimeError(
                    f"{key}: existing file has wrong SHA256: expected {expected}, got {observed}"
                )

        if verify_only:
            raise FileNotFoundError(f"{key}: canonical baseline file missing: {relative}")

        filename = quote(relative.name)
        url = f"https://zenodo.org/records/{record_id}/files/{filename}?download=1"
        print(f"FETCH    {key}: {relative}")
        _download_verified(url, destination, expected)
        downloaded += 1
        verified += 1
        print(f"VERIFIED {key}: sha256={expected}")

    print(
        f"Baseline packaging complete: {verified} verified file(s), "
        f"{downloaded} downloaded from Zenodo record {record_id}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: inferred from this script).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify canonical files without downloading anything.",
    )
    args = parser.parse_args()
    package_baseline_inputs(args.root.resolve(), verify_only=args.verify_only)


if __name__ == "__main__":
    main()
