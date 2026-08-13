# GOBLIN-Spatial scenario architecture

## Study boundary

The principal study is cattle focused. The validated historical ED baseline remains the foundation and formally ends after livestock/cohort reconstruction, land reconciliation and SE enrichment. Soil, Standard Output, future livestock scenarios, grassland release and alternative-land allocation are downstream analytical layers; they do not redefine the historical baseline.

A scenario selects either the 2020 or 2025 ED state, applies dairy- and/or suckler-cow reductions, propagates those reductions through the existing 21 cattle cohorts, values Standard Output exposure, optionally calculates GOBLIN grassland requirement and potential spared grassland when authoritative pasture-DM controls are supplied, and then optionally screens alternative land opportunities at ED level.

Sheep remain unchanged context in the principal study.

## One sequential scenario engine

The study workflow is:

`validated ED baseline -> select 2020/2025 -> dairy/suckler reduction -> 2030/2040/2050 cattle cohorts -> Standard Output exposure -> grassland release -> ED soil opportunity -> alternative land allocation`

Dairy and suckler reductions are independently editable. If milestone reductions are not supplied, the engine interpolates from zero at the selected baseline year to the requested endpoint. Direct milestone reductions can be supplied instead.

The high-level study wrapper is `scenario/study_workflow.py`. It produces both wide scenario results and long-form ED x cohort audit tables.

## Adult cows are the scenario controls

For adult class k:

`NationalReduction(k) = round(BaselineNationalTotal(k) * ReductionFraction(k))`

The adult reduction is allocated across the existing ED footprint and subtracted from the selected baseline. No adult livestock is seeded into an ED where that class was absent.

The young cattle response is not entered independently. It follows from the relationship already observed between adult cows and follower cohorts in each ED.

## The 18 pre-adult cattle cohorts are distinct

The baseline contains six DxD, six DxB and six BxB pre-adult cohorts:

- male calves
- female calves
- heifers under two years
- steers under two years
- heifers over two years
- steers over two years

This gives `6 DxD + 6 DxB + 6 BxB = 18` distinct pre-adult cohorts. They are never collapsed to a single generic young-stock ratio in the study audit.

DxD and DxB cohorts use dairy cows as their parent adult population. BxB cohorts use suckler cows. Bulls remain the twenty-first cattle cohort and respond to the combined adult-cow signal, but the publication-facing parent/follower dependency audit is deliberately the 18 pre-adult cohorts.

## Simple ED adult-to-cohort ripple

If an ED contains the relevant parent adults, each individual follower cohort uses that ED's own realised adult reduction rate:

`FollowerReductionRate(e,k) = AdultReduction(e,origin(k)) / BaselineAdult(e,origin(k))`

and:

`FollowerReduction(e,k) = BaselineFollower(e,k) * FollowerReductionRate(e,k)`

which is exactly equivalent to:

`FollowerReduction(e,k) = AdultReduction(e,origin(k)) * BaselineFollower(e,k) / BaselineAdult(e,origin(k))`

Therefore every ED preserves its own observed adult-to-cohort relationship as its parent population contracts. The calculation is done separately for all 18 pre-adult cohorts.

## Orphan / receiver ED x cohort cases

Orphan status belongs to an **ED x cohort relationship**, not automatically to an entire ED. An ED may contain one young-stock cohort without its corresponding parent adults while containing normal parent/follower relationships for other cohorts.

If cohort k is present but the relevant parent adults are absent in that ED, the row is a receiver/orphan relationship for that cohort. It is not frozen during a cattle reduction.

Its baseline relationship is recorded relative to the relevant parent adults elsewhere in the same county:

`OrphanRatio(e,k) = BaselineFollower(e,k) / CountyBaselineAdult(origin(k))`

When the county parent-adult population contracts:

`OrphanReduction(e,k) = CountyAdultReduction(origin(k)) * OrphanRatio(e,k)`

which is equivalent to:

`OrphanReduction(e,k) = BaselineFollower(e,k) * CountyAdultReductionRate(origin(k))`

Therefore a receiver ED loses young stock when the breeding-cow population supplying that county falls. No arbitrary 30%, 50% or other spillover factor is imposed. The observed baseline orphan-cohort-to-county-adult relationship determines the size of the ripple.

Only if a cohort exists in a county with no corresponding parent adults at all is the national adult reduction rate used as a fallback.

The model records the source as:

- `LOCAL_ED`
- `COUNTY_RECEIVER`
- `NATIONAL_ORPHAN`
- `NONE`

## ED relationship and scenario audit tables

`build_18_cohort_dependency_audit()` records one baseline row for every ED x 18 pre-adult cohort, including:

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

`build_scenario_cohort_audit()` then adds one row per ED x milestone x 18 cohorts with:

- previous cohort head
- incremental reduction
- cumulative reduction
- scenario cohort head
- applied reduction rate
- applied signal source
- the corresponding fixed baseline ED/cohort relationship

These are transparent accounting relationships. They are not claimed to be observed animal-movement links.

## Cattle-only study scenarios

The study-facing interface keeps sheep fixed and supports:

- dairy-only reduction
- suckler-only reduction
- combined dairy + suckler reduction
- reproducible randomised spatial-incidence sensitivity for the same national endpoint

The same engine works from a 2020 or 2025 starting state and for any endpoint reduction fraction.

## Standard Output is downstream

Standard Output is calculated only after the physical cattle state has been solved. It reports fixed-2020 production-value exposure and never drives animal allocation. The historical baseline produced by `goblin-spatial build` therefore does not require Standard Output fields.

## Grassland release requires authoritative GOBLIN feed controls

The solved cattle pathway, with unchanged sheep context, can be passed to GOBLIN pasture/feed accounting:

`scenario livestock -> pasture dry-matter demand -> required grassland -> potential spared grassland`

The validated ED `ALL_GRASSLAND` remains the controlling land total. Potential spared grassland and any additional grassland requirement are reported separately.

The study workflow deliberately refuses to invent pasture-DM coefficients. A grassland-release run must receive a complete year x 31-cohort pasture-DM control table derived from upstream GOBLIN animal/feed definitions. Without that table the scenario still runs through livestock, the 18-cohort audit and Standard Output, but it stops before claiming spared hectares.

## Alternative land opportunity

Potential release is not automatic land-use conversion:

`PotentialRelease != Opportunity != RealisedConversion`

ED soil and forest context are attached only if the user requests an alternative-land allocation after potential release has been calculated. Land-use shares are explicit user/policy assumptions and default to zero.

## Reproducible command-line workflow

Build the historical baseline only:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Run a cattle scenario from the existing baseline:

```bash
goblin-spatial scenario \
  --baseline-year 2020 \
  --target-year 2050 \
  --dairy-reduction 0.30 \
  --suckler-reduction 0.30
```

Or build and run in one command:

```bash
goblin-spatial run-all \
  --baseline-year 2020 \
  --target-year 2050 \
  --dairy-reduction 0.30 \
  --suckler-reduction 0.30
```

A scenario writes:

- `scenario_schedule.csv`
- `scenario_national_summary.csv`
- `scenario_ed_results.csv`
- `baseline_ed_18_cohort_relationships.csv`
- `scenario_ed_18_cohort_audit.csv`

If no authoritative pasture-DM control table is supplied, no spared-grassland result is produced. This is a deliberate scientific guardrail rather than a missing default.
