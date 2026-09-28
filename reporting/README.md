# Reporting

The `reporting/` tree contains **derived reporting products built from validated GOBLIN-Spatial outputs**. It is downstream of the scientific baseline: reporting organises, queries, maps and presents model results without changing the underlying agricultural reconstruction.

For the current historical-baseline release, the authoritative scientific state remains the validated ED × year baseline under `data/processed/`. Reporting products are derived from that state.

---

## Install reporting dependencies

From the repository root:

```bash
pip install -e ".[reporting]"
```

This installs the geospatial, Parquet and plotting dependencies used by the reporting layer.

To include the optional DuckDB query interface:

```bash
pip install -e ".[reporting,query]"
```

DuckDB is a convenience query layer over the reporting tables. The CSV/Parquet products remain the canonical reporting data.

---

## Historical baseline reporting

After the historical baseline, validation diagnostics and catchment products have been built, create the historical reporting bundle with:

```bash
python scripts/build_historical_results_bundle.py
```

The bundle is written to:

```text
reporting/report_data/historical/
```

It contains transparent CSV and Parquet tables together with a provenance manifest. If the optional `query` dependency is installed, the build also creates a DuckDB query copy.

The reporting bundle is intended for manuscript analysis, reproducible queries and downstream visualisation. It does not recalculate or modify baseline science.

See [`docs/historical_results_bundle.md`](../docs/historical_results_bundle.md) for the table inventory and query examples.

---

## Reporting structure

Reporting directories are created as needed:

```text
reporting/
├── report_data/     # canonical derived reporting tables
├── figure_data/     # figure-ready extracts
├── table_data/      # table-ready extracts
├── figures/         # generated figures
├── maps/            # generated maps
├── tables/          # rendered tables
├── gis/             # GIS-ready exports
├── query/           # optional query databases/catalogues
└── explorer/        # optional interactive/exploration outputs
```

Generated reporting artefacts are generally ignored by Git. Publish or archive selected outputs separately when required.

Scientific controls and authoritative model inputs belong under `data/`, not in `reporting/`.

---

## Future pathway reporting

The reporting framework can also materialise report data from completed future pathway runs:

```bash
goblin-spatial-report-data \
  --principal-root data/processed/principal \
  --output-root reporting/report_data
```

This produces typed Parquet tables, transparent CSV companions and provenance metadata from completed model outputs.

Future pathway reporting builds on the frozen historical baseline and remains separate from the baseline reconstruction itself.

---

## Reporting principle

> **Scientific outputs are produced upstream; reporting makes them easier to inspect, compare and communicate.**

The reporting layer may aggregate, reshape or format validated outputs for analysis and presentation, but it does not change the scientific controls or the underlying model state.
