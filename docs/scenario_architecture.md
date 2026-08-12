# GOBLIN-Spatial scenario architecture

## Principal study design

The principal GOBLIN-Spatial scenario is a **single configurable net-zero livestock-reduction experiment**. It is not organised around Policy, SplitGas, AllGas or other pathway labels.

The user selects:

- the immutable ED baseline year: `2020` or `2025`;
- the net-zero target year;
- the dairy-cow reduction fraction;
- the suckler-cow reduction fraction;
- the sheep reduction fraction.

Changing those controls and rerunning the model must be sufficient to produce a new spatial scenario. The validated baseline is never rewritten.

The principal interface is:

```python
run_net_zero_scenario(
    panel,
    baseline_year=...,
    target_year=...,
    dairy_reduction=...,
    suckler_reduction=...,
    sheep_reduction=...,
)
```

The lower-level pathway/allocation modules remain in the repository as experimental/general infrastructure, but they are not the principal study definition.

## Fixed starting state

GOBLIN-Spatial contains validated annual ED states and allows the scenario study to begin from either 2020 or 2025.

`Baseline(e,k) = validated observed/reconstructed activity for ED e and livestock class k in the selected baseline year`

The selector only chooses the starting state. It does not smooth, redistribute or otherwise alter it.

A 2020 scenario and a 2025 scenario therefore begin from different observed/reconstructed livestock geographies, but within any single run the selected baseline is fixed.

## Adult cattle reductions are the scenario controls

The core cattle assumptions are reductions in the adult breeding populations:

- dairy cows;
- suckler cows.

For adult class k:

`NationalReduction(k) = round(BaselineNationalTotal(k) * ReductionFraction(k))`

The principal engine distributes that reduction pro-rata across the existing ED adult footprint and subtracts it from the baseline:

`ScenarioAdult(e,k) = BaselineAdult(e,k) - AdultReduction(e,k)`

No livestock is seeded into an ED where the relevant adult class was absent.

The important modelling choice is that **young cattle do not receive independently invented national reduction assumptions**. Their response follows from the adult reduction and the observed ED cohort structure.

## Adult and young cattle are one herd adjustment

Each validated ED already contains its own relationship between adult breeding stock and young/follower cohorts. The net-zero engine preserves that heterogeneity.

For an active breeding ED:

`FollowerReductionRate(e,k) = AdultReduction(e,origin(k)) / BaselineAdult(e,origin(k))`

and the continuous implied follower reduction is:

`ImpliedFollowerReduction(e,k) = BaselineFollower(e,k) * FollowerReductionRate(e,k)`

which is algebraically equivalent to:

`AdultReduction(e,origin(k)) * BaselineFollower(e,k) / BaselineAdult(e,origin(k))`

Thus changing one adult reduction assumption automatically changes the associated young cattle throughout the model.

The origin logic is:

- DxD and DxB followers respond to the dairy-cow reduction signal;
- BxB followers respond to the suckler-cow reduction signal;
- bulls respond to the combined adult-cow reduction signal.

The integer scenario closes to the rounded sum of these ED-level implied reductions. There is no separate external national target for every young cohort in the principal net-zero engine.

## Breeding, rearing and finishing geography

The baseline livestock geography can separate breeding from rearing/finishing activity. An ED may therefore contain young cattle even when it contains few or no corresponding breeding cows. Such an ED must not be frozen simply because its local adult denominator is zero.

The response hierarchy is:

`local breeding ED -> same-county receiver/rearing/finishing ED -> national orphan fallback`

1. **Local breeding ED**: use its own realised adult reduction rate.
2. **Same-county receiver/rearing/finishing ED**: when the follower cohort exists but the matching adult class is absent locally, inherit the realised reduction rate of the corresponding breeding adults in that county.
3. **National orphan fallback**: only when the follower cohort exists in a county with no corresponding breeding adults at all, use the national adult reduction rate.

The model records the signal source for every follower cohort as `LOCAL_ED`, `COUNTY_RECEIVER`, `NATIONAL_ORPHAN` or `NONE` so this behaviour is auditable.

This structure allows finishing/rearing locations to contract when the breeding stock supplying the production chain contracts, while still preserving local and county livestock geography.

## Sheep

The current principal control is a reduction fraction applied to `TOTAL_SHEEP`. The resulting ED total-sheep reduction is disaggregated through the existing ten GOBLIN sheep cohorts in proportion to the cohorts already present in each ED. This preserves local lowland/upland and age structure and does not invent separate national young-sheep targets.

If the study later fixes a specifically ewe-led sheep mechanism, that should be introduced explicitly rather than silently changing the meaning of the current `sheep_reduction` control.

## Complete livestock state

The scenario therefore produces a full baseline and scenario state for:

- 21 cattle cohorts;
- 10 sheep cohorts;
- 31 livestock cohorts in total.

For cattle cohort k:

- `BASE_COHORT_k`
- `REDUCTION_COHORT_k`
- `SCENARIO_COHORT_k`
- `REDUCTION_SIGNAL_k`
- `REDUCTION_SIGNAL_SOURCE_k`

For sheep cohort k:

- `BASE_SHEEP_COHORT_k`
- `REDUCTION_SHEEP_COHORT_k`
- `SCENARIO_SHEEP_COHORT_k`

Every scenario count obeys:

`Scenario = Baseline - Reduction`

and no scenario cohort may become negative.

## Parameter reaction is the central scenario test

The scenario engine must satisfy a simple reaction property:

- hold the baseline fixed;
- change one adult reduction parameter;
- the corresponding adult scenario changes;
- related follower cohorts change automatically;
- unrelated livestock groups remain unchanged unless their own control changes.

For example, increasing only the dairy-cow reduction must reduce dairy cows and dairy-origin DxD/DxB followers, including same-county finishing/rearing EDs, while BxB cohorts remain unchanged when the suckler reduction remains unchanged.

This is tested directly in `tests/test_net_zero.py`.

## Standard Output is downstream

Standard Output is evaluated only after the physical 31-cohort scenario has been solved:

`BaselineSO(e) = sum_k BaselineActivity(e,k) * SOCoefficient(e,k)`

`ScenarioSO(e) = sum_k ScenarioActivity(e,k) * SOCoefficient(e,k)`

`SOExposure(e) = BaselineSO(e) - ScenarioSO(e)`

Changing an SO coefficient must never change livestock numbers. Changing a livestock scenario parameter can change SO because the underlying physical activities change.

SO is production-value exposure, not farm income, profit or welfare.

## LSU is a diagnostic, not the land-release equation

Scenario LSU may be calculated from the reconciled livestock state for reporting and stocking-pressure diagnostics. It is not the primary spared-grassland equation.

GOBLIN-Spatial follows the feed-balance sequence:

`31-cohort livestock population -> pasture dry-matter demand -> effective grass supply -> required grassland`

For ED e:

`PastureDM(e) = sum_k Population(e,k) * PastureDMPerHead(k)`

The selected baseline is calibrated as the fixed point:

`BaselineEffectiveSupply(e) = BaselinePastureDM(e) / BaselineGrassland(e)`

Then:

`ScenarioRequiredGrassland(e) = ScenarioPastureDM(e) / ScenarioEffectiveSupply(e)`

and:

`PotentialSparedGrassland(e) = max(0, BaselineGrassland(e) - ScenarioRequiredGrassland(e))`

If scenario demand exceeds the baseline land capacity, the model reports the additional grassland requirement rather than hiding it.

## Spared land is not automatic conversion

The analytical distinction remains:

`PotentialRelease != Opportunity != RealisedConversion`

A hectare no longer required for livestock feed is not automatically forestry, rewetting, cropland, bioenergy or nature land. Soil, capability and other suitability screening occurs only after potential release has been calculated.

## Principal workflow

```text
validated annual ED panel
        |
        +--> choose baseline year: 2020 or 2025
        |
        +--> edit net-zero controls
             - dairy reduction
             - suckler reduction
             - sheep reduction
             - target year
        |
        +--> pro-rata adult livestock reduction from existing ED footprint
        |
        +--> ED adult-to-young cohort response
        |
        +--> same-county rearing/finishing response
        |
        +--> national orphan fallback only where required
        |
        +--> complete 21 cattle + 10 sheep scenario
        |
        +--> Standard Output exposure
        |
        +--> pasture dry-matter demand
        |
        +--> required grassland
        |
        +--> potential spared grassland
        |
        +--> downstream land-opportunity screening
```

The principal study question is therefore not which named national policy pathway is chosen. It is how the validated Irish ED livestock system reacts spatially to a specified net-zero reduction in the adult livestock controls, given the observed breeding/rearing/finishing and cohort structure of each place.
