"""Smoke tests for the installed LPIS-aware downstream commands."""

import subprocess


def _help(command: str):
    return subprocess.run(
        [command, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_opportunity_console_script_is_installed() -> None:
    result = _help("goblin-spatial-opportunity")
    assert result.returncode == 0
    assert "screen" in result.stdout
    assert "allocate" in result.stdout


def test_lpis_profile_console_script_is_installed() -> None:
    result = _help("goblin-spatial-lpis")
    assert result.returncode == 0
    assert "--year" in result.stdout
    assert "--lpis-2020" in result.stdout
    assert "--lpis-2025" in result.stdout
