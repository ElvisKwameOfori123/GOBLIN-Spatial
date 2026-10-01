# Running GOBLIN-Spatial

GOBLIN-Spatial now has one active scientific scope in this repository: the **2015-2025 historical baseline, multiscale reporting/signatures, evaluation and illustrative perturbation**.

Scenario-development code is preserved separately in `ElvisKwameOfori123/GOBLIN-Spatial-SC` and is not part of this runtime.

## Install

Python 3.10 or newer is required.

```bash
pip install -e ".[geo,reporting,query]"
```

## Verify repository inputs

```bash
goblin-spatial fetch-data --verify-only
```

The command checks the repository-contained scientific inputs against `data_manifest.yaml` and downloads nothing.

## Build only the core historical baseline

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

This reconstructs the 2015-2025 ED panel through livestock cohorts, land/farm structure, fixed-2020 Standard Output and ED cohort signatures.

## Build the complete historical release

For the manuscript and query-ready release, use:

```bash
python scripts/build_historical_release.py
```

The script runs, in order:

1. core historical baseline build;
2. historical evaluation and cattle diagnostics;
3. county, WFD catchment, GOBLIN-compatible catchment and national views;
4. the independent coherence audit;
5. the historical release bundle, including livestock signatures, parent-follower relationships and the illustrative perturbation.

If any step fails, the build stops.

The final release is written to:

```text
reporting/report_data/historical/
```

The directory contains CSV and Parquet tables plus `historical_results.sqlite` and `historical_results.duckdb`. See `docs/historical_outputs.md` for the table guide.

## Individual build steps

These remain available for development and diagnosis:

```bash
python scripts/build_cattle_annual_panel.py
python scripts/build_sheep_annual_panel.py
python scripts/build_livestock_panels.py
python scripts/run_historical_validation.py
python scripts/run_cattle_code2_two_anchor_diagnostics.py
python scripts/run_cattle_genetics_diagnostics.py
python scripts/build_catchment_baseline.py
python scripts/audit_historical_baseline.py
python scripts/build_historical_results_bundle.py
```

## Reporting boundary

The historical ED baseline is the scientific authority. County, catchment and national views are derived from that common ED state. Livestock signatures and the illustrative perturbation are derived analytical products and do not rebuild or alter the baseline.
