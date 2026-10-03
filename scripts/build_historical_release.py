#!/usr/bin/env python
"""Build the complete 2015-2025 historical baseline release, in order.

    python scripts/build_historical_release.py

Runs the same sequence as CI:

0. Stage 00 census input check: the prepared 2010 and 2020 ED census inputs
   must regenerate exactly from the raw AVA42 table
   (scripts/prepare_census_inputs.py --check)
1. core build: livestock (CSO 13, GOBLIN 31), land, farm structure,
   Standard Output, 2020 ED signatures
2. historical validation and cattle diagnostics
3. county, WFD catchment, Colm catchment and national views
4. cross-product coherence audit (stops here if any check fails)
5. release bundle: CSV + Parquet tables, DuckDB and SQLite copies,
   _columns dictionary, _readme

Output: reporting/report_data/historical/ (see docs/historical_outputs.md).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument(
        "--skip-stage00-check",
        action="store_true",
        help="build from census inputs that differ from Stage 00 (robustness variants only)",
    )
    parser.add_argument(
        "--no-audit-stop",
        action="store_true",
        help="continue past a failed coherence audit (robustness variants only)",
    )
    args = parser.parse_args()
    config = ["--config", args.config]

    steps = [
        ("Stage 00 census input check", [sys.executable, "scripts/prepare_census_inputs.py", "--check"]),
        ("Core baseline build", [sys.executable, "-m", "goblin_spatial.cli", "build", *config]),
        ("Historical validation", [sys.executable, "scripts/run_historical_validation.py"]),
        ("Cattle two-anchor diagnostics", [sys.executable, "scripts/run_cattle_code2_two_anchor_diagnostics.py"]),
        ("Cattle genetics diagnostics", [sys.executable, "scripts/run_cattle_genetics_diagnostics.py"]),
        ("County, catchment and national views", [sys.executable, "scripts/build_catchment_baseline.py"]),
        ("Coherence audit", [sys.executable, "scripts/audit_historical_baseline.py", *config]),
        ("Release bundle", [sys.executable, "scripts/build_historical_results_bundle.py", *config]),
    ]
    if args.skip_stage00_check:
        steps = steps[1:]
    if args.no_audit_stop:
        steps = [(label, cmd + ["--allow-audit-failures"] if label == "Release bundle" else cmd) for label, cmd in steps]
    for number, (label, command) in enumerate(steps, start=1):
        print(f"\n[{number}/{len(steps)}] {label}", flush=True)
        start = time.time()
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0 and args.no_audit_stop and label == "Coherence audit":
            print("      coherence audit failed; continuing (--no-audit-stop)", flush=True)
            continue
        if result.returncode != 0:
            print(f"Stopped: '{label}' failed (exit {result.returncode}).", file=sys.stderr)
            return result.returncode
        print(f"      done in {time.time() - start:.0f} s", flush=True)

    print("\nHistorical release complete: reporting/report_data/historical/")
    print("  historical_results.sqlite and historical_results.duckdb hold every table;")
    print("  _readme and _columns explain them. See docs/historical_outputs.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
