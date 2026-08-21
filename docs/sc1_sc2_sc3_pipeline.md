# GOBLIN-Spatial SC1 -> SC2 -> SC3 pipeline

This document is the current scientific contract for the v1 scenario refactor. The historical Stage 01-09 baseline is already verified and frozen. Scenario code must preserve the rule that national GOBLIN controls quantities while GOBLIN-Spatial resolves spatial incidence, opportunity and feasibility.

## Run selection

Every run starts with:

1. a `SCENARIO_ID` from `data/controls/scenario/GOBLIN_Scenario_Controls.csv`;
2. a `RUN_START_YEAR`, either 2020 or 2025; and
3. one principal spatial allocation policy.

The scenario table does not contain a fixed baseline-land total. The selected ED state supplies the starting grassland:

```text
BaselineGrassland(r) = sum_ed ALL_GRASSLAND(ed, RUN_START_YEAR)
RunGrossRelease(r)   = BaselineGrassland(r) - TARGET_LIVESTOCK_LAND_HA(SCENARIO_ID)
```

The editable control table remains the authority for current cattle endpoints and future land-use targets. Older standalone scenario scripts are scientific references for mathematics only and must not overwrite the current control CSV.

## SC1: livestock transition, exposure and released land

SC1 is the complete pre-opportunity stage:

```text
selected 2020/2025 Stage-08 ED baseline
        +
selected national scenario endpoint
        |
        v
adult-cattle spatial allocation
        |
        v
exact national dairy:suckler endpoint
        |
        v
Stage-09 ED cohort signatures
LOCAL_ED / COUNTY_RECEIVER / NATIONAL_ORPHAN / NONE
        |
        v
complete 21-cattle-cohort endpoint
        |
        +--> sheep carried unchanged
        |
        v
fixed-2020 Standard Output exposure
        |
        v
SC1 distributional / foresight diagnostics
        |
        v
national livestock-land release control
        +
solved livestock pasture-DM spatial propensity
        +
08B G1/G2/G3 ED capacity
        |
        v
GOBLIN_RELEASED_G1_HA + G2 + G3
        |
        v
frozen GOBLIN_RELEASED_GRASSLAND_HA
```

### Adult allocation

Principal policies redistribute a common national endpoint rather than changing it. No category is seeded into an unsupported ED footprint. Where a category expands, expansion remains PRORATA within the existing category footprint.

### Cohort propagation

The selected baseline-year Stage-09 signatures preserve ED heterogeneity while national GOBLIN/COHORTS margins remain authoritative when supplied.

```text
DxD -> DAIRY
DxB -> DAIRY
BxB -> SUCKLER
bulls -> ADULT_COWS
```

The local/county/national signature hierarchy is an accounting/propagation mechanism, not evidence of observed animal movement.

### Standard Output and distributional metrics

Standard Output is calculated after the physical cattle state is solved, using fixed-2020 coefficients. It is production-value exposure, not farm income, profit or welfare.

Gini, top-share, ED concentration, county incidence, protection relief, displaced burden, pathway sensitivity, allocation sensitivity and robust-exposure metrics are reporting diagnostics only. They never feed back into livestock or land allocation.

### Released land

The national gross release is externally/pathway controlled. GOBLIN-Spatial spatialises it. Pasture-DM change supplies a biological/spatial signal. The precomputed 08B capability layer supplies G1/G2/G3 physical capacity cells. The resulting G1/G2/G3 released hectares must close exactly to each ED's frozen total release and may never exceed validated `ALL_GRASSLAND`.

08C mapped physical soil and LPIS do not move SC1 release.

## SC1 freeze boundary

After SC1 national and ED closure, downstream stages may not change:

```text
SCENARIO_DAIRY_COW
SCENARIO_OTHER_COW
all 21 cattle cohort counts
SC1 Standard Output exposure
GOBLIN_RELEASED_G1_HA
GOBLIN_RELEASED_G2_HA
GOBLIN_RELEASED_G3_HA
GOBLIN_RELEASED_GRASSLAND_HA
```

## 08B: agricultural capability

08B is the principal agricultural capability representation:

```text
C1 + C2 -> G1
C3 + C4 -> G2
C5 + C6 -> G3
```

`fsizuaa` is a source weighting denominator only. It does not replace `ALL_GRASSLAND`.

The compact 08B profile is prepared once. Normal scenario runs attach it and do not reopen the heavy source. The same compact profile supports SC1 G-group capacity and SC2 Class1-6 reconstruction.

## 08C: independent mapped physical soil

08C is a second soil representation and is not blended with 08B. It retains mapped physical composition, drainage and peat context.

```text
G3 != peat
mapped peat != farmed peat
mapped peat != automatically rewettable grassland
```

08C mapped shares are not multiplied by `ALL_GRASSLAND` to manufacture an observed grassland-by-soil map. Their role is physical context and dual-soil robustness evidence.

## LPIS

LPIS is matched to the observed scenario start year:

```text
2020 run -> corrected 2020 LPIS v2
2025 run -> validated 2025 LPIS v1
```

LPIS is parcel-informed context, not the controlling ED grassland total and not identification of the exact parcel from which livestock was removed.

Normal runtime consumes the compact dual-year ED profile only. The multi-GB parcel overlay is a one-time preprocessing operation and must never be triggered automatically by SC1-SC3.

## SC2: mature v3.1 opportunity and physical eligibility

SC2 begins only after SC1 release is frozen:

```text
frozen SC1 release including G1/G2/G3
        +
matched-year compact LPIS
        +
independent compact 08C
        |
        v
Opportunity-v2 scores
        |
        v
released Class1-6 reconstruction
        |
        v
organic / mineral quantities
        |
        v
SC3 physical eligibility envelopes
```

The package implementation is `src/goblin_spatial/land/sc2_opportunity.py`, wired through `src/goblin_spatial/land/sc2_context.py`.

### Required release closure

For every ED:

```text
RELEASED_CLASS_1_HA + RELEASED_CLASS_2_HA = GOBLIN_RELEASED_G1_HA
RELEASED_CLASS_3_HA + RELEASED_CLASS_4_HA = GOBLIN_RELEASED_G2_HA
RELEASED_CLASS_5_HA + RELEASED_CLASS_6_HA = GOBLIN_RELEASED_G3_HA
sum(RELEASED_CLASS_1_HA ... RELEASED_CLASS_6_HA)
    = GOBLIN_RELEASED_GRASSLAND_HA
```

SC2 may append interpretation and capacity fields only. It may not alter any pre-existing SC1 field.

### Mature productivity weighting

The recovered SC2 v3.1 Opportunity-v2 science uses:

```text
GOBLIN_SOIL_PRODUCTIVITY_INDEX
= 0.85*G1 + 0.80*G2 + 0.70*G3
```

This is retained as an opportunity/productivity indicator. It is not a released-land generator and must never be used to divide already-released hectares.

### Opportunity versus physical capacity

Opportunity scores and physical eligibility remain distinct. The same hectare may appear in several overlapping SC2 eligibility envelopes, so SC2 hectares must not be added across land uses.

Principal SC3-ready envelopes are:

```text
AD / biorefinery grass : Classes 1-4 mineral
Willow                  : Classes 1-3 mineral
Additional tillage      : Classes 1-3 mineral
Forest                  : Classes 1-5 mineral
Rewetting signal        : organic released-land context
```

Strict tillage (Classes 1-2) and wide willow (Classes 1-4) remain explicit sensitivity variants.

## SC3: mature v2.7 explicit target allocation

SC3 reads the same selected scenario row's explicit national land-use targets. The allocator contains no pathway-specific target table.

### Stage A: joint LP

Five released-land uses are solved jointly:

```text
AD_GRASS
BIOREFINERY_GRASS
WILLOW
ADDITIONAL_TILLAGE
FOREST
```

The principal allocator is a lexicographic continuous linear program:

1. minimise total unmet target hectares;
2. hold the minimum unmet total fixed and maximise opportunity ranking.

Stage-2 scores are target-normalised so a larger national target does not dominate the soft objective merely because it contains more hectares.

Hard individual SC2 capacities are supplemented by shared physical pools. These nested pools prevent overlapping eligibility envelopes from double-using the same released capability. Forest additionally requires finite positive `FOREST_YC_WEIGHTED_MEAN` in the principal specification.

There is no arbitrary sequential Stage-A priority. The old sequential API is explicitly rejected by the v2.7 package allocator.

### Stage B: sequential rewetting

Rewetting occurs only after Stage A.

The principal national drained-organic-grassland stock anchor is 141,000 ha. It is spatialised by:

```text
ALL_GRASSLAND * IFS_PEAT_CUTOVER_UAA_SHARE
```

then normalised to the national stock and intersected with the frozen SC1 released-land geography. After Stage A, that capacity is tightened again to the actual remaining ED Available land. Rewetting is then allocated only inside this post-Stage-A feasible capacity.

This ordering prevents physical double assignment.

`RELEASED_ORGANIC_WEIGHT_HA` remains an unscaled SC2 diagnostic/spatial signal. Colm/IFS mapped peat remains independent context and does not manufacture the 141 kha stock.

### SC3 accounting

For every use `k`:

```text
RealisedConversion(k) <= NationalTarget(k)
UnmetTarget(k) = NationalTarget(k) - RealisedConversion(k)
```

For every ED:

```text
StageARealised
+ RewettingRealised
+ ResidualAvailableLand
= FrozenSC1Release
```

The parent-GOBLIN source `Available` balancing item is retained as source accounting. SC3 separately reports the physically uncommitted residual after rewetting.

No eligibility is silently broadened to force a target to close.

## Principal runtime

`goblin-spatial-principal` now supports:

```text
--stage SC1
--stage SC2
--stage SC3
```

`SC3` runs the full light-weight chain from the selected Stage-08 baseline through SC1 and mature SC2 before invoking the v2.7 allocator. The runtime uses compact 08B, LPIS and 08C controls only and never initiates heavy source processing.

SciPy is an optional `scenario` dependency so the verified historical baseline does not acquire an optimisation dependency merely because SC3 exists.

## Validation gate

The scenario package has lightweight deterministic contract tests for:

- exact adult/category and 21-cohort closure;
- unchanged sheep context;
- SC1 release closure and capacity constraints;
- SC2 G1/G2/G3 and Class1-6 closure;
- mature 0.85/0.80/0.70 Opportunity-v2 compatibility;
- dual-soil no-blend behavior;
- Stage-A shared-pool non-double-use;
- explicit unmet targets;
- forest-YC hard eligibility;
- sequential rewetting constrained to post-Stage-A Available; and
- final ED/national SC3 closure.

These tests existing in the branch does not mean the integrated scenario refactor is already regression-verified. Full acceptance requires the real compact controls and one deliberate integrated validation run.

## Compute-budget guardrail

Compute cost is a hard implementation constraint.

Use this order:

```text
source/code inspection
-> tiny deterministic tests
-> no-download preflight
-> compact-control validation
-> one meaningful integrated validation
-> CI only at a deliberate acceptance checkpoint
```

The preflight checks compact Stage-08, scenario, 08B, LPIS and 08C inputs without downloading, rebuilding or spatially intersecting anything.

Do not open the scenario PR yet. The LPIS rebuild workflow watches configuration/LPIS-related paths on pull requests and can trigger expensive processing. Recover/reuse existing compact controls before considering any heavy rebuild.