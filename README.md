# GOBLIN-Spatial

**A constraint-preserving spatial framework for reconstructing agricultural systems, spatialising livestock transition pathways, identifying released-land opportunities, and testing feasible alternative land-use transitions.**

GOBLIN-Spatial connects nationally controlled agricultural and AFOLU pathways with fine-scale agricultural geography. The current Irish implementation reconstructs a historical agricultural system for **2,857 Electoral Divisions (EDs) from 2015 to 2025**, anchored to the **2020 CSO Census of Agriculture**, and then uses that frozen baseline to examine where future livestock adjustment, land release and alternative land-use opportunities could occur.

The model is deliberately hierarchical. National pathways determine how much change occurs. GOBLIN-Spatial determines where that change can occur while preserving agricultural geography, livestock cohort relationships and land constraints.

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
             NATIONAL PATHWAY
      SI_SG | BE_SG | ALL_GAS_NZ
                    |
                    v
       SC1 SPATIAL LIVESTOCK TRANSITION
   adult-cow change -> follower cohorts -> EDs
                    |
                    v
        GROSS POTENTIAL LAND RELEASE
                    |
                    v
       SC2 RELEASED-LAND OPPORTUNITY
      soil + LPIS + geography + context
                    |
                    v
      SC3 CONSTRAINED LAND ALLOCATION
                    |
                    v
   realised conversion + unmet target + residual
                    |
                    v
        SPATIAL TRANSITION FORESIGHT
```

The central rule is:

> **GOBLIN controls national pathway quantities. GOBLIN-Spatial resolves geography and feasibility.**

Spatial policies can alter **where** adjustment occurs, but they must not silently change the national scenario endpoint.

---

# Current development status

GOBLIN-Spatial is being migrated into a clean v1 Python package on the development branch before changes are merged to `main`.

The migration rule is strict:

> **Refactor the software, not the validated scientific mathematics.**

Current status:

| Component | Status |
| --- | --- |
| Historical baseline, Stages 01-09 | **Regression verified** |
| Compact baseline input packaging | **SHA256 verified and active in GitHub** |
| Baseline input equivalence audit | **Passed** |
| 08B agricultural soil input | Frozen input available, downstream integration retained |
| 08C physical soil input | Frozen input available, downstream integration retained |
| SC1 livestock transition | Scientific reference logic established, v1 refactor still to be completed |
| SC2 released-land opportunity | Scientific reference logic established, v1 refactor still to be completed |
| SC3 alternative land-use allocation | Scientific reference logic established, v1 refactor still to be completed |
| Merge to `main` | **Not yet performed** |

The verified historical baseline is therefore stable. The next substantial software work is the scenario engine, not another redesign of the baseline.

---

# 1. Historical baseline

## 1.1 Final baseline boundary

The historical baseline finishes at **Stage 09 ED cohort signatures**.

```text
CATTLE
01  2020 ED cattle reconciliation
02  2015-2025 ED cattle panel
05C 21 GOBLIN cattle cohorts
        |
        |-----------------|
        |                 |
        v                 v
                       04 MERGE
        ^                 ^
        |                 |
        |-----------------|
        |
SHEEP
03A AAA09 region -> corrected county controls
03B corrected county -> ED sheep panel
05A annual DAFM breed composition
05B ED breed/type enrichment
05D 10 GOBLIN sheep cohorts
        |
        v
31-COHORT LIVESTOCK MASTER
        |
        v
06 LAND + CROPS + FARM STRUCTURE / SE
        |
        v
07 CLEAN VALIDATED EXPORT
        |
        v
08 FIXED-2020 STANDARD OUTPUT
        |
        v
09 FROZEN ED COHORT SIGNATURES
        |
        v
HISTORICAL BASELINE COMPLETE
```

Stages 08B and 08C do **not** reconstruct historical livestock. They are downstream spatial-context layers used after the historical system has been frozen.

## 1.2 Historical package boundary

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

Cattle and sheep are built independently. Merge joins the two validated systems on `YEAR + CSOED`; it does not recalculate either livestock population.

---

# 2. Cattle baseline

## Stage 01: 2020 ED cattle anchor

The 2020 CSO ED agricultural census provides the within-county spatial pattern. CSO AAA10 supplies the exact county controls for:

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

## Stage 02: annual cattle panel

The reconciled 2020 within-county ED pattern is held as the spatial support. Annual AAA10 county totals control 2015-2025 cattle populations. The 2020 ED state is copied exactly.

Non-2020 ED values are reconstructed estimates, not independently observed annual ED censuses.

## Stage 05C: 21 GOBLIN cattle cohorts

The CSO cattle population remains authoritative. GOBLIN supplies biological relationships only.

For 2015-2020, year-specific GOBLIN relationships are used. For 2021-2025, the 2020 biological relationships are held constant and applied to the current CSO dairy/suckler structure.

Genetic support is ED-informed:

```text
dairy cows   -> DxD / DxB support
suckler cows -> BxB support
```

Sparse receiver/rearing exceptions are retained where young cattle occur without the corresponding local parent population and support is required for exact national closure.

Every ED-year must satisfy:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
```

---

# 3. Sheep baseline

The production sheep baseline follows the validated **03A -> 03B** hierarchy.

## Stage 03A: regional controls to corrected county controls

The 2020 ED `TOTAL_SHEEP` distribution supplies the fine-scale spatial footprint.

The frozen AAA09 workbook contains two relevant sheets:

- `County_WIDE`: County -> detailed-region / NUTS2 crosswalk;
- `Region_WIDE`: raw AAA09 detailed-region totals and demographic composition for 2015-2025.

The observed 2020 ED sheep footprint is reconciled to exact 2020 detailed-region totals. Those corrected ED values are aggregated to corrected 2020 county anchors. For non-2020 years, each region's AAA09 total is distributed to counties using the corrected 2020 county shares.

The four non-overlapping sheep classes are reconciled jointly:

```text
EWES_2_PLUS
EWES_UNDER_2
RAMS
OTHER_SHEEP
```

## Stage 03B: county to ED

Corrected annual county sheep totals are allocated to EDs using the corrected 2020 within-county ED pattern. The 2020 state is reproduced exactly and structural zero support is preserved.

## DAFM county sheep hold-out

`03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv` is retained for independent/hold-out validation. It does not replace the production CSO/AAA09 sheep population in the current validated baseline.

## Stages 05A and 05B: breed composition

DAFM breed anchors provide **composition only** for 2016, 2020, 2022 and 2025. Annual shares are reconstructed using the validated interpolation rules and applied to the CSO-controlled sheep population without changing total sheep numbers.

Mountain + Mountain Cross is retained as an upland-type proxy for GOBLIN-compatible mapping. It is not presented as an observed ED hill-farm classification.

## Stage 05D: 10 GOBLIN sheep cohorts

The enriched sheep population is expressed in the 10 GOBLIN sheep cohorts.

```text
Lowland ewes
Upland ewes
Lowland lamb_less_1_yr
Lowland male_less_1_yr
Lowland lamb_more_1_yr
Lowland ram
Upland lamb_less_1_yr
Upland male_less_1_yr
Upland lamb_more_1_yr
Upland ram
```

Every ED-year must satisfy:

```text
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
```

---

# 4. Stage 04: livestock merge

Cattle and sheep are merged only after their independent accounting checks pass.

```text
21 cattle cohorts
+ 10 sheep cohorts
= 31 GOBLIN livestock cohorts
```

The merge does not alter cattle or sheep numbers.

---

# 5. Stage 06: land, crops and farm structure

Stage 06 adds the structural variables required to interpret agricultural adjustment:

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

AQA06 supplies annual regional change around the 2020 ED land structure. The validated seven-region mapping is deterministic and stored in the code.

Every ED-year must satisfy:

```text
AREA_FARMED =
ALL_GRASSLAND
+ TOTAL_CEREALS
+ OTHER_CROPS_HA
```

Farm holdings and holder-age indicators use the validated State/county trajectories around the fixed 2020 ED anchor.

Stage 06 must not change any of the 31 livestock cohorts.

---

# 6. Stage 07: clean historical export

Stage 07 is an output and validation boundary. It standardises the historical deliverable without changing scientific values.

The complete panel has:

```text
2,857 EDs
11 years: 2015-2025
31,427 ED-year rows
```

---

# 7. Stage 08: Standard Output

Stage 08 applies fixed IFS-2020 Standard Output coefficients to reconstructed agricultural activities.

It measures **agricultural production-value exposure**. It is not farm profit, household income or welfare.

The runtime mapping is frozen in:

```text
08_IFS2020_Standard_Output_Mapping.xlsx
```

The mapping values livestock cohorts directly and selected crop-area variables while preventing double counting of aggregate livestock controls and physical grassland.

Stage 08 must not change pre-existing livestock, land, crop or farm-structure values.

---

# 8. Stage 09: frozen ED cohort signatures

Stage 09 is the final historical stage and the bridge into future livestock scenarios.

It freezes the relationship between the 2020 ED adult-cow structure and cattle follower cohorts. The signature table distinguishes:

```text
LOCAL_ED
COUNTY_RECEIVER
NATIONAL_ORPHAN
NONE
```

These are accounting relationships inferred from reconstructed livestock geography. They are not direct observations of animal movement.

The key scenario principle is to preserve ED heterogeneity rather than replace every ED with one national biological coefficient.

Conceptually, for follower cohort `c` and ED `j`:

```text
ED baseline signature
q_jc = baseline follower cohort / relevant baseline parent
```

A future adult-cow pathway changes the parent population. The frozen ED signature provides the first spatial estimate for the follower cohort. The resulting ED values are then reconciled to the required national GOBLIN cohort total while disturbing the historical spatial structure as little as possible.

Stage 09 belongs to the baseline package and does not import or run scenario code.

---

# 9. National scenario pathways

The principal spatial scenarios share the same **2020 baseline**. They differ in the national transition endpoint supplied to GOBLIN-Spatial.

The current principal pathways are:

| Pathway | 2050 dairy cows | 2050 suckler cows | Interpretation |
| --- | ---: | ---: | --- |
| `SI_SG` | 1,600,000 | 160,000 | Split-gas pathway with comparatively limited dairy contraction |
| `BE_SG` | 1,540,000 | 154,000 | Bioeconomy split-gas pathway with stronger alternative land demand |
| `ALL_GAS_NZ` | 875,000 | 87,500 | All-gas net-zero pathway with much deeper livestock contraction |

These are **national adult-cow endpoints**. They are not independently selected by each ED.

The scenario sequence is:

```text
national adult pathway
        |
        v
ED adult-cow allocation
        |
        v
ED-specific cohort propagation
        |
        v
national cohort reconciliation
        |
        v
spatial livestock transition
```

Spatial allocation rules may redistribute the burden of adjustment across EDs, but for a given pathway they must preserve the required national endpoint.

---

# 10. SC1: spatial livestock transition and destocking

SC1 answers:

> **Where could a nationally specified livestock reduction occur, and what does that imply for the complete ED livestock system?**

SC1 is not simply a proportional reduction of `TOTAL_CATTLE`.

The scenario first changes the adult control populations, principally dairy and suckler cows. The remaining cattle cohorts then respond through the biological and spatial relationships frozen in Stage 09.

## 10.1 Adult controls

For every scenario year:

```text
sum_ED DairyCow_ED,t   = DairyCow_GOBLIN,t
sum_ED SucklerCow_ED,t = SucklerCow_GOBLIN,t
```

Where national GOBLIN cohort targets are available or derived from GOBLIN biological relationships:

```text
sum_ED Cohort_c,ED,t = Cohort_c,GOBLIN,t
```

and for every ED:

```text
TOTAL_CATTLE_ED,t = sum(21 cattle cohorts)
```

## 10.2 Spatial cohort inheritance

The preferred spatial hierarchy is:

```text
LOCAL_ED signature
        |
        v
COUNTY receiver for follower cohorts without local parent support
        |
        v
NATIONAL fallback only for genuine county orphans
```

This prevents the scenario engine from homogenising all EDs with one national coefficient.

## 10.3 Destocking is spatial exposure, not a separate national scenario

Different spatial policies can be tested against the same national pathway. For example, a policy may place more adjustment in particular livestock structures or protect particular production concentrations. Such policies alter geography, not the national scenario total.

This separation makes it possible to compare:

```text
same national climate pathway
            +
different spatial allocation rule
            =
different local transition exposure
```

---

# 11. Gross potential land release

Livestock contraction creates a **potential gross release of grassland from livestock pressure**.

The national quantity is controlled by GOBLIN. GOBLIN-Spatial spatialises that national quantity across EDs.

```text
GOBLIN national gross release
            |
            v
spatial livestock-pressure change
            |
            v
ED gross PotentialRelease
```

The principal accounting rule is:

> **The national GOBLIN gross-release quantity is authoritative. A stocking-rate or feed-DM calculation can be used as a diagnostic spatial weight or sensitivity, but it does not replace the national land-release control.**

This distinction is essential because three concepts are different:

```text
PotentialRelease
!= Opportunity
!= RealisedConversion
```

- **PotentialRelease**: land potentially released from livestock pressure by SC1.
- **Opportunity**: the biophysical and land-use characteristics of that released land assessed in SC2.
- **RealisedConversion**: hectares actually allocated to an alternative use under SC3 constraints.

Potential release does not mean the land automatically changes use.

## 11.1 Current split-gas reference quantities

The current validated national accounting gives approximately:

```text
SI_SG gross livestock land release = 1.593 Mha
BE_SG gross livestock land release = 1.587 Mha
```

These values are deliberately similar. Their later residual land differs because the pathways assign very different amounts of released land to new uses.

For example:

```text
SI_SG
Gross release                     1.593 Mha
AD grass + additional forest      0.504 Mha
Residual available land           1.089 Mha

BE_SG
Gross release                     1.587 Mha
AD + biorefinery + willow
+ additional tillage + forest     1.184 Mha
Residual available land           0.403 Mha
```

Therefore **1.089 Mha and 0.403 Mha are residual available land, not gross livestock land release**.

Organic-soil rewetting is treated separately from that gross released-livestock-land closure where required by the scenario accounting.

---

# 12. 08B and 08C: independent soil representations

Soil enters **after** the livestock transition. Soil does not decide where animals are removed.

GOBLIN-Spatial intentionally retains two independent soil representations.

## 12.1 08B Cathal/NFS agricultural capability

The NFS-derived capability system groups source classes into:

```text
G1 = C1 + C2
G2 = C3 + C4
G3 = C5 + C6
```

For the 2020 national grassland-weighted reference, the current frozen layer gives approximately:

```text
G1  38.62%
G2  39.90%
G3  21.47%
```

G3 is **not synonymous with peat** and must not be interpreted as strictly organic soil.

## 12.2 08C Colm/IFS mapped physical soil

The physical-soil representation retains categories such as:

```text
deep well drained
shallow well drained
poorly drained
poorly drained peaty
alluvium
peat
miscellaneous
```

It is mapped to the broader G1/G2/G3 interpretation only where required for comparison. The physical-soil layer and the NFS capability layer remain separate and are not blended into one synthetic soil score.

## 12.3 Soil rule

```text
livestock transition first
        |
        v
potential released land
        |
        v
soil interpretation and opportunity screening
```

Soil informs what may be suitable after land is released. It does not alter the national livestock pathway or retroactively change animal allocation.

---

# 13. SC2: released-land opportunity characterisation

SC2 answers:

> **What is the released land like, and which alternative uses appear spatially plausible?**

SC2 does **not** rerun livestock adjustment and does not increase or reduce the hectares released by SC1.

Its purpose is to characterise the released-land pool using independent spatial evidence, including:

```text
08B agricultural capability
08C mapped physical soil
LPIS parcel/land-use information
ED geography
rural / mixed / urban context where required
other frozen opportunity indicators
```

The principal LPIS reference for the common-2020 scenario design is **LPIS 2020**. LPIS 2025 is retained as an optional later-year or sensitivity input rather than replacing the common 2020 scenario baseline.

Conceptually:

```text
SC1 PotentialRelease
        +
soil capability
        +
physical soil
        +
LPIS / land-use context
        +
spatial constraints
        |
        v
ReleasedLandOpportunity
```

SC2 can therefore identify differences between EDs that release similar areas but have very different alternative-use possibilities.

The model does not require every released hectare to have an alternative use.

---

# 14. Alternative land-use opportunities

The scenario engine evaluates several alternative land uses where they are explicitly required by a national pathway and where local conditions permit them.

The current principal set includes:

```text
AD_GRASS
BIOREFINERY
WILLOW
ADDITIONAL_TILLAGE
FOREST
REWETTING
```

These are not treated as interchangeable hectares. Each use has its own eligibility, capacity and allocation logic.

## Anaerobic-digestion grass

AD grass is an explicit national land-use target where required by the pathway. Spatial allocation is restricted to released land that satisfies the relevant eligibility and availability conditions.

## Biorefinery land

Biorefinery land is a pathway-specific bioeconomy demand. It is principally associated with the `BE_SG` scenario and competes with other eligible uses for released land.

## Willow

Willow represents an energy/bioeconomy land-use alternative. Allocation is constrained by the available released-land pool and spatial suitability rather than forced uniformly across EDs.

## Additional tillage

Additional tillage represents conversion toward extra cropland where the pathway requires it and the released land is compatible with the relevant opportunity rules.

## Forestry

Additional forest is allocated from eligible released land subject to the pathway target and spatial constraints. Soil capability and other available forest-opportunity information are interpretation or allocation inputs, not reasons to alter the preceding livestock scenario.

## Rewetting

Rewetting is constrained by drained organic-grassland availability. It is not equivalent to allocating all G3 land to rewetting.

The available organic stock is spatialised using the appropriate peat/cutover evidence and is further constrained by remaining land availability after non-overlapping allocations.

---

# 15. SC3: constrained alternative land-use allocation

SC3 answers:

> **Given the released land and its opportunity characteristics, how much of each national land-use target can actually be placed in space?**

SC3 is the feasibility and allocation stage.

It receives:

```text
SC1 released-land quantity
+
SC2 opportunity and eligibility evidence
+
explicit national land-use targets
```

and returns:

```text
RealisedConversion
UnmetTarget
ResidualAvailableLand
```

## 15.1 Stage A allocation

The current validated allocation reference treats the following as Stage A uses:

```text
AD_GRASS
BIOREFINERY
WILLOW
ADDITIONAL_TILLAGE
FOREST
```

Allocation uses hard eligibility constraints plus soft spatial scoring/optimisation. The objective is to meet the national target where feasible without violating the available released-land stock.

After Stage A:

```text
ParentAvailable = ReleasedLand - StageAAllocations
```

## 15.2 Stage B rewetting

Rewetting is then allocated against the remaining available land and the spatial stock of eligible drained organic grassland.

For every ED:

```text
Rewetting_ED <= RemainingAvailable_ED
Rewetting_ED <= EligibleOrganicCapacity_ED
```

Forced overlap with already allocated Stage A land is not permitted.

## 15.3 No forced infeasible hectares

A national target is a target, not permission to create land that does not exist.

```text
if target <= feasible capacity:
    target can be met
else:
    realise feasible capacity
    report unmet target explicitly
```

The model therefore reports spatial infeasibility rather than forcing hectares into unsuitable EDs.

---

# 16. Current pathway land-use targets

The current validated SC3 reference contains the following principal targets.

| Pathway | Rewetting | AD grass | Biorefinery | Willow | Additional tillage | Additional forest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `SI_SG` | 70 kha | 130 kha | 0 | 0 | 0 | 374 kha |
| `BE_SG` | 70 kha | 130 kha | 180 kha | 400 kha | 100 kha | 374 kha |
| `ALL_GAS_NZ` | 127 kha | 310 kha | 0 | 529.8 kha | 500 kha | 577 kha |

These values are national pathway controls. They are not ED-level quotas.

The spatial model asks whether, and where, they can be realised.

In the current ALL_GAS_NZ reference, the rewetting target is slightly above the feasible drained-organic-grassland capacity. That is treated as a valid model result: feasible hectares are realised and the remaining target is reported as unmet rather than forced into unsuitable land.

---

# 17. Land accounting and closure

The land accounting is deliberately explicit.

For a pathway:

```text
GrossPotentialRelease
        |
        +--> Stage A realised uses
        |
        +--> remaining available land
                     |
                     +--> eligible rewetting
                     |
                     +--> residual unallocated land
```

Important distinctions:

```text
Gross release != residual available land
Target != realised allocation
G3 != peat
Released land != automatically converted land
Opportunity != conversion
```

Where a scenario closes against the gross released-land pool:

```text
GrossPotentialRelease
=
Realised non-overlapping released-land uses
+
ResidualAvailableLand
```

Rewetting is accounted according to its explicit organic-land constraint and is kept separate where the national GOBLIN land-accounting design requires it.

---

# 18. Spatial foresight outputs

GOBLIN-Spatial is not only a downscaling model. The scenario chain is designed as a spatial stress test of plausible national agricultural transitions.

The full sequence allows the model to ask:

```text
Where is livestock adjustment concentrated?
Where is production-value exposure concentrated?
How much land could be released?
What is that released land like?
Which alternative uses are spatially compatible?
Where can national targets be realised?
Where are targets constrained by land capability or capacity?
Which EDs face high transition exposure but limited opportunity?
```

This supports an interpretive exposure-opportunity framing:

| Transition exposure | Alternative-use opportunity | Interpretation |
| --- | --- | --- |
| High | Stronger | Prepared transition potential |
| High | Limited | Priority transition constraint |
| Low or contingent | Stronger | Strategic opportunity |
| Low or contingent | Limited | Lower immediate priority / monitor |

These categories are foresight and policy-interpretation outputs. They do not change the underlying national pathway totals.

---

# 19. Data architecture

GOBLIN-Spatial uses a hybrid scientific-data strategy.

```text
GitHub
├── code
├── tests
├── configuration
├── manifest
├── compact historical inputs
└── compact scenario controls when activated

Zenodo
└── large frozen spatial inputs
```

## 19.1 Compact historical inputs in GitHub

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

The first eight production controls plus the DAFM county-sheep hold-out are checksum-verified against the frozen input release.

The published `05C_Cattle_Cohort_Relationships_2012_2020.csv` filename is retained for reproducibility even though the source contains GOBLIN sheep relationships used by Stage 05D as well as cattle relationships used by Stage 05C.

## 19.2 Compact scenario controls

The frozen bundle also contains compact scenario controls such as:

```text
SC1_Cattle_Scenario_Endpoints_2050.csv
SC1_ED_Rural_Mixed_Urban_2022.xlsx
```

These are intentionally kept outside the historical `run_baseline()` workflow. Their canonical GitHub activation belongs to the scenario refactor rather than the completed baseline migration.

## 19.3 Large Zenodo-backed spatial inputs

```text
08B_NFS_Agricultural_Soil_Capability.csv
08C_IFS_Mapped_Physical_Soil_Package.zip
SC2_LPIS_2020_Frozen.parquet
SC2_LPIS_2025_Frozen.parquet
SC2_ED_Boundaries_Frozen.gpkg
```

**Frozen data version DOI:** `10.5281/zenodo.22035538`

**Concept DOI:** `10.5281/zenodo.22035537`

`data_manifest.yaml` is the machine-readable authority for canonical paths, checksums and source roles.

Hosting location does not determine scientific ownership. A large soil file may be stored on Zenodo while still belonging scientifically to the downstream baseline-enrichment/scenario-preparation workflow.

---

# 20. Principal baseline outputs

The verified baseline writes:

```text
data/processed/
├── goblin_spatial_master_2015_2025.csv
├── GOBLIN_Spatial_Final_Clean_Data_2015_2025.xlsx
├── 08_GOBLIN_Spatial_Standard_Output_2015_2025.csv
├── 09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv
└── validation_summary.csv
```

Future scenario outputs will be generated rather than treated as model inputs. The intended scenario result families include:

```text
SC1 ED livestock pathway
SC1 ED cohort pathway
SC1 gross PotentialRelease
SC2 ReleasedLandOpportunity
SC2 soil / LPIS opportunity diagnostics
SC3 realised alternative land-use allocation
SC3 unmet national target
SC3 residual available land
scenario QA and closure tables
```

---

# 21. Validation rules

A refactored stage is not accepted because the code looks cleaner. It must preserve its scientific contract.

## Historical baseline gates

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
Stage 09 contains one unique row per ED x follower cohort
```

The current branch has passed:

```text
9 packaged baseline/validation files: SHA256 PASS
8 production-input migration equivalence checks: PASS
27 historical baseline unit/contract tests: PASS
complete Stage 01-09 regression: PASS
```

## Scenario gates

The scenario refactor must additionally enforce:

```text
national dairy endpoint exact
national suckler endpoint exact
national cohort controls exact where specified
ED cohort closure exact
national gross land release exact
no ED releases more land than permitted
SC2 does not change SC1 livestock or release totals
SC3 allocation <= eligible available land
no double allocation of the same hectare
realised + unmet = national target where applicable
unmet target reported rather than forced
soil systems remain independent
LPIS does not determine livestock reductions
```

The target migration workflow is:

```text
validated scientific reference
        |
        v
refactored module
        |
        v
same frozen inputs
        |
        v
output / closure comparison
        |
        v
PASS
        |
        v
module accepted
```

---

# 22. Interpretation boundaries

The following boundaries are fundamental to correct use of GOBLIN-Spatial:

- The 2020 CSO ED census is the fine-scale historical spatial anchor.
- Non-2020 ED values are reconstructed estimates rather than independent annual ED observations.
- AAA10 controls annual cattle totals at county level.
- Raw AAA09 detailed-region statistics control the production sheep hierarchy.
- DAFM breed information changes sheep composition, not population totals.
- Standard Output is production-value exposure, not income or profit.
- Stage 09 signatures are inferred accounting relationships, not observed animal movements.
- National GOBLIN scenario endpoints are authoritative.
- Spatial scenario policies alter geography, not the national pathway quantity.
- National GOBLIN gross land release is authoritative for principal scenario accounting.
- Stocking-rate/feed-derived land release is diagnostic or sensitivity evidence unless explicitly adopted as a separate scenario.
- Potential release is not opportunity.
- Opportunity is not realised conversion.
- Soil informs released-land interpretation after livestock transition; it does not determine animal allocation.
- The Cathal/NFS and Colm/IFS soil systems remain separate.
- G3 is not equivalent to peat.
- LPIS 2020 is the principal parcel reference for the common-2020 scenario framework; LPIS 2025 is optional/sensitivity context.
- National alternative land-use targets are never forced into EDs when spatial capacity is insufficient.

---

# 23. Developer usage

Install in editable mode:

```bash
pip install -e .
```

Run the verified historical reconstruction:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

The Python-level complete baseline entry point is:

```python
from goblin_spatial.pipeline import run_baseline

baseline = run_baseline("configs/ireland_2015_2025.yaml")
```

The final v1 user-facing scenario CLI will be simplified as SC1-SC3 are migrated. Until that refactor passes its own regression gates, scenario commands should not be interpreted as having the same verification status as the completed historical baseline.

---

# 24. Scientific design summary

GOBLIN-Spatial separates five questions that are often conflated:

```text
1. What is the historical agricultural system?
        -> Stages 01-09

2. How much national livestock adjustment is required?
        -> GOBLIN pathway

3. Where can that livestock adjustment occur?
        -> SC1

4. What opportunities exist on the potentially released land?
        -> 08B + 08C + SC2

5. Which alternative land-use targets can actually be realised?
        -> SC3
```

That separation is the core of the framework. Livestock adjustment is not inferred from soil. Land opportunity is not assumed from livestock reduction. National land targets are not automatically feasible. The model carries each constraint forward explicitly so that local transition exposure, opportunity and infeasibility remain visible.

---

# Citation

**Frozen model-input dataset:**

> Ofori, E. (2026). *GOBLIN-Spatial Frozen Model Inputs for Irish Electoral Division Agricultural and Land-Transition Modelling, Version 1.0.0* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.22035538

A software DOI will be added when the v1 software release is frozen.

Individual source datasets remain subject to their respective attribution and licensing terms.
