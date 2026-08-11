# GOBLIN-Spatial

**A modular, constraint-preserving framework for translating national GOBLIN livestock and land-use pathways to fine-scale spatial data.**

GOBLIN-Spatial extends the national GOBLIN modelling approach by providing a reproducible way to represent livestock, land use and selected farm structural indicators at Electoral Division (ED) level in Ireland. It does not replace the national model. It provides the spatial layer needed to examine where nationally consistent livestock and land-use pathways are represented locally.

The package is designed so that researchers can regenerate the same spatial dataset from the underlying inputs, update individual data sources as new years become available, improve individual modules independently, and reproduce the final validated outputs.

## Why GOBLIN-Spatial?

GOBLIN provides a national AFOLU modelling framework and a biologically detailed livestock cohort structure. GOBLIN-Spatial translates national and higher-level official controls to **2,857 Electoral Divisions**, a fine-grained local administrative geography used here as the spatial unit for the Irish agricultural application.

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

1. **`cattle`**: 2020 cattle baseline, annual ED cattle panel and 21 GOBLIN cattle cohorts.
2. **`sheep`**: region-to-county-to-ED sheep reconciliation, composition enrichment and 10 GOBLIN sheep cohorts.
3. **`land`**: annual ED farmed area, grassland, cereals and other crop area.
4. **`se`**: social-economic farm structure indicators, currently agricultural holdings, average holding size, mean holder age and median holder age.

Cattle and sheep are built independently and then merged. Land and SE are attached to the merged livestock master. Shared reconciliation, validation and export utilities support the four scientific modules.

## Current Irish implementation

The validated baseline covers:

- **2,857 Electoral Divisions**
- **2015-2025**
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

## Core methodological principle

GOBLIN-Spatial separates three roles:

1. **Fine-scale official statistics determine spatial pattern.**
2. **Coarser official annual statistics determine temporal totals and composition.**
3. **The GOBLIN cohort structure determines biological livestock disaggregation.**

The package does not run an independent national herd model inside every ED. It takes the controlled ED livestock population as the spatial population to be represented and expresses it in the GOBLIN cohort structure while preserving ED, county, regional and national accounting constraints.

## Development data layout

For the current development phase, the core working input datasets are kept directly in GitHub because they are small enough to version conveniently. This makes the package easy to clone, test and improve without a separate data-download step.

```text
data/
├── raw/
│   ├── cattle/
│   ├── sheep/
│   └── land/
├── controls/
├── interim/       # generated, ignored by Git
└── processed/     # generated, ignored by Git
```

Tracked working inputs currently include the 2020 ED baseline, annual cattle controls, sheep county/region controls, the sheep source workbook, annual land controls, GOBLIN cohort relationships, SE controls and the county-region mapping. Compressed `.csv.xz` files are read directly by pandas and do not need to be manually unpacked.

If the input bundle becomes large, these same paths can later be backed by Zenodo or official download URLs without changing the scientific module structure.

## Install

```bash
pip install -e .
```

## Build

The intended normal-user interface is one command:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

which executes:

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

Modularity is for development and maintenance. A developer can improve one module independently, while a normal user rebuilds the complete dataset at once.

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
│   ├── raw/
│   │   ├── cattle/
│   │   ├── sheep/
│   │   └── land/
│   ├── controls/
│   ├── interim/
│   └── processed/
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
| `CSO_All_Years` | 2015-2025 | CSO-controlled livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015-2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 CSO ED snapshot |
| `GOBLIN_2020` | 2020 | Exact 2020 GOBLIN cohort snapshot |

The modular package will be regression-tested against this validated reference output before a stable v1.0 release is declared.

## Status

**Validated Irish baseline complete for 2015-2025. Modular package implementation in progress.**

## Author

**Elvis Kwame Ofori**  
University of Galway
