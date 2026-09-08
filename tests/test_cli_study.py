from __future__ import annotations

from types import SimpleNamespace

import pytest

import goblin_spatial.cli as cli


def test_study_baseline_only_stops_without_scenario_runner(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(cli, "load_config", lambda path: SimpleNamespace(name=str(path)))
    monkeypatch.setattr(cli, "run_baseline", lambda cfg: calls.append(("baseline", cfg.name)))

    def _unexpected(*args, **kwargs):
        raise AssertionError("principal scenario runner must not be called")

    monkeypatch.setattr(cli.subprocess, "run", _unexpected)

    cli._run_study(
        config_path="configs/ireland_2015_2025.yaml",
        through="baseline",
        scenario=None,
        baseline_year=2020,
        allocation_rule="PRORATA",
        protection_strength=0.50,
    )

    assert calls == [("baseline", "configs/ireland_2015_2025.yaml")]


def test_study_sc3_builds_baseline_then_delegates_explicit_colm_controls(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(cli, "load_config", lambda path: SimpleNamespace(name=str(path)))
    monkeypatch.setattr(cli, "run_baseline", lambda cfg: calls.append(("baseline", cfg.name)))

    def _capture(command, check):
        calls.append(("principal", command, check))

    monkeypatch.setattr(cli.subprocess, "run", _capture)

    cli._run_study(
        config_path="configs/ireland_2015_2025.yaml",
        through="sc3",
        scenario="SI_SG",
        baseline_year=2020,
        allocation_rule="PRORATA",
        protection_strength=0.50,
        output_dir="results/test",
        colm_eligibility_rules="controls/colm_rules.csv",
        rewetting_capacity="controls/rewetting.csv",
    )

    assert calls[0] == ("baseline", "configs/ireland_2015_2025.yaml")
    _, command, check = calls[1]
    assert check is True
    assert command[1:3] == ["-m", "goblin_spatial.principal_cli"]
    assert "SI_SG" in command
    assert command[command.index("--stage") + 1] == "SC3"
    assert command[command.index("--allocation-rule") + 1] == "PRORATA"
    assert command[command.index("--output-dir") + 1] == "results/test"
    assert command[command.index("--colm-eligibility-rules") + 1] == "controls/colm_rules.csv"
    assert command[command.index("--rewetting-capacity") + 1] == "controls/rewetting.csv"


def test_study_requires_scenario_beyond_baseline(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_config", lambda path: SimpleNamespace())
    monkeypatch.setattr(cli, "run_baseline", lambda cfg: None)

    with pytest.raises(ValueError, match="--scenario is required"):
        cli._run_study(
            config_path="configs/ireland_2015_2025.yaml",
            through="sc1",
            scenario=None,
            baseline_year=2020,
            allocation_rule="PRORATA",
            protection_strength=0.50,
        )


def test_study_blocks_2025_sc2_sc3(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_config", lambda path: SimpleNamespace())
    monkeypatch.setattr(cli, "run_baseline", lambda cfg: None)

    with pytest.raises(ValueError, match="SC2/SC3 currently require"):
        cli._run_study(
            config_path="configs/ireland_2015_2025.yaml",
            through="sc3",
            scenario="SI_SG",
            baseline_year=2025,
            allocation_rule="PRORATA",
            protection_strength=0.50,
            colm_eligibility_rules="controls/colm_rules.csv",
        )


def test_study_sc3_requires_explicit_colm_rules(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_config", lambda path: SimpleNamespace())
    monkeypatch.setattr(cli, "run_baseline", lambda cfg: None)

    with pytest.raises(ValueError, match="--colm-eligibility-rules is required"):
        cli._run_study(
            config_path="configs/ireland_2015_2025.yaml",
            through="sc3",
            scenario="SI_SG",
            baseline_year=2020,
            allocation_rule="PRORATA",
            protection_strength=0.50,
        )


def test_parser_supports_reproducible_staged_study_command() -> None:
    args = cli._parser().parse_args(
        [
            "study",
            "--through",
            "sc2",
            "--scenario",
            "BE_SG",
            "--allocation-rule",
            "SOCIAL_VULNERABILITY_PROTECTION",
        ]
    )
    assert args.command == "study"
    assert args.through == "sc2"
    assert args.scenario == "BE_SG"
    assert args.allocation_rule == "SOCIAL_VULNERABILITY_PROTECTION"
