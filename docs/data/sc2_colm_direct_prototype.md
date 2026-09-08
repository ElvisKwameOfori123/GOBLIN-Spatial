# Colm-direct SC2 physical-resource prototype

This prototype tests whether GOBLIN-Spatial can construct SC2 physical eligibility directly from Colm's mapped physical-soil evidence without requiring G1/G2/G3 as an intermediate classification.

It is intentionally parallel to the frozen production SC2 v3.1 path. It does not alter SC1, SC3 or the current manuscript results.

## Scientific sequence

```text
frozen SC1 released land by ED
        -> Colm ED physical-soil shares
        -> proportional soil-resolved released-land resource
        -> explicit evidence-backed use-specific eligibility rules
        -> future SC3 interface after validation
```

The Stage-1 transformation is source-grounded:

```text
COLM_RELEASED_<SOIL>_HA
    = GOBLIN_RELEASED_GRASSLAND_HA
      * IFS_MAP_<SOIL>_SHARE
```

The resulting hectares are a proportional within-ED characterisation of the released-land resource. They do not identify observed released parcels.

## No implicit capability classification

The prototype does not derive or use G1/G2/G3. It retains the seven Colm mapped categories:

- deep well drained
- shallow well drained
- poorly drained
- poorly drained peaty
- alluvium
- peat
- miscellaneous

The seven released-soil quantities must close exactly to the frozen SC1 released-land total in each ED.

## Eligibility rules

No tillage, willow, AD/biorefinery, forestry or rewetting rule is hard-coded at this stage.

A future-use rule must explicitly provide one coefficient in the range 0-1 for every Colm category. The rule application also requires a version identifier and evidence note. Missing categories, implicit defaults and out-of-range coefficients are rejected.

This design separates:

```text
source evidence -> physical resource -> modelling rule -> eligible capacity
```

and prevents a provisional scientific assumption from silently becoming part of the production model.

## Promotion criteria

The Colm-direct path should not replace production SC2 until:

1. every use-specific soil rule has a documented scientific basis;
2. rule coefficients and exclusions are reviewable in a versioned control table;
3. national and ED-level capacity diagnostics are checked;
4. LPIS and other non-soil opportunity evidence are integrated separately where required;
5. results are compared with the frozen SC2 v3.1 benchmark;
6. SC3 feasibility and headline manuscript outputs are revalidated.

Until those conditions are met, the existing production SC1-SC3 path remains authoritative.
