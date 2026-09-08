# Colm-direct SC2 physical-resource prototype

> **Status: historical prototype note.** This document records the first SC2-only Colm-direct experiment. The active migration has since expanded to a coherent SC1-SC3 architecture. The authoritative design for the migration branch is `docs/colm_direct_sc1_sc3_architecture.md`.

This prototype originally tested whether GOBLIN-Spatial could construct SC2 physical eligibility directly from Colm's mapped physical-soil evidence without requiring G1/G2/G3 as an intermediate classification.

The prototype's central scientific idea has been retained, but its original statement that SC1 and SC3 remain unchanged is no longer current. In the active Colm-direct migration:

- SC1 is soil-independent and spatialises the authoritative national GOBLIN release from the solved livestock/pasture-DM transition subject only to `ALL_GRASSLAND` capacity;
- SC2 characterises the frozen SC1 release using Colm physical soil plus LPIS agricultural context and applies only explicit, evidence-backed eligibility rules;
- SC3 allocates explicit GOBLIN land-use targets jointly over finite ED x Colm-soil resource cells and reports realised, unmet and residual land;
- legacy 08B/G1/G2/G3 remains available only as a benchmark/provenance implementation.

## Prototype scientific sequence

```text
frozen SC1 released land by ED
        -> Colm ED physical-soil shares
        -> proportional soil-resolved released-land resource
        -> explicit evidence-backed use-specific eligibility rules
        -> SC3 finite-resource allocation after validation
```

The physical-resource transformation remains:

```text
COLM_RELEASED_<SOIL>_HA
    = GOBLIN_RELEASED_GRASSLAND_HA
      * IFS_MAP_<SOIL>_SHARE
```

The resulting hectares are a proportional within-ED characterisation of the released-land resource. They do not identify observed released parcels or parcel-level soil provenance.

## No implicit capability classification

The Colm-direct chain does not derive or use G1/G2/G3. It retains the seven mapped physical categories:

- deep well drained
- shallow well drained
- poorly drained
- poorly drained peaty
- alluvium
- peat
- miscellaneous

The seven released-soil quantities must close exactly to the frozen SC1 released-land total in every ED.

## Eligibility rules

No tillage, willow, AD/biorefinery, forestry or rewetting suitability rule is silently hard-coded.

A Stage-A future-use rule must explicitly provide a coefficient for every Colm category, with a version identifier and evidence note. Missing categories, implicit defaults and out-of-range coefficients are rejected. Rewetting is excluded from soil-only eligibility because mapped peat is not equivalent to drained agricultural organic soil or rewettable capacity.

The retained distinction is:

```text
potential release
    != physical resource
    != eligibility
    != opportunity
    != realised conversion
```

## Current promotion criteria

The Colm-direct SC1-SC3 branch should not replace the frozen legacy production results until:

1. full automated tests pass;
2. SC1 soil-independence is verified;
3. every Stage-A eligibility rule has a documented scientific basis;
4. a validated drained-organic/agricultural rewetting-capacity control is supplied;
5. Colm-direct outputs are compared with the frozen 08B benchmark;
6. SC3 is rerun across the principal pathway/allocation matrix;
7. reporting, figures and manuscript results are regenerated and independently checked.

For current architecture and invariants, use `docs/colm_direct_sc1_sc3_architecture.md` rather than this historical note.
