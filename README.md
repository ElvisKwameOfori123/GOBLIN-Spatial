# GOBLIN-Spatial

**A modular, constraint-preserving framework for translating national GOBLIN livestock and land-use pathways to fine-scale spatial data.**

GOBLIN-Spatial extends the national GOBLIN modelling approach by providing a reproducible way to represent livestock, land use and selected farm structural indicators at Electoral Division (ED) level in Ireland. Rather than replacing the national model, it provides the spatial layer needed to examine where national livestock and land-use pathways occur.

The package is designed so that researchers can regenerate the same spatial dataset from the underlying inputs, update individual data sources as new years become available, improve individual modules independently, and reproduce the final validated outputs.

## Why GOBLIN-Spatial?

GOBLIN provides a national AFOLU modelling framework and a biologically detailed livestock cohort structure. National results are essential for maintaining internally consistent agricultural and land-use pathways, but national totals alone cannot show how change is distributed across local agricultural areas.

GOBLIN-Spatial addresses that gap by translating national and higher-level official controls to **2,857 Electoral Divisions**, a fine-grained local administrative geography used here as the spatial unit for the Irish agricultural application.

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
 Cattle + Sheep + Land + SE indicators
```

## Four scientific modules

The public scientific structure is deliberately simple:

1. **`cattle`**: 2020 cattle baseline, annual ED cattle panel and 21 GOBLIN cattle cohorts.
2. **`sheep`**: region-to-county-to-ED sheep reconciliation, composition enrichment and 10 GOBLIN sheep cohorts.
3. **`land`**: annual ED farmed area, grassland, cereals and other crop area.
4. **`se`**: social-economic farm structure indicators, currently agricultural holdings, average holding size, mean holder age and median holder age.

Cattle and sheep are built independently and then merged. Land and SE are subsequently attached to the merged livestock master. Shared reconciliation, validation and export utilities support these modules but are not separate scientific components.

## Current Irish implementation

The validated baseline covers:

- **2,857 Electoral Divisions**
- **2015–2025**
- **31,427 ED-year observations**
- **21 GOBLIN cattle cohorts**
- **10 GOBLIN sheep cohorts**
- annual cattle and sheep populations
- cattle age-sex structure
- sheep demographic and type structure
- agricultural holdings and average holding size
- mean and median holder age
- farmed area, grassland, cereals and other crop area

The **2020 Census of Agriculture ED dataset is the fixed fine-scale spatial anchor**. Annual official statistics provide temporal controls around that baseline, while the GOBLIN cohort structure provides biological disaggregation.

## Data architecture

GitHub stores the software, configuration, documentation, tests and small control tables that are useful to version with the code. Large or binary source datasets are kept outside Git and are obtained through the package data-fetch layer.

```text
GitHub repository
      |
      |  goblin-spatial fetch-data
      v
Zenodo / official source snapshot
      |
      v
 data/raw/              (ignored by Git)
      |
      |  goblin-spatial build
      v
CATTLE -> SHEEP -> MERGE -> LAND -> SE -> VALIDATE -> EXPORT
      |
      v
 data/processed/        (ignored by Git)
```

`data_manifest.yaml` records the exact filename, destination and SHA256 checksum of every required input. This makes each release reproducible even when official source websites later change.

Small package controls remain versioned under `data/controls/`, including social-economic controls, sheep composition anchors and GOBLIN cohort relationships.

## Install

```bash
pip install -e .
```

## Fetch data

Once the external data record URLs are configured in `data_manifest.yaml`:

```bash
goblin-spatial fetch-data
```

The command downloads the pinned raw inputs into `data/raw/` and verifies each file against its SHA256 checksum. Existing files with the correct checksum are reused.

During development, the same command also recognises manually placed files. This allows the package to be tested before the first Zenodo record is published.

## Build the complete dataset

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

A complete build executes:

```text
CATTLE
   ↓
SHEEP
   ↓
MERGE
   ↓
LAND
   ↓
SE
   ↓
VALIDATE
   ↓
EXPORT
```

Modularity is for development and maintenance. A normal user runs one command for the complete build, while a developer can improve or test an individual module independently.

## Core methodological principle

GOBLIN-Spatial separates three roles:

1. **Fine-scale official statistics determine spatial pattern.**
2. **Coarser official annual statistics determine temporal totals and composition.**
3. **The GOBLIN cohort structure determines biological livestock disaggregation.**

The package does **not** run an independent national herd model inside every ED. It takes the controlled ED livestock population as the spatial population to be represented and expresses it in the GOBLIN cohort structure while preserving ED, county, regional and national accounting constraints.

## Accounting constraints

For every ED-year:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

The 2020 ED baseline is locked and must not be overwritten by higher-level annual controls.

## Repository structure

```text
GOBLIN-Spatial/
├── pyproject.toml
├── README.md
├── data_manifest.yaml
├── configs/
│   └── ireland_2015_2025.yaml
├── data/
│   ├── controls/          # small versioned controls
│   ├── raw/               # downloaded, not versioned
│   ├── interim/           # generated, not versioned
│   └── processed/         # generated, not versioned
├── src/goblin_spatial/
│   ├── cattle/
│   ├── sheep/
│   ├── land/
│   ├── se/
│   ├── reconciliation/
│   ├── data_fetch.py
│   ├── pipeline.py
│   └── cli.py
├── tests/
└── docs/
```

## Current validated output

The reference workflow produces `07_GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx` with four clean sheets:

| Sheet | Coverage | Content |
|---|---|---|
| `CSO_All_Years` | 2015–2025 | CSO-controlled livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015–2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 CSO ED snapshot |
| `GOBLIN_2020` | 2020 | Exact 2020 GOBLIN cohort snapshot |

The modular package will be regression-tested against this already validated reference output before a stable v1.0 release is declared.

## Status

**Validated Irish baseline complete for 2015–2025. Modular package and reproducible data-fetch layer under active development.**

## Author

**Elvis Kwame Ofori**  
University of Galway
