# GOBLIN-Spatial principal scenario architecture

## 1. Governing model boundary

GOBLIN-Spatial does not create a competing national future. It spatialises a national GOBLIN pathway while preserving the national quantities supplied by that pathway.

> **GOBLIN establishes the national livestock and land-use transition. GOBLIN-Spatial resolves its geography.**

The supported production chain is:

```text
Historical Stages 01-09
        -> validated ED baseline
        -> repository-contained 2020 land-context bundle
        -> SC1 livestock incidence and released-land geography
        -> SC2 opportunity and physical eligibility
        -> SC3 feasible land-use allocation
```

The principal spatial baseline is 2020. A 2025 livestock state may be used for SC1 sensitivity analysis, but LPIS-dependent 2025 SC2/SC3 are blocked until a separately validated compact 2025 spatial context is frozen.

## 2. Repository-contained 2020 spatial evidence

Normal runtime uses:

`data/controls/land/ED_Land_Context_2020/`

with three authoritative compact files:

```text
ED_Soil_Capability_08B.csv
ED_Physical_Soil_08C.csv
ED_LPIS_Context_2020_RUNTIME.csv
```

All three cover the same 2,857 model EDs. The runtime verifies their frozen SHA256 values and joins only the required columns in memory. The result is the validated 40-field logical context used by SC1 and SC2.

The three layers remain scientifically distinct.

### 2.1 08B agricultural capability

08B contains Class 1-6 shares, G1/G2/G3 shares, forest yield-class context and peat/cutover context. It is the agricultural-capability layer used in the SC1 released-land capacity solve and downstream capability interpretation.

Validated provenance is preserved exactly:

```text
2,820 direct ED profiles
37 county-fallback profiles
```

The required mapping is:

```text
Class1 + Class2 = G1
Class3 + Class4 = G2
Class5 + Class6 = G3
```

Runtime does not re-run the original source-resolution hierarchy.

### 2.2 08C independent mapped physical soil

08C is independent physical-soil context used only after SC1 is frozen. It does not alter livestock allocation or released-land hectares and is not blended into 08B.

Mapped peat is not automatically farmed peat and is not automatically rewettable land.

### 2.3 LPIS 2020 context

LPIS 2020 is a neutral evidence/context layer used in SC2. It was recovered from mature 2020 SC2 results and cross-validated between SI_SG and BE_SG across all four allocation policies.

LPIS does not replace `ALL_GRASSLAND`, allocate livestock, generate released land or directly choose realised SC3 hectares.

## 3. SC1: national livestock endpoint to ED livestock geography

### 3.1 National authority

The editable scenario control supplies the national pathway endpoint. The production runner does not accept a second generic fractional-reduction scenario definition.

Adult dairy and suckler cows are the primary livestock controls. Where national total-cattle or exact 21-cohort targets are supplied, those margins remain authoritative. Where only adult endpoints are supplied, the frozen GOBLIN/COHORTS reference derives the national follower-cohort margins.

### 3.2 Adult incidence policies

The supported incidence policies are:

```text
PRORATA
DAIRY_PROTECTION
ECONOMIC_CAPACITY_PROTECTION
SOCIAL_VULNERABILITY_PROTECTION
```

Protection redistributes a fixed national contraction. It does not reduce the required national adjustment. Category expansion remains proportional and cannot seed a new adult-category ED footprint.

The historical identifier `ECONOMIC_CAPACITY_PROTECTION` is retained for reproducibility. Operationally, the policy protects EDs with lower inferred economic capacity and therefore greater vulnerability under the fixed-2020 production-value indicators.

### 3.3 ED cattle cohort response

The cattle state contains 21 cohorts. Dairy-origin followers use dairy cows as their parent signal, beef-origin followers use suckler cows, and bulls use the combined adult-cow signal.

The baseline determines each follower cohort's dependency class:

```text
LOCAL_ED
COUNTY_RECEIVER
NATIONAL_ORPHAN
NONE
```

This preserves ED-specific cohort fingerprints rather than replacing them with one national coefficient. Receiver relationships are accounting dependencies, not claims about observed animal movements.

Exact national cohort margins are reconciled without creating a cohort in an ED where it was absent at baseline.

### 3.4 Sheep

The principal transition is cattle focused. Sheep are fixed unless an explicit national sheep control is introduced. A numerical zero elsewhere in a pathway table is not interpreted as a sheep-removal instruction.

### 3.5 Standard Output

Standard Output is appended after the physical livestock state is solved. It is fixed-2020 livestock production-value exposure, not income, profit, welfare or compensation, and it never changes the livestock solution.

## 4. SC1 released-land geography

### 4.1 National released land is authoritative

For the selected baseline:

```text
Gross livestock-land release
    = selected baseline ALL_GRASSLAND
    - pathway TARGET_LIVESTOCK_LAND_HA
```

GOBLIN-Spatial does not replace this national quantity with an independently calculated local pasture-DM spared-land total.

### 4.2 Role of pasture dry matter

The 31-cohort pasture-DM control provides the spatial livestock-pressure signal and an independent land-requirement diagnostic. It does not become a second national land authority.

All pathways use the same spatialisation method. Dairy, beef and sheep pressure contributions are derived from the solved livestock states and rescaled to the authoritative national gross release.

### 4.3 08B capacity constraint

Released land must remain within each ED's `ALL_GRASSLAND` capacity and its frozen G1/G2/G3 agricultural-capability composition.

08C and LPIS do not enter this SC1 solve.

## 5. SC2: released land to opportunity and eligibility

SC2 starts only after SC1 is frozen. It cannot recompute livestock or change any SC1 released-land hectare.

SC2 combines:

```text
frozen SC1 release
+ 08B capability
+ LPIS 2020 context
+ independent 08C physical soil
```

The central interpretation rule is:

```text
PotentialRelease != Opportunity != RealisedConversion
```

Potential release is the spatial land budget associated with the national livestock pathway. Opportunity describes compatibility with alternative uses. Neither is a forecast of actual land conversion.

## 6. SC3: explicit national targets to feasible ED allocations

SC3 receives its land-use targets from the same editable national pathway control. The allocator never invents hectares.

Current uses are:

```text
AD grass
biorefinery grass
willow
additional tillage
additional forest
rewetting
```

The main Stage-A uses are allocated jointly subject to ED released-land budgets, use-specific eligibility and shared physical pools. The optimisation first minimises total unmet target hectares and then, conditional on that minimum, favours higher opportunity scores.

If a national target is infeasible, the unmet hectares are reported rather than forced into an unsuitable ED.

### 6.1 Rewetting accounting

Rewetting is handled after Stage A. Its capacity is constrained by the post-Stage-A residual and the anchored drained-organic-grassland stock.

Two quantities remain distinct:

- **GOBLIN parent Available land**: released land left after the principal new-use targets before the rewetting overlay;
- **strict residual available land**: land remaining after realised rewetting in the exclusive spatial accounting.

The second quantity must not be presented as if it were the source pathway's original `Available` category.

## 7. Pathway consistency

A run is one internally consistent package. Livestock endpoints, livestock-land targets, alternative-use targets and reconciliation outputs must all come from the same pathway identifier.

```text
SI_SG       -> SI_SG controls throughout
BE_SG       -> BE_SG controls throughout
ALL_GAS_NZ  -> ALL_GAS_NZ controls throughout
```

The current scenario CSV is the runtime authority.

## 8. Reproducibility boundary

A normal 2020 run is repository-contained. It requires no external spatial source and must not automatically:

```text
download LPIS parcels
download soil packages
fetch ED geometry
run GIS intersections
rebuild the compact 2020 land controls
```

Those operations belong only to explicit first-principles reconstruction workflows. External reconstruction must be deliberately requested and heavy GitHub Actions are manual-only.

## 9. Strategic-foresight interpretation

GOBLIN-Spatial is not a parcel-level land-use forecast and does not predict individual farm adoption.

Its purpose is to identify:

- EDs with robust livestock-transition exposure across plausible pathways;
- EDs whose exposure depends strongly on the incidence rule;
- locations where released-land geography aligns with alternative-use opportunity;
- locations where national land-use targets encounter spatial constraints; and
- areas where high adjustment exposure and weak opportunity indicate a need for earlier transition preparation.

## 10. Supported commands

Repository-only input verification:

```bash
goblin-spatial fetch-data --verify-only
```

Historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Principal scenarios:

```bash
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC1
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC2
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC3
```

Optional first-principles reconstruction is separate and explicit:

```bash
goblin-spatial fetch-data --include-reconstruction-sources
goblin-spatial-lpis ...
```

These reconstruction commands are not invoked by the principal runtime.
