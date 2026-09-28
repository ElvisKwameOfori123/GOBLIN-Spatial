# Running GOBLIN-Spatial

> **Current release: the 2015-2025 historical baseline.** Scenario modules (SC1-SC3) remain in the repository but are dormant and not part of the historical baseline release. `goblin-spatial study` defaults to `--through baseline`, and the guided runner offers the baseline only; scenario stages run only when requested explicitly (`--through sc1|sc2|sc3`, or `GOBLIN_SPATIAL_SCENARIOS=1` for the guided menu). The sections below document those stages for later use.

GOBLIN-Spatial supports four explicit stopping points:

```text
Baseline
SC1
SC2
SC3
```

The staged interface is deliberate. A user can inspect or validate each scientific boundary before continuing downstream.

## Guided interface

Run:

```bash
goblin-spatial
```

The interactive runner offers:

```text
1. Baseline only
2. Through SC1
3. Through SC2
4. Full study through SC3
```

For scenario stages it then asks for an active national GOBLIN pathway and a spatial incidence rule. SC1 may use the 2020 or reconstructed 2025 livestock baseline. SC2 and SC3 use the validated 2020 spatial soil + LPIS context only.

## Reproducible staged execution

### Baseline only

```bash
goblin-spatial study --through baseline
```

### Through SC1

```bash
goblin-spatial study \
  --through sc1 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

### Through SC2

SC2 can be run as physical-resource + LPIS context without applying future-use eligibility:

```bash
goblin-spatial study \
  --through sc2 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

An explicit eligibility-control file may also be supplied where a scientifically approved rule set exists.

### Through SC3

SC3 requires a complete, versioned, evidence-backed eligibility-control file. There is no default land-use suitability matrix.

```bash
goblin-spatial study \
  --through sc3 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --colm-eligibility-rules path/to/validated_soil_eligibility.csv \
  --rewetting-capacity path/to/validated_rewetting_capacity.csv
```

`--rewetting-capacity` is required only when the selected pathway has a positive rewetting target. Mapped peat is not accepted as a substitute for validated drained agricultural organic-soil capacity.

The `--colm-eligibility-rules` flag retains the source-preparation name used by the internal control loader. The scientific object supplied by the file is a **soil/drainage-class eligibility rule set**.

## Active pathways

Active scenario IDs are read from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

The current active pathways are:

```text
SI_SG
BE_SG
ALL_GAS_NZ
```

All quantities used in one run must come from the same scenario ID.

## Spatial incidence rules

The validated principal SC1 incidence rules are:

```text
PRORATA
DAIRY_PROTECTION
ECONOMIC_CAPACITY_PROTECTION
SOCIAL_VULNERABILITY_PROTECTION
```

The default protection strength is `0.50`. It can be changed explicitly for sensitivity analysis with `--protection-strength`.

## Repository verification

Verify repository-contained inputs and checksums with:

```bash
goblin-spatial fetch-data --verify-only
```

## Historical baseline build

The historical baseline can also be built directly:

```bash
goblin-spatial build \
  --config configs/ireland_2015_2025.yaml
```

This reconstructs the validated 2015-2025 panel and writes the Standard Output-enriched baseline used by SC1.

## Low-level principal runner

Advanced users who already have a validated baseline can call the principal runner directly:

```bash
goblin-spatial-principal BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --stage SC2
```

The high-level `goblin-spatial study` command is preferred for ordinary use because it rebuilds the validated baseline before continuing to the selected stage.

## Output directories

By default, scenario results are written beneath:

```text
data/processed/principal/<SCENARIO>_<BASELINE_YEAR>_<ALLOCATION_RULE>/
```

Typical stage outputs include:

```text
sc1_ed_results.csv
sc1_national_livestock_summary.csv
sc1_national_metrics.csv
sc1_county_summary.csv
sc1_control_summary.csv
sc1_goblin_reconciliation.csv
sc2_ed_context.csv
sc3_ed_results.csv
sc3_national_summary.csv
```

A custom output directory can be supplied with `--output-dir`.

## Reporting boundary

The scientific engine stops at validated frozen outputs. Maps, charts, tables and publication figures are downstream reporting products and should read these files without recalculating SC1, SC2 or SC3 science.
