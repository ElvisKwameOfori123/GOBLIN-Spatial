# GOBLIN-Spatial principal scenario architecture

## 1. Model boundary

GOBLIN-Spatial does not generate an alternative national future. It spatialises a national GOBLIN pathway while preserving the national quantities supplied by that pathway.

The governing contract is:

> **GOBLIN establishes the national livestock and land-use transition. GOBLIN-Spatial resolves its geography.**

This separates four questions that should not be conflated:

1. What national livestock endpoint is being studied?
2. Where does the required livestock adjustment occur?
3. Where is the associated national released-land total represented spatially?
4. Which parts of that released-land geography are compatible with explicit alternative land-use targets?

The production sequence is therefore:

```text
Historical Stages 01-09
        -> validated ED baseline
        -> frozen ED_Land_Context_2020
        -> SC1 livestock incidence and released-land geography
        -> SC2 opportunity and physical eligibility
        -> SC3 feasible land-use allocation
```

The principal spatial baseline is 2020. A 2025 ED livestock state may be used for SC1 sensitivity analysis, but LPIS-dependent SC2/SC3 are disabled until a separately validated 2025 land-context control is available.

## 2. Historical state and fixed spatial evidence

The historical reconstruction contains 2,857 EDs and preserves the livestock, land, farm-structure and Standard Output variables required by the scenario analysis. Stage 09 provides the ED-specific cattle cohort structure used to propagate national endpoints spatially.

The principal scenario runtime uses one repository-contained 2020 spatial control:

`data/controls/land/ED_Land_Context_2020`

Its final contract is 2,857 EDs by 40 neutral fields. It carries three evidence layers in one reproducible storage object:

- **08B agricultural capability**, used in SC1 released-land spatialisation;
- **08C mapped physical soil**, used downstream as independent physical evidence;
- **LPIS 2020 context**, used downstream for opportunity and eligibility.

These layers are not blended into one soil concept. Shared storage is an engineering decision, not a scientific merger.

The 08B final model-ED control preserves the validated provenance hierarchy of 2,820 direct ED profiles and 37 county fallbacks. Runtime attachment does not re-run that hierarchy.

## 3. SC1: national livestock endpoint to ED livestock geography

### 3.1 National authority

The editable scenario table supplies absolute national controls for the selected pathway. The production runner does not accept a second generic fractional-reduction scenario definition.

Adult dairy and suckler cows are the primary national livestock controls. A pathway may expand one adult category while contracting the other, provided the overall endpoint is internally feasible.

Where national total-cattle or exact 21-cohort targets are supplied, they remain authoritative. Where only adult endpoints are supplied, the frozen GOBLIN/COHORTS relationship reference is used to derive national follower-cohort margins.

### 3.2 Adult incidence policies

The supported SC1 incidence policies are:

- `PRORATA`
- `DAIRY_PROTECTION`
- `ECONOMIC_CAPACITY_PROTECTION`
- `SOCIAL_VULNERABILITY_PROTECTION`

The historical identifier `ECONOMIC_CAPACITY_PROTECTION` is retained for reproducibility. Operationally, the score protects EDs with lower economic capacity, meaning greater inferred vulnerability under the fixed-2020 Standard Output exposure indicators.

Protection changes **where** a fixed national contraction lands. It does not reduce the national contraction. Category expansion remains proportional and cannot seed a new ED footprint.

### 3.3 ED-specific cattle cohort response

The cattle state contains 21 cohorts. Dairy-origin follower cohorts use dairy cows as their parent signal, beef-origin follower cohorts use suckler cows, and bulls use the combined adult-cow signal.

For each follower cohort, the baseline determines its spatial relationship to the relevant parent population. The hierarchy is:

1. `LOCAL_ED` when the ED contains both the cohort and its parent adults;
2. `COUNTY_RECEIVER` when the cohort is present but its parent adults are elsewhere in the county;
3. `NATIONAL_ORPHAN` only when no relevant parent adults exist in the county;
4. `NONE` when the cohort is absent.

This preserves ED-specific cohort fingerprints rather than replacing them with a national average coefficient. Receiver relationships are accounting dependencies, not claims about observed animal movements.

When exact national cohort margins are imposed, reconciliation changes the minimum necessary ED counts while respecting the existing cohort footprint. A positive target cannot create a cohort in an ED where that cohort was absent at baseline.

### 3.4 Sheep

The principal transition is cattle focused. Sheep are carried unchanged unless an explicit national sheep control is introduced. A numerical zero in an unrelated scenario table field is not interpreted as a command to remove sheep.

### 3.5 Standard Output

Standard Output is appended after the physical livestock state is solved. It is a fixed-2020 livestock production-value exposure measure. It is not farm income, profit, welfare, compensation or a behavioural response variable, and it never changes the national or ED livestock solution.

## 4. SC1 released-land geography

### 4.1 National released land is authoritative

The national gross released-land total comes from GOBLIN land accounting. For a selected baseline run:

```text
Gross livestock-land release
    = selected baseline ALL_GRASSLAND
    - pathway TARGET_LIVESTOCK_LAND_HA
```

GOBLIN-Spatial does not replace that national quantity with an independently calculated pasture-DM spared-land total.

### 4.2 Role of pasture dry matter

The 31-cohort pasture-DM control remains useful for spatial pressure accounting. Cohort-specific changes in pasture demand identify where livestock pressure falls most strongly. This signal is used to distribute the externally controlled national release across EDs.

The independently implied grassland requirement remains a diagnostic. It can reveal tension between the national land control and the livestock/feed state, but it is not a second national land authority.

### 4.3 Symmetric pathway treatment

All pathways use the same release-spatialisation method. Dairy, beef and sheep pressure contributions are derived from the solved baseline/scenario pasture-DM states and rescaled to the authoritative national gross release.

No SI_SG or BE_SG pathway receives a special hard-coded system-land allocation inside the spatial engine.

### 4.4 08B capacity constraint

Released land is represented within each ED's `ALL_GRASSLAND` capacity and its frozen 08B G1/G2/G3 composition. SC1 cannot allocate more released land to an ED or soil group than the corresponding grassland capacity.

08C physical soil and LPIS do not enter this livestock-release solve.

## 5. SC2: released land to opportunity and eligibility

SC2 takes the frozen SC1 result as an immutable input. It never recomputes livestock and never changes the ED released-land vector.

SC2 attaches the 2020 LPIS and independent 08C evidence from the frozen land context, then derives opportunity scores and physical eligibility quantities used by SC3.

The interpretation is:

```text
PotentialRelease != Opportunity != RealisedConversion
```

`PotentialRelease` is the spatial budget associated with the national livestock pathway. `Opportunity` describes compatibility with alternative uses. Neither quantity is a prediction of actual conversion.

## 6. SC3: explicit national targets to feasible ED allocations

SC3 receives land-use targets from the same editable national scenario control. The allocator never invents target hectares.

Supported targets are:

- AD grass
- biorefinery grass
- willow
- additional tillage
- additional forest
- rewetting

The main mineral/bioeconomy uses are allocated jointly subject to ED released-land budgets, use-specific physical eligibility and nested shared physical pools. The first optimisation objective minimises total unmet target hectares. Conditional on that minimum, the second objective favours higher SC2 opportunity scores.

If a national target is spatially infeasible, the model reports the unmet hectares rather than forcing conversion into an ineligible ED.

### Rewetting accounting

Rewetting is handled sequentially after the main released-land allocation. Its capacity is constrained by the post-allocation residual and an externally anchored drained-organic-grassland stock spatialised using the relevant 08B organic-soil context.

Two quantities must remain distinct:

- **GOBLIN parent Available land**, the gross released land left after the principal new-use targets before the rewetting overlay;
- **strict residual available land**, what remains after realised rewetting in the exclusive spatial accounting.

This prevents the source pathway's `Available` category from being incorrectly relabelled as gross spared grassland.

## 7. Pathway consistency

A scenario run is a single internally consistent package. The pathway identifier controls its livestock endpoint, livestock-land target, land-use targets and reconciliation outputs.

Components from different pathways must never be mixed. In particular:

```text
SI_SG livestock + SI_SG land release + SI_SG land-use targets
BE_SG livestock + BE_SG land release + BE_SG land-use targets
ALL_GAS_NZ livestock + ALL_GAS_NZ land release + ALL_GAS_NZ land-use targets
```

The scenario control CSV is the runtime authority for the active pathways and their current endpoint values.

## 8. Reproducibility boundary

A normal 2020 scenario run is intentionally lightweight. It requires the validated historical baseline and repository-contained compact controls. It must not automatically:

- download LPIS parcels;
- fetch ED geometry;
- download soil packages;
- rebuild GIS overlays;
- regenerate the frozen 2020 land context.

Those operations belong to explicit first-principles reconstruction workflows. The heavy GitHub Actions are manual-only for the same reason.

## 9. Interpretation for strategic foresight

GOBLIN-Spatial is not a parcel-level land-use forecast and does not predict which individual farms will adopt a particular transition.

Its analytical purpose is to identify:

- EDs with robust livestock-transition exposure across plausible national pathways;
- EDs whose exposure depends strongly on the incidence rule;
- locations where released-land geography aligns with alternative land-use opportunity;
- locations where national land-use targets encounter spatial constraints;
- areas where earlier policy preparation may be needed because high adjustment exposure coincides with weak transition opportunity.

Protection, opportunity and compatibility should therefore be interpreted as spatial stress-test results, not behavioural predictions.

## 10. Supported runtime

The principal command is:

```bash
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC1
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC2
goblin-spatial-principal <SCENARIO_ID> --baseline-year 2020 --stage SC3
```

`goblin-spatial` is reserved for the historical baseline and data-management commands. `goblin-spatial-lpis` is retained only as an explicit reconstruction tool and is not invoked by the principal runtime.
