# Running GOBLIN-Spatial

GOBLIN-Spatial can be run either interactively or with explicit reproducible commands.

The guided interface is a thin wrapper around the validated historical baseline and principal SC1 -> SC2 -> SC3 runner. It does not change scenario mathematics.

## Guided mode

Run:

```bash
goblin-spatial
```

When launched from an interactive terminal, GOBLIN-Spatial asks how far the study should run:

```text
1. Baseline only
2. Baseline + SC1 livestock transition
3. Baseline + SC1 + SC2 opportunity analysis
4. Full study: Baseline + SC1 + SC2 + SC3
```

If `Baseline only` is selected, the validated 2015-2025 historical baseline is built through Stage 09 and the workflow stops. No scenario questions are asked.

For SC1, SC2 or SC3, the interface then asks for the active national GOBLIN pathway and the spatial incidence rule. SC1 may use the reconstructed 2020 or 2025 livestock baseline. SC2 and SC3 remain restricted to the validated frozen 2020 spatial context.

## Explicit reproducible mode

The same stop points are available without prompts through the `study` command.

### Baseline only

```bash
goblin-spatial study --through baseline
```

### Baseline + SC1

```bash
goblin-spatial study \
  --through sc1 \
  --scenario SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

### Baseline + SC1 + SC2

```bash
goblin-spatial study \
  --through sc2 \
  --scenario SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

### Full study through SC3

```bash
goblin-spatial study \
  --through sc3 \
  --scenario SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

The active scenario IDs are read from `data/controls/scenario/GOBLIN_Scenario_Controls.csv`. The validated principal incidence rules are:

```text
PRORATA
DAIRY_PROTECTION
ECONOMIC_CAPACITY_PROTECTION
SOCIAL_VULNERABILITY_PROTECTION
```

The default protection strength remains the validated principal value of `0.50` and can be changed explicitly with `--protection-strength` for sensitivity analysis.

## Scientific reporting workbook

After a completed principal run, create the scientific reporting package with:

```bash
goblin-spatial-report data/processed/principal/SI_SG_2020_PRORATA
```

The reporting command reads the canonical run CSV files and writes derived reporting outputs without overwriting them:

```text
GOBLIN_Spatial_Scientific_Results.xlsx
sc3_land_accounting_summary.csv
sc3_scientific_validation.csv
```

The workbook separates parent GOBLIN target accounting from realised spatial feasibility. In particular, it reports three distinct land quantities:

```text
GOBLIN parent Available target
SC3 post-Stage-A unallocated released land
SC3 final unallocated released land after rewetting
```

This avoids using one `Available` label for different accounting concepts. The canonical model CSV files remain the machine-readable source of truth.

An alternative workbook location can be supplied explicitly:

```bash
goblin-spatial-report data/processed/principal/SI_SG_2020_PRORATA \
  --output results/SI_SG_PRORATA_scientific_results.xlsx
```

## Existing low-level commands remain supported

Repository verification:

```bash
goblin-spatial fetch-data --verify-only
```

Historical baseline only:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Direct principal scenario execution remains available for users who already have a validated Stage-08 baseline:

```bash
goblin-spatial-principal SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --stage SC3
```

The staged `goblin-spatial study` command intentionally rebuilds the validated historical baseline first, then delegates scenario execution to `goblin-spatial-principal` and stops after the requested stage.
