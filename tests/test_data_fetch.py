"""Tests for the repository-contained data-manifest contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from goblin_spatial.data_fetch import fetch_data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fetch_data_verifies_git_tracked_file(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.csv"
    fixture.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = {
        "datasets": {
            "fixture": {
                "source": "git",
                "path": "fixture.csv",
                "sha256": _sha256(fixture),
                "required": True,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    resolved = fetch_data(manifest_path)

    assert resolved["fixture"] == fixture


def test_fetch_data_rejects_bad_hash(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.csv"
    fixture.write_text("a\n1\n", encoding="utf-8")
    manifest = {
        "datasets": {
            "fixture": {
                "source": "git",
                "path": "fixture.csv",
                "sha256": "0" * 64,
                "required": True,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="BAD HASH"):
        fetch_data(manifest_path)


def test_fetch_data_allows_missing_optional_local_file(tmp_path: Path) -> None:
    manifest = {
        "datasets": {
            "optional": {
                "source": "local",
                "path": "not_present.csv",
                "required": False,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    resolved = fetch_data(manifest_path)

    assert "optional" not in resolved


def test_fetch_data_rejects_external_sources(tmp_path: Path) -> None:
    manifest = {
        "datasets": {
            "external": {
                "source": "external",
                "path": "anything.csv",
                "required": False,
            }
        }
    }
    manifest_path = tmp_path / "data_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="UNSUPPORTED SOURCE"):
        fetch_data(manifest_path)
