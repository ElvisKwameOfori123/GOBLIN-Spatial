"""Tests for the repository-only default data-management boundary."""

from __future__ import annotations

import sys

import goblin_spatial.cli as cli


def test_fetch_data_cli_is_repository_only_by_default(monkeypatch) -> None:
    captured = {}

    def fake_fetch_data(path, *, verify_only=False, tracked_only=False):
        captured.update(
            path=str(path),
            verify_only=verify_only,
            tracked_only=tracked_only,
        )
        return {}

    monkeypatch.setattr(cli, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(sys, "argv", ["goblin-spatial", "fetch-data"])

    cli.main()

    assert captured["tracked_only"] is True
    assert captured["verify_only"] is False


def test_external_reconstruction_requires_explicit_opt_in(monkeypatch) -> None:
    captured = {}

    def fake_fetch_data(path, *, verify_only=False, tracked_only=False):
        captured.update(
            path=str(path),
            verify_only=verify_only,
            tracked_only=tracked_only,
        )
        return {}

    monkeypatch.setattr(cli, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(
        sys,
        "argv",
        ["goblin-spatial", "fetch-data", "--include-reconstruction-sources"],
    )

    cli.main()

    assert captured["tracked_only"] is False
