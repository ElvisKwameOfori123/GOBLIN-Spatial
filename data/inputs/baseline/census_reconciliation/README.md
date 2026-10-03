# Stage 00 census reconciliation: audit tables

Written by `scripts/prepare_census_inputs.py` (library: `src/goblin_spatial/preparation/`). The method is described in `docs/methodology.md` section 2.0. Every file here regenerates exactly from the raw inputs; `python scripts/prepare_census_inputs.py --check` verifies this and is the first step of `scripts/build_historical_release.py`.

## Inputs and what is written

| Role | File |
|---|---|
| Raw census ED table (read only) | `../00_CSO_AVA42_Livestock_ED_2000_2010_2020.csv` |
| Exact census county totals, the controls (read only) | `../00_CSO_Census_County_Livestock_2010_2020.csv` |
| Independent cross-check of the 2020 county totals (read only) | `../01_CSO_AAA10_Cattle_County_2015_2025.csv`, `../03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx` |
| Prior evidence (read only) | `../02_DAFM_AIM_ED_Cattle_Profile_2020.csv` |
| Prepared 2020 input (2,857 EDs) | `../01_CSO_ED_Agricultural_Baseline_2020.csv` |
| Prepared 2010 input (3,409 EDs) | `../CSO_ED2010.csv` |

Only `DAIRY_COW`, `OTHER_COW`, `TOTAL_CATTLE`, `OTHER_CATTLE` and `TOTAL_SHEEP` are written. All non-livestock fields (land, holdings, holder age, LSU, identifiers) are preserved exactly, and the row order, encoding, quoting and line endings of the original CSV files round-trip unchanged; the writer refuses a file that does not.

The county table was transcribed from CSO Census of Agriculture 2010 Final Results Tables 8A and 8B (North and South Tipperary summed) and 2020 Results Tables 4.2 and 4.4. The 2010 rows were read twice, from the full report (`full2010.pdf`) and from the separate tables file (`Tables2010.pdf`), with no difference across all 104 county values. Before use it must pass: counties sum to the AVA42 State total in each year and variable; no county total is below its published ED sum; the hidden amount is positive exactly in the counties that have blank cells; and every 2020 county value lies within 50 head of AAA10 (cattle) and AAA09 (sheep, by region). Any transcription error would almost certainly break one of these.

## Audit tables

| File | Content |
|---|---|
| `filled_cells.csv` | One row per filled census cell: `YEAR`, `KEY`, ED, county, `IN_MODEL`, variable, `FILLED_VALUE`, prior `SOURCE`, `SHRINKAGE_LAMBDA`, `ABOVE_COW_CAP`, `TEST_ERROR_PCT`, `CONFIDENCE_CLASS`. |
| `county_closure.csv` | Per year, variable and county: census county total, published ED sum, hidden total, blank cells, filled (equals hidden), head placed above the cow cap, head filled outside the model universe. |
| `county_control_checks.csv` | The validation of the census county table listed above, including census minus AAA10/AAA09. |
| `state_closure.csv` | Per year and variable: State total, published sum, filled inside and outside the model universe, reconciled total (difference zero). |
| `cow_cap.csv` | 99th percentile cow share of cattle among published EDs with at least 200 cattle. |
| `hidden_cell_test.csv` | Hidden-cell test scores (`DISPLACED_PCT`, `SPEARMAN`) for every named prior, the equal split and the frozen chain at each lambda, for three test sizes; `POPULATION = WITHOUT_<first prior>` rows repeat the test on EDs lacking the first prior of the chain. |
| `hidden_cell_source_error.csv` | Error of the frozen chain by prior source and lambda (source of `TEST_ERROR_PCT`). |
| `shrinkage_selection.csv` | Selected lambda per year and variable. |
| `temporal_holdout_2010_2020.csv` | 2010 within-county shares applied to 2020 county totals, scored on EDs published in both censuses, at ED and WFD catchment level. Tests the persistence assumption behind non-census years; it is not a test of the filled cells. |
| `coverage_outside_model.csv` | Census animals in the 552 EDs outside the 2,857-ED model universe, by county, WFD catchment and State. |
| `robustness_variants.csv`, `robustness_signature_agreement.csv` | Headline results under census-input variants A (v1.1 dairy-only reconciliation), B (this stage) and C (AIM evidence first in 2020), from `scripts/run_census_reconciliation_robustness.py`. |

`TEST_ERROR_PCT` is the weighted absolute error, sum of |predicted - observed| over sum of observed, of hidden test cells that used the same prior source at the selected lambda. It is a per-source error for small cells, not a confidence interval for one ED. It is not halved, so unlike `DISPLACED_PCT` in `hidden_cell_test.csv` it is not a misplaced share; keep the two names distinct. `CONFIDENCE_CLASS` summarises it: EXACT, HIGH up to 25%, MODERATE up to 50%, LOW above.

A county's only blank cell for a variable is identified exactly by the county margin: `SOURCE = COUNTY_RESIDUAL`, `TEST_ERROR_PCT = 0`, `CONFIDENCE_CLASS = EXACT`, no lambda (22 cells). Priors and shrinkage matter only in counties with two or more blank cells, which is why the hidden-cell test hides at least two cells per county.

## Reading the evidence

- County placement of suppressed animals is census-exact. Only the placement among two or more blank EDs within a county is reconstructed.
- The hidden test cells are the smallest published cells, yet real suppressed cells are smaller still (2020 mean per blank cell: 188 dairy cows, 37 other cows, 147 cattle, 301 sheep). Errors measured on test cells are therefore indicative, and the test favours methods that do not overstate between-cell spread, which is what shrinkage does.
- Weighted by filled animals, `TEST_ERROR_PCT` in 2020 is 24.6% for dairy cows, 26.2% other cows, 40.6% total cattle and 26.8% sheep. Total cattle errors are high because most of the 84 blank 2020 totals are city and town EDs with little earlier evidence; 65 of them lie outside the model universe. Together they hold 12,337 cattle (0.17% of the State), 8,744 of them outside the model universe.
- AIM evidence is matched only one-to-one. Unqualified AIM names that could refer to either of two census EDs (e.g. "Kilbarry" and "Kilbarry (Part Rural)", "Cootehill Rural" and "Cootehill Urban") are discarded, not guessed.
- Where a county's exact hidden total cannot fit under the cow cap, the cap gives way in that county and the cells are flagged (92 other cows in total, 2010 and 2020).
- Many 2010 dairy and sheep fills sit in EDs with a published 2020 zero. That is the census record of exit (a few holdings in 2010, none in 2020), not an artefact of the fill.
