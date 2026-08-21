# Explicit cumulative land-use target allocation

The policy-neutral opportunity envelope deliberately stops before land conversion. When a study or policy pathway supplies explicit national hectare targets, GOBLIN-Spatial can then allocate those requested hectares across EDs without inventing land-use shares.

## Target table

Use a CSV with one row per scenario milestone and cumulative national hectare targets:

```text
MILESTONE_YEAR,FOREST_HA,REWETTING_HA,AD_GRASS_HA,WILLOW_HA,ENERGY_GRASS_HA,NATURE_HA
2030,...
2040,...
2050,...
```

Targets must be non-negative and non-decreasing through time for each land use. The target years must match the cattle scenario milestones exactly. `configs/land_use_targets_template.csv` provides a zero-target schema and therefore makes no policy assumption.

## Allocation rule

At each milestone, the model tries to reach the supplied cumulative national target for each land use. Allocation is spatially weighted by the ED opportunity score and cannot exceed the ED's currently unallocated `POTENTIAL_SPARED_GRASSLAND_HA`.

Previously allocated hectares remain allocated. Earlier unmet target is carried forward and may be filled later if additional eligible spared land becomes available. If the target still cannot be reached because spared land or eligible capacity is insufficient, the shortfall is reported explicitly and is not forced into an ineligible ED.

Land uses are mutually exclusive in this allocation stage. The default priority is:

`REWETTING -> FOREST -> AD_GRASS -> WILLOW -> ENERGY_GRASS -> NATURE`

Priority is an explicit scenario choice and can be changed at the command line.

## Command

```bash
goblin-spatial allocate-land \
  --scenario-ed-results data/processed/scenarios/D30_S30_FROM_2020/scenario_ed_results.csv \
  --soil-profile data/controls/soil/ED_GOBLIN_soil_profile.csv.xz \
  --targets path/to/land_targets.csv
```

The command writes:

- `scenario_ed_land_target_allocation.csv`
- `scenario_national_land_target_allocation.csv`
- `land_use_targets_applied.csv`

For every land use and milestone the outputs retain the requested cumulative target, cumulative hectares actually allocated, and cumulative unmet target. `RETAINED_SPARED_GRASSLAND_HA` is the portion of potential release not yet allocated to an alternative use at that milestone.

The accounting identity is checked in every ED and milestone:

`sum(cumulative alternative-land hectares) + retained spared grassland = potential spared grassland`

This stage therefore preserves the study boundary:

`PotentialRelease -> Opportunity -> ExplicitTargetAllocation`

It does not claim parcel-level suitability and does not infer policy targets from the livestock scenario.
