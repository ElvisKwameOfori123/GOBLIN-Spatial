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

For cattle, the 2010 and published 2020 CSO Census of Agriculture ED distributions provide two fine-scale spatial anchors. Dairy cows, other/suckler cows and other cattle are reconstructed separately. For 2015-2019, each component's within-county ED share moves linearly from its 2010 share to its published 2020 share; the corresponding annual AAA10 county component control is then imposed exactly using pro-rata Hamilton allocation. The published 2020 ED values are retained unchanged. For 2021-2025, each component holds its published 2020 ED share while the annual AAA10 county control changes. A component published as zero in an ED in 2020 therefore remains zero there after 2020. Total cattle is derived as dairy cows + other cows + other cattle. Differences between the published 2020 ED sums and AAA10 are recorded as source differences only and are not spatially allocated. The intervening ED path is a reconstruction assumption, not an independently observed annual ED series.

For sheep, the published 2020 ED total is likewise retained unchanged, including every published zero. For 2015-2019, each ED's within-county sheep share moves linearly from its 2010 share toward its published 2020 share. County weights within each AAA09 region are adjusted by the DAFM breeding-ewe share index and renormalised before the AAA09 regional total is imposed exactly. For 2021-2025, the published 2020 ED support pattern is held while the same DAFM county-direction index and AAA09 regional controls provide annual higher-level change. A sheep value published as zero in 2020 therefore remains zero after 2020. The 2020 difference between the published ED sum and AAA09 is recorded as a source difference only and is not seeded into EDs.

The undivided ED \`OTHER_CATTLE\` total is then separated into the seven CSO age-sex groups under exact accounting constraints. AAA10 supplies the authoritative county age-sex composition. The A0 null applies that county composition uniformly across EDs. The production A1 prior uses the 2020 DAFM/AIM ED age profile only to shift the odds of under-one versus one-to-two-year cattle. The DAFM/AIM values are the arithmetic mean of the June and December 2020 stock observations, so they are interpreted as a two-snapshot approximation to the resident standing herd rather than as an exact point-in-time census or a continuous annual mean. DAFM under-one combines 0-3, 3-6 and 6-12 months; one-to-two combines 12-18 and 18-24 months. For ED \(e\) in county \(c\),

\[
\operatorname{logit}(p_e)
=
\operatorname{logit}(p_c)
+
\left[\operatorname{logit}(q_e)-\operatorname{logit}(q_c)\right],
\]

where \(p_c\) is the AAA10 under-one share of the combined under-one plus one-to-two county pool, and \(q_e\) and \(q_c\) are the corresponding DAFM ED and county shares. Probabilities are bounded by a fixed \(10^{-6}\) epsilon only to make logits finite. Bulls and cattle aged two years and over retain the county prior, and sex composition within the two adjusted young-age groups comes from the county AAA10 ratios. The prior is reconciled by iterative proportional fitting and exact integerisation so every ED \`OTHER_CATTLE\` row and every rescaled AAA10 county age-sex column closes exactly. DAFM rows aggregated as \`DED < 5 HERDS\` contribute to the county reference but are not assigned to individual EDs; unmatched EDs receive the county DAFM ratio, making their log-odds adjustment neutral.

The resulting age-sex table is frozen before genetic disaggregation. Step 4 then separates each fixed age-sex container into DxD, DxB and BxB without moving cattle between EDs or changing any age-sex control. GOBLIN/COHORTS supplies the exact national age-sex-specific genetic margins. DAFM/AIM broad dairy/beef composition supplies a 2020 spatial prior. For a matched ED, the AIM dairy share is first placed on the fixed CSO total and the fixed CSO dairy-cow count is removed,

\[
q_e = \frac{T_e\,(AIM\_DAIRY_e/AIM\_TOTAL_e)-D_e}{O_e},
\]

where \(T_e\), \(D_e\) and \(O_e\) are the fixed CSO total cattle, dairy cows and other cattle. This is a composition signal, not a new cattle count. If the local cross-source residual falls outside \((0,1)\), if the ED is unmatched, or if no usable denominator exists, the corresponding county signal is used instead. No value is forced to zero because of the absence of local adult cows.

For age-sex container \(j\), the national GOBLIN DxD share remains the biological centre of the prior and the AIM signal supplies only the spatial log-odds shift,

\[
\operatorname{logit}(p^{DxD}_{e,j})
=
\operatorname{logit}(p^{DxD}_{N,j})
+
\left[\operatorname{logit}(q_e)-\operatorname{logit}(q_N)\right].
\]

The residual beef-type pool is divided between DxB and BxB using a soft combination of local biological production evidence and the national residual mix. Expected local DxB contribution is proportional to dairy cows and the relevant GOBLIN DxB coefficient; expected local BxB contribution is proportional to suckler cows and the relevant GOBLIN BxB coefficient. A national mixing component is added to both so that suckler-only, dairy-only and no-adult-cow EDs can all contain followers even where the corresponding adult cows are absent locally. This supplies biological composition support only; it does not assign movement or origin. Adult-cow absence is therefore never a structural genetics gate. Only an already-fixed zero age-sex cell is a structural zero. IPF and exact integerisation then restore every ED age-sex row and every national DxD/DxB/BxB margin exactly. The 2020 AIM spatial signature is held as the fine-scale type prior across 2015-2025, while reconstructed annual cow populations and the year-specific GOBLIN relationships supply the annual biological context.

Other livestock, land and farm-structure variables continue to use their documented official higher-level controls and spatial anchors. The framework combines these sources through hierarchical reconciliation rather than treating every non-census ED value as independently observed.

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
