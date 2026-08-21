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


def _activate_manifest_sources(manifest_path: Path, entry_keys: set[str]) -> bool:
    """Change verified baseline entries from git_pending to git in-place.

    This intentionally edits only the ``source`` line inside the already parsed
    baseline dataset blocks so hand-maintained YAML comments and formatting are
    preserved.
    """

    lines = manifest_path.read_text(encoding="utf-8").splitlines(keepends=True)
    current_key: str | None = None
    changed = False

    for index, line in enumerate(lines):
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            current_key = line.strip()[:-1]
            continue
        if current_key in entry_keys and line.strip() == 'source: "git_pending"':
            lines[index] = line.replace('"git_pending"', '"git"')
            changed = True

    if changed:
        manifest_path.write_text("".join(lines), encoding="utf-8")
    return changed


def package_baseline_inputs(
    root: Path,
    *,
    verify_only: bool = False,
    activate_manifest: bool = False,
) -> None:
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

    if activate_manifest:
        changed = _activate_manifest_sources(
            manifest_path,
            {key for key, _ in entries},
        )
        print("Manifest baseline sources activated: git" if changed else "Manifest baseline sources already active.")

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
    parser.add_argument(
        "--activate-manifest",
        action="store_true",
        help="After every canonical baseline file passes SHA256, change only those manifest sources from git_pending to git.",
    )
    args = parser.parse_args()
    if args.verify_only and args.activate_manifest:
        parser.error("--verify-only and --activate-manifest cannot be combined")
    package_baseline_inputs(
        args.root.resolve(),
        verify_only=args.verify_only,
        activate_manifest=args.activate_manifest,
    )


if __name__ == "__main__":
    main()
