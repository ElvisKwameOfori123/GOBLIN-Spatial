# Data Dictionary

This file documents the clean indicators exposed by the final GOBLIN-Spatial data workbook.

## Core identifiers

| Variable | Meaning |
|---|---|
| `YEAR` | Calendar year, 2015–2025 |
| `CSOED` | Harmonised CSO Electoral Division identifier used by the workflow |
| `EDID` | Electoral Division identifier where available |
| `ED` | Electoral Division code/name field from the source data |
| `EDNAME` | Electoral Division name |
| `County` | County |
| `COUNTYNAME` | County name field retained from source data |

## Farm structure and holder age

| Variable | Meaning |
|---|---|
| `AGRICULTURAL_HOLDINGS` | Number of agricultural holdings represented in the ED-year |
| `AVERAGE_SIZE_OF_HOLDINGS` | Average holding size in hectares |
| `AVERAGE_AGE_OF_HOLDER` | Mean age of farm holder |
| `MEDIAN_AGE_OF_HOLDER` | Median age of farm holder |

The 2020 values are the locked CSO ED baseline. Non-2020 values are reconstructed from official higher-level temporal controls.

## Land

| Variable | Meaning |
|---|---|
| `AREA_FARMED` | Total agricultural area farmed, hectares |
| `ALL_GRASSLAND` | Grassland area, hectares |
| `TOTAL_CEREALS` | Total cereal area, hectares |
| `OTHER_CROPS_HA` | Remaining crop/other agricultural land after reconciliation, hectares |

Accounting identity:

`AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA`

## Headline livestock

| Variable | Meaning |
|---|---|
| `DAIRY_COW` | Dairy cows |
| `OTHER_COW` | Other cows / suckler-cow control |
| `OTHER_CATTLE` | Cattle other than dairy cows and other cows |
| `TOTAL_CATTLE` | Total cattle |
| `TOTAL_SHEEP` | Total sheep |
| `LSU` | Livestock unit indicator where retained in the source master |

## GOBLIN cattle cohorts

The final GOBLIN cattle representation contains 21 cohorts:

1. `dairy_cows`
2. `suckler_cows`
3. `DxD_calves_m`
4. `DxD_calves_f`
5. `DxB_calves_m`
6. `DxB_calves_f`
7. `BxB_calves_m`
8. `BxB_calves_f`
9. `DxD_heifers_less_2_yr`
10. `DxD_steers_less_2_yr`
11. `DxB_heifers_less_2_yr`
12. `DxB_steers_less_2_yr`
13. `BxB_heifers_less_2_yr`
14. `BxB_steers_less_2_yr`
15. `DxD_heifers_more_2_yr`
16. `DxD_steers_more_2_yr`
17. `DxB_heifers_more_2_yr`
18. `DxB_steers_more_2_yr`
19. `BxB_heifers_more_2_yr`
20. `BxB_steers_more_2_yr`
21. `bulls`

For every ED-year, these cohorts sum exactly to `TOTAL_CATTLE`.

## GOBLIN sheep cohorts

The final GOBLIN sheep representation contains 10 cohorts:

1. `Lowland ewes`
2. `Upland ewes`
3. `Lowland lamb_less_1_yr`
4. `Lowland male_less_1_yr`
5. `Lowland lamb_more_1_yr`
6. `Lowland ram`
7. `Upland lamb_less_1_yr`
8. `Upland male_less_1_yr`
9. `Upland lamb_more_1_yr`
10. `Upland ram`

The GOBLIN `Upland` naming is operationally represented by the DAFM Mountain + Mountain Cross type aggregate in the current spatialisation.

For every ED-year, these cohorts sum exactly to `TOTAL_SHEEP`.
