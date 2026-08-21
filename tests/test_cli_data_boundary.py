"""Tests for the repository-only data-management boundary."""

from __future__ import annotations

import sys

import goblin_spatial.cli as cli


def test_fetch_data_cli_is_always_repository_only(monkeypatch) -> None:
    captured = {}

    def fake_fetch_data(path, *, verify_only=True, tracked_only=True):
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
    assert captured["verify_only"] is True


def test_external_reconstruction_flag_is_not_supported(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["goblin-spatial", "fetch-data", "--include-reconstruction-sources"],
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("external reconstruction flag must not be accepted")
