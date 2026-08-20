# GOBLIN-Spatial

**A constraint-preserving spatial framework for reconstructing agricultural systems at fine spatial resolution and preparing them for spatial transition analysis.**

GOBLIN-Spatial connects nationally controlled agricultural and AFOLU information with fine-scale agricultural geography. The current Irish implementation reconstructs a historical agricultural system for **2,857 Electoral Divisions (EDs) from 2015 to 2025**, anchored to the **2020 CSO Census of Agriculture**.

The historical model is deliberately hierarchical. Fine-scale 2020 ED data provide the spatial anchor. Annual official statistics provide the higher-level temporal controls. GOBLIN livestock relationships provide biological disaggregation without replacing the official livestock population.

```text
2020 CSO ED agricultural census
            │
            ├── fine-scale livestock geography
            ├── land and crop geography
            └── farm-structure anchor
            │
            +
            │
2015-2025 official controls
            │
            ├── AAA10 county cattle
            ├── AAA09 regional sheep
            ├── AQA06 regional land-use change
            └── farm-structure / demographic controls
            │
            ▼
Reconstructed ED agricultural system, 2015-2025
```

Non-2020 ED values are reconstructed estimates. They are not presented as independently observed annual ED censuses.

## Development status

GOBLIN-Spatial is being migrated into a clean v1 Python package on a development branch before changes are merged to `main`.

The migration rule is strict:

> **Refactor the software, not the validated scientific mathematics.**

Each stage must reproduce its validated reference behaviour before it is accepted. The current development priority is the **historical baseline through Stage 09**. Scenario refactoring is deliberately deferred until the baseline is complete and regression-tested.

---

# Historical baseline

## Final baseline boundary

The historical baseline finishes at **Stage 09 ED signatures**.

```text
CATTLE
01  2020 ED cattle reconciliation
02  2015-2025 ED cattle panel
05C 21 GOBLIN cattle cohorts
        │
        │
        ├───────────────┐
        │               │
        ▼               ▼
                     04 MERGE
        ▲               ▲
        │               │
        ├───────────────┘
        │
SHEEP
03A AAA09 region -> corrected county controls
03B corrected county -> ED sheep panel
05A annual DAFM breed composition
05B ED breed/type enrichment
05D 10 GOBLIN sheep cohorts
        │
        ▼
31-COHORT LIVESTOCK MASTER
        │
        ▼
06 LAND + CROPS + FARM STRUCTURE / SE
        │
        ▼
07 CLEAN VALIDATED EXPORT
        │
        ▼
08 FIXED-2020 STANDARD OUTPUT
        │
        ▼
09 FROZEN ED COHORT SIGNATURES
        │
        ▼
HISTORICAL BASELINE COMPLETE
```

**Stages 08B and 08C are not part of the historical baseline.** They are downstream soil-context layers used when the completed baseline is prepared for future scenario analysis.

## Package boundary

The v1 historical interface is organised as:

```text
src/goblin_spatial/baseline/
├── cattle.py                 # 01, 02, 05C
├── sheep.py                  # 03A, 03B, 05A, 05B, 05D
├── merge.py                  # 04
├── land_farm_structure.py    # 06
├── clean_export.py           # 07
├── standard_output.py        # 08
└── signatures.py             # 09
```

Cattle and sheep are built independently. The merge stage joins the two validated systems on `YEAR + CSOED`; it does not recalculate livestock populations.

---

# Cattle module

The cattle module follows the validated CSO-first hierarchy.

### Stage 01: 2020 ED cattle anchor

The 2020 CSO ED data provide the within-county spatial pattern. CSO AAA10 provides the exact county controls for:

```text
DAIRY_COW
OTHER_COW
TOTAL_CATTLE
```

After reconciliation:

```text
OTHER_CATTLE = TOTAL_CATTLE - DAIRY_COW - OTHER_COW
```

AAA10 then supplies the county age-sex composition used to partition `OTHER_CATTLE` into bulls and six young/other cattle age-sex containers.

No GOBLIN genetic information is used in Stage 01.

### Stage 02: annual cattle panel

The reconciled 2020 within-county ED pattern is held as the spatial support. Annual AAA10 county totals control 2015-2025 cattle populations. The 2020 ED state is copied exactly.

### Stage 05C: 21 GOBLIN cattle cohorts

The existing CSO cattle population remains authoritative. GOBLIN supplies biological relationships only.

For 2015-2020, year-specific GOBLIN relationships are used. For 2021-2025, the 2020 biological relationships are held constant and applied to each year's current CSO dairy/suckler structure.

Genetic support is ED-informed:

```text
dairy cows   -> DxD / DxB support
suckler cows -> BxB support
```

Sparse receiver/rearing exceptions are retained where young cattle occur without the corresponding local parent population and where support is required for exact national closure.

Every ED-year must satisfy:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
```

---

# Sheep module

The production sheep baseline follows the validated **03A -> 03B** hierarchy.

### Stage 03A: regional controls to corrected county controls

The 2020 ED `TOTAL_SHEEP` distribution supplies the fine-scale spatial footprint. The frozen AAA09 workbook contains two relevant sheets:

- `County_WIDE`: used for the deterministic County -> detailed-region / NUTS2 crosswalk;
- `Region_WIDE`: supplies the raw AAA09 detailed-region totals and demographic composition for 2015-2025.

The observed 2020 ED sheep footprint is first reconciled to exact 2020 detailed-region totals. Those corrected ED values are aggregated to corrected 2020 county anchors. For non-2020 years, each region's raw AAA09 total is distributed to counties using the corrected 2020 county shares.

The four non-overlapping sheep classes are reconciled jointly:

```text
EWES_2_PLUS
EWES_UNDER_2
RAMS
OTHER_SHEEP
```

### Stage 03B: county to ED

Corrected annual county sheep totals are allocated to EDs using the corrected 2020 within-county ED pattern. The 2020 state is reproduced exactly and structural zero support is preserved.

### DAFM county sheep totals

`03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv` is retained for independent/hold-out validation. It is **not** used to replace the production CSO/AAA09 sheep population in the current validated baseline.

### Stages 05A and 05B: breed composition

DAFM breed anchors provide **composition only** for 2016, 2020, 2022 and 2025. Annual shares are reconstructed using the validated interpolation rules and applied to the CSO-controlled sheep population without changing sheep totals.

Mountain + Mountain Cross is retained as an upland-type proxy for GOBLIN-compatible mapping. It is not presented as an observed ED hill-farm classification.

### Stage 05D: 10 GOBLIN sheep cohorts

The enriched sheep population is expressed in the 10 GOBLIN sheep cohorts. Every ED-year must satisfy:

```text
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
```

---

# Stage 04: livestock merge

Cattle and sheep are merged only after their independent accounting checks pass.

The resulting system contains:

```text
21 cattle cohorts
+ 10 sheep cohorts
= 31 GOBLIN livestock cohorts
```

The merge does not alter cattle or sheep numbers.

---

# Stage 06: land, crops and farm structure / SE

Stage 06 adds the eight structural fields used by the historical model:

```text
AREA_FARMED
ALL_GRASSLAND
TOTAL_CEREALS
OTHER_CROPS_HA
AGRICULTURAL_HOLDINGS
AVERAGE_SIZE_OF_HOLDINGS
AVERAGE_AGE_OF_HOLDER
MEDIAN_AGE_OF_HOLDER
```

The exact 2020 ED values are locked.

AQA06 supplies annual **regional change** around the 2020 ED land structure. The validated seven-region mapping is deterministic and stored in the code, so a separate county-region input file is not required.

Every ED-year must satisfy:

```text
AREA_FARMED =
ALL_GRASSLAND
+ TOTAL_CEREALS
+ OTHER_CROPS_HA
```

Farm holdings and holder-age indicators use the validated State/county trajectories around the fixed 2020 ED anchor. Average holding size preserves the reported 2020 ED anchor and is reconstructed from relative changes in land and holdings outside 2020.

Stage 06 must not change any of the 31 livestock cohorts.

---

# Stage 07: clean baseline export

Stage 07 is an output/validation boundary. It standardises the historical deliverable without changing scientific values.

The complete historical panel has:

```text
2,857 EDs
11 years: 2015-2025
31,427 ED-year rows
```

---

# Stage 08: Standard Output

Stage 08 applies fixed IFS-2020 Standard Output coefficients to the reconstructed activities.

It measures **agricultural production-value exposure**. It is not farm profit, household income or welfare.

The runtime mapping is frozen in:

```text
08_IFS2020_Standard_Output_Mapping.xlsx
```

The mapping values livestock cohorts directly and also covers the selected crop-area variables while preventing double counting of aggregate livestock controls and physical grassland.

Stage 08 must not change pre-existing livestock, land, crop or farm-structure values.

---

# Stage 09: frozen ED signatures

Stage 09 is the **final baseline stage**.

It freezes the pre-scenario relationship between the 2020 ED adult-cow structure and each cattle follower cohort. The signature table distinguishes:

```text
LOCAL_ED
COUNTY_RECEIVER
NATIONAL_ORPHAN
NONE
```

These are accounting relationships inferred from the reconstructed livestock geography. They are not direct observations of animal movement.

Stage 09 belongs to the baseline package and does not import or run scenario code. Future scenario modules consume these frozen relationships downstream.

---

# Soil and future scenario preparation

After the historical baseline is complete, spatial context can be attached for scenario work.

```text
HISTORICAL BASELINE THROUGH 09
        │
        ▼
08B Cathal/NFS agricultural capability
        │
        ▼
08C Colm/IFS mapped physical soil
        │
        ▼
future scenario workflow
```

The two soil systems remain separate. They are not blended into one soil index, and neither changes historical cattle, sheep, crop or land reconstruction.

LPIS and frozen ED geometry also enter only on the downstream spatial/scenario side.

Scenario code is intentionally not being refactored in the current baseline pass.

---

# Data architecture

GOBLIN-Spatial uses a hybrid data strategy.

```text
GitHub
├── code
├── tests
├── configuration
├── manifest
└── compact baseline inputs

Zenodo
└── large frozen spatial inputs
```

## Compact historical inputs

```text
data/inputs/baseline/
├── 01_CSO_ED_Agricultural_Baseline_2020.csv
├── 01_CSO_AAA10_Cattle_County_2015_2025.csv
├── 03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx
├── 05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv
├── 05C_Cattle_Cohort_Relationships_2012_2020.csv
├── 06_CSO_AQA06_Agricultural_Land_Use.xlsx
├── 06_Farm_Structure_Demographic_Controls.csv
└── 08_IFS2020_Standard_Output_Mapping.xlsx
```

The frozen bundle also contains the DAFM county sheep hold-out file for validation.

The published `05C_Cattle_Cohort_Relationships_2012_2020.csv` filename is retained for reproducibility even though the source contains the GOBLIN sheep series used by Stage 05D as well as the cattle series used by Stage 05C.

## Large Zenodo-backed spatial inputs

```text
data/inputs/spatial/
├── 08B_NFS_Agricultural_Soil_Capability.csv
├── 08C_IFS_Mapped_Physical_Soil_Package.zip
├── SC2_LPIS_2020_Frozen.parquet
├── SC2_LPIS_2025_Frozen.parquet
└── SC2_ED_Boundaries_Frozen.gpkg
```

**Frozen data version DOI:** `10.5281/zenodo.22035538`

**Concept DOI:** `10.5281/zenodo.22035537`

`data_manifest.yaml` is the machine-readable authority for canonical paths, checksums and source roles.

During migration, canonical compact paths are activated only after the exact frozen file has been physically placed and regression-tested. Legacy paths remain temporary fallbacks so directory reorganisation cannot silently change the model.

---

# Baseline outputs

The refactored baseline writes the historical master and clean workbook, then the final Stage 08 and Stage 09 outputs.

```text
data/processed/
├── goblin_spatial_master_2015_2025.csv
├── GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx
├── 08_GOBLIN_Spatial_Standard_Output_2015_2025.csv
├── 09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv
└── validation_summary.csv
```

---

# Validation gates before merge to `main`

A refactored stage is not accepted because it looks cleaner. It must reproduce the validated scientific contract.

Required baseline gates include:

```text
31,427 ED-year rows
2,857 unique EDs
years exactly 2015-2025
no duplicate YEAR-CSOED keys
no negative livestock or land values

sum(21 cattle cohorts) = TOTAL_CATTLE
sum(10 sheep cohorts) = TOTAL_SHEEP

AREA_FARMED =
ALL_GRASSLAND
+ TOTAL_CEREALS
+ OTHER_CROPS_HA

2020 cattle anchor locked
2020 sheep anchor locked
2020 land/farm-structure fields locked
Stage 08 changes no pre-existing activity
Stage 09 contains one unique row per ED × follower cohort
```

The migration workflow is:

```text
validated reference script
        ↓
refactored module
        ↓
same frozen input
        ↓
output comparison
        ↓
PASS
        ↓
module accepted
```

Only after the complete baseline passes its regression gates should the draft refactor be merged into `main`.

---

# Developer usage

Install in editable mode:

```bash
pip install -e .
```

Run the current historical reconstruction:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

The Python-level complete baseline entry point is:

```python
from goblin_spatial.pipeline import run_baseline

baseline = run_baseline("configs/ireland_2015_2025.yaml")
```

The user-facing CLI will be simplified after the baseline regression migration is complete.

---

# Interpretation boundaries

- The 2020 CSO ED census is the fine-scale spatial anchor.
- Non-2020 ED values are reconstructed estimates rather than independent annual ED observations.
- AAA10 controls annual cattle totals at county level.
- Raw AAA09 detailed-region statistics control the production sheep hierarchy.
- DAFM breed information changes composition, not sheep population totals.
- AQA06 supplies regional land-use change around the exact 2020 ED anchor.
- Standard Output is production-value exposure, not income or profit.
- Stage 09 signatures are inferred accounting relationships, not observed animal movements.
- 08B and 08C are downstream soil context for scenario preparation, not historical baseline reconstruction.

---

# Citation

**Frozen model-input dataset:**

> Ofori, E. (2026). *GOBLIN-Spatial Frozen Model Inputs for Irish Electoral Division Agricultural and Land-Transition Modelling, Version 1.0.0* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.22035538

A software DOI will be added when the v1 software release is frozen.

Individual source datasets remain subject to their respective attribution and licensing requirements.

---

# Author

**Elvis Kwame Ofori**  
University of Galway
