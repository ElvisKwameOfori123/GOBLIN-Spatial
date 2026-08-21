# Styles split-gas transition contract

This note fixes the principal livestock-transition interpretation for the GOBLIN-Spatial foresight study.

## National adult endpoints

The source-controlled adult endpoints are in `configs/styles_split_gas_adult_endpoints.csv`, taken from Table 2 of Styles et al. (2025), *Structured foresight reframes risk around transitions towards sustainable and resilient farming in a volatile world*:

- `SI_SG`, 2050: 1,600,000 dairy cows and 160,000 suckler cows;
- `BE_SG`, 2050: 1,540,000 dairy cows and 154,000 suckler cows.

Both endpoints use the reported 10:1 dairy:suckler profile. These values are adult controls only. They do not create a total-cattle target or a gross released-land target unless those quantities are supplied separately from the matching GOBLIN pathway.

## Baseline-to-endpoint adjustment

GOBLIN-Spatial does not build a future ED herd from zero. The selected 2020 or 2025 spatial herd is reduced and re-composed to the same national endpoint.

The validated national adult baselines are:

- 2020: 1,567,600 dairy + 983,500 suckler = 2,551,100 adult cows;
- 2025: 1,588,100 dairy + 778,800 suckler = 2,366,900 adult cows.

Therefore both SI_SG and BE_SG are large **overall adult-cow contractions** from either baseline. However, SI_SG is not a dairy reduction: its 1.600 million dairy endpoint is 32,400 above the 2020 dairy baseline and 11,900 above the 2025 dairy baseline. The pathway combines a small dairy increase with a very large suckler reduction.

The principal spatial quantity allocated by the protection rules is therefore:

`total adult-cow reduction = baseline adult cows - pathway adult endpoint`

not an independent requirement that every livestock category must decline in every ED.

## Principal endpoint route

`run_principal_goblin_endpoint()` uses the sourced 2050 endpoint only. It does not manufacture 2030 or 2040 livestock reductions. Earlier milestones should enter the principal study only when matching national GOBLIN values are explicitly sourced or an interpolation assumption is deliberately declared.

The principal route is:

`selected baseline -> universal total-adult contraction -> exact dairy/suckler composition -> 21-cattle-cohort response -> total cattle`

## Universal ED participation

Every ED with adult cattle at baseline participates in the overall adult-cow contraction. Protection changes the intensity of that total reduction; it does not exempt an adult-cattle ED. Complete local adult-cattle exit is allowed.

The retained adult herd is then reconciled to the exact pathway dairy:suckler composition. A category is never seeded into an ED where it was absent at baseline, but category shares can change within mixed dairy+suckler EDs. This is how SI_SG can increase dairy nationally while total adult cows still decline everywhere.

At the end of the cohort response, every cattle-bearing ED must contain fewer total cattle than at baseline. Individual dairy-linked cohorts may increase where the pathway becomes more dairy-oriented, but the complete cattle population must contract in every ED.

## Biological response and total cattle

DxD and DxB cohorts follow the scenario-to-baseline dairy-parent multiplier; BxB cohorts follow the suckler-parent multiplier; bulls follow the combined adult-cow multiplier. The existing local, county-receiver and national-orphan hierarchy is retained.

After the response:

`SCENARIO_TOTAL_CATTLE = sum(21 scenario cattle cohorts)`

An external national total-cattle or exact 21-cohort target is enforced only when the matching GOBLIN pathway supplies it explicitly.

## Land boundary

The adult endpoint does not by itself define gross land release. When a matching GOBLIN gross livestock-land release is supplied, that national hectare total is spatialised using the geography of cohort-specific pasture-DM pressure reduction. The existing internally calculated `POTENTIAL_SPARED_GRASSLAND_HA` remains a separate diagnostic.

`Available` residual land must not be substituted for gross livestock-land release.
