# Validation

The current validated baseline covers 2,857 Electoral Divisions for 2015–2025, giving 31,427 ED-year observations.

## Script 5C: cattle cohorts

The 21 GOBLIN cattle cohorts reproduce the fixed CSO ED cattle population exactly.

Key accounting checks from the validated run:

- maximum original CSO cattle-control change: `0`
- maximum ED age-sex cohort difference: `0`
- maximum 21-cohort `TOTAL_CATTLE` difference: `0`
- maximum national target difference: `0`
- negative genetic cells: `0`
- age-sex structural-zero violations: `0`
- young-only ED pre-adult closure difference: `0`

The corrected cattle spatial support is also validated explicitly. In the 2020 baseline:

- zero-dairy EDs: `1,463`
- zero-dairy EDs retaining zero DxD/DxB cattle: `1,142`
- zero-dairy EDs admitted as receiver/rearing exceptions: `321`
- EDs with no adult cows but positive `OTHER_CATTLE`: `51`
- dairy-only EDs: `11`
- dairy-only EDs receiving BxB cattle: `0`

The 321 zero-dairy receiver/rearing exceptions are not imposed as a fixed percentage. They arise from the ED support algorithm required to keep the complete 2015–2025 set of CSO age-sex rows and national GOBLIN genetic margins simultaneously feasible. Most zero-dairy EDs therefore retain a true dairy-origin structural zero, while a limited set of EDs with strong young-stock/receiver characteristics can carry bought-in DxD or DxB cattle.

These support checks validate the internal biological-spatial logic of the disaggregation. They are not a claim that the precise genetic mix of every ED has been independently observed.

## Script 5D: final 31 cohorts

The 10 GOBLIN sheep cohorts reproduce the fixed sheep population exactly and combine with the 21 cattle cohorts to produce the final 31-cohort representation.

Key checks from the validated run:

- maximum Lowland cohort difference: `0`
- maximum Upland cohort difference: `0`
- maximum 10-cohort `TOTAL_SHEEP` difference: `0`
- maximum original-control change: `0`
- maximum national sheep target difference: `0`
- negative GOBLIN sheep cells: `0`
- zero-sheep ED cohort violations: `0`
- maximum final 31-cohort livestock difference: `0`

## Script 6: land and farm structure

The 2020 ED baseline is explicitly locked.

Key checks from the validated run:

- maximum change in any of the eight 2020 structural/land indicators: `0`
- maximum livestock/cohort change: `0`
- negative land cells: `0`
- maximum ED land-accounting difference: approximately `9.09e-10 ha`, numerical floating-point noise

For every ED-year:

`AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA`

## Script 7: clean research workbook

The final clean workbook validation passed with:

- 31,427 rows in each all-years sheet
- 2,857 rows in each 2020 sheet
- 35 columns in `CSO_All_Years`
- 50 columns in `GOBLIN_All_Years`
- exact 2020 subset identity
- no model-diagnostic, status, target/allocation or reconstruction-method fields in the clean presentation sheets

## Automated regression

The complete input bundle is now Git-tracked. GitHub Actions therefore runs both the compact tests and the full 2015–2025 regression automatically. The full regression checks national cattle and sheep totals, cohort closure, land/SE constraints and the final clean-workbook dimensions.

## Interpretation

Exact closure validates the accounting and reconciliation constraints of the spatialisation. It should not be described as independent empirical validation of every reconstructed non-2020 ED value. Non-baseline annual ED values are controlled reconstructions from official higher-level statistics around the fixed 2020 spatial anchor.
