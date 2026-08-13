# GOBLIN pathway authority and GOBLIN-Spatial transition accounting

## Purpose

GOBLIN-Spatial does not replace the national GOBLIN scenario. National GOBLIN supplies the pathway quantities; GOBLIN-Spatial resolves where the transition occurs across the validated ED baseline.

For the planned transition study, the principal pathway identifiers are `SI_SG` and `BE_SG`. Exact pathway values must come from the corresponding GOBLIN outputs. They must not be inferred from unrelated rows or mixed across pathway families.

## Baseline

The validated historical reconstruction is unchanged. A future scenario can start from either 2020 or 2025. A 2025 run measures the remaining adjustment from the 2025 ED state to the relevant national endpoint; it does not reapply a percentage derived from 2020.

## Livestock authority

Adult dairy and suckler populations remain the biological drivers of the spatial cohort response. DxD and DxB followers respond to dairy, BxB followers respond to suckler, and bulls respond to the combined adult-cow signal. Local ED relationships are used first, county receiver relationships second, and national fallback only for true county orphans.

After the response, total cattle is the sum of the solved 21 cattle cohorts. The control hierarchy is:

1. exact 21 national cohort targets, when GOBLIN supplies all of them;
2. adult dairy/suckler targets plus an authoritative national total-cattle target;
3. adult targets only, with total cattle reported as the resulting diagnostic.

No missing national cohort target is invented. Where a national total-cattle target is supplied, a mismatch is currently reported as an explicit failure rather than silently rebalanced. A reconciliation method should be added only after its scientific rule is agreed.

The principal study remains cattle-focused and keeps sheep fixed unless a later study explicitly changes that boundary.

## Land authority

`POTENTIAL_SPARED_GRASSLAND_HA` remains the internally calculated fixed-feed GOBLIN-Spatial diagnostic:

`ED livestock -> cohort pasture DM -> required grassland -> potential spared grassland`.

When the originating GOBLIN pathway supplies an authoritative national livestock-land release, that national total controls the principal pathway analysis. `allocate_national_goblin_land_release()` distributes only that known national total across EDs using the geography of cohort-specific pasture-DM pressure reduction, with `ALL_GRASSLAND` as the ED capacity bound.

The two quantities therefore have different roles:

- `GOBLIN_RELEASED_GRASSLAND_HA`: authoritative national GOBLIN total spatialised across EDs;
- `POTENTIAL_SPARED_GRASSLAND_HA`: independent GOBLIN-Spatial diagnostic for reconciliation and sensitivity analysis.

The reported GOBLIN `Available` land residual is not the same as gross livestock-land release and must remain a separate pathway quantity.

## National reconciliation

Every externally supplied pathway control should be auditable against the spatial result. `build_goblin_reconciliation()` writes a tidy target-versus-spatial-sum table for dairy cows, suckler cows, total cattle when supplied, exact 21-cohort controls when supplied, and authoritative livestock-land release when supplied.

Downstream land-use targets and the GOBLIN available-land residual are retained in the same audit as pending controls until the corresponding land-allocation stage has been completed. This keeps pathway authority visible without pretending that a downstream target has already been spatially realised.

## Land opportunity and realised use

Soil and LPIS remain downstream. They do not determine livestock reduction and do not change the released-land total. They characterise the opportunity context of EDs to which released land has been attributed.

Transition land helpers prefer `GOBLIN_RELEASED_GRASSLAND_HA` when it is available and fall back to `POTENTIAL_SPARED_GRASSLAND_HA` only when an external GOBLIN release has not been supplied.

The accounting boundary remains:

`released land -> opportunity -> explicit land-use target allocation`.

Opportunity scores are screening evidence, not realised conversion. Future land uses are allocated only when explicit national hectare targets are supplied from the same GOBLIN pathway or another stated policy/study source. Unmet targets are reported rather than forced into ineligible EDs.

## Spatial policy experiment

The national endpoint must remain identical across allocation rules. `PRORATA`, `DAIRY_PROTECTION`, and other supported protection/sensitivity rules change only where the transition lands. Protection therefore redistributes the national adjustment; it does not remove it.

The main policy outputs are the geography of livestock reduction, total-cattle and cohort change, Standard Output production-value exposure, the geography of released land, and the compatibility of that land with alternative enterprises and land uses.

## Current implementation boundary

Implemented now:

- external GOBLIN pathway-control data classes;
- explicit ED and national total-cattle accounting;
- optional exact national total-cattle validation;
- optional exact 21-cohort target route;
- GOBLIN-controlled national released-land spatialisation using cohort pasture-DM pressure change;
- national target-versus-ED reconciliation audit;
- transition land-capacity helpers that prefer the GOBLIN-controlled release;
- existing independent fixed-feed land-release calculation retained as a diagnostic.

Still requiring substantive inputs/decisions:

- authoritative `SI_SG` and `BE_SG` livestock, land-release and land-use target values;
- a scientifically agreed reconciliation rule if adult-driven cohorts do not close to a supplied aggregate total-cattle target;
- final vulnerability/productivity indicators before those protection rules are used substantively;
- full principal-study CLI wiring after the national pathway inputs are frozen.

The historical baseline must not be rebuilt or altered by these downstream changes.
