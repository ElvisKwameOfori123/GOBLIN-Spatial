# GOBLIN-Spatial

**A constraint-preserving spatial framework for reconstructing agricultural systems, spatialising livestock transition pathways, identifying released-land opportunities, and testing feasible alternative land-use transitions.**

GOBLIN-Spatial provides the spatial layer linking the national GOBLIN AFOLU modelling framework to fine-scale agricultural geography. The current Irish implementation reconstructs a historical agricultural system for **2,857 Electoral Divisions (EDs) from 2015 to 2025**, anchored to the **2020 CSO Census of Agriculture**, and then provides the spatial machinery required to examine where future livestock adjustment, land release, alternative land-use opportunity and feasible land-use transition could occur.

The model is deliberately hierarchical:

```text
NATIONAL GOBLIN PATHWAY
How much livestock and land-use change is required?
                    |
                    v
GOBLIN-SPATIAL
Where can that change occur while preserving
agricultural geography, livestock structure and land constraints?
```

The complete scientific sequence is:

```text
HISTORICAL AGRICULTURAL SYSTEM
2020 ED anchor + 2015-2025 official controls
                    |
                    v
        31-cohort ED livestock baseline
                    |
                    v
          land + crops + farm structure
                    |
                    v
           Standard Output exposure
                    |
                    v
          frozen ED cohort signatures
                    |
                    v
         HISTORICAL BASELINE COMPLETE
                    |
                    v
        08B / 08C soil context
                    |
                    v
         national GOBLIN pathway
                    |
                    v
      SC1 spatial livestock transition
                    |
                    v
       authoritative gross land release
                    |
                    v
      SC2 released-land opportunity
       soil + LPIS + ED geography
                    |
                    v
      SC3 constrained land allocation
                    |
                    v
 realised conversion + unmet target + residual land
                    |
                    v
       SPATIAL TRANSITION FORESIGHT
```

## Development status

The project is being migrated into a clean v1 Python package.

The **historical baseline through Stage 09 has been refactored and regression-verified on draft PR #1**. The scenario stack is described here because it is part of the scientific model, but SC1-SC3 will undergo their own refactor and regression pass before being treated as the final v1 scenario implementation.

The migration rule is strict:

> **Software structure may improve, but validated scientific mathematics must not change silently.**

---

# 1. What GOBLIN-Spatial is designed to answer

GOBLIN-Spatial is not a replacement for the national GOBLIN model. GOBLIN remains the authority for national livestock and land-use pathway totals. GOBLIN-Spatial resolves the **geography of transition**.

The framework is designed to answer questions such as:

- Where is livestock adjustment concentrated under a national pathway?
- Which EDs face the greatest livestock and production-value exposure?
- How much land could be released from livestock production in each ED?
- What are the agricultural and physical characteristics of that released land?
- Which alternative land uses are compatible with that land?
- Where can explicit national land-use targets be realised spatially?
- Where are targets constrained by land availability, soil or parcel suitability?
- Which areas combine high transition exposure with limited alternative opportunity?

The model therefore separates three concepts that must not be conflated:

```text
PotentialRelease != Opportunity != RealisedConversion
```

- **PotentialRelease** is land released from livestock pressure under the pathway.
- **Opportunity** describes what that released land could plausibly support.
- **RealisedConversion** is land actually allocated to an alternative use after eligibility and capacity constraints are applied.

---

# 2. Scientific authority hierarchy

The framework follows a strict authority order:

```text
GOBLIN national pathway
        |
        v
national livestock / land-use requirement
        |
        v
GOBLIN-Spatial ED allocation
        |
        v
soil + LPIS + geography
        |
        v
spatial opportunity and feasibility
```

This means:

- national livestock endpoints are not changed to make spatial allocation easier;
- soil does not determine historical livestock numbers;
- soil and LPIS do not decide where livestock must be removed in SC1;
- the national gross land release supplied by GOBLIN remains authoritative;
- SC2 characterises released land rather than recalculating the livestock transition;
- SC3 does not force infeasible hectares merely to satisfy a national target.

---

# 3. Historical baseline, 2015-2025

The historical baseline is the verified foundation of the model and ends at **Stage 09 ED signatures**.

```text
CATTLE                              SHEEP
01 2020 ED cattle anchor            03A regional -> county sheep controls
02 annual ED cattle panel           03B county -> ED sheep panel
05C 21 cattle cohorts               05A annual breed composition
                                    05B ED breed/type enrichment
                                    05D 10 sheep cohorts
             \                       /
              \                     /
                 04 LIVESTOCK MERGE
                         |
                         v
                31 livestock cohorts
                         |
                         v
          06 land + crops + farm structure / SE
                         |
                         v
                 07 clean validated export
                         |
                         v
             08 fixed-2020 Standard Output
                         |
                         v
              09 frozen ED cohort signatures
                         |
                         v
               HISTORICAL BASELINE COMPLETE
```

The complete historical system contains:

```text
2,857 EDs
11 years: 2015-2025
31,427 ED-year rows
21 cattle cohorts
10 sheep cohorts
31 livestock cohorts in total
```

Non-2020 ED values are reconstructed estimates. They are not presented as independently observed annual ED censuses.

## 3.1 Cattle module

### Stage 01: 2020 ED cattle anchor

The 2020 CSO ED agricultural census provides the fine-scale cattle geography. CSO AAA10 county statistics provide the controlling county totals for:

```text
DAIRY_COW
OTHER_COW
TOTAL_CATTLE
```

The residual population is:

```text
OTHER_CATTLE = TOTAL_CATTLE - DAIRY_COW - OTHER_COW
```

AAA10 age-sex information then partitions `OTHER_CATTLE` into the required age-sex containers. GOBLIN genetic information is not used to determine the Stage 01 population.

### Stage 02: annual ED cattle panel

The reconciled 2020 within-county ED pattern supplies the spatial support. Annual AAA10 county totals control the 2015-2025 cattle trajectory. The 2020 ED state remains the fixed anchor.

### Stage 05C: 21 GOBLIN cattle cohorts

The CSO cattle population remains authoritative. GOBLIN supplies biological relationships used to express that population in the 21 GOBLIN cattle cohorts.

For 2015-2020, year-specific GOBLIN relationships are used. For 2021-2025, the 2020 biological relationships are retained and applied to each year's current CSO-controlled livestock structure.

Genetic support is linked to the adult-cow structure:

```text
dairy cows   -> DxD and DxB support
suckler cows -> BxB support
```

Every ED-year must satisfy:

```text
sum(21 cattle cohorts) = TOTAL_CATTLE
```

## 3.2 Sheep module

The production sheep population follows the validated **03A -> 03B** hierarchy.

### Stage 03A: regional controls to corrected county controls

The 2020 ED `TOTAL_SHEEP` distribution provides the fine-scale footprint. The frozen AAA09 workbook provides:

- `County_WIDE`: County -> detailed-region / NUTS2 crosswalk;
- `Region_WIDE`: detailed-region sheep totals and demographic composition for 2015-2025.

The observed 2020 ED footprint is reconciled to the 2020 detailed-region totals, aggregated to corrected county anchors, and used to distribute non-2020 regional totals spatially.

The four non-overlapping sheep classes are reconciled jointly:

```text
EWES_2_PLUS
EWES_UNDER_2
RAMS
OTHER_SHEEP
```

### Stage 03B: county to ED

Corrected annual county totals are allocated to EDs using the corrected 2020 within-county spatial pattern. Structural zero support is retained.

### DAFM county sheep hold-out

`03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv` is retained as independent validation evidence. It does not replace the production CSO/AAA09 population controls in the current baseline.

### Stages 05A and 05B: breed composition

DAFM breed anchors for 2016, 2020, 2022 and 2025 supply **composition only**. They do not alter the CSO-controlled sheep population total.

Mountain and Mountain Cross sheep are mapped operationally to the GOBLIN-compatible upland grouping. This is not an observed ED hill-farm classification.

### Stage 05D: 10 GOBLIN sheep cohorts

The enriched sheep population is expressed in the 10 GOBLIN sheep cohorts.

Every ED-year must satisfy:

```text
sum(10 sheep cohorts) = TOTAL_SHEEP
```

## 3.3 Stage 04: livestock merge

Cattle and sheep remain separate until both systems pass their own accounting checks. They are then merged on `YEAR + CSOED`.

```text
21 cattle cohorts
+ 10 sheep cohorts
= 31 livestock cohorts
```

The merge does not recalculate cattle or sheep numbers.

## 3.4 Stage 06: land, crops and farm structure / SE

Stage 06 adds:

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

The exact 2020 ED values are the spatial anchor. AQA06 regional statistics supply annual land-use change around that anchor.

Every ED-year must satisfy:

```text
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

Stage 06 must not change livestock values.

## 3.5 Stage 07: clean baseline export

Stage 07 is an output and validation boundary. It produces the clean historical deliverable without changing scientific values.

## 3.6 Stage 08: Standard Output

Stage 08 applies fixed IFS-2020 Standard Output coefficients to the reconstructed agricultural activities.

Standard Output is interpreted as **agricultural production-value exposure**. It is not farm profit, household income or welfare.

The frozen runtime mapping is:

```text
08_IFS2020_Standard_Output_Mapping.xlsx
```

Stage 08 must not change pre-existing livestock, land, crop or farm-structure values.

## 3.7 Stage 09: frozen ED cohort signatures

Stage 09 is the final historical-baseline stage.

It freezes the pre-scenario relationship between each ED's adult-cow structure and its cattle follower cohorts. The receiver hierarchy distinguishes:

```text
LOCAL_ED
COUNTY_RECEIVER
NATIONAL_ORPHAN
NONE
```

These are modelled accounting relationships inferred from reconstructed livestock geography, not observations of individual animal movement.

The scenario principle is:

```text
national GOBLIN relationships determine national cohort totals
+
ED baseline signatures retain the geography of those cohorts
```

---

# 4. Historical baseline verification

The v1 historical baseline through Stage 09 has passed its regression suite on the development branch.

Current verification includes:

```text
9/9 packaged baseline and validation inputs pass SHA256 verification
8/8 production-input migration-equivalence checks pass
27/27 historical baseline unit/contract tests pass
full Stage 01 -> Stage 09 reconstruction passes
```

Core regression gates include:

```text
2,857 unique EDs
31,427 ED-year rows
years exactly 2015-2025
no duplicate YEAR-CSOED keys
sum(21 cattle cohorts) = TOTAL_CATTLE
sum(10 sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
2020 cattle anchor retained
2020 sheep anchor retained
2020 land/farm-structure anchors retained
Stage 08 changes no pre-existing activity
Stage 09 has unique ED x follower-cohort signatures
```

---

# 5. Scenario-preparation soil context: 08B and 08C

The historical baseline ends at Stage 09. **08B and 08C begin the downstream scenario-preparation side of the framework.**

```text
HISTORICAL BASELINE THROUGH 09
        |
        +--> 08B Cathal/NFS agricultural-capability soil
        |
        +--> 08C Colm/IFS mapped physical soil
        |
        v
SCENARIO-READY SPATIAL CONTEXT
```

The two soil systems remain independent.

### 08B agricultural capability

The NFS/Cathal layer represents agricultural capability using the six source soil classes collapsed into three broad opportunity groups:

```text
G1 = C1 + C2
G2 = C3 + C4
G3 = C5 + C6
```

It is an agricultural-opportunity representation, not a physical soil map.

### 08C mapped physical soil

The IFS/Colm layer provides a separate mapped physical-soil representation using categories such as deep well drained, shallow well drained, poorly drained, poorly drained peaty, alluvium and peat.

The two layers are not blended into a single soil index.

`G3` must not be interpreted as equivalent to peat or organic soil.

---

# 6. National livestock pathways

The principal GOBLIN-Spatial scenario set uses a common 2020 baseline and three national pathways:

| Pathway | 2050 dairy cows | 2050 suckler cows | Interpretation |
|---|---:|---:|---|
| `SI_SG` | 1.60 million | 0.160 million | Split-gas pathway with comparatively smaller cattle contraction |
| `BE_SG` | 1.54 million | 0.154 million | Bioeconomy-oriented split-gas pathway |
| `ALL_GAS_NZ` | 0.875 million | 0.0875 million | Stronger all-gas net-zero livestock contraction |

These national endpoints are external controls. Spatial policies may alter **where** adjustment occurs, but they must not alter the national endpoint.

Sheep remain part of the validated historical ED system unless an explicit sheep scenario is supplied. A cattle pathway is not interpreted as an instruction to remove Irish sheep.

---

# 7. SC1: spatial livestock transition and destocking

SC1 converts a national livestock pathway into a spatially heterogeneous ED transition.

The sequence is:

```text
national dairy + suckler pathway
        |
        v
ED adult-cow transition
        |
        v
Stage 09 ED cohort signatures
        |
        v
21-cohort future cattle structure
        |
        v
exact national reconciliation
        |
        v
spatial livestock adjustment / destocking
```

The key design principle is that EDs retain their historical cohort signatures as far as possible. National biological relationships determine the national cohort requirement, but the ED baseline determines the spatial expression of those cohorts.

The intended national constraints include:

```text
sum(ED dairy cows)   = national dairy target
sum(ED suckler cows) = national suckler target
sum(ED cohort c)     = national cohort-c target, where controlled
```

and at ED level:

```text
TOTAL_CATTLE = sum(21 cattle cohorts)
```

SC1 therefore answers **where the livestock transition is concentrated**, not which alternative land use should replace it.

---

# 8. Gross land release

The national GOBLIN pathway is the authority for **gross livestock land release**. GOBLIN-Spatial spatialises that national total across EDs.

A diagnostic stocking-rate or feed-demand calculation may be retained as a sensitivity or consistency check, but it does not replace the authoritative national release total.

For the current reference pathway controls:

```text
SI_SG gross livestock land release ~= 1.593 Mha
BE_SG gross livestock land release ~= 1.587 Mha
```

These values must not be confused with the smaller residual land remaining after some released land has already been allocated to new uses.

For example:

```text
SI_SG
Gross release      1.593 Mha
AD grass           0.130 Mha
additional forest  0.374 Mha
Residual available 1.089 Mha

BE_SG
Gross release      1.587 Mha
AD grass           0.130 Mha
biorefinery         0.180 Mha
willow              0.400 Mha
additional tillage 0.100 Mha
additional forest  0.374 Mha
Residual available 0.403 Mha
```

Thus:

```text
GrossRelease != ResidualAvailableLand
```

---

# 9. SC2: released-land opportunity

SC2 begins only after SC1 has established the livestock transition and gross released-land geography.

SC2 asks:

> **What is the released land like, and what alternative uses could it plausibly support?**

Its principal spatial evidence includes:

```text
released land from SC1
        +
08B agricultural-capability soil
        +
08C mapped physical soil
        +
LPIS parcel information
        +
frozen ED geography
        v
released-land opportunity / eligibility
```

SC2 does **not**:

- rerun the livestock transition;
- alter national livestock endpoints;
- alter the authoritative gross land release;
- multiply one soil system by the other;
- assume that every potentially released hectare is available for every future use.

LPIS 2020 is the principal parcel reference for scenarios using the common 2020 baseline. LPIS 2025 is retained as an optional sensitivity/additional spatial reference rather than silently replacing the common-baseline parcel layer.

---

# 10. Alternative land-use opportunities

The model currently represents a set of alternative or additional land uses that may compete for released agricultural land:

```text
AD_GRASS
BIOREFINERY
WILLOW
ADDITIONAL_TILLAGE
FOREST
REWETTING
```

Their interpretation differs:

- **AD grass**: grassland supplying anaerobic-digestion feedstock where compatible with the pathway.
- **Biorefinery**: biomass/feedstock land associated with bioeconomy scenarios.
- **Willow**: short-rotation woody biomass opportunity subject to land suitability.
- **Additional tillage**: expansion of crop area where agricultural capability and land constraints permit.
- **Forest**: additional afforestation subject to spatial eligibility and pathway targets.
- **Rewetting**: restoration of eligible drained organic grassland, subject to organic-soil capacity and remaining available land.

The existence of a national target does not imply that every ED is eligible or that the national target is spatially feasible.

---

# 11. SC3: constrained alternative land-use allocation

SC3 converts opportunity into **realised spatial allocation**.

The validated allocation logic is sequential.

## Stage A

The first allocation stage considers:

```text
AD_GRASS
BIOREFINERY
WILLOW
ADDITIONAL_TILLAGE
FOREST
```

Each use is subject to hard eligibility constraints and soft opportunity scores.

After Stage A:

```text
ParentAvailable = ReleasedLand - StageAAllocations
```

## Stage B: rewetting

Rewetting is then allocated from the remaining compatible land using the organic-soil capacity representation.

The model enforces:

```text
Rewetting_ED <= remaining available land in ED
```

and does not permit forced overlap with land already allocated to Stage A uses.

The feasibility rule is simple:

```text
if national target <= feasible spatial capacity:
    realise target
else:
    realise feasible amount
    report unmet target
```

SC3 therefore reports:

```text
Target
RealisedConversion
UnmetTarget
ResidualAvailableLand
```

rather than forcing an infeasible spatial solution.

---

# 12. Reference national land-use targets

The current reference controls include the following cumulative land-use requirements:

| Pathway | Rewetting | AD grass | Biorefinery | Willow | Additional tillage | Additional forest |
|---|---:|---:|---:|---:|---:|---:|
| `SI_SG` | 70 kha | 130 kha | 0 | 0 | 0 | 374 kha |
| `BE_SG` | 70 kha | 130 kha | 180 kha | 400 kha | 100 kha | 374 kha |
| `ALL_GAS_NZ` | 127 kha | 310 kha | 0 | 529.8 kha | 500 kha | 577 kha |

If a target exceeds spatial capacity, the difference is retained as an explicit unmet requirement rather than hidden by over-allocation.

---

# 13. Exposure, opportunity and transition foresight

GOBLIN-Spatial is intended as a **spatial stress-test of plausible national pathways**.

A useful interpretation combines transition exposure with alternative opportunity:

| Transition exposure | Alternative opportunity | Interpretation |
|---|---|---|
| High | Stronger | **Prepared transition potential** |
| High | Limited | **Priority transition constraint** |
| Lower / contingent | Stronger | **Strategic opportunity** |
| Lower / contingent | Limited | **Lower immediate priority / monitor** |

This is a foresight interpretation, not a prediction that a particular ED will necessarily adopt a specific land use.

Standard Output can contribute to the exposure dimension by representing production-value exposure. It is not interpreted as farm income, profitability or welfare.

---

# 14. Data architecture

GOBLIN-Spatial uses a hybrid data strategy.

```text
GitHub
├── code
├── tests
├── configuration
├── manifest
└── compact historical-baseline controls

Zenodo
└── large frozen soil / LPIS / geography inputs
```

## Compact historical inputs tracked in GitHub

```text
data/inputs/baseline/
├── 01_CSO_ED_Agricultural_Baseline_2020.csv
├── 01_CSO_AAA10_Cattle_County_2015_2025.csv
├── 03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx
├── 03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv
├── 05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv
├── 05C_Cattle_Cohort_Relationships_2012_2020.csv
├── 06_CSO_AQA06_Agricultural_Land_Use.xlsx
├── 06_Farm_Structure_Demographic_Controls.csv
└── 08_IFS2020_Standard_Output_Mapping.xlsx
```

The DAFM county sheep file is included for hold-out validation rather than production control.

## Compact scenario controls

```text
SC1_Cattle_Scenario_Endpoints_2050.csv
SC1_ED_Rural_Mixed_Urban_2022.xlsx
```

## Large frozen spatial inputs

```text
08B_NFS_Agricultural_Soil_Capability.csv
08C_IFS_Mapped_Physical_Soil_Package.zip
SC2_LPIS_2020_Frozen.parquet
SC2_LPIS_2025_Frozen.parquet
SC2_ED_Boundaries_Frozen.gpkg
```

Frozen data release:

**Version DOI:** `10.5281/zenodo.22035538`

**Concept DOI:** `10.5281/zenodo.22035537`

`data_manifest.yaml` is the machine-readable authority for canonical paths, checksums and source roles.

---

# 15. Package architecture

The v1 target separates historical reconstruction from future scenario analysis.

```text
src/goblin_spatial/
├── baseline/
│   ├── cattle.py
│   ├── sheep.py
│   ├── merge.py
│   ├── land_farm_structure.py
│   ├── clean_export.py
│   ├── standard_output.py
│   └── signatures.py
│
├── scenario/
│   ├── sc1_transition.py
│   ├── sc2_opportunity.py
│   └── sc3_allocation.py
│
├── data/
├── utils/
├── config.py
├── pipeline.py
└── cli.py
```

The historical baseline package is being accepted only after regression equivalence. SC1-SC3 will follow the same rule during their v1 migration.

---

# 16. Baseline outputs

The refactored historical pipeline produces:

```text
data/processed/
├── goblin_spatial_master_2015_2025.csv
├── GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx
├── 08_GOBLIN_Spatial_Standard_Output_2015_2025.csv
├── 09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv
└── validation_summary.csv
```

Scenario outputs are kept separate from the historical reconstruction and will include ED livestock transitions, released-land accounting, opportunity/eligibility layers, realised land-use allocations, unmet targets and residual available land.

---

# 17. Validation philosophy

A module is not accepted because it is cleaner or faster. It must satisfy the relevant scientific accounting contracts.

The migration workflow is:

```text
validated reference logic
        |
        v
refactored module
        |
        v
same frozen input
        |
        v
output / accounting comparison
        |
        v
PASS
        |
        v
module accepted
```

Important model invariants include:

```text
National controls remain authoritative
Cattle and sheep close to their cohort totals
Land accounting closes at ED-year level
Standard Output does not alter physical activity
Stage 09 does not depend on scenario code
SC1 preserves national livestock targets
SC2 preserves SC1 released-land accounting
SC3 preserves land availability and reports infeasibility
```

---

# 18. Interpretation boundaries

- The 2020 CSO ED census is the fine-scale spatial anchor.
- Non-2020 ED values are reconstructed estimates rather than independent annual ED observations.
- AAA10 controls annual cattle totals at county level.
- AAA09 detailed-region statistics control the production sheep hierarchy.
- DAFM breed information changes sheep composition, not sheep population totals.
- AQA06 supplies regional land-use change around the exact 2020 ED anchor.
- Standard Output is production-value exposure, not income or profit.
- Stage 09 signatures are inferred accounting relationships, not observed animal movements.
- 08B and 08C are independent downstream soil representations.
- G3 soil capability is not synonymous with peat or organic soil.
- Soil and LPIS do not determine livestock reductions.
- Potential release is not the same as opportunity or realised conversion.
- Residual available land is not the same as gross livestock land release.
- Unmet land-use targets are valid model results when spatial capacity is insufficient.

---

# 19. Developer usage

Install in editable mode:

```bash
pip install -e .
```

Verify tracked model inputs:

```bash
goblin-spatial fetch-data --verify-only --tracked-only
```

Build the historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Python entry point:

```python
from goblin_spatial.pipeline import run_baseline

baseline = run_baseline("configs/ireland_2015_2025.yaml")
```

Scenario commands currently remain under migration and will be simplified as SC1-SC3 are moved into their final v1 modules.

---

# 20. Citation

**Frozen model-input dataset:**

> Ofori, E. (2026). *GOBLIN-Spatial Frozen Model Inputs for Irish Electoral Division Agricultural and Land-Transition Modelling, Version 1.0.0* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.22035538

A software DOI will be added when the v1 software release is frozen.

Individual source datasets remain subject to their respective attribution and licensing conditions. See the frozen-input README, manifest and source documentation for provenance.
