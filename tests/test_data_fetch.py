"""Tests for the external-data registry and archive post-processing contract."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import yaml

from goblin_spatial.data_fetch import fetch_data


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_fetch_data_verifies_and_extracts_local_zip(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    member = source_dir / "example.shp"
    member.write_bytes(b"fixed spatial fixture")

    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(member, arcname="example.shp")

    manifest = {
        "datasets": {
            "fixture": {
                "source": "local",
                "path": "bundle.zip",
                "known_hash": f"md5:{_digest(archive, 'md5')}",
                "archive": "zip",
                "extract_to": "external",
                "primary_path": "external/example.shp",
                "primary_sha256": _digest(member, "sha256"),
                "required_members": ["external/example.shp"],
                "required": True,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    resolved = fetch_data(manifest_path)

    expected = tmp_path / "external" / "example.shp"
    assert resolved["fixture"] == expected
    assert expected.read_bytes() == b"fixed spatial fixture"


def test_verify_only_does_not_unpack_missing_archive_members(tmp_path: Path) -> None:
    member = tmp_path / "member.txt"
    member.write_text("fixture", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(member, arcname="member.txt")

    manifest = {
        "datasets": {
            "fixture": {
                "source": "local",
                "path": "bundle.zip",
                "known_hash": f"sha256:{_digest(archive, 'sha256')}",
                "archive": "zip",
                "extract_to": "external",
                "primary_path": "external/member.txt",
                "required_members": ["external/member.txt"],
                "required": False,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    resolved = fetch_data(manifest_path, verify_only=True)

    assert "fixture" not in resolved
    assert not (tmp_path / "external" / "member.txt").exists()
