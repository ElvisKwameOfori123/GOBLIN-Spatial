# GOBLIN-Spatial final results reporting

## Purpose

The final reporting layer is deliberately downstream of the scientific model. SC1, SC2 and SC3 continue to write canonical CSV outputs. Reporting code reads those completed runs and produces a coherent scientific package without altering any model mathematics or overwriting canonical results.

The architecture follows the useful separation adopted in the GOBLIN ecosystem: scenario generation first materialises structured result frames, and plotting/assessment tools consume those frames afterwards.

```text
validated historical baseline
        -> 12 principal SC1-SC3 runs
        -> canonical per-run CSV outputs
        -> cross-run scientific tables
        -> master Excel workbook + SQLite database
        -> high-resolution comparison figures
        -> maps later
```

## Principal study matrix

The final 2020 spatial foresight study is the exact cross-product of:

```text
Pathways
  SI_SG
  BE_SG
  ALL_GAS_NZ

Incidence rules
  PRORATA
  DAIRY_PROTECTION
  ECONOMIC_CAPACITY_PROTECTION
  SOCIAL_VULNERABILITY_PROTECTION
```

This gives 12 principal runs. The final study-report command requires the complete matrix by default. `--allow-partial` exists only for development and testing.

## Final outputs

Running:

```bash
goblin-spatial-study-report data/processed/final_principal \
  --output-dir data/processed/final_results
```

produces:

```text
GOBLIN_Spatial_Final_Results_Master.xlsx
GOBLIN_Spatial_Final_Results.sqlite
GOBLIN_Spatial_Figure_Data.csv
figures/
```

The Excel workbook is the human-readable scientific reporting object. The SQLite database is the queryable cross-run result store. The CSV figure table is the explicit bridge between numerical results and graphics.

## Workbook structure

The master workbook contains:

- run registry and controls;
- national headline results;
- livestock endpoints;
- SC1 exposure and distribution metrics;
- corrected three-ledger land accounting;
- SC3 national allocation and unmet targets;
- validation and GOBLIN reconciliation;
- protection-versus-PRORATA comparisons;
- redistribution summaries;
- robust/pathway/allocation sensitivity diagnostics;
- county results;
- full combined SC1, SC2 and SC3 ED results;
- figure data and an embedded figure gallery;
- a data dictionary.

The full ED sheets are retained for scientific auditability. Clean national and cross-run sheets are provided for normal reporting and manuscript use.

## SQLite structure

The SQLite database stores the same major study tables, including:

```text
run_registry
national_results
controls
livestock
metrics
county
reconciliation
land_accounting
validation
sc3_national
sc1_ed
sc2_ed
sc3_ed
sc1_comparison
redistribution
robust_exposure
figure_data
report_metadata
```

Indexes are added for the main scenario/rule/ED lookup paths.

## Figure package

The reporting layer currently generates high-resolution PNG and vector SVG outputs for:

1. national cattle composition at the pathway endpoint;
2. Standard Output production-value exposure across pathways and incidence rules;
3. realised allocation of released livestock land;
4. spatially unmet land-use targets, when non-zero;
5. protection relief and displaced production-value burden relative to PRORATA;
6. ED pathway sensitivity versus allocation-rule sensitivity.

The plots are produced from structured figure-data frames, not by recalculating model outputs inside the graphics functions.

## Land-accounting rule

The final reporting layer preserves three distinct quantities:

```text
GOBLIN parent Available target accounting
Realised post-Stage-A unallocated released land
Final unallocated released land after rewetting
```

The parent quantity reproduces national pathway accounting. The latter two report realised spatial feasibility. They must not be silently substituted for one another.

## Maps

Maps are intentionally not part of reporting version 1.0. The tabular and graphical result layer should first be scientifically frozen. Mapping can then consume the same combined ED tables for robust exposure, protection relief, displaced burden, released land, opportunity, unmet targets and final residual land.

## Reproducible full-run workflow

A manual GitHub Actions workflow, `.github/workflows/final-results.yml`, builds the historical baseline, runs all 12 principal SC1-SC3 combinations, creates the final reporting package and uploads it as the `GOBLIN-Spatial-final-results` artifact.
