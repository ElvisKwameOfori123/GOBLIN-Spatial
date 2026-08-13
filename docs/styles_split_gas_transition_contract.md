# Styles split-gas transition contract

This note fixes the principal livestock-transition interpretation for the GOBLIN-Spatial foresight study.

## National adult endpoints

The source-controlled adult endpoints are in `configs/styles_split_gas_adult_endpoints.csv`, taken from Table 2 of Styles et al. (2025), *Structured foresight reframes risk around transitions towards sustainable and resilient farming in a volatile world*:

- `SI_SG`, 2050: 1,600,000 dairy cows and 160,000 suckler cows;
- `BE_SG`, 2050: 1,540,000 dairy cows and 154,000 suckler cows.

Both endpoints use the reported 10:1 dairy:suckler profile. These values are adult controls only. They do not create a total-cattle target or a gross released-land target unless those quantities are supplied separately from the matching GOBLIN pathway.

## Reduction calculation

GOBLIN-Spatial does not build a future ED herd from zero. For baseline year `b` and pathway `p`:

`national reduction(b,p) = national GOBLIN-Spatial baseline(b) - national pathway endpoint(p)`

The 2020 and 2025 analyses therefore use the same pathway destination but can have different remaining reductions.

If an endpoint exceeds the selected baseline for an adult category, the principal reduction-only study fails rather than expanding or seeding that category.

## Universal ED participation

For every non-null adult reduction, every ED with a positive baseline stock of that category participates in the reduction.

Protection changes reduction intensity, not participation. A protected ED still reduces, but by less than it otherwise would; the unchanged national reduction is consequently shifted toward other EDs.

An ED may reach zero in a livestock category if its allocated reduction equals its baseline stock. Zero-baseline EDs remain zero.

Because counts are integer, a non-null reduction must be large enough to remove at least one animal from each eligible ED. Otherwise the universal-participation allocation is declared infeasible.

## Biological response and total cattle

Dairy reductions drive DxD and DxB follower changes. Suckler reductions drive BxB follower changes. Bulls respond to the combined adult-cow signal. Existing local, county-receiver and national-orphan relationships remain unchanged.

After the response:

`SCENARIO_TOTAL_CATTLE = sum(21 scenario cattle cohorts)`

An external national total-cattle or exact 21-cohort target is used only when the matching GOBLIN pathway supplies it explicitly.

## Land boundary

The national adult endpoint does not by itself define gross land release. When a matching GOBLIN gross livestock-land release is later supplied, that national hectare total is spatialised using the geography of cohort-specific pasture-DM pressure reduction. The existing internally calculated `POTENTIAL_SPARED_GRASSLAND_HA` remains a separate diagnostic.

`Available` residual land must not be substituted for gross livestock-land release.
