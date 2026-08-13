# GOBLIN pathway authority and GOBLIN-Spatial transition accounting

## Purpose

GOBLIN-Spatial does not replace national GOBLIN. GOBLIN supplies the pathway quantities; GOBLIN-Spatial resolves where the transition occurs across the validated ED baseline.

The principal study pathways are `SI_SG` and `BE_SG`. Their 2050 adult endpoints are source-controlled from Styles et al. (2025):

- `SI_SG`: 1,600,000 dairy cows + 160,000 suckler cows;
- `BE_SG`: 1,540,000 dairy cows + 154,000 suckler cows.

## Baseline and adult transition

The historical reconstruction is unchanged. The scenario can start from 2020 or 2025 and uses the same national endpoint from either starting year.

The validated adult baselines are:

- 2020: 1,567,600 dairy + 983,500 suckler;
- 2025: 1,588,100 dairy + 778,800 suckler.

Both pathways therefore reduce total adult cows substantially. SI_SG nevertheless increases dairy slightly relative to either baseline while sharply reducing sucklers. The principal spatial allocation is consequently the **overall adult-cow contraction**, not a requirement that dairy and sucklers each decline in every ED.

Every ED with adult cattle participates in the total adult contraction. Protection changes reduction intensity rather than granting exemption. Complete local adult-cattle exit is allowed. The retained adult stock is then reconciled to the exact national dairy:suckler endpoint inside existing category footprints, so no dairy or suckler category is seeded into an ED where it was absent at baseline.

## Cohort response and total cattle

DxD and DxB followers respond to the scenario-to-baseline dairy-parent multiplier. BxB followers respond to the suckler-parent multiplier. Bulls respond to the combined adult-cow multiplier. The local ED, county receiver and national orphan hierarchy is preserved.

After propagation:

`SCENARIO_TOTAL_CATTLE = sum(21 scenario cattle cohorts)`

Every cattle-bearing ED must finish below its selected baseline total cattle in the principal transition. Individual dairy-linked cohorts may rise where the pathway becomes more dairy-oriented, but the complete cattle stock contracts locally.

The national control hierarchy remains:

1. exact 21 cohort targets, only if supplied explicitly by GOBLIN;
2. adult endpoints plus an authoritative total-cattle target, if supplied;
3. adult endpoints only, with total cattle an endogenous diagnostic.

No missing total-cattle or cohort target is invented.

The principal study remains cattle-focused and keeps sheep fixed unless a later study explicitly changes that boundary.

## Land authority

`POTENTIAL_SPARED_GRASSLAND_HA` remains the internal fixed-feed diagnostic:

`ED livestock -> cohort pasture DM -> required grassland -> potential spared grassland`.

When the matching GOBLIN pathway supplies an authoritative gross livestock-land release, that national total controls the principal pathway analysis. `allocate_national_goblin_land_release()` spatialises it using cohort-specific pasture-DM pressure reduction, with `ALL_GRASSLAND` as the ED capacity bound.

- `GOBLIN_RELEASED_GRASSLAND_HA`: authoritative external national release spatialised to EDs;
- `POTENTIAL_SPARED_GRASSLAND_HA`: independent diagnostic.

The GOBLIN `Available` residual is not gross livestock-land release and must remain separate.

## Land opportunity and realised use

Soil and LPIS are downstream. They do not determine livestock reduction or change the released-land total. They characterise the opportunity context of EDs to which released land has been attributed.

`released land -> opportunity -> explicit land-use target allocation`

Opportunity is not realised conversion. Future uses are allocated only when explicit national hectare targets are supplied from the same pathway or another stated source. Unmet targets are reported rather than forced into ineligible EDs.

## National reconciliation

`build_goblin_reconciliation()` audits externally supplied national controls against the ED spatial sums for dairy, suckler, total cattle when supplied, exact cohorts when supplied, and authoritative livestock-land release when supplied.

## Current implementation boundary

Implemented now:

- source-controlled SI_SG / BE_SG adult endpoints;
- total-adult contraction allocation with universal ED participation;
- exact dairy/suckler endpoint reconciliation inside existing footprints;
- signed adult composition change, including SI_SG dairy increase;
- local/county/national signed cohort multipliers;
- ED total-cattle contraction reconciliation;
- exact total-cattle validation when an external target is supplied;
- GOBLIN-controlled national land-release spatialisation;
- national target-versus-ED reconciliation audit;
- fixed-feed land-release diagnostic retained separately.

Still requiring authoritative pathway inputs:

- exact gross livestock-land release for SI_SG and BE_SG;
- exact future land-use targets from those same scenario packages;
- any exact national total-cattle or 21-cohort endpoint if GOBLIN reports them;
- final vulnerability/productivity indicators before those protection rules are used substantively.

The historical baseline must not be rebuilt or altered by these downstream changes.
