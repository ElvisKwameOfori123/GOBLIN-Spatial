# GOBLIN-Spatial

**A modular, constraint-preserving framework for translating national GOBLIN livestock and land-use pathways to fine-scale spatial data.**

GOBLIN-Spatial extends the national GOBLIN modelling approach by providing a reproducible way to represent livestock, land use and selected farm structural indicators at Electoral Division (ED) level in Ireland. Rather than replacing the national model, it provides the spatial layer needed to examine where national livestock and land-use pathways occur.

The package is designed so that researchers can regenerate the same spatial dataset from the underlying inputs, update individual data sources as new years become available, improve individual modules independently, and reproduce the final validated outputs.

## Why GOBLIN-Spatial?

GOBLIN provides a national AFOLU modelling framework and a biologically detailed livestock cohort structure. National results are essential for maintaining internally consistent agricultural and land-use pathways, but national totals alone cannot show how change is distributed across local agricultural areas.

GOBLIN-Spatial addresses that gap by translating national and higher-level official controls to **2,857 Electoral Divisions**, a fine-grained local administrative geography used here as the spatial unit for the Irish agricultural application.

The framework therefore links:

```text
National GOBLIN / official agricultural controls
                    |
                    v
      Constraint-preserving reconciliation
                    |
                    v
       Electoral Division representation
                    |
                    v
 Livestock cohorts + land + farm structure
```

The result is a spatial representation that remains consistent with the national and higher-level statistics from which it is derived.

## Core principle

GOBLIN-Spatial separates three roles:

1. **Fine-scale official statistics determine spatial pattern.**
2. **Coarser official annual statistics determine temporal totals and composition.**
3. **The GOBLIN cohort structure determines biological livestock disaggregation.**

These roles are deliberately kept separate.

The package does **not** run an independent national herd model inside every ED. Instead, it takes the official ED livestock population as the spatial population to be represented and disaggregates that fixed population into the GOBLIN cohort structure while preserving ED, county, regional and national accounting constraints.

## Current Irish implementation

The validated baseline currently covers:

- **2,857 Electoral Divisions**
- **2015–2025**
- **31,427 ED-year observations**
- **21 GOBLIN cattle cohorts**
- **10 GOBLIN sheep cohorts**
- annual cattle and sheep populations
- cattle age-sex structure
- sheep demographic and type structure
- agricultural holdings
- average holding size
- mean and median holder age
- farmed area
- grassland
- cereals
- other crop area

The **2020 Census of Agriculture ED dataset is the fixed fine-scale spatial anchor**. Annual official statistics provide temporal controls around that baseline, while the GOBLIN cohort structure provides biological disaggregation.

## Package objective

GOBLIN-Spatial is being developed as a reusable research software and data-generation package, not simply as a collection of analysis scripts.

A user should ultimately be able to:

```bash
pip install -e .
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

and regenerate the validated spatial dataset from the required input data.

The modular structure will allow, for example:

- a new year of CSO cattle data to be added without rewriting the cohort module;
- sheep composition methods to be improved independently;
- new land controls to be incorporated without changing livestock accounting;
- additional socioeconomic indicators to be added as separate modules;
- validation rules to run automatically after every build;
- the Irish application to remain one implementation of a broader national-to-local spatialisation framework.

## Planned package architecture

```text
GOBLIN-Spatial/
├── pyproject.toml
├── README.md
├── CITATION.cff
├── LICENSE
│
├── src/
│   └── goblin_spatial/
│       ├── io/
│       ├── reconciliation/
│       ├── cattle/
│       ├── sheep/
│       ├── cohorts/
│       ├── land/
│       ├── socioeconomic/
│       ├── validation/
│       ├── export/
│       └── pipeline.py
│
├── configs/
│   └── ireland_2015_2025.yaml
│
├── data/
│   ├── raw/
│   ├── controls/
│   ├── interim/
│   └── processed/
│
├── tests/
├── examples/
└── docs/
```

Raw inputs will be retained separately from generated data. Where redistribution is permitted, required CSV/input files can be stored with the package. Where redistribution is restricted, the repository will document how to obtain the source data and where the package expects them to be placed.

## Reconciliation framework

The package uses hierarchical reconciliation so that fine-scale spatial weights and higher-level official controls remain consistent.

Reusable reconciliation tools include:

- proportional allocation;
- Hamilton / largest-remainder integer allocation;
- iterative proportional fitting where row and column controls must both be satisfied;
- structural-zero preservation;
- exact accounting validation.

These methods are shared across livestock, land and farm-structure modules rather than duplicated in separate scripts.

## Livestock representation

### Cattle

The final cattle population is represented using **21 GOBLIN cattle cohorts**. GOBLIN cohort relationships determine DxD, DxB and BxB biological composition, while the CSO ED population remains the controlling spatial population.

For every ED-year:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
```

### Sheep

The sheep population is reconciled through a region-to-county-to-ED hierarchy and represented using **10 GOBLIN sheep cohorts**.

For every ED-year:

```text
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
```

## Land and farm structure

The spatial dataset also contains annual farmed area, grassland, cereals and other crop area, together with agricultural holdings, average holding size and holder-age indicators.

Land accounting satisfies for every ED-year:

```text
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

with no negative land components.

## 2020 spatial anchor

The 2020 ED values are locked as the baseline spatial representation. Higher-level annual statistics are used as temporal-change controls rather than replacement ED totals.

The protected 2020 variables include:

- `AVERAGE_SIZE_OF_HOLDINGS`
- `AGRICULTURAL_HOLDINGS`
- `AVERAGE_AGE_OF_HOLDER`
- `MEDIAN_AGE_OF_HOLDER`
- `AREA_FARMED`
- `ALL_GRASSLAND`
- `TOTAL_CEREALS`
- `OTHER_CROPS_HA`

This distinction is important: non-2020 ED values are reconstructed annual spatial estimates constrained by official statistics, while the 2020 ED baseline is directly retained.

## Current validated output

The current workflow produces:

`07_GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx`

with four clean sheets:

| Sheet | Coverage | Content |
|---|---|---|
| `CSO_All_Years` | 2015–2025 | CSO-controlled livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015–2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 CSO ED snapshot |
| `GOBLIN_2020` | 2020 | Exact 2020 GOBLIN cohort snapshot |

The presentation workbook contains substantive indicators only. Diagnostics, reconciliation controls and validation information remain part of the reproducible build process.

## Validation philosophy

A build is considered valid only if the package reproduces the accounting constraints of the validated reference workflow.

Core tests include:

```text
2020 final values = 2020 baseline values exactly
sum(21 cattle cohorts) = TOTAL_CATTLE
sum(10 sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
no negative land components
no unintended change to official livestock controls
```

The modular package will be regression-tested against the already validated reference pipeline before a stable release is declared.

## Data sources

The current Irish implementation integrates information from:

- Central Statistics Office Ireland (CSO), including Census of Agriculture and annual agricultural statistics;
- Department of Agriculture, Food and the Marine (DAFM) sheep composition information;
- the GOBLIN cohort structure and associated biological relationships.

Detailed source attribution, redistribution status and variable provenance will be maintained in the documentation and data-control files.

## Status

**Validated Irish baseline complete for 2015–2025. Modular package development in progress.**

The current development task is to refactor the validated workflow into reusable package modules while requiring the modular implementation to reproduce the existing validated outputs.

## Author

**Elvis Kwame Ofori**  
University of Galway
