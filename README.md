# GOBLIN-Spatial

**A modular, constraint-preserving framework for translating national GOBLIN livestock and land-use pathways to fine-scale spatial data.**

GOBLIN-Spatial extends the national GOBLIN modelling approach with a reproducible spatial layer for livestock, land use and selected farm structural indicators. The current implementation demonstrates the framework for Ireland at Electoral Division (ED) level.

GOBLIN remains the national AFOLU framework. **GOBLIN-Spatial governs the spatial representation of that system.**

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

The package is organised around four scientific responsibilities:

1. **`cattle`**: reconciled 2020 cattle baseline, annual 2015-2025 ED cattle panel and 21 GOBLIN cattle cohorts.
2. **`sheep`**: region-to-county-to-ED sheep reconciliation, DAFM breed-composition enrichment and 10 GOBLIN sheep cohorts.
3. **`land`**: annual ED farmed area, grassland, cereals and other crop area.
4. **`se`**: social-economic farm structure indicators, currently agricultural holdings, average holding size, mean holder age and median holder age.

Cattle and sheep are built independently and then merged. Land and SE are attached to the merged livestock master. Shared Hamilton allocation, exact integer transport, IPF reconciliation, validation and export utilities support the four modules.

## Irish 2015-2025 implementation

The validated application contains:

- **2,857 agricultural ED units** used in the current working baseline
- **2015-2025** annual coverage
- **31,427 ED-year observations**
- **21 GOBLIN cattle cohorts**
- **10 GOBLIN sheep cohorts**
- annual cattle and sheep populations
- cattle age-sex structure
- sheep demographic and breed-type structure
- agricultural holdings and average holding size
- mean and median holder-age indicators
- farmed area, grassland, cereals and other crop area

The ED is the fine local administrative geography used in this agricultural application. Ireland is the current demonstration, not the methodological boundary of the framework.

## What is fixed in 2020?

The 2020 anchor has two related but distinct treatments.

### Livestock

Fine-scale ED livestock distributions provide the spatial pattern, while official county or detailed-region statistics provide controlling totals and composition. The 2020 livestock layer is therefore **reconciled first and then frozen**. Subsequent GOBLIN cohort disaggregation cannot change the reconciled ED, county, regional or national livestock population.

This is important where fine-scale official cells are unavailable or suppressed: higher-level official controls recover the complete livestock population, while the within-control-area distribution is a constrained reconstruction from available ED weights.

### Land and SE

The 2020 ED land and selected social-economic values are retained exactly as the fine-scale anchor. Higher-level Farm Structure Survey and annual land statistics are used as temporal change controls around that fixed 2020 state rather than as replacement ED totals.

## Core methodological principle

The framework separates three roles:

1. **Fine-scale official data provide spatial information.**
2. **Coarser official statistics control totals, composition and temporal change.**
3. **The GOBLIN cohort structure provides biological disaggregation.**

The package does not run a separate national herd-dynamics model inside every ED. The controlled spatial livestock population is first established, then expressed in the GOBLIN cohort structure without changing that population.

## Temporal interpretation

The 2015-2025 panel is a **reconstructed ED panel**, not eleven independent ED censuses.

- cattle temporal change is controlled at county level using annual CSO cattle statistics while the 2020 within-county ED footprint is retained;
- sheep temporal change is controlled through the validated detailed-region → county → ED hierarchy;
- cattle age-sex composition is controlled at county level;
- DAFM Mountain + Mountain Cross sheep composition is used as an **upland-type proxy**, not as an independently observed ED hill-farm classification;
- non-2020 holder-age values are reconstructed indicators derived from official temporal controls.

These rules are deliberate components of the spatial reconstruction and should be respected when interpreting local trends.

## Install

```bash
pip install -e .
```

## Data

Compact, auditable controls are versioned directly in GitHub. The current development manifest keeps the two larger full-data inputs external and pins their exact SHA256 checksums:

- `CSO_ED_2020.csv`
- `AQA06_Unpivoted_2013_2025.csv`

The remaining cattle, sheep, GOBLIN cohort, SE and county-region controls are currently tracked in the repository. Before public release, the external full-data entries can point to a versioned Zenodo record or stable official source without changing the scientific module API.

To inspect the data contract:

```bash
goblin-spatial fetch-data --verify-only --tracked-only
```

Once the external full-data inputs are available at the paths declared in `configs/ireland_2015_2025.yaml`, the complete build can be run directly.

## One-command build

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

This executes:

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

The normal user runs one command. Developers can call any module independently when updating or testing one part of the framework.

## Scientific accounting constraints

Every complete build must satisfy:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

Additional safeguards require:

- 31,427 ED-year rows and 2,857 EDs for the Ireland 2015-2025 configuration;
- no duplicate `YEAR-CSOED` observations;
- no negative livestock or land values;
- exact preservation of the eight 2020 land/SE anchor fields;
- exact closure to the controlling livestock totals;
- preservation of structural-zero support where required.

The final validator also reports the difference between the preserved reported average holding size and the mechanically implied `AREA_FARMED / AGRICULTURAL_HOLDINGS` ratio as a diagnostic. It does not force the two measures to be identical.

## Outputs

A successful build writes:

```text
data/processed/
├── goblin_spatial_master_2015_2025.csv
├── GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx
└── validation_summary.csv
```

The clean workbook contains four sheets:

| Sheet | Coverage | Content |
|---|---|---|
| `CSO_All_Years` | 2015-2025 | CSO-facing livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015-2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 subset of `CSO_All_Years` |
| `GOBLIN_2020` | 2020 | Exact 2020 subset of `GOBLIN_All_Years` |

For the validated reference build, the CSO sheets contain **35 columns**, the GOBLIN sheets contain **50 columns**, and each 2020 sheet contains **2,857 rows**.

## Repository structure

```text
GOBLIN-Spatial/
├── pyproject.toml
├── README.md
├── data_manifest.yaml
├── configs/
├── data/
│   ├── raw/
│   ├── controls/
│   ├── interim/
│   └── processed/
├── src/goblin_spatial/
│   ├── cattle/
│   ├── sheep/
│   ├── land/
│   ├── se/
│   ├── reconciliation/
│   ├── validation/
│   ├── export/
│   ├── data_fetch.py
│   ├── pipeline.py
│   └── cli.py
├── tests/
└── docs/
```

## Validation status

The modular sheep composition/cohort stage reproduces the frozen validated sheep enrichment and all 10 GOBLIN sheep cohorts exactly. The modular land and SE stages reproduce the frozen Script 6 output to floating-point precision. The final validation/export layer reproduces the reference dimensions of the clean workbook: 31,427 all-year rows, 2,857 2020 rows, 35 CSO columns and 50 GOBLIN columns.

A full-data regression test is included in `tests/test_full_regression.py`. It is designed to run once the two external full-data inputs are present and checks the complete 2015-2025 national cattle, sheep and holdings series together with final workbook dimensions.

## Status

**Validated Irish 2015-2025 baseline complete. Modular Python package implemented. Full-data integration regression is ready to run when the two pinned external input files are present in the repository working tree or connected through the data manifest.**

## Author

**Elvis Kwame Ofori**  
University of Galway
