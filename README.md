# GOBLIN-Spatial

**A modular, constraint-preserving framework for reconstructing and representing nationally controlled agricultural systems at fine spatial resolution.**

GOBLIN-Spatial provides the spatial layer connecting the national GOBLIN AFOLU modelling framework with local agricultural geography. It reconstructs livestock, land-use and selected farm-structure information at Electoral Division (ED) level while preserving the statistical and biological totals from which those local representations are derived.

The current Irish implementation produces a validated annual agricultural baseline for **2,857 EDs from 2015 to 2025**, anchored to the 2020 Census of Agriculture and expressed in both official agricultural categories and GOBLIN-compatible livestock cohorts.

GOBLIN remains the national AFOLU framework. **GOBLIN-Spatial governs the spatial representation of that system.** The validated baseline can subsequently support spatialisation of national GOBLIN pathways and other place-based agricultural analyses.

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

For cattle, the final genetic disaggregation is explicitly **ED-informed**. Dairy cows provide the default support for DxD and DxB cohorts, other/suckler cows provide the default support for BxB cohorts, and a sparse set of receiver/rearing EDs is admitted where the ED's own young-stock structure indicates bought-in cattle and where such support is needed for exact national GOBLIN closure. County controls determine cattle totals and age-sex composition; they do **not** make every ED eligible for every genetic cohort.

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

Install the optional upstream GOBLIN feed/land packages when reproducing pasture-DM and spared-land stages:

```bash
pip install -e ".[goblin]"
```

## Data

The complete Ireland 2015-2025 development input bundle is currently versioned directly in GitHub for simple and reproducible use. The manifest pins the two principal full-data CSVs by SHA256 checksum:

- `data/raw/cattle/CSO_ED_2020.csv`
- `data/raw/land/AQA06_Unpivoted_2013_2025.csv`

The cattle, sheep, GOBLIN cohort, SE and county-region controls are also tracked in the repository. The agricultural-soil layer is a downstream scenario enrichment and is not required to reconstruct the historical baseline. Before a public v1.0 release, larger/raw source files can be moved to a versioned Zenodo record or stable official source without changing the scientific module API.

To verify the complete data contract:

```bash
goblin-spatial fetch-data --verify-only
```

## One-command historical build

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

This is the formal historical-baseline boundary. Soil, Standard Output, future scenarios, grassland release and land-use allocation are downstream study layers rather than requirements for constructing the baseline.

The normal user runs one command. Developers can call any module independently when updating or testing one part of the framework.

## Cattle transition study

The principal transition study is cattle focused. Sheep remain fixed context while dairy and suckler reductions are independently editable. A scenario can start from either the validated 2020 or 2025 ED state.

The cattle baseline contains **18 distinct pre-adult cohorts** — six DxD, six DxB and six BxB age-sex cohorts — plus dairy cows, suckler cows and bulls, giving 21 cattle cohorts in total. The scenario ripple is calculated separately for every pre-adult cohort.

For an ED that contains the relevant parent adults, the cohort follows that ED's own realised adult-cow reduction rate. If an ED contains a cohort but no matching parent adults, that ED×cohort relationship is treated as a county receiver and follows the reduction rate of the relevant parent adults in the same county. A national fallback is used only where the county itself has no matching parent adults.

Run a scenario from an already built baseline:

```bash
goblin-spatial scenario \
  --baseline-year 2020 \
  --target-year 2050 \
  --dairy-reduction 0.30 \
  --suckler-reduction 0.30
```

Or build the baseline and run the scenario in one command:

```bash
goblin-spatial run-all \
  --baseline-year 2020 \
  --target-year 2050 \
  --dairy-reduction 0.30 \
  --suckler-reduction 0.30
```

A scenario writes:

```text
data/processed/scenarios/<scenario>/
├── scenario_schedule.csv
├── scenario_national_summary.csv
├── scenario_ed_results.csv
├── baseline_ed_18_cohort_relationships.csv
└── scenario_ed_18_cohort_audit.csv
```

The two audit tables make the adult-to-cohort ripple explicit for every ED and every one of the 18 pre-adult cohorts, including county-receiver relationships.

Standard Output is evaluated downstream after the physical herd has been solved. It never changes animal allocation.

### Grassland release guardrail

Spared grassland is calculated only when the user supplies an authoritative GOBLIN pasture-DM control table with columns:

```text
YEAR, COHORT, PASTURE_DM_T_PER_HEAD_YEAR
```

For example:

```bash
goblin-spatial scenario \
  --baseline-year 2020 \
  --target-year 2050 \
  --dairy-reduction 0.30 \
  --suckler-reduction 0.30 \
  --pasture-dm-controls data/controls/pasture/goblin_pasture_dm.csv
```

If those controls are absent, the model stops after livestock/cohort and Standard Output results rather than inventing pasture coefficients or reporting unsupported spared hectares.

Alternative-land shares also default to zero. Forestry, rewetting, AD grass, willow, energy grass and nature/restoration allocations are performed only when the user explicitly supplies shares and the spared-land stage has already been completed.

See `docs/scenario_architecture.md` for the full study contract.

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
- preservation of age-sex and ED genetic structural-zero support where required;
- no DxD/DxB allocation to non-receiver zero-dairy EDs;
- no BxB allocation to non-receiver zero-suckler EDs.

The final validator also reports the difference between the preserved reported average holding size and the mechanically implied `AREA_FARMED / AGRICULTURAL_HOLDINGS` ratio as a diagnostic. It does not force the two measures to be identical.

**Exact closure validates the accounting and reconciliation constraints of the spatialisation. It should not be interpreted as independent empirical validation of every reconstructed non-2020 ED value.**

## Outputs

A successful historical build writes:

```text
data/processed/
├── goblin_spatial_master_2015_2025.csv
├── GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx
└── validation_summary.csv
```

The clean historical workbook contains four sheets:

| Sheet | Coverage | Content |
|---|---|---|
| `CSO_All_Years` | 2015-2025 | CSO-facing livestock, farm structure, holder age and land indicators |
| `GOBLIN_All_Years` | 2015-2025 | 31 GOBLIN livestock cohorts plus farm structure, holder age and land indicators |
| `CSO_2020` | 2020 | Exact 2020 subset of `CSO_All_Years` |
| `GOBLIN_2020` | 2020 | Exact 2020 subset of `GOBLIN_All_Years` |

For the validated reference build, the CSO sheets contain **35 columns**, the GOBLIN sheets contain **50 columns**, and each 2020 sheet contains **2,857 rows**.

## What GOBLIN-Spatial can support

The validated 2015-2025 spatial baseline is the principal historical output. Because it links nationally controlled agricultural populations with fine-scale geography, it can subsequently support applications including:

- spatial cattle-transition analysis;
- local livestock-pressure analysis;
- potential grassland-release analysis;
- catchment-scale agricultural analysis;
- soil and land-suitability overlays;
- place-based transition analysis;
- spatial inputs to synthetic-farm, microsimulation and agent-based modelling workflows.

These are **applications of the spatial framework**, rather than assumptions required to construct the validated baseline.

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
│   ├── scenario/
│   ├── pressure/
│   ├── soil/
│   ├── standard_output/
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

The cattle module reproduces all official ED, county and national cattle controls exactly while enforcing the corrected sparse ED-informed DxD/DxB/BxB support. In the 2020 baseline, 1,142 of 1,463 zero-dairy EDs retain zero dairy-origin young stock, while 321 receiver/rearing EDs provide the movement-aware exception required for exact closure.

The modular sheep composition/cohort stage reproduces the validated sheep enrichment and all 10 GOBLIN sheep cohorts exactly. The modular land and SE stages reproduce the validated Script 6 accounting to floating-point precision. The final historical validation/export layer reproduces the clean-workbook dimensions: 31,427 all-year rows, 2,857 2020 rows, 35 CSO columns and 50 GOBLIN columns.

The cattle-study regression additionally runs real Irish dairy-only, suckler-only and combined 30% reductions from the 2020 baseline plus a combined 30% reduction from 2025. It verifies unchanged sheep, exact adult endpoints, non-negative cohort states, all 18 ED×cohort relationships, county-receiver ripple behaviour and downstream Standard Output exposure.

GitHub Actions automatically runs both compact tests and the full 2015-2025 regression on each relevant update.

## Status

**Validated Ireland 2015-2025 spatial agricultural baseline complete. Cattle-only sequential transition workflow implemented and regression-tested.**

The remaining empirical gate for reported spared-hectare results is a pinned authoritative GOBLIN pasture-DM control table derived from upstream GOBLIN animal/feed definitions. Until that control is supplied, the model deliberately does not claim real spared-grassland quantities.

## Author

**Elvis Kwame Ofori**  
University of Galway