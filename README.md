# GOBLIN-Spatial

**A constraint-preserving framework for spatialising national livestock and land-use pathways.**

GOBLIN-Spatial is a reproducible research workflow that expresses official Irish agricultural statistics at Electoral Division (ED) level in the GOBLIN livestock cohort structure while preserving the underlying official population and land controls.

## Current release scope

The validated baseline covers:

- **2,857 Electoral Divisions**
- **2015–2025**
- **31,427 ED-year observations**
- **21 GOBLIN cattle cohorts**
- **10 GOBLIN sheep cohorts**
- annual cattle and sheep populations
- farm structure indicators
- holder-age indicators
- annual land-use indicators

The **2020 Census of Agriculture ED dataset is the fixed fine-scale spatial anchor**. Annual official statistics provide temporal controls, while the GOBLIN cohort structure provides biological disaggregation.

## Core methodological rule

GOBLIN-Spatial separates three roles:

1. **Fine-scale official statistics determine geography.**
2. **Coarser official annual statistics determine temporal totals and composition.**
3. **GOBLIN determines biological cohort structure.**

The workflow does not run a national herd model independently inside each ED. Instead, the already-controlled ED livestock population is expressed in the GOBLIN cohort structure while preserving ED, county and national accounting constraints.

## Final validated data product

The current workflow produces:

`07_GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx`

with four clean sheets:

| Sheet | Coverage | Content |
|---|---|---|
| `CSO_All_Years` | 2015–2025 | CSO-controlled livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015–2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 CSO ED snapshot |
| `GOBLIN_2020` | 2020 | Exact 2020 GOBLIN cohort snapshot |

The clean workbook contains substantive indicators only. Model diagnostics, reconciliation flags, intermediate targets and provenance-control fields are retained in the reproducible workflow rather than the presentation sheets.

## Pipeline

```text
Official CSO / DAFM / GOBLIN inputs
        |
        v
Script 01  2020 cattle reconciliation and age-sex structure
        |
Script 02  Annual ED cattle panel, 2015–2025
        |
Script 03A Region-to-county sheep controls
        |
Script 03B County-to-ED sheep panel
        |
Script 04  Cattle + sheep ED livestock master
        |
Script 05A DAFM sheep composition controls
        |
Script 05B ED sheep breed/type enrichment
        |
Script 05C 21 GOBLIN cattle cohorts
        |
Script 05D 10 GOBLIN sheep cohorts / final 31 cohorts
        |
Script 06  Annual land + farm-structure + holder-age enrichment
        |
Script 07  Final clean four-sheet workbook
```

## Accounting constraints

For every ED-year, the final cattle cohorts satisfy:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
```

and the sheep cohorts satisfy:

```text
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
```

Land accounting satisfies:

```text
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

with no negative land components.

## 2020 anchor

The 2020 ED values are locked. Annual controls are used to reconstruct change around this baseline rather than overwrite it.

This applies to:

- `AVERAGE_SIZE_OF_HOLDINGS`
- `AGRICULTURAL_HOLDINGS`
- `AVERAGE_AGE_OF_HOLDER`
- `MEDIAN_AGE_OF_HOLDER`
- `AREA_FARMED`
- `ALL_GRASSLAND`
- `TOTAL_CEREALS`
- `OTHER_CROPS_HA`

## Repository structure

```text
GOBLIN-Spatial/
├── README.md
├── requirements.txt
├── .gitignore
├── scripts/
├── data/
│   ├── controls/
│   └── README.md
└── docs/
    ├── methodology.md
    ├── data_dictionary.md
    └── validation.md
```

Large raw-source files and generated outputs are intentionally excluded from normal Git history. Release-ready datasets can be distributed separately through GitHub Releases and/or an archival repository such as Zenodo.

## Data sources

The workflow integrates official and model-derived information including:

- Central Statistics Office Ireland (CSO), Census of Agriculture and agricultural statistical tables
- CSO annual cattle, sheep and land-use controls
- Department of Agriculture, Food and the Marine (DAFM) sheep composition information
- GOBLIN cohort structure for biological livestock disaggregation

Detailed source attribution and variable provenance will be documented in `docs/methodology.md` and `docs/data_dictionary.md`.

## Status

**Validated baseline workflow complete for 2015–2025.**

The next repository step is to migrate the validated scripts to portable relative paths without changing any calculations or outputs.

## Author

**Elvis Kwame Ofori**

University of Galway
