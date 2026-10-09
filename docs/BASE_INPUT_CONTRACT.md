# Canonical biological baseline contract

GOBLIN-Spatial has a fixed livestock input order. This is the biological
foundation that all later spatial, economic and environmental layers must use.

## 1. CSO-13 statistical state

The first canonical product is:

`CSO_13_Cohort_Annual_Panel_2015_2025`

on the `YEAR x CSOED` backbone.

It contains 13 atomic livestock groups:

### Cattle, 9 groups

1. DAIRY_COW
2. OTHER_COW
3. BULLS
4. CATTLE_MALE_UNDER_1
5. CATTLE_FEMALE_UNDER_1
6. CATTLE_MALE_1_2
7. CATTLE_FEMALE_1_2
8. CATTLE_MALE_2_PLUS
9. CATTLE_FEMALE_2_PLUS

### Sheep, 4 groups

10. EWES_2_PLUS
11. EWES_UNDER_2
12. RAMS
13. OTHER_SHEEP

This is the statistical livestock state. It contains no DxD/DxB/BxB genetics
and no lowland/upland sheep-system subdivision.

## 2. GOBLIN-31 biological state

The second canonical product is:

`GOBLIN_31_Cohort_Annual_Panel_2015_2025`

on exactly the same `YEAR x CSOED` backbone.

It expands the CSO state into:

- 21 cattle cohorts;
- 10 sheep cohorts.

The 21 cattle cohorts comprise adult dairy cows, suckler cows and bulls plus
18 follower cohorts split by parental origin (DxD, DxB, BxB), sex and age.

The 10 sheep cohorts preserve the CSO sheep controls while introducing the
GOBLIN lowland/upland production-system structure.

The CSO-13 fields remain in the GOBLIN-31 product as `CSO_` control columns,
so the biological expansion can always be reconciled back to the statistical
input state.

## Required model order

The model contract is:

```text
CSO-13 statistical livestock state
        ↓
GOBLIN-31 biological expansion
        ↓
land and farm structure
        ↓
Standard Output
        ↓
county / WFD / GOBLIN-compatible catchment / national reporting
        ↓
livestock signatures and other synthesis layers
        ↓
optional reference modules such as LCAD, InformBio or human-edible protein
```

Later layers may add variables, indicators or alternative reporting views.
They must not redefine the CSO-13 or GOBLIN-31 livestock populations.

## Existing integrity conditions

The production code already checks that:

- the 9 CSO cattle groups sum to TOTAL_CATTLE;
- the 4 CSO sheep groups sum to TOTAL_SHEEP;
- 2020 matches the prepared CSO Census anchor;
- the 21 GOBLIN cattle cohorts close back to CSO cattle;
- the 10 GOBLIN sheep cohorts close back to CSO sheep;
- the CSO control columns in the 31-cohort product are identical to the
  corresponding 13-group product.

`src/goblin_spatial/baseline_contract.py` now exposes this as a single
canonical contract for downstream code and tests.
