# GOBLIN pathway authority and GOBLIN-Spatial transition accounting

## Purpose

GOBLIN-Spatial does not replace national GOBLIN. GOBLIN supplies the pathway quantities; GOBLIN-Spatial resolves where those quantities are represented and whether the associated land-use transformation is spatially feasible.

The controlling principle is:

> **GOBLIN determines the national pathway. GOBLIN-Spatial resolves its geography, incidence and spatial feasibility.**

## National authority

For every selected scenario, the scenario-control table supplies the authoritative quantities used by the spatial model, including:

- dairy and suckler endpoint;
- target livestock-land area;
- future national requirements for AD grass, biorefinery grass, willow, additional tillage, forest and rewetting;
- any additional total-cattle or exact cohort controls when explicitly available.

Scenario IDs must remain internally consistent. Livestock endpoints, land-release controls and future land-use targets from one scenario are never mixed with another scenario.

## Baseline and livestock transition

The historical reconstruction is independent of the scenario engine. A selected 2020 or 2025 livestock baseline is passed to SC1, but the national future endpoint is supplied by the same GOBLIN pathway in either case.

Adult dairy and suckler controls anchor the principal cattle transition. The remaining 21 cattle cohorts respond through the validated biological cohort structure and any explicit national controls. Sheep remain fixed unless an explicit pathway control changes that assumption.

National reconciliation is checked after spatialisation.

## Authoritative livestock-land release

The pathway target livestock-land area is the parent land control.

For a selected baseline:

```text
Gross livestock-land release
    = baseline ALL_GRASSLAND
      - pathway TARGET_LIVESTOCK_LAND_HA
```

That national quantity is frozen before spatialisation.

SC1 resolves where it falls using the solved livestock/pasture-DM transition signal, with `ALL_GRASSLAND` as the only ED land-capacity ceiling.

Soil, LPIS and future-use suitability do not determine:

- the national release total;
- livestock allocation;
- or the ED release vector.

The principal accounting variable is:

```text
GOBLIN_RELEASED_GRASSLAND_HA
```

and must satisfy:

```text
sum_e GOBLIN_RELEASED_GRASSLAND_HA[e]
    = authoritative national gross release
```

## Pasture-DM diagnostics are separate

The livestock cohort state also produces an independent pasture-demand land balance, including:

- `POTENTIAL_SPARED_GRASSLAND_HA`;
- `SIGNED_GRASSLAND_BALANCE_HA`;
- `ADDITIONAL_GRASSLAND_REQUIRED_HA`.

These are diagnostics. They are not rescaled to become the authoritative national release and do not create a second land authority.

## SC2 authority boundary

Only after SC1 is frozen does the model attach:

- mapped physical soil and drainage classes;
- LPIS agricultural-use and management context;
- explicit evidence-backed future-use eligibility controls.

SC2 therefore asks what the frozen transition-space resource can plausibly support. It cannot change the livestock solution or the amount/location of released land.

The scientific distinction is:

```text
Release
    != Physical resource
    != Eligibility
    != Opportunity
    != Allocation
    != Adoption
```

## SC3 authority boundary

SC3 consumes the future land-use requirements from the **same GOBLIN scenario** and tests them against finite eligible released land.

For every use:

```text
Realised_u + Unmet_u = Target_u
```

A target is not forced into spatially ineligible land. Unmet hectares are a model result.

The five principal competing uses are AD grass, biorefinery grass, willow, additional tillage and forest. They share the same finite released-resource cells, so a hectare can be allocated only once.

Rewetting is treated separately because mapped peat is not equivalent to drained agricultural organic soil. A positive rewetting target therefore requires independently validated capacity evidence.

## GOBLIN `Available` is not gross release

The parent GOBLIN `Available` residual must remain distinct from gross livestock-land release.

Gross release is the transition-space budget created by the livestock-land change. `Available` is a residual after pathway land-use claims are accounted for at national level.

GOBLIN-Spatial therefore never uses `Available` as the national release control.

## Post-SC3 spatial flexibility

A feasible SC3 allocation is not automatically a unique geography. The optional flexibility analysis holds the realised national hectares of every end use fixed and asks whether alternative feasible spatial configurations exist under the same frozen resource and eligibility constraints.

This distinguishes spatially necessary locations from interchangeable ones without changing the national pathway.

## National reconciliation

`build_goblin_reconciliation()` audits externally supplied national controls against the ED spatial sums for the quantities available in the selected pathway.

The model should fail rather than silently continue when an authoritative upstream control is internally impossible or when accounting closure is violated.
