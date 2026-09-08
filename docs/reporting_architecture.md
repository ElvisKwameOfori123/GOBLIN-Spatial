# GOBLIN-Spatial reporting architecture

## Purpose

GOBLIN-Spatial separates scientific calculation from reporting so that maps, charts, tables and interactive exploration cannot silently alter model results.

The governing rule is:

> **Reporting reads frozen results; reporting never creates model results.**

The architecture is informed by established modelling practice in GOBLIN/COHORTS, LUTO2 and its downstream Vue reporting system, parameter-sweep explorers such as LandOpti, post-processing and agreement mapping in Nature's Frontiers, and the broader principle used in integrated assessment and spatial optimisation systems of preserving technical model outputs before generating standardised reporting products.

GOBLIN-Spatial does not depend on those projects. Their useful software patterns are adapted to the scientific boundaries of this framework.

---

## Scientific boundary

The complete flow is:

```text
GOBLIN national pathway
        ↓
Baseline / SC1 / SC2 / SC3
        ↓
validated frozen run outputs
        ↓
SCIENTIFIC SYNTHESIS
cross-run comparisons already defined by the scientific engine
        ↓
standardised report data
        ↓
PUBLICATION REPORTING
maps / charts / tables / GIS exports
        ↓
OPTIONAL INTERACTIVE EXPLORER
precomputed results only
```

Three layers are deliberately distinguished.

### Model layer

The model creates scientific results. This includes livestock allocation, cohort propagation, production-value exposure, authoritative released-land spatialisation, physical-resource characterisation, eligibility, finite-resource SC3 allocation and feasible-geography optimisation.

### Scientific synthesis layer

The synthesis layer compares already completed model runs. It may invoke scientific comparison functions that are part of the validated model, for example:

- protection relief relative to PRORATA;
- displaced burden;
- robust minimum exposure;
- pathway sensitivity;
- allocation-rule sensitivity;
- post-SC3 same-end-use flexibility diagnostics.

It must not rerun or modify the underlying scenario.

### Reporting layer

Reporting may:

- catalogue completed runs;
- hash and register source result files;
- materialise typed report-data tables;
- select columns and reshape existing results for presentation;
- join results to the single frozen ED geometry;
- format labels, units and legends;
- create exact figure-data extracts;
- render maps, graphs, tables and GIS-ready outputs.

Reporting must not:

- allocate livestock;
- recalculate released land;
- infer soil or future-use eligibility;
- solve SC3;
- rerun feasible-geography optimisation;
- change pathway controls;
- derive an alternative definition of robustness, exposure or redistribution.

A dedicated test prevents the reporting package from importing the main model-allocation and solver modules.

---

## Frozen run contract

A principal GOBLIN-Spatial run may contain:

```text
sc1_ed_results.csv
sc1_national_livestock_summary.csv
sc1_national_metrics.csv
sc1_county_summary.csv
sc1_control_summary.csv
sc1_goblin_reconciliation.csv
sc2_ed_context.csv                 # when SC2 was completed
sc3_ed_results.csv                 # when SC3 was completed
sc3_national_summary.csv           # when SC3 was completed
```

These files remain the native scientific outputs. The reporting architecture consumes them rather than replacing them.

A reporting run identity is taken from the scientific control summary, not guessed from a directory name. The canonical identity is:

```text
SCENARIO_ID__BASELINE_YEAR__ALLOCATION_RULE
```

For example:

```text
BE_SG__2020__PRORATA
BE_SG__2020__DAIRY_PROTECTION
ALL_GAS_NZ__2020__SOCIAL_VULNERABILITY_PROTECTION
```

The report-data registry also stores target year, protection strength, completed stage, source directory and scientific-engine commit where available.

Every consumed source file is registered with a SHA-256 digest and byte size so a reporting product can be traced back to the exact frozen result files from which it was created.

---

## Canonical report-data formats

The reporting layer uses files rather than a second authoritative model database.

### Machine-readable tables

**Parquet** is the preferred machine-readable report-data format because it preserves types, is compact and supports efficient cross-run analysis.

### Transparent companion tables

**CSV** is written alongside Parquet for inspection, collaboration and archival transparency.

### Spatial geometry

The one geometry authority is:

```text
data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg
```

Results are joined using `CSOED`. Geometry is not copied into every scientific result table.

Every complete ED map must satisfy:

```text
model EDs = geometry EDs = joined EDs = 2,857
```

before rendering is permitted.

### Metadata and provenance

JSON/YAML records are used for:

- report-data manifests;
- run metadata;
- metric metadata;
- figure-data manifests;
- future publication-figure definitions.

### SQL-style querying

DuckDB may be used as an optional query interface over Parquet. It is not a second source of scientific truth and is not required by the model engine.

### Excel and GIS exports

Excel workbooks and GIS-ready layers are downstream dissemination products generated from standardised report data. They are not analytical inputs to later figures.

---

## Report-data layout

Generated outputs are written below `reporting/` and are ignored by Git. Source code and the reporting contract remain tracked.

```text
reporting/
├── report_data/
│   ├── run_registry.parquet
│   ├── source_files.parquet
│   ├── sc1/
│   │   ├── ed_results.parquet
│   │   ├── national_metrics.parquet
│   │   ├── county_summary.parquet
│   │   ├── comparison_ed.parquet
│   │   ├── redistribution.parquet
│   │   └── robust_exposure.parquet
│   ├── sc2/
│   │   └── ed_context.parquet
│   ├── sc3/
│   │   ├── ed_results.parquet
│   │   └── national_summary.parquet
│   └── report_data_manifest.json
├── figure_data/
├── table_data/
├── figures/
├── maps/
├── tables/
├── gis/
└── explorer/
```

CSV companions are generated beside the Parquet tables when requested.

Post-SC3 flexibility products will be added to the same contract when a completed feasible-geography analysis is materialised for publication.

---

## SC1 scientific synthesis

SC1 is not reduced to one livestock-change map. Its reporting architecture preserves the full incidence and distributional result family.

Completed SC1 runs are combined into one ED × pathway × allocation-rule ensemble. The synthesis layer then delegates to the existing validated scientific functions in `scenario/comparison.py`.

The resulting report-data products include:

### Transition incidence

- total cattle reduction and local expansion;
- livestock production-value exposure and local gain;
- per-holding exposure intensity;
- authoritative released grassland;
- independent pasture-DM diagnostics;
- national shares and concentration diagnostics.

### Protection and redistribution

Relative to PRORATA, the model reports:

```text
SIGNED_DIFFERENCE_FROM_PRORATA
PROTECTION_RELIEF
DISPLACED_BURDEN
```

for the scientific metrics supported by the comparison layer.

### Robust and contingent exposure

For the complete supplied pathway × implementation ensemble, the model reports continuous diagnostics including:

```text
ROBUST_MIN
MEAN
MAX
TOTAL_RANGE
PATHWAY_SENSITIVITY
ALLOCATION_SENSITIVITY
```

No reporting code invents an alternative threshold or weighted robustness score.

---

## SC2 reporting

SC2 reporting begins only after SC1 release is frozen.

It can report:

- mapped physical soil/drainage composition of released transition space;
- LPIS agricultural context;
- evidence-backed future-use eligibility where a validated rule set has been supplied;
- productive response potential where supported by the scientific controls.

The reporting layer must preserve the distinction:

```text
released land
!= physical resource
!= eligibility
!= opportunity
```

Rewetting is reported as an environmental/restoration land requirement and capacity. It must not automatically contribute to a productive livelihood/adaptability score.

---

## SC3 and spatial-flexibility reporting

SC3 reporting uses the frozen finite-resource allocation output and must preserve:

```text
Target = Realised + Unmet
```

for each land use.

An unmet target is a spatial-feasibility result, not a software error.

The optional post-SC3 analysis holds the realised national hectares of **each end use separately** fixed while exploring alternative feasible geographies. Reporting may display existing sampled-frequency, sampled-range and exact-bound outputs but must not rerun the optimisation itself.

Useful future spatial-flexibility products include:

- reference allocation;
- sampled minimum and maximum allocation;
- sampled allocation range;
- positive allocation frequency;
- persistent/robust-positive locations;
- exact selected ED-use minimum and maximum bounds.

This follows the useful general idea of spatial agreement/persistence mapping across alternative feasible solutions, while retaining the specific GOBLIN-Spatial interpretation: alternatives are feasible same-outcome geographies, not predicted adoption probabilities.

---

## Metric registry

Presentation metadata are kept separately from scientific formulas.

The metric registry may specify:

- publication label;
- unit;
- scientific result family;
- stage;
- sequential or diverging visual semantics;
- optional visual midpoint;
- interpretation boundary.

It must never contain a new scientific formula.

For example, Standard Output exposure is consistently labelled as **livestock production-value exposure**. It is not farm income, profitability or household welfare.

---

## Figure-data contract

Every publication figure should have an exact tabular extract saved before the graphic is rendered.

Example:

```text
reporting/figure_data/
├── fig03_transition_incidence.csv
├── fig03_transition_incidence.manifest.json
├── fig05_redistribution.csv
└── fig05_redistribution.manifest.json
```

Each manifest records:

- figure ID;
- exact columns;
- source report-data tables;
- row count;
- SHA-256 of the CSV;
- confirmation that no scientific recalculation occurred during extraction.

This makes the data behind a manuscript figure independently inspectable without opening plotting code.

---

## Publication-first workflow

The first reporting implementation is designed for static, reproducible research outputs.

```text
frozen model outputs
        ↓
report-data builder
        ↓
validated report-data tables
        ↓
figure-data/table-data extracts
        ↓
SVG / PDF / PNG / XLSX / GIS outputs
```

The interactive explorer comes later, after publication figures and their scientific interpretations are stable.

This avoids coupling scientific analysis to a web interface and follows the useful LUTO/LandOpti principle that an explorer should browse precomputed outputs rather than trigger model optimisation.

---

## Planned publication result sequence

The reporting architecture is designed to support the scientific story rather than expose every model column equally.

A likely publication sequence is:

1. structural agricultural conditions underlying transition incidence;
2. SC1 physical, production-value and land-transition incidence;
3. concentration of transition burden;
4. protection relief and displaced burden relative to PRORATA;
5. robust minimum exposure and pathway versus implementation sensitivity;
6. SC2 released-resource composition and productive response potential;
7. SC3 target, realised, unmet and residual land accounting;
8. post-SC3 spatial necessity, persistence and flexibility;
9. optional place-based resilience/preparedness synthesis where scientifically justified.

Detailed validation and secondary maps can remain supplementary rather than crowding the principal manuscript.

---

## Command-line materialisation

Once completed principal runs exist beneath the principal-run directory, canonical report data can be built with:

```bash
goblin-spatial-report-data \
  --principal-root data/processed/principal \
  --output-root reporting/report_data
```

The default writes Parquet plus CSV companions. For environments without the reporting extras, a transparent CSV-only build can be requested:

```bash
goblin-spatial-report-data \
  --principal-root data/processed/principal \
  --output-root reporting/report_data \
  --csv-only
```

The command only consumes completed run outputs. It does not execute the scientific model.

---

## Architectural invariants

The reporting system should be considered correct only while all of the following remain true:

1. the scientific engine is upstream and unchanged by reporting;
2. cross-run scientific synthesis delegates to validated scientific functions;
3. report data are derived only from completed frozen outputs;
4. every run has explicit scenario/baseline/allocation identity;
5. source result files are hash-registered;
6. one frozen ED geometry is used for all ED cartography;
7. complete ED joins close at 2,857 rows;
8. metric labels and units are centrally registered;
9. every publication figure can expose the exact data used to render it;
10. an interactive explorer, if added, consumes precomputed outputs only.

These invariants keep the reporting layer reproducible, inspectable and scientifically subordinate to the frozen GOBLIN-Spatial engine.
