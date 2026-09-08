"""Cross-run SC1 synthesis from frozen principal-run outputs.

This module is intentionally downstream of completed SC1 runs.  It discovers
and combines frozen ``sc1_ed_results.csv`` files and delegates all scientific
comparison mathematics to :mod:`goblin_spatial.scenario.comparison`.

It never reruns livestock allocation, cohort propagation, Standard Output,
release spatialisation, SC2 or SC3.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from goblin_spatial.scenario.comparison import (
    build_sc1_robust_exposure,
    compare_sc1_to_prorata,
    summarise_sc1_redistribution,
)


SC1_ED_FILE = "sc1_ed_results.csv"
SC1_CONTROL_FILE = "sc1_control_summary.csv"


@dataclass(frozen=True)
class Sc1FrozenRun:
    """Identity and location of one completed SC1 principal run."""

    run_id: str
    run_dir: Path
    scenario_id: str
    baseline_year: int
    target_year: int
    allocation_rule: str
    protection_strength: float
    through_stage: str


@dataclass(frozen=True)
class Sc1CrossRunSynthesis:
    """Validated SC1 ensemble and its existing scientific comparison outputs."""

    ensemble: pd.DataFrame
    comparison_ed: pd.DataFrame
    redistribution: pd.DataFrame
    robust_exposure: pd.DataFrame


def _single_control_row(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if len(frame) != 1:
        raise ValueError(f"SC1 control summary must contain exactly one row: {path}")
    required = {
        "SCENARIO_ID",
        "RUN_START_YEAR",
        "TARGET_YEAR",
        "ALLOCATION_POLICY",
        "PROTECTION_STRENGTH_LAMBDA",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SC1 control summary missing columns {missing}: {path}")
    return frame.iloc[0]


def _stage_for_run(run_dir: Path) -> str:
    if (run_dir / "sc3_ed_results.csv").exists():
        return "SC3"
    if (run_dir / "sc2_ed_context.csv").exists():
        return "SC2"
    return "SC1"


def discover_sc1_runs(principal_root: str | Path) -> list[Sc1FrozenRun]:
    """Discover completed principal runs beneath ``principal_root``.

    A directory qualifies only when both the frozen SC1 ED results and the
    one-row SC1 control summary are present.  Run identity comes from the
    control summary rather than from the directory name.
    """

    root = Path(principal_root)
    if not root.exists():
        raise FileNotFoundError(f"principal run root not found: {root}")

    runs: list[Sc1FrozenRun] = []
    for ed_path in sorted(root.rglob(SC1_ED_FILE)):
        run_dir = ed_path.parent
        control_path = run_dir / SC1_CONTROL_FILE
        if not control_path.exists():
            raise FileNotFoundError(
                f"frozen SC1 run is missing {SC1_CONTROL_FILE}: {run_dir}"
            )
        control = _single_control_row(control_path)
        scenario = str(control["SCENARIO_ID"]).strip()
        baseline_year = int(control["RUN_START_YEAR"])
        target_year = int(control["TARGET_YEAR"])
        rule = str(control["ALLOCATION_POLICY"]).strip().upper()
        strength = float(control["PROTECTION_STRENGTH_LAMBDA"])
        run_id = f"{scenario}__{baseline_year}__{rule}"
        runs.append(
            Sc1FrozenRun(
                run_id=run_id,
                run_dir=run_dir,
                scenario_id=scenario,
                baseline_year=baseline_year,
                target_year=target_year,
                allocation_rule=rule,
                protection_strength=strength,
                through_stage=_stage_for_run(run_dir),
            )
        )

    if not runs:
        raise FileNotFoundError(
            f"no completed SC1 runs containing {SC1_ED_FILE} were found beneath {root}"
        )

    ids = [run.run_id for run in runs]
    if len(ids) != len(set(ids)):
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        raise ValueError(f"duplicate frozen run identities discovered: {duplicates}")
    return runs


def load_sc1_ensemble(
    runs: Iterable[Sc1FrozenRun],
    *,
    expected_eds: int | None = 2857,
) -> pd.DataFrame:
    """Load frozen SC1 ED tables into one validated cross-run ensemble."""

    frames: list[pd.DataFrame] = []
    for run in runs:
        path = run.run_dir / SC1_ED_FILE
        frame = pd.read_csv(path, low_memory=False)
        if "CSOED" not in frame.columns:
            raise ValueError(f"SC1 ED result missing CSOED: {path}")
        if frame["CSOED"].duplicated().any():
            raise ValueError(f"SC1 ED result contains duplicate CSOED values: {path}")
        if expected_eds is not None and len(frame) != int(expected_eds):
            raise ValueError(
                f"SC1 ED result has {len(frame)} rows, expected {int(expected_eds)}: {path}"
            )

        if "PATHWAY_NAME" in frame.columns:
            values = set(frame["PATHWAY_NAME"].astype(str).str.strip())
            if values != {run.scenario_id}:
                raise ValueError(
                    f"SC1 pathway identity disagrees with control summary for {run.run_id}: {values}"
                )
        else:
            frame["PATHWAY_NAME"] = run.scenario_id

        if "PATHWAY_ALLOCATION_RULE" in frame.columns:
            values = set(frame["PATHWAY_ALLOCATION_RULE"].astype(str).str.strip().str.upper())
            if values != {run.allocation_rule}:
                raise ValueError(
                    f"SC1 allocation identity disagrees with control summary for {run.run_id}: {values}"
                )
        else:
            frame["PATHWAY_ALLOCATION_RULE"] = run.allocation_rule

        frame["RUN_ID"] = run.run_id
        frame["REPORT_BASELINE_YEAR"] = run.baseline_year
        frame["REPORT_TARGET_YEAR"] = run.target_year
        frame["REPORT_THROUGH_STAGE"] = run.through_stage
        frames.append(frame)

    ensemble = pd.concat(frames, ignore_index=True, sort=False)
    if ensemble[["RUN_ID", "CSOED"]].duplicated().any():
        raise ValueError("SC1 reporting ensemble requires one row per RUN_ID x CSOED")
    return ensemble


def build_sc1_crossrun_synthesis(
    ensemble: pd.DataFrame,
) -> Sc1CrossRunSynthesis:
    """Build the validated SC1 redistribution and robustness products.

    The formulas remain owned by ``scenario.comparison``.  This function only
    orchestrates those frozen scientific interfaces and packages their outputs
    for downstream report-data materialisation.
    """

    comparison = compare_sc1_to_prorata(ensemble)
    redistribution = summarise_sc1_redistribution(comparison)
    robust = build_sc1_robust_exposure(ensemble)
    return Sc1CrossRunSynthesis(
        ensemble=ensemble,
        comparison_ed=comparison,
        redistribution=redistribution,
        robust_exposure=robust,
    )
