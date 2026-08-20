# GOBLIN-Spatial

**A constraint-preserving spatial modelling framework for reconstructing agricultural systems at fine spatial resolution and spatialising nationally defined livestock and land-use transition pathways.**

GOBLIN-Spatial connects the national **GOBLIN AFOLU modelling framework** with fine-scale agricultural geography. The framework first reconstructs a controlled historical agricultural baseline at Electoral Division (ED) level and then uses that baseline to examine where nationally specified livestock adjustment may occur, how much agricultural land may be released, what that land is like, and which alternative land uses are spatially feasible.

The current Irish implementation covers **2,857 Electoral Divisions from 2015 to 2025**, anchored to the 2020 Census of Agriculture and represented in both official agricultural categories and GOBLIN-compatible livestock cohorts.

```text
National GOBLIN pathway
          │
          ▼
  GOBLIN-Spatial
          │
          ├── Where does livestock adjustment occur?
          ├── How much agricultural land may be released?
          ├── What are the characteristics of that land?
          └── Which alternative land uses are spatially feasible?
```

## Development status

The historical ED reconstruction and the downstream Standard Output, dual-soil and SC1-SC3 scientific workflows have been developed and validated in the reference modelling pipeline. The GitHub package is being migrated stage by stage into a single unified **GOBLIN-Spatial v1** implementation.

The migration rule is strict:

> **Modularisation changes software structure, not model mathematics.**

A migrated module is accepted only after it reproduces the corresponding frozen validated reference output.

---

## Model architecture

GOBLIN-Spatial contains two connected engines within one codebase:

```text
                    GOBLIN-SPATIAL

            ┌──────────────────────┐
            │   BASELINE ENGINE    │
            │      2015-2025       │
            └──────────┬───────────┘
                       │
                       ▼
            Enriched spatial baseline
                       │
                       ▼
            ┌──────────────────────┐
            │   SCENARIO ENGINE    │
            │      SC1-SC3         │
            └──────────────────────┘
```

These are not separate models. The Scenario Engine consumes the system produced by the Baseline Engine.

---

# Baseline Engine

The Baseline Engine reconstructs the historical ED agricultural system while preserving the controlling livestock, land and biological totals.

```text
Cattle + Sheep
      │
      ▼
Livestock cohort structure
      │
      ▼
Land + farm structure
      │
      ▼
Standard Output
      │
      ▼
Agricultural capability soil
      │
      ▼
Mapped physical soil
      │
      ├──────────────► Final enriched baseline
      │
      ▼
Frozen livestock signatures
```

The validated stage sequence is:

```text
01 → 02 → 03_0 → 03A → 03B → 04
                     ↓
              05A → 05B → 05C → 05D
                     ↓
                    06
                     ↓
                    07
                     ↓
                    08
                     ↓
                   08B
                     ↓
                   08C
                     ↓
                    09
```

The planned v1 package groups these stages into logical scientific modules while retaining stage identity inside the functions:

```text
baseline/
├── cattle.py                 # 01, 02, 05C
├── sheep.py                  # 03_0, 03A, 03B, 05A, 05B, 05D
├── merge.py                  # 04
├── land_farm_structure.py    # 06
├── clean_export.py           # 07
├── standard_output.py        # 08
├── agricultural_soil.py      # 08B
├── physical_soil.py          # 08C
└── signatures.py             # 09
```

### Livestock

Fine-scale agricultural data provide the ED spatial pattern, while higher-level official statistics control livestock totals and composition. The controlled livestock population is established first and is then expressed through the GOBLIN biological cohort structure without changing that population.

The Irish baseline contains **21 cattle cohorts** and **10 sheep cohorts**. Cattle cohort disaggregation retains an ED-informed distinction between dairy-origin and beef-origin young stock while allowing a restricted set of receiver/rearing EDs where the observed young-stock structure indicates livestock movement.

### Land and farm structure

The baseline also reconstructs:

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

The 2020 ED values provide the fine-scale anchor. Higher-level annual controls describe temporal change around that anchor.

These variables describe land and farm structural context. They should not be interpreted as a complete representation of household socioeconomic conditions.

### Standard Output

Standard Output is added using fixed IFS-2020 coefficients and is interpreted as **agricultural production-value exposure**. It is not farm profit, household income or welfare.

### Dual-soil representation

GOBLIN-Spatial retains two separate soil representations:

- **Cathal/NFS agricultural capability** provides the agricultural capacity frame.
- **Colm/IFS mapped physical soil** provides independent mapped soil characteristics such as drainage, peat association and parent material.

The two soil systems are intentionally retained separately rather than blended.

---

# Scenario Engine

The Scenario Engine takes nationally defined GOBLIN pathways and tests their spatial implications through three sequential stages.

```text
SC1
National livestock pathway
        │
        ▼
ED livestock adjustment
        │
        ▼
Potential released land
        │
        ▼
SC2
LPIS + agricultural capability
+ mapped physical soil + land context
        │
        ▼
Released-land opportunity
        │
        ▼
SC3
National land-use targets
+ spatial eligibility/capacity
        │
        ▼
Realised allocation
+ unmet target
+ uncommitted land
```

The v1 scenario modules are:

```text
scenario/
├── sc1_transition.py
├── sc2_opportunity.py
└── sc3_allocation.py
```

## SC1: Spatial livestock transition

SC1 spatialises nationally specified livestock endpoints across EDs. Alternative allocation policies can change **where adjustment occurs**, but they cannot change the national pathway endpoint.

SC1 also spatialises the authoritative national released-land quantity. It does not decide the future land use of that released land.

## SC2: Released-land opportunity

SC2 characterises the land released in SC1 using LPIS, agricultural capability, mapped physical soil, organic-soil evidence and other spatial eligibility information.

SC2 does not rerun the livestock transition and does not change the amount of land released by SC1.

## SC3: Land-transition feasibility

SC3 combines released-land opportunity with explicit national land-use targets. Allocation is constrained by the amount and characteristics of land actually available.

A national target is therefore not forced into EDs where sufficient eligible capacity does not exist. SC3 reports realised allocation, unmet target and remaining uncommitted land.

### Central distinction

A core rule of GOBLIN-Spatial is:

```text
Potential Release ≠ Opportunity ≠ Realised Conversion
```

Livestock contraction may release agricultural land. That does not mean every released hectare is suitable for every alternative use, and spatial suitability does not mean that all suitable land is necessarily converted.

---

# National and spatial authority

GOBLIN-Spatial separates national and spatial modelling responsibilities:

```text
Official agricultural statistics
        ↓
control the historical agricultural system

GOBLIN
        ↓
controls national transition pathways

GOBLIN-Spatial
        ↓
controls spatial representation
and tests spatial feasibility
```

GOBLIN-Spatial does not redefine the national GOBLIN pathway. Its role is to examine what that pathway implies when agricultural geography, livestock structure, soils and land-use constraints are taken seriously.

---

# Data and reproducibility

The final v1 software and scientific data will be distributed separately:

```text
GitHub
├── Python source code
├── tests
├── configuration
├── data manifest
└── documentation

Zenodo
└── versioned frozen model inputs

Local installation
└── data/inputs/
```

The package already uses a Pooch-based data-fetching and SHA256 verification system. For v1, this mechanism will be connected to the frozen external data release so that missing inputs can be retrieved automatically while existing files are verified and reused.

The final frozen input contract contains the following scientific categories.

### Livestock

```text
01_CSO_ED_Agricultural_Baseline_2020.csv
01_CSO_AAA10_Cattle_County_2015_2025.csv
03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx
03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv
05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv
05C_Cattle_Cohort_Relationships_2012_2020.csv
```

### Land and farm structure

```text
06_CSO_AQA06_Agricultural_Land_Use.xlsx
06_Farm_Structure_Demographic_Controls.csv
```

### Economic context

```text
08_IFS2020_Standard_Output_Mapping.xlsx
```

### Soil

```text
08B_NFS_Agricultural_Soil_Capability.csv
08C_IFS_Mapped_Physical_Soil_Package.zip
```

### Scenario controls

```text
SC1_Cattle_Scenario_Endpoints_2050.csv
SC1_ED_Rural_Mixed_Urban_2022.xlsx
```

### Spatial opportunity

```text
SC2_LPIS_2020_Frozen.parquet
SC2_LPIS_2025_Frozen.parquet
SC2_ED_Boundaries_Frozen.gpkg
```

The principal scenario configuration uses the **2020 baseline and LPIS 2020**. LPIS 2025 is retained for optional alternative-baseline or sensitivity applications.

**Frozen input DOI:** to be added after the v1 data release is published.

---

# Current developer usage

Install the package in editable mode:

```bash
pip install -e .
```

Verify the currently declared development data contract:

```bash
goblin-spatial fetch-data --verify-only
```

Build the currently modularised historical package:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

The final v1 CLI will expose separate baseline, scenario and full-pipeline commands once the validated 08-SC3 stages have completed regression migration.

---

# Accounting and validation

The baseline obeys the core identities:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP

AREA_FARMED =
ALL_GRASSLAND
+ TOTAL_CEREALS
+ OTHER_CROPS_HA
```

The Irish reference baseline contains:

```text
2,857 EDs
2015-2025
31,427 ED-year observations
21 cattle cohorts
10 sheep cohorts
```

Scenario accounting additionally requires:

```text
SC1 national livestock totals
= national GOBLIN pathway totals

SC1 spatial released land
= authoritative national released-land total

SC2 released land
= SC1 released land

SC3 realised allocation
<= eligible spatial capacity
```

For each targeted land use:

```text
Realised allocation + Unmet target = Target
```

Exact accounting closure demonstrates consistency with the model constraints. It should not be interpreted as independent empirical validation of every reconstructed ED-level value.

---

# Regression migration rule

The original scientific pipeline was developed and validated stage by stage. During conversion to the Python package, every module must reproduce its corresponding frozen reference output before it is accepted.

```text
Validated reference script
          ↓
Modular function
          ↓
Same frozen input
          ↓
Output comparison
          ↓
PASS
          ↓
Module accepted
```

This preserves scientific equivalence while improving software structure, testing and reproducibility.

---

# Interpretation boundaries

Users should observe the following limits:

- Non-2020 ED values are reconstructed rather than independent annual ED census observations.
- Standard Output represents production-value exposure rather than profit, household income or welfare.
- Cathal/NFS agricultural capability and Colm/IFS physical soil are separate information layers.
- G3 soil capability should not automatically be interpreted as peat or organic soil.
- LPIS contributes information about land-use characteristics and potential opportunity. It does not prescribe future land use.
- Scenario allocation policies change the spatial distribution of livestock adjustment, not the national scenario endpoint.
- Potential released land should not be interpreted as land that is automatically converted to another use.

---

# Intended v1 repository structure

```text
GOBLIN-Spatial/
├── README.md
├── pyproject.toml
├── data_manifest.yaml
├── configs/
│
├── src/
│   └── goblin_spatial/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── pipeline.py
│       │
│       ├── data/
│       │   ├── fetch.py
│       │   ├── data_manager.py
│       │   └── validate_inputs.py
│       │
│       ├── baseline/
│       │   ├── cattle.py
│       │   ├── sheep.py
│       │   ├── merge.py
│       │   ├── land_farm_structure.py
│       │   ├── clean_export.py
│       │   ├── standard_output.py
│       │   ├── agricultural_soil.py
│       │   ├── physical_soil.py
│       │   └── signatures.py
│       │
│       ├── scenario/
│       │   ├── sc1_transition.py
│       │   ├── sc2_opportunity.py
│       │   └── sc3_allocation.py
│       │
│       └── utils/
│           ├── paths.py
│           ├── io.py
│           ├── allocation.py
│           └── validation.py
│
├── tests/
│
└── data/
    ├── inputs/
    └── outputs/
```

Paper-specific analysis, figures and exploratory workflows are deliberately outside the core v1 package.

The core software is therefore:

```text
Data management
      +
Baseline Engine
      +
Scenario Engine
```

---

# Citation

When the v1 release is complete, users should cite both the software release and the corresponding frozen data release so that the code version and the exact scientific input version can be identified independently.

**Software DOI:** to be added.

**Frozen model-input DOI:** to be added.

Individual datasets remain subject to their respective source licences and attribution requirements.

---

# Author

**Elvis Kwame Ofori**  
University of Galway

---

**GOBLIN-Spatial links nationally controlled agricultural and AFOLU transition pathways with fine-scale agricultural geography while preserving the distinction between livestock adjustment, potential land release, spatial opportunity and realised land-use transition.**
