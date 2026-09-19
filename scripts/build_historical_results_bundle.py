#!/usr/bin/env python
"""Build canonical manuscript-facing data for the historical GOBLIN-Spatial paper.

The ED x year baseline remains authoritative. This script materialises transparent
CSV/Parquet tables plus a read-only-style DuckDB query copy for inspection.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.synthesis.historical import build_historical_result_tables


def _configured_output(cfg, key: str, default: str) -> Path:
    raw = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(raw)
    return path if path.is_absolute() else cfg.project_root / path


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument(
        "--output-root",
        default="reporting/report_data/historical",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    root = cfg.project_root
    master_path = _configured_output(
        cfg,
        "standard_output_master",
        "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    wfd_path = root / "data/processed/goblin_spatial_wfd_catchment_2015_2025.csv"
    crosswalk_path = root / "data/processed/ed_wfd_catchment_crosswalk.csv"
    validation_dir = root / "data/processed/validation/historical"

    required = [master_path, wfd_path, crosswalk_path, validation_dir / "historical_validation_overview.csv"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Historical result bundle requires completed baseline, validation and "
            f"catchment outputs. Missing: {missing}"
        )

    master = pd.read_csv(master_path, low_memory=False)
    wfd = pd.read_csv(wfd_path, low_memory=False)
    crosswalk = pd.read_csv(crosswalk_path, dtype={"CSOED": str}, low_memory=False)

    tables = build_historical_result_tables(
        master,
        wfd,
        crosswalk,
        ed_anchor_path=root / cfg.files["cso_ed_2020"],
        cattle_control_path=root / cfg.files["cso_cattle_county"],
        validation_dir=validation_dir,
    )

    out = Path(args.output_root)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    table_meta: dict[str, dict[str, object]] = {}
    for name, frame in tables.items():
        csv_path = out / f"{name}.csv"
        parquet_path = out / f"{name}.parquet"
        frame.to_csv(csv_path, index=False)
        frame.to_parquet(parquet_path, index=False)
        table_meta[name] = {
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "csv": str(csv_path.relative_to(root)),
            "parquet": str(parquet_path.relative_to(root)),
            "csv_sha256": _sha(csv_path),
            "parquet_sha256": _sha(parquet_path),
        }

    # Optional SQL query copy. Parquet/CSV remain the canonical reporting files.
    db_path = out / "historical_results.duckdb"
    try:
        import duckdb
    except ImportError:
        duckdb = None

    if duckdb is not None:
        if db_path.exists():
            db_path.unlink()
        con = duckdb.connect(str(db_path))
        try:
            for name, frame in tables.items():
                con.register("_frame", frame)
                con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _frame')
                con.unregister("_frame")
            con.execute(
                "CREATE TABLE _bundle_metadata AS SELECT ? AS model_commit, ? AS note",
                [
                    _git_commit(root),
                    "Query copy only; CSV/Parquet are canonical reporting data.",
                ],
            )
        finally:
            con.close()

    sources = {
        str(master_path.relative_to(root)): _sha(master_path),
        str(wfd_path.relative_to(root)): _sha(wfd_path),
        str(crosswalk_path.relative_to(root)): _sha(crosswalk_path),
        str((validation_dir / "historical_validation_overview.csv").relative_to(root)): _sha(
            validation_dir / "historical_validation_overview.csv"
        ),
    }
    manifest = {
        "bundle": "GOBLIN_SPATIAL_HISTORICAL_RESULTS",
        "version": "1.0",
        "model_commit": _git_commit(root),
        "authoritative_state": str(master_path.relative_to(root)),
        "reporting_boundary": (
            "Derived manuscript/query data only. Does not alter baseline science."
        ),
        "sources": sources,
        "tables": table_meta,
        "duckdb": str(db_path.relative_to(root)) if db_path.exists() else None,
    }
    (out / "historical_results_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Historical result bundle:", out)
    print("Tables:", ", ".join(sorted(tables)))
    print("\nAnchor reconciliation:")
    print(tables["anchor_reconciliation_2020"].to_string(index=False))
    print("\nSO decomposition:")
    print(tables["so_change_2015_2025"].to_string(index=False))
    print("\nStable-ED sensitivity:")
    print(tables["stable_ed_sensitivity"].to_string(index=False))
    print("\nMultiscale example:")
    print(tables["multiscale_example_2020"].to_string(index=False))
    print("\nTop matched pairs:")
    print(tables["matched_pairs_2020"].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
