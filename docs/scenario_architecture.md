# GOBLIN-Spatial scenario architecture

## Core principle

GOBLIN determines the national pathway. GOBLIN-Spatial does not construct a new ED livestock population from scratch. It starts from the selected validated ED baseline (2020 or 2025), subtracts the national change required by the GOBLIN pathway from animals already present, propagates the associated biological cohort response through ED and within-county livestock geography, and then evaluates production exposure, livestock pressure, potential land release and downstream land-use opportunity.

For livestock category k at milestone t:

NationalReduction(k,t) = NationalBaseline(k) - GOBLINTarget(k,t)

At ED level:

Scenario(e,k,t) = PreviousState(e,k,t-1) - IncrementalReduction(e,k,t)

and, relative to the original selected baseline:

CumulativeReduction(e,k,t) = Baseline(e,k) - Scenario(e,k,t)

This distinction between incremental and cumulative reduction is required for a coherent transition pathway.

## National pathway and milestones

Direct GOBLIN national values for 2030, 2040 and 2050 are always preferred when available. If GOBLIN supplies only a 2050 endpoint, GOBLIN-Spatial may construct explicit intermediate targets as a transparent scenario assumption. The default fallback is linear interpolation:

N(k,t) = N(k,base) + lambda(t) * [N(k,2050) - N(k,base)]

where:

lambda(t) = (t - base_year) / (2050 - base_year)

For a 2025 baseline, lambda is 0.20 in 2030, 0.60 in 2040 and 1.00 in 2050. For a 2020 baseline, it is 0.333, 0.667 and 1.00. Linear interpolation is a fallback, not a claim that the real transition must be linear. Front-loaded or back-loaded trajectories can later be implemented as sensitivity pathways.

Milestones are spatially cumulative. The 2040 state is produced by subtracting the additional 2030-to-2040 reduction from the 2030 ED state, and the 2050 state by subtracting the additional 2040-to-2050 reduction from the 2040 state. For a contraction pathway:

Baseline(e,k) >= Scenario(e,k,2030) >= Scenario(e,k,2040) >= Scenario(e,k,2050)

apart from categories explicitly allowed to expand. If a GOBLIN pathway includes expansion, that must use a separate expansion rule rather than forcing it through the reduction-only engine.

## Three independent scenario dimensions

Every spatial scenario state is identified by three dimensions:

S(p,r,t)

where p is the GOBLIN/net-zero pathway or accounting definition, r is the spatial allocation rule, and t is the milestone year. The national pathway determines the size and timing of adjustment. The allocation rule determines where the fixed adjustment occurs. Time determines how far along the transition the system has moved.

This separation is fundamental. Alternative allocation rules must never change the national GOBLIN target.

## Adult livestock allocation

At each milestone, GOBLIN supplies the national dairy-cow, suckler-cow and sheep target, or the corresponding reduction. GOBLIN-Spatial allocates only the additional reduction required since the previous milestone.

PRORATA assigns approximately equal proportional reductions across the existing footprint. DAIRY_PROTECTION gives EDs with larger baseline dairy herds a smaller proportional dairy reduction, transferring more of the fixed national burden to lower-dairy EDs. PRODUCTIVITY_PROTECTION protects EDs with higher pre-scenario productivity. VULNERABILITY_PROTECTION protects EDs with higher pre-scenario vulnerability. HYBRID_BALANCED combines specified protection objectives. SCORE_WEIGHTED accepts another pre-scenario protection score for study-specific analyses.

All protection scores are fixed from the selected baseline or other pre-scenario information. They are not recalculated from scenario outcomes, avoiding circular allocation.

For every rule:

sum_e IncrementalReduction(e,k,t) = NationalTarget(k,t-1) - NationalTarget(k,t)

No ED can lose more animals than it currently contains and no rule may seed livestock into an ED where the category is absent unless an explicit expansion model is being run.

## Adult and cohort response are one herd adjustment

Adult cows and young cattle are not treated as independent reductions. A milestone represents a coherent herd state. The adult change and the associated follower response are therefore propagated together, although this does not imply that biological turnover occurs literally instantaneously within a year.

For breeding ED e, the first spatial signal is the ED's own baseline adult-to-cohort relationship. Conceptually:

DeltaDxD(e) ~= DeltaDairy(e) * r_DxD(e)

DeltaDxB(e) ~= DeltaDairy(e) * r_DxB(e)

DeltaBxB(e) ~= DeltaSuckler(e) * r_BxB(e)

with analogous age-sex relationships and bulls linked to the relevant adult-cow structure. These are marginal spatial-response relationships, not independent national biological coefficients.

ED heterogeneity is retained. Two EDs losing the same number of dairy cows can generate different DxD and DxB responses because their baseline herd structures differ.

## ED first, county second

The first response is always within the ED. However, some EDs function mainly as receiver, rearing or finishing locations and may contain substantial young stock despite having few or no corresponding adult cows. These EDs must not be protected accidentally simply because the parent animals are located elsewhere.

County is therefore used as the operational livestock-movement pool after the direct ED response. The core model assumes that unresolved breeding-to-rearing spatial separation is handled within the same county. This is a modelling boundary, not a claim that real cattle never cross county borders. Cross-county movement can later be tested as a sensitivity if movement data justify it.

The spatial hierarchy is:

ED direct adult-cohort response -> within-county breeder/receiver/rearing/finishing adjustment -> sparse orphan handling -> national accounting closure.

County context is a movement/rearing bridge, not a substitute for ED biology and not a county-average fallback that makes every ED eligible for every cohort.

Receiver/rearing reductions are allocated from cohorts already present in those EDs. Scenario cohort counts therefore remain baseline-relative:

ScenarioCohort(e,k,t) = PreviousCohort(e,k,t-1) - IncrementalCohortReduction(e,k,t)

## National GOBLIN/COHORTS control

GOBLIN/COHORTS remains the authority for the national 21-cohort cattle structure. ED relationships generate the spatial response; national cohort controls validate and reconcile that response.

For every cattle cohort k and milestone t:

sum_e ScenarioCohort(e,k,t) = GOBLINScenarioCohort(k,t)

Reconciliation should preserve the ED-first and county-second support structure. National closure must not be interpreted as unconstrained movement of animals between distant counties. Integer residuals and sparse orphan cases are resolved within biologically and spatially eligible support wherever possible.

Sheep follows the same principle using the 10 GOBLIN sheep cohorts: ED flock structure first, county support where required, exact national cohort closure last.

## Scenario livestock output

Each ED-year-pathway-rule record should preserve the baseline and report both incremental and cumulative change. Core identifiers are:

PATHWAY
NET_ZERO_DEFINITION
ALLOCATION_RULE
BASELINE_YEAR
MILESTONE_YEAR
CSOED
County

For each livestock category and cohort the output should contain:

BASE_<CATEGORY>
PREVIOUS_<CATEGORY>
INCREMENTAL_REDUCTION_<CATEGORY>
CUMULATIVE_REDUCTION_<CATEGORY>
SCENARIO_<CATEGORY>

This makes it possible to distinguish what changed during 2030-2040 from what has changed in total since the selected baseline.

## Livestock pressure and LSU

Once the complete scenario herd is closed, scenario LSU is calculated from the scenario livestock structure:

ScenarioLSU(e,t) = sum_k ScenarioAnimal(e,k,t) * LSUCoefficient(k)

CumulativeLSUReduction(e,t) = BaselineLSU(e) - ScenarioLSU(e,t)

The land module must use the fully reconciled scenario herd, not adult reductions alone.

## Intensity and potential grassland release

Livestock reduction does not imply an identical proportional land reduction. Land requirement depends on scenario livestock pressure and the assumed productivity/intensity of retained agricultural land.

A transparent formulation is:

BaselineStockingPressure(e) = BaselineLSU(e) / BaselineAgriculturalGrassland(e)

ScenarioRequiredGrass(e,t) = ScenarioLSU(e,t) / [BaselineStockingPressure(e) * IntensityMultiplier(e,t)]

PotentialReleasedGrassland(e,t) = max(0, BaselineAgriculturalGrassland(e) - ScenarioRequiredGrass(e,t))

with ScenarioRequiredGrass capped to physically feasible agricultural grassland. IntensityMultiplier = 1 represents unchanged baseline pressure; values above 1 represent explicitly assumed intensification of the retained livestock land. Intensification is always a scenario assumption and must never be introduced silently.

The land base should be the validated agricultural grassland within the GOBLIN-Spatial land accounting, not generic physical grass cover.

Potential released grassland is not automatically abandoned, converted or available. It is land no longer required to support the modelled livestock pressure under the stated assumptions.

## Standard Output exposure

Standard Output is calculated after the scenario livestock population has been established.

BaselineSO(e) = sum_k BaselineActivity(e,k) * SOCoefficient(k)

ScenarioSO(e,t) = sum_k ScenarioActivity(e,k,t) * SOCoefficient(k)

LivestockSOLoss(e,t) = BaselineSO(e) - ScenarioSO(e,t)

SO is an agricultural production-value/exposure metric, not profit, disposable income or welfare. Income, labour and capital exposure from FADN/IFS-type evidence should remain separate economic modules. Coefficients mapped from regional or system-level evidence must be labelled as mapped/imputed rather than directly observed ED economics.

## Land opportunity before realised allocation

Potential land release is followed by a suitability/opportunity screen based on soil, land capability, organic-soil status, drainage and other relevant spatial constraints. Candidate outputs may include forestry opportunity, nature/restoration opportunity, rewetting opportunity, cropland opportunity, AD-grass opportunity and retained low-intensity grassland.

PotentialRelease != Opportunity != RealisedConversion

Opportunity layers may overlap because one hectare can initially be suitable for more than one use. They must not be summed as mutually exclusive hectares until an explicit land-allocation step is applied.

## GOBLIN land-use targets remain national controls

Where a GOBLIN pathway already specifies national afforestation, rewetting, AD-grass, cropland or other land-use deployment, GOBLIN-Spatial should spatialise those national targets across eligible opportunity land rather than invent a new national land-use total.

The logic is therefore parallel to livestock:

GOBLIN national land-use target -> GOBLIN-Spatial opportunity/eligibility -> spatial allocation across released/eligible ED land -> exact national land-use closure.

If no national deployment target exists, GOBLIN-Spatial should report opportunity only and should not label opportunity hectares as realised conversion.

## Final experiment structure

The full experiment is:

GOBLIN/net-zero definition
-> national 2030/2040/2050 livestock pathway
-> selected 2020 or 2025 ED baseline
-> spatial allocation rule
-> incremental ED adult reduction
-> simultaneous ED adult/cohort response
-> within-county receiver/rearing/finishing adjustment
-> exact national 21-cattle + 10-sheep cohort closure
-> scenario LSU
-> Standard Output exposure
-> intensity/productivity assumption
-> potential agricultural grassland release
-> soil/land-capability opportunity screen
-> spatialisation of any GOBLIN national land-use targets
-> ED, county, regional and national transition outputs.

The central analytical distinction remains: the GOBLIN/net-zero definition determines how much national adjustment is required, while the allocation rule determines who and where bears that adjustment. The resulting spatial pattern then determines cohort incidence, production exposure, livestock-pressure release and the geography of alternative land-use opportunity.
