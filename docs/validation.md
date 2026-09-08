# GOBLIN-Spatial validation

Validation is designed around protected scientific boundaries rather than visual agreement with expected maps.

The development rule is:

> **Software structure may improve, but scientific mathematics must not change silently.**

## Historical baseline

The validated historical panel covers 2,857 EDs for 2015-2025.

Core identities include:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

The 2020 ED baseline is locked as the principal fine-scale spatial anchor. Surrounding years are controlled reconstructions using repeated official higher-level statistics.

## SC1 validation

SC1 must preserve the national GOBLIN pathway while resolving its geography.

For every authoritative livestock control supplied by the selected pathway:

```text
sum_e scenario_livestock[e,k] = national_target[k]
```

For released land:

```text
sum_e GOBLIN_RELEASED_GRASSLAND_HA[e]
    = authoritative national gross release
```

and for every ED:

```text
0 <= GOBLIN_RELEASED_GRASSLAND_HA[e] <= ALL_GRASSLAND[e]
```

The independent pasture-DM diagnostic is checked separately and is not rescaled to the parent release.

### Soil/LPIS invariance

A protected regression test deliberately changes downstream mapped-soil and LPIS fields and verifies that the SC1 released-land vector is unchanged.

This is a causal-boundary test:

```text
change soil / LPIS evidence
        ↓
SC1 livestock and released-land geography must remain identical
```

## SC2 validation

SC2 may characterise the frozen release but may not change it.

For every ED:

```text
sum_s ReleasedPhysicalResource[e,s]
    = GOBLIN_RELEASED_GRASSLAND_HA[e]
```

The seven mapped physical-soil shares must close to one and all physical-resource areas must be finite and non-negative.

The frozen soil and LPIS controls must:

- cover the same 2,857-ED universe;
- contain unique canonical ED keys;
- match the frozen SHA-256 values;
- use the validated 2020 context year.

Eligibility controls must explicitly cover every required future use × soil-class combination and contain only finite coefficients in `[0,1]`. Rewetting is rejected from the generic soil-only eligibility matrix.

## SC3 validation

SC3 treats released land as a finite shared resource.

For every ED × physical-resource cell:

```text
sum_u allocation[e,s,u] <= released_resource[e,s]
```

For every national use target:

```text
Realised_u + Unmet_u = Target_u
```

The allocator must never create negative allocation, exceed physical released resource or double-count the same hectare across competing uses.

A positive rewetting target requires an explicit validated capacity control. Mapped peat alone cannot create rewetting capacity.

## Post-SC3 flexibility validation

Alternative feasible geographies must preserve the same realised national end-use vector as the reference SC3 solution.

For every use `u`:

```text
sum_e AlternativeAllocation[e,u]
    = sum_e ReferenceAllocation[e,u]
```

while retaining the same physical-resource and eligibility constraints.

Exact ED-use minimum/maximum bounds are therefore interpreted within the same national realised outcome, not as different scenarios.

## Scenario isolation

Scenario IDs are hard boundaries. Livestock endpoints, target livestock-land area and future land-use requirements for one pathway must never be combined with another pathway.

The scenario-control loader and reconciliation tests enforce this boundary.

## Repository-contained input verification

`data_manifest.yaml` is the machine-readable authority for frozen production inputs. `goblin-spatial fetch-data --verify-only` verifies required repository files and checksums rather than downloading or rebuilding model inputs.

## Continuous integration

The CI workflow covers:

- Python compilation;
- repository input verification;
- frozen 2020 soil + LPIS context checks;
- historical baseline unit tests;
- complete 2015-2025 regression;
- SC1 endpoint, release, comparison and metric tests;
- SC2 physical-resource and eligibility tests;
- SC3 finite-resource and feasible-geography tests;
- canonical baseline rebuild;
- real end-to-end SC1;
- real end-to-end SC2 physical-resource preparation.

A real SC3 publication run is deliberately not fabricated in CI because SC3 requires an explicit scientifically approved eligibility control and, where relevant, rewetting-capacity evidence.

## Interpretation of validation

Exact closure validates accounting, reconciliation and implementation boundaries. It is not independent empirical validation of every reconstructed non-2020 ED value, nor does it validate actual future farmer behaviour.

The model should fail transparently rather than silently continue when authoritative controls are internally impossible, required scientific evidence is absent or an accounting identity is violated.
