# GOBLIN-Spatial methodology

## Overview

GOBLIN-Spatial is a constraint-preserving spatial foresight framework that connects nationally coherent GOBLIN AFOLU pathways to Electoral Division (ED) agricultural geography.

The framework does not create a second national future. National livestock endpoints, target livestock-land area and future land-use requirements remain controlled by the selected GOBLIN pathway. GOBLIN-Spatial resolves where transition incidence falls, what physical response resource is created, whether future land-use requirements can fit within that finite resource and whether the same national outcome has one necessary geography or several feasible geographies.

The analytical sequence is:

```text
National GOBLIN pathway
        ↓
Baseline
        ↓
SC1 transition incidence
        ↓
freeze livestock + released-land geography
        ↓
SC2 spatial response potential
        ↓
freeze physical resource + eligibility
        ↓
SC3 spatial transformability
        ↓
realised + unmet + residual
        ↓
post-SC3 spatial flexibility
```

## Historical spatial baseline

The Irish implementation reconstructs agriculture from 2015 to 2025 across 2,857 EDs represented in the harmonised agricultural dataset.

The 2020 CSO Census of Agriculture is the principal fine-scale spatial anchor. Annual higher-level official controls constrain surrounding livestock, land and farm-structure totals. The framework combines these controls through hierarchical reconciliation rather than treating every non-2020 ED value as independently observed.

For cattle, the ED publication supplies only dairy cows, other/suckler cows, total cattle and the residual `OTHER_CATTLE` population. The 2020 publication contains dairy cells reported as zero that cannot be distinguished internally from confidentiality-withheld values. A frozen support mask derived from the 2010 AVA42 Census identifies published-zero 2020 EDs in which dairy was either withheld or positive in 2010. The selected Stage A reconstruction preserves every published positive 2020 dairy value and allocates each county's known AAA10 dairy residual only across that support mask, weighted by the ED's published 2020 `OTHER_CATTLE`. Added dairy is reclassified from `OTHER_CATTLE`, so the published ED total cattle population is unchanged before county reconciliation.

AAA10 then supplies the controlling annual county populations for 2015-2025. It also supplies the seven non-cow age-sex groups that are not published at ED level. The county age-sex proportions are reconciled exactly to each ED's residual cattle envelope before GOBLIN/COHORTS national biological relationships subdivide the six pre-adult age-sex groups into DxD, DxB and BxB cohorts. Thus ED evidence determines the local cattle envelope, county statistics determine annual age-sex structure, and GOBLIN/COHORTS supplies the national genetic relationships used for biological subdivision.

The baseline contains:

- 21 biologically linked cattle cohorts;
- 10 sheep cohorts;
- grassland, cereals and other agricultural land;
- selected farm-structure variables;
- fixed-2020 Standard Output as a production-value exposure indicator.

For every ED-year:

```text
sum(21 cattle cohorts) = TOTAL_CATTLE
sum(10 sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

## National pathway authority

For each selected scenario, GOBLIN remains authoritative for the quantities supplied in the scenario-control table. Scenario IDs are never mixed.

For a selected baseline, gross livestock-land release is:

```text
Gross release
    = baseline ALL_GRASSLAND
      - pathway TARGET_LIVESTOCK_LAND_HA
```

This national quantity is frozen before spatialisation.

The parent GOBLIN `Available` residual is not used as gross livestock-land release.

## SC1: transition incidence

SC1 answers:

> Where does the nationally specified livestock transition fall, and where is the authoritative livestock-land release represented?

The principal sequence is:

```text
national adult livestock endpoint
        ↓
spatial incidence rule
        ↓
ED adult dairy/suckler state
        ↓
21-cohort cattle response + fixed sheep unless controlled otherwise
        ↓
production-value exposure
        ↓
pasture-DM transition signal
        ↓
authoritative national release spatialised to EDs
```

The principal incidence rules are `PRORATA`, `DAIRY_PROTECTION`, `ECONOMIC_CAPACITY_PROTECTION` and `SOCIAL_VULNERABILITY_PROTECTION`. They change the geography of adjustment but not the national pathway.

### SC1 land boundary

SC1 is deliberately independent of spatial soil, LPIS and future-use suitability evidence.

The ED release vector is driven by the solved livestock/pasture-DM transition signal and bounded only by `ALL_GRASSLAND`:

```text
0 <= released_land[e] <= ALL_GRASSLAND[e]
```

and nationally:

```text
sum_e released_land[e] = authoritative GOBLIN gross release
```

If the primary livestock-pressure signal saturates local grassland capacity, remaining hectares are redistributed transparently across still-available livestock-bearing grassland. Fallback hectares are reported.

### Independent pasture-DM diagnostic

The pasture-DM land balance is retained separately:

- `SIGNED_GRASSLAND_BALANCE_HA`;
- `POTENTIAL_SPARED_GRASSLAND_HA`;
- `ADDITIONAL_GRASSLAND_REQUIRED_HA`.

These diagnostics are not rescaled to become the authoritative parent release.

## SC2: spatial response potential

SC2 starts only after the SC1 livestock solution and released-land vector are frozen.

It uses two separate 2020 ED evidence layers:

1. mapped physical soil and drainage classes;
2. LPIS agricultural-use and management context.

The seven physical categories are deep well drained, shallow well drained, poorly drained, poorly drained peaty, alluvium, peat and miscellaneous.

Frozen release is proportionally characterised within each ED:

```text
released_soil[e,s]
    = released_land[e] × mapped_soil_share[e,s]
```

with the closure condition:

```text
sum_s released_soil[e,s] = released_land[e]
```

This is a proportional ED-level resource characterisation. It is not a claim that the exact released parcels or their exact soil provenance are observed.

LPIS remains separate context. The compact runtime does not contain a validated parcel-level soil × LPIS joint overlay and does not manufacture one through an independence assumption.

### Eligibility and opportunity

Future-use eligibility must be explicit, complete, versioned and evidence-backed. No default coefficients are inferred by the model.

Eligibility is distinct from opportunity. Opportunity may later rank eligible locations using defensible evidence, but no arbitrary composite opportunity score is applied by default.

The controlling distinction is:

```text
Release
    != Physical resource
    != Eligibility
    != Opportunity
    != Allocation
    != Adoption
```

## SC3: spatial transformability

SC3 tests whether the future land-use requirements from the same GOBLIN pathway can jointly fit within finite eligible released land.

The principal competing Stage-A uses are:

- AD grass;
- biorefinery grass;
- willow;
- additional tillage;
- forest.

For ED `e`, physical soil class `s` and use `u`:

```text
sum_u allocation[e,s,u] <= released_soil[e,s]
```

A hectare eligible for several uses remains one hectare.

For every national use target:

```text
Realised_u + Unmet_u = Target_u
```

Unmet hectares are therefore a substantive spatial-feasibility result rather than software failure.

The optimiser first minimises total unmet target. A secondary opportunity objective is used only when an explicit evidence-backed opportunity mapping is supplied.

## Rewetting

Rewetting is treated as a separate environmental/restoration requirement.

```text
Mapped peat
    != drained agricultural organic soil
    != rewettable capacity
```

A positive rewetting target therefore requires independently validated capacity evidence. Rewetting does not automatically increase productive diversification or alternative-income opportunity.

## Post-SC3 spatial flexibility

A single feasible linear-program solution is not interpreted as a uniquely necessary geography.

The optional post-SC3 analysis holds the realised national hectares of each individual end use fixed and searches for alternative feasible spatial allocations under the same frozen resource and eligibility constraints.

This can distinguish:

- spatially necessary or persistent locations;
- flexible or interchangeable locations.

For selected ED-use questions, exact minimum and maximum feasible allocations can be calculated while preserving the same national outcome.

## Interpretation

GOBLIN-Spatial is a spatial foresight and transition-incidence framework. It does not predict individual farmer behaviour, parcel conversion, willingness to adopt, market prices, household welfare or the exact realised 2050 geography.

Its principal use is to reveal where nationally coherent pathways generate robust exposure, constrained response space, feasible transformation and spatial flexibility before the future is known.
