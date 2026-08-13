# GOBLIN-Spatial scenario architecture

## Study boundary

The principal study is cattle focused. The validated historical ED baseline remains the foundation. A scenario selects either the 2020 or 2025 ED state, applies dairy- and/or suckler-cow reductions, propagates those reductions through the 21 cattle cohorts, values Standard Output exposure, calculates GOBLIN grassland requirement and potential spared grassland, and then screens alternative land opportunities at ED level.

Sheep remain unchanged context in the principal study.

## One sequential scenario engine

The study workflow is:

`validated ED baseline -> select 2020/2025 -> dairy/suckler reduction -> 2030/2040/2050 cattle cohorts -> Standard Output exposure -> grassland release -> ED soil opportunity -> alternative land allocation`

Dairy and suckler reductions are independently editable. If milestone reductions are not supplied, the engine interpolates from zero at the selected baseline year to the requested endpoint. Direct milestone reductions can be supplied instead.

## Adult cows are the scenario controls

For adult class k:

`NationalReduction(k) = round(BaselineNationalTotal(k) * ReductionFraction(k))`

The adult reduction is allocated across the existing ED footprint and subtracted from the selected baseline. No adult livestock is seeded into an ED where that class was absent.

The young cattle response is not entered independently. It follows from the relationship already observed between adult cows and follower cohorts in each ED.

## Simple ED adult-to-cohort ripple

For DxD and DxB cohorts, the parent population is dairy cows. For BxB cohorts, the parent population is suckler cows. Bulls follow the combined adult-cow population.

If an ED contains the relevant parent adults, its follower cohort uses that ED's own realised adult reduction rate:

`FollowerReductionRate(e,k) = AdultReduction(e,origin(k)) / BaselineAdult(e,origin(k))`

and:

`FollowerReduction(e,k) = BaselineFollower(e,k) * FollowerReductionRate(e,k)`

which is exactly equivalent to:

`FollowerReduction(e,k) = AdultReduction(e,origin(k)) * BaselineFollower(e,k) / BaselineAdult(e,origin(k))`

So the baseline adult-to-cohort ratio in each ED is preserved as the adult population contracts.

## Orphan / receiver EDs

Some EDs contain a young-stock cohort but no corresponding parent adults. These are receiver/orphan EDs for that cohort. They are not frozen during a cattle reduction.

Their baseline relationship is recorded relative to the relevant parent adults elsewhere in the same county:

`OrphanRatio(e,k) = BaselineFollower(e,k) / CountyBaselineAdult(origin(k))`

When the county parent-adult population contracts:

`OrphanReduction(e,k) = CountyAdultReduction(origin(k)) * OrphanRatio(e,k)`

which is equivalent to:

`OrphanReduction(e,k) = BaselineFollower(e,k) * CountyAdultReductionRate(origin(k))`

Therefore a receiver ED loses young stock when the breeding-cow population supplying that county falls. No arbitrary 30%, 50% or other spillover factor is imposed: the observed baseline orphan-cohort-to-county-adult relationship determines the size of the ripple.

Only if the cohort exists in a county with no corresponding parent adults at all is the national adult reduction rate used as a fallback.

The model records the source for every cohort as:

- `LOCAL_ED`
- `COUNTY_RECEIVER`
- `NATIONAL_ORPHAN`
- `NONE`

## ED relationship audit table

`build_ed_cohort_dependency_profile()` records, for every ED x follower cohort:

- baseline year
- ED and county
- cohort
- parent adult origin
- baseline parent adults
- baseline cohort head
- `ED_COHORT_PER_ADULT_RATIO`
- county parent-adult total
- county cohort total
- `ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO`
- `ORPHAN_SHARE_OF_COUNTY_COHORT`
- cohort spatial role

These are transparent accounting relationships. They are not claimed to be observed animal-movement links.

## National biological closure

GOBLIN/COHORTS remains authoritative for the national biological target of each cattle cohort. GOBLIN-Spatial uses the local and county ripple relationships only to determine where the required national cohort reduction falls.

The integer allocation is bounded by the existing ED cohort stock and closes exactly to the national cohort target.

## Cattle-only study scenarios

The study-facing interface keeps sheep fixed and supports:

- dairy-only reduction
- suckler-only reduction
- combined dairy + suckler reduction
- reproducible randomised spatial-incidence sensitivity for the same national endpoint

The same engine works from a 2020 or 2025 starting state and for any endpoint reduction fraction.

## Standard Output

Standard Output is calculated only after the physical cattle state has been solved. It reports production-value exposure and never drives animal allocation.

## Grassland release

The solved cattle pathway, with unchanged sheep context, is passed to GOBLIN pasture/feed accounting:

`scenario livestock -> pasture dry-matter demand -> required grassland -> potential spared grassland`

The validated ED `ALL_GRASSLAND` remains the controlling land total. Potential spared grassland and any additional grassland requirement are reported separately.

## Alternative land opportunity

Potential release is not automatic land-use conversion:

`PotentialRelease != Opportunity != RealisedConversion`

ED soil and forest context are used only after potential release has been calculated to screen where forestry, rewetting, AD grass, willow, energy grass and nature/restoration may be plausible.
