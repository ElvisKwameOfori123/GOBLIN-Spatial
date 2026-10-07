# GOBLIN-Spatial data dictionary

This document describes the principal variables exposed by the historical baseline, livestock signatures and multiscale reporting products. A complete column-by-column dictionary ships with the historical release bundle as `_columns` and `_columns.csv`.

## Core identifiers

| Variable | Meaning |
|---|---|
| `YEAR` | Calendar year in the 2015-2025 historical panel |
| `CSOED` | Harmonised Electoral Division identifier |
| `ED` / `EDNAME` | Electoral Division source code/name fields where available |
| `County` | County |

## Historical livestock

| Variable | Meaning |
|---|---|
| `DAIRY_COW` | Published/reconstructed dairy cows |
| `OTHER_COW` | Published/reconstructed other cows, represented biologically as suckler cows |
| `OTHER_CATTLE` | Other cattle before biological subdivision |
| `TOTAL_CATTLE` | Total cattle |
| `TOTAL_SHEEP` | Total sheep |

The GOBLIN livestock representation contains 21 cattle cohorts and 10 sheep cohorts. These sum exactly to `TOTAL_CATTLE` and `TOTAL_SHEEP` respectively for every ED-year.

The 21 cattle cohorts comprise adult dairy cows, suckler cows and bulls plus 18 follower cohorts defined by parental origin (DxD, DxB, BxB), sex and age.

## Farm structure

| Variable | Meaning |
|---|---|
| `AGRICULTURAL_HOLDINGS` | Number of agricultural holdings represented in the ED-year |
| `AVERAGE_SIZE_OF_HOLDINGS` | Average holding size, hectares |
| `AVERAGE_AGE_OF_HOLDER` | Mean holder age where reconstructed |
| `MEDIAN_AGE_OF_HOLDER` | Median holder age at ED scale |

The 2020 ED values are the local spatial anchor. Non-2020 values are reconstructed using documented higher-level temporal controls.

## Historical land

| Variable | Meaning |
|---|---|
| `AREA_FARMED` | Total agricultural area farmed, hectares |
| `ALL_GRASSLAND` | Grassland area, hectares |
| `TOTAL_CEREALS` | Total cereal area, hectares |
| `OTHER_CROPS_HA` | Remaining crop/other agricultural land after reconciliation, hectares |

Accounting identity:

```text
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

## Standard Output

The release contains livestock, crop and covered-total Standard Output components derived from fixed 2020 coefficients.

Standard Output is interpreted as a **production-value exposure indicator**. It is not profit, household income, welfare, compensation need or land value.

## Reporting geographies

Principal geography identifiers include:

| Variable | Meaning |
|---|---|
| `WFD_CATCHMENT_ID` | Official WFD catchment identifier |
| `WFD_CATCHMENT` | Official WFD catchment name |
| `COLM_CATCHMENT` | 37-unit GOBLIN-compatible catchment name |
| `GEOGRAPHY_TYPE` | Geography represented in signature tables, e.g. ED, county, WFD catchment or Ireland |
| `GEOGRAPHY_ID` | Identifier for the represented geography |
| `GEOGRAPHY_NAME` | Display name for the represented geography |

Additive quantities are summed. Ratios are recomputed from aggregated numerators and denominators.

## Livestock signatures

Principal signature fields include:

| Variable | Meaning |
|---|---|
| `DAIRY_SHARE_ADULT_PCT` | Dairy cows as a percentage of adult cows |
| `DXD_SHARE_FOLLOWERS_PCT` | DxD followers as a percentage of all followers |
| `DXB_SHARE_FOLLOWERS_PCT` | DxB followers as a percentage of all followers |
| `BXB_SHARE_FOLLOWERS_PCT` | BxB followers as a percentage of all followers |
| `FOLLOWER_TO_ADULT_RATIO` | Followers per adult cow |
| `CATTLE_PER_FARMED_HA` | Total cattle per farmed hectare |
| `SHEEP_PER_FARMED_HA` | Total sheep per farmed hectare |
| `GRASSLAND_SHARE_FARMED_PCT` | Grassland as a percentage of farmed area |
| `CEREAL_SHARE_FARMED_PCT` | Cereals as a percentage of farmed area |
| `SO_PER_FARMED_HA` | Covered fixed-2020 Standard Output per farmed hectare |
| `UPLAND_SHARE_SHEEP_PCT` | Mountain/upland-type sheep share |

The long signature table retains each ratio together with its numerator and denominator.

## Parent-follower relationship tables

| Variable | Meaning |
|---|---|
| `COHORT` | Follower or linked cattle cohort |
| `PARENT_POPULATION` | Biologically relevant adult-parent population |
| `FOLLOWER_PER_PARENT` | Follower-to-parent relationship where defined |
| `COHORT_SPATIAL_ROLE` | Finest spatial support class for the relationship |

Support classes are:

- `LOCAL_ED`: corresponding adult parents are present in the ED;
- `COUNTY_RECEIVER`: followers occur locally but the corresponding adult-parent population is supported at county scale;
- `NATIONAL_ORPHAN`: final national fallback.

These are biological relationship-support classes, not movement, trade or origin observations.

## Catchment signature spread

The `wfd_signature_spread` table pairs each catchment accounting value with
the denominator-weighted distribution of ED signatures intersecting that
catchment.

| Variable | Meaning |
|---|---|
| `CATCHMENT_VALUE` | Catchment signature recalculated from fractionally aggregated numerator and denominator |
| `ED_WEIGHTED_P10` | Weighted 10th percentile of intersecting ED signature values |
| `ED_WEIGHTED_P50` | Weighted median of intersecting ED signature values |
| `ED_WEIGHTED_P90` | Weighted 90th percentile of intersecting ED signature values |
| `ED_WEIGHTED_P90_P10` | Within-catchment P90-P10 spread |
| `INTERSECTING_EDS` | EDs contributing positive denominator weight |
| `DISTRIBUTION_DENOMINATOR` | Sum of ED signature denominators after fractional catchment weighting |

This structural distribution complements the catchment accounting value. It
does not relocate livestock within an ED and does not replace the fractional
ED-to-catchment accounting rule.

## Interpretation boundary

Historical outputs describe reconstructed agricultural populations, biological structure and spatial attribution. They do not directly observe animal movements, farm-to-farm trade, individual behaviour, exact within-ED livestock location, water-quality impacts or future scenario outcomes.
