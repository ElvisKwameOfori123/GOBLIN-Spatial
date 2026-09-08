"""Build canonical downstream report data from frozen GOBLIN-Spatial runs.

The builder follows a strict boundary:

    scientific engine -> frozen CSV outputs -> scientific cross-run synthesis
    -> typed report-data tables

It never invokes Baseline, SC1, SC2, SC3 or the feasible-geography solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Iterable

import pandas as pd

from goblin_spatial.reporting.catalog import file_sha256
from goblin_spatial.reporting.io import write_report_table
from goblin_spatial.reporting.validation import validate_reporting_root
from goblin_spatial.synthesis.sc1_crossrun import (
    Sc1FrozenRun,
    build_sc1_crossrun_synthesis,
    discover_sc1_runs,
    load_sc1_ensemble,
)


REPORT_DATA_VERSION = "1.0"

RUN_FILES = (
    "sc1_ed_results.csv",
    "sc1_national_livestock_summary.csv",
    "sc1_national_metrics.csv",
    "sc1_county_summary.csv",
    "sc1_control_summary.csv",
    "sc1_goblin_reconciliation.csv",
    "sc2_ed_context.csv",
    "sc3_ed_results.csv",
    "sc3_national_summary.csv",
)


@dataclass(frozen=True)
class ReportDataBuild:
    output_root: Path
    run_registry: pd.DataFrame
    source_files: pd.DataFrame
    written_tables: dict[str, dict[str, Path]]
    manifest_path: Path


def _detect_git_commit(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _run_record(run: Sc1FrozenRun, *, model_commit: str | None) -> dict[str, object]:
    return {
        "RUN_ID": run.run_id,
        "SCENARIO_ID": run.scenario_id,
        "BASELINE_YEAR": run.baseline_year,
        "TARGET_YEAR": run.target_year,
        "ALLOCATION_RULE": run.allocation_rule,
        "PROTECTION_STRENGTH_LAMBDA": run.protection_strength,
        "THROUGH_STAGE": run.through_stage,
        "RUN_DIRECTORY": str(run.run_dir),
        "MODEL_COMMIT": model_commit,
    }


def _source_file_records(
    runs: Iterable[Sc1FrozenRun],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for run in runs:
        for filename in RUN_FILES:
            path = run.run_dir / filename
            if not path.exists():
                continue
            records.append(
                {
                    "RUN_ID": run.run_id,
                    "FILENAME": filename,
                    "PATH": str(path),
                    "SHA256": file_sha256(path),
                    "SIZE_BYTES": int(path.stat().st_size),
                }
            )
    return records


def _read_run_tables(
    runs: Iterable[Sc1FrozenRun],
    filename: str,
) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    for run in runs:
        path = run.run_dir / filename
        if not path.exists():
            continue
        frame = pd.read_csv(path, low_memory=False)
        frame.insert(0, "RUN_ID", run.run_id)
        frame.insert(1, "REPORT_SCENARIO_ID", run.scenario_id)
        frame.insert(2, "REPORT_ALLOCATION_RULE", run.allocation_rule)
        frame.insert(3, "REPORT_BASELINE_YEAR", run.baseline_year)
        frame.insert(4, "REPORT_TARGET_YEAR", run.target_year)
        frames.append(frame)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True, sort=False)


def _write_named(
    written: dict[str, dict[str, Path]],
    name: str,
    frame: pd.DataFrame | None,
    *,
    output_root: Path,
    parquet: bool,
    csv: bool,
) -> None:
    if frame is None:
        return
    written[name] = write_report_table(
        frame,
        output_root / name,
        parquet=parquet,
        csv=csv,
    )


def build_report_data(
    principal_root: str | Path,
    output_root: str | Path = "reporting/report_data",
    *,
    project_root: str | Path = ".",
    expected_eds: int = 2857,
    parquet: bool = True,
    csv: bool = True,
    model_commit: str | None = None,
) -> ReportDataBuild:
    """Materialise canonical report-data tables from completed principal runs.

    Parameters
    ----------
    principal_root:
        Directory containing completed ``goblin-spatial-principal`` run folders.
    output_root:
        Generated report-data directory. It may not sit inside ``src``,
        ``data/inputs`` or ``data/controls``.
    expected_eds:
        Frozen ED universe expected for every SC1 run.
    parquet, csv:
        Output formats. Parquet is the canonical machine format; CSV is the
        transparent human-readable companion.
    model_commit:
        Optional explicit scientific-engine commit. If omitted, the builder
        attempts ``git rev-parse HEAD`` without failing if Git is unavailable.
    """

    project = Path(project_root).resolve()
    out = validate_reporting_root(project, output_root)
    runs = discover_sc1_runs(principal_root)
    commit = model_commit or _detect_git_commit(project)

    run_registry = pd.DataFrame(
        [_run_record(run, model_commit=commit) for run in runs]
    ).sort_values("RUN_ID", kind="stable").reset_index(drop=True)
    source_files = pd.DataFrame(_source_file_records(runs)).sort_values(
        ["RUN_ID", "FILENAME"], kind="stable"
    ).reset_index(drop=True)

    ensemble = load_sc1_ensemble(runs, expected_eds=expected_eds)
    synthesis = build_sc1_crossrun_synthesis(ensemble)

    written: dict[str, dict[str, Path]] = {}
    _write_named(written, "run_registry", run_registry, output_root=out, parquet=parquet, csv=csv)
    _write_named(written, "source_files", source_files, output_root=out, parquet=parquet, csv=csv)
    _write_named(written, "sc1/ed_results", synthesis.ensemble, output_root=out, parquet=parquet, csv=csv)
    _write_named(written, "sc1/comparison_ed", synthesis.comparison_ed, output_root=out, parquet=parquet, csv=csv)
    _write_named(written, "sc1/redistribution", synthesis.redistribution, output_root=out, parquet=parquet, csv=csv)
    _write_named(written, "sc1/robust_exposure", synthesis.robust_exposure, output_root=out, parquet=parquet, csv=csv)

    file_to_name = {
        "sc1_national_livestock_summary.csv": "sc1/national_livestock_summary",
        "sc1_national_metrics.csv": "sc1/national_metrics",
        "sc1_county_summary.csv": "sc1/county_summary",
        "sc1_control_summary.csv": "sc1/control_summary",
        "sc1_goblin_reconciliation.csv": "sc1/reconciliation",
        "sc2_ed_context.csv": "sc2/ed_context",
        "sc3_ed_results.csv": "sc3/ed_results",
        "sc3_national_summary.csv": "sc3/national_summary",
    }
    for filename, name in file_to_name.items():
        _write_named(
            written,
            name,
            _read_run_tables(runs, filename),
            output_root=out,
            parquet=parquet,
            csv=csv,
        )

    manifest = {
        "REPORT_DATA_VERSION": REPORT_DATA_VERSION,
        "BUILT_AT_UTC": datetime.now(timezone.utc).isoformat(),
        "MODEL_COMMIT": commit,
        "PRINCIPAL_ROOT": str(Path(principal_root).resolve()),
        "EXPECTED_EDS": int(expected_eds),
        "RUN_COUNT": int(len(run_registry)),
        "SCENARIOS": sorted(run_registry["SCENARIO_ID"].astype(str).unique().tolist()),
        "ALLOCATION_RULES": sorted(run_registry["ALLOCATION_RULE"].astype(str).unique().tolist()),
        "TABLES": {
            name: {fmt: str(path) for fmt, path in paths.items()}
            for name, paths in sorted(written.items())
        },
        "BOUNDARY": "REPORTING_READS_FROZEN_RESULTS_AND_DOES_NOT_RECALCULATE_MODEL_SCIENCE",
    }
    manifest_path = out / "report_data_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ReportDataBuild(
        output_root=out,
        run_registry=run_registry,
        source_files=source_files,
        written_tables=written,
        manifest_path=manifest_path,
    )
