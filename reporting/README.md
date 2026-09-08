# Reporting outputs

Generated reporting artefacts belong here and are downstream of validated model outputs.

Expected subdirectories are created by the reporting builder as needed:

```text
reporting/
├── report_data/
├── figure_data/
├── table_data/
├── figures/
├── maps/
├── tables/
├── gis/
└── explorer/
```

Build canonical report data from completed principal runs with:

```bash
goblin-spatial-report-data \
  --principal-root data/processed/principal \
  --output-root reporting/report_data
```

The default writes typed Parquet tables plus transparent CSV companions and a provenance manifest. Generated reporting directories are ignored by Git; publish or archive selected outputs separately when required.

Do not place scientific controls or authoritative model inputs in this tree.
