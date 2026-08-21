# GOBLIN-Spatial SC1 -> SC2 -> SC3 pipeline

This note is the current scenario contract for the v1 refactor. It separates the
validated historical ED baseline from future pathway analysis and preserves the
rule that national GOBLIN controls quantities while GOBLIN-Spatial resolves
spatial incidence, opportunity and feasibility.

## Run selection

Every run starts with two independent choices:

1. `SCENARIO_ID` from `data/controls/scenario/GOBLIN_Scenario_Controls.csv`.
2. `RUN_START_YEAR`, either 2020 or 2025.

The scenario table does not contain a fixed baseline-land total. The runner first
selects the 2,857 ED rows for the requested baseline year and calculates the
national starting grassland from the actual baseline `ALL_GRASSLAND` values.

For run r:

```text
BaselineGrassland(r) = sum_ed ALL_GRASSLAND(ed, RUN_START_YEAR)
RunGrossRelease(r)   = BaselineGrassland(r) - TARGET_LIVESTOCK_LAND_HA(SCENARIO_ID)
```

Changing the run start year therefore changes the baseline state and the implied
run release while leaving the national 2050 endpoint definition unchanged.

The control table is data-driven. `SCENARIO_NO`, `SCENARIO_ID`, `SCENARIO_NAME`,
`ACTIVE` and endpoint values can be edited without hard-coding pathway names in
the runner. Only `ACTIVE` rows are selectable.

## SC1: cattle transition, exposure and released land

SC1 is the complete pre-opportunity transition stage. It is not only an adult-cow
reduction.

```text
selected 2020/2025 ED baseline
        +
selected national scenario endpoint
        |
        v
adult-cattle spatial allocation
        |
        v
exact national dairy:suckler composition
        |
        v
Stage 09 ED cohort signatures
LOCAL_ED / COUNTY_RECEIVER / NATIONAL_ORPHAN
        |
        v
complete 21-cohort cattle endpoint
        |
        +--> sheep copied unchanged
        |
        v
fixed-2020 Standard Output exposure
        |
        v
SC1 distributional diagnostics
        |
        v
GOBLIN pasture-DM pressure change
        |
        v
ED released grassland with exact national closure
        |
        v
FREEZE SC1
```

### SC1A adult cattle endpoint

The principal endpoint allocates the total adult-cow contraction across the
existing ED footprint. The requested national dairy and suckler counts are then
reconciled exactly. Allocation rules change where the contraction falls, not the
national endpoint.

No adult cattle are silently seeded into an unsupported spatial footprint.
Protection rules alter relative cut intensity and do not change national totals.

### SC1B 21-cohort cattle state

The selected baseline-year ED signatures control the follower response:

```text
DxD -> DAIRY
DxB -> DAIRY
BxB -> SUCKLER
bulls -> ADULT_COWS
```

For each ED x follower relationship the response source is:

```text
LOCAL_ED
COUNTY_RECEIVER
NATIONAL_ORPHAN
NONE
```

The 18 pre-adult cohorts remain publication-facing audit relationships. Bulls are
the nineteenth follower and complete the 21-cohort cattle state with dairy and
suckler adults.

National GOBLIN/COHORTS margins remain authoritative when supplied. ED signatures
determine geography, not national biology.

### SC1C Standard Output exposure

Standard Output is applied only after the physical cattle endpoint is solved.
Fixed 2020 coefficients are used for baseline and scenario states so the result is
production-value exposure rather than price drift.

Core outputs include:

```text
BASE_SO_LIVESTOCK_2020_EUR
SCENARIO_SO_LIVESTOCK_2020_EUR
SO_LIVESTOCK_CHANGE_2020_EUR
SO_LIVESTOCK_EXPOSURE_2020_EUR
SO_LIVESTOCK_CHANGE_PCT
```

SO is not profit, farm income or welfare.

### SC1D distributional metrics

SC1 reporting now includes a separate distributional module. These quantities are
diagnostics only and never feed back into livestock allocation.

The national report includes:

```text
GINI_BASE_SO_LIVESTOCK
GINI_SCENARIO_SO_LIVESTOCK
DELTA_GINI_SO_LIVESTOCK
GINI_SO_LOSS
GINI_TOTAL_CATTLE_REDUCTION
GINI_ADULT_CATTLE_REDUCTION
GINI_RELEASED_GRASSLAND
TOP_10PCT_ED_SHARE_*
TOP_20PCT_ED_SHARE_*
EDS_FOR_50PCT_*
EDS_FOR_80PCT_*
```

Because an ED may in principle gain SO after cattle-composition change, signed SO
exposure is split transparently into positive gross loss and gross gain before a
loss-distribution Gini is calculated.

ED reporting also includes, where inputs exist:

```text
SO_LIVESTOCK_GROSS_LOSS_PER_HOLDING_2020_EUR
TOTAL_CATTLE_REDUCTION_PER_HOLDING
GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE
```

County summaries aggregate the physical and SO incidence and report each county's
share of national loss, cattle reduction and released grassland.

### SC1E GOBLIN land release

The national gross release used by a run is derived from the selected baseline ED
land and the scenario endpoint land control. The released hectares are then
spatialised using cattle pasture-DM pressure change while respecting each ED's
`ALL_GRASSLAND` capacity.

Soil and LPIS do not alter this solved geography.

The SC1 handoff is therefore:

```text
ED cattle endpoint
+ unchanged sheep context
+ SO exposure
+ distribution metrics
+ frozen ED released grassland
```

## Freeze boundary

Once SC1 closes nationally, the following may not be changed downstream:

```text
SCENARIO_DAIRY_COW
SCENARIO_OTHER_COW
all 21 cattle cohort counts
SC1 Standard Output exposure
GOBLIN_RELEASED_GRASSLAND_HA
```

Soil and LPIS can interpret or constrain the use of released land. They cannot
move cattle reductions or released hectares between EDs.

## 08B: agricultural soil capability

08B is the principal agricultural capability layer.

```text
C1 + C2 -> G1
C3 + C4 -> G2
C5 + C6 -> G3
```

`fsizuaa` is a source weighting denominator only. It never replaces
`ALL_GRASSLAND`.

After SC1 release is frozen, 08B partitions/interprets the released-land context
inside each ED. The ED row total must remain exactly the SC1 released hectares.

## 08C: physical soil context

08C is a separate physical-soil evidence layer and must not be blended into 08B
as if both represented the same denominator.

It retains physical categories such as well-drained, poorly drained, peaty and
peat context. In particular:

```text
G3 != peat
mapped peat != farmed peat
mapped peat != automatically rewettable grassland
```

The 08C integration must be frozen before its fields are allowed to affect SC2
eligibility.

## LPIS

LPIS is matched to the selected run baseline:

```text
2020 run -> validated 2020 LPIS control
2025 run -> validated 2025 LPIS control
```

LPIS does not replace `ALL_GRASSLAND` and does not identify the exact parcel from
which cattle were removed. It supplies a parcel-informed opportunity/capacity
envelope inside the already solved ED release.

## SC2: policy-neutral opportunity

SC2 starts only after the SC1 row totals are frozen.

```text
SC1 released land
+ 08B agricultural capability
+ 08C physical soil context
+ selected-year LPIS
        |
        v
land-use-specific overlapping opportunity envelopes
```

The required land-use opportunities are:

```text
AD_GRASS
BIOREFINERY_GRASS
WILLOW
ADDITIONAL_TILLAGE
FOREST
REWETTING
```

SC2 is not a final allocation. The same hectare may initially be eligible for
multiple uses, so opportunity hectares must never be summed across uses.

The old generic 0.85/0.80/0.70 soil weighting is not to be treated as a frozen
SC2 allocation rule. Its scientific meaning must be revalidated before the v1
SC2 screen is frozen.

## SC3: explicit national target allocation

SC3 reads the editable national land-use targets from the same scenario row and
places them only within SC2 eligible capacity.

Stage A released-land uses are:

```text
AD_GRASS
BIOREFINERY_GRASS
WILLOW
ADDITIONAL_TILLAGE
FOREST
```

For every ED:

```text
sum(Stage-A realised conversion) <= frozen SC1 released land
```

A hectare can be eligible for several uses in SC2 but can be realised only once
in SC3.

Rewetting remains a separate organic-soil control. It is tested after Stage A
against remaining eligible organic agricultural land so physical conversion is
not double counted. The source-model pre-rewetting Available balance and the
final post-rewetting residual must therefore be reported as distinct quantities.

For each land use k:

```text
RealisedConversion(k) <= NationalTarget(k)
UnmetTarget(k) = NationalTarget(k) - RealisedConversion(k)
```

No unsuitable hectares are forced merely to close a national target.

Final accounting reports at least:

```text
StageAAvailableLand
RealisedConversion
UnmetTarget
ResidualAvailableLand
```

and preserves:

```text
PotentialRelease != Opportunity != RealisedConversion
GrossRelease != ResidualAvailableLand
```

## Current implementation gate

The editable scenario-control loader and the expanded SC1 distributional outputs
are now the first v1-refactor implementation step. The generic runner deliberately
stops after SC1 for these new controls.

SC2/SC3 should only be enabled after all of the following are validated together:

1. 08B released-land partition closure.
2. 08C physical-soil attachment and terminology.
3. selected-year LPIS control closure.
4. land-use-specific SC2 eligibility/ranking rules.
5. absolute-target SC3 allocation with mutually exclusive realised hectares,
   separate rewetting handling, unmet targets and final residual accounting.

This gate is deliberate. It prevents the older Styles opportunity weights from
silently becoming the final v1 science.

## Compute-budget guardrail

Scenario development should be validated with small unit/contract tests first.
GitHub Actions should be reserved for a single meaningful checkpoint or PR run,
not triggered after every small scenario edit. The current main CI remains focused
on the frozen historical baseline while the scenario branch is developed.
