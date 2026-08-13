"""Smoke test for the installed LPIS-aware opportunity command."""

import subprocess


def test_opportunity_console_script_is_installed() -> None:
    result = subprocess.run(
        ["goblin-spatial-opportunity", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "screen" in result.stdout
    assert "allocate" in result.stdout
