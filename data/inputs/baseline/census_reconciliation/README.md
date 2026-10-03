# Stage 00 census reconciliation: audit tables

Written by `scripts/prepare_census_inputs.py` (library: `src/goblin_spatial/preparation/`). The method is described in `docs/methodology.md` section 2.0. Every file here regenerates byte for byte from the raw AVA42 table and the 2020 controls; `python scripts/prepare_census_inputs.py --check` verifies this and is the first step of `scripts/build_historical_release.py`.

## Inputs and what is written

| Role | File |
|---|---|
| Raw census (read only) | `../00_CSO_AVA42_Livestock_ED_2000_2010_2020.csv` |
| 2020 controls (read only) | `../01_CSO_AAA10_Cattle_County_2015_2025.csv`, `../03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx` |
| Prior evidence (read only) | `../02_DAFM_AIM_ED_Cattle_Profile_2020.csv` |
| Prepared 2020 input (2,857 EDs) | `../01_CSO_ED_Agricultural_Baseline_2020.csv` |
| Prepared 2010 input (3,409 EDs) | `../CSO_ED2010.csv` |

Only `DAIRY_COW`, `OTHER_COW`, `TOTAL_CATTLE`, `OTHER_CATTLE` and `TOTAL_SHEEP` are written. Row order, every other column (land, holdings, holder age, LSU, identifiers), encoding, quoting and line endings are carried over unchanged, and the writer refuses a file that does not round-trip exactly.

## Audit tables

| File | Content |
|---|---|
| `filled_cells.csv` | One row per filled census cell: `YEAR`, `KEY`, ED, county, `IN_MODEL`, variable, `FILLED_VALUE`, prior `SOURCE`, `SHRINKAGE_LAMBDA`, `TEST_ERROR_PCT`, `CONFIDENCE_CLASS`. |
| `state_closure.csv` | Per year and variable: State total, published sum, filled sum inside and outside the model universe, reconciled total (difference from State is zero by construction and checked). |
| `unit_closure.csv` | Per year, variable and control unit (county, region or State): control, published sum, rounded gap, target, filled, animals passed or received under the cow cap, deviation from the rounded control. |
| `cow_cap.csv` | 99th percentile cow share of cattle among published EDs with at least 200 cattle. |
| `hidden_cell_test.csv` | Hidden-cell test scores (`DISPLACED_PCT`, `SPEARMAN`) for every named prior, the equal split and the frozen chain at each lambda, for three test sizes; `POPULATION = WITHOUT_<first prior>` rows repeat the test on EDs lacking the first prior of the chain. |
| `hidden_cell_source_error.csv` | Error of the frozen chain by prior source and lambda (source of `TEST_ERROR_PCT`). |
| `shrinkage_selection.csv` | Selected lambda per year and variable. |
| `temporal_holdout_2010_2020.csv` | 2010 within-county shares applied to 2020 county totals, scored on EDs published in both censuses, at ED and WFD catchment level. Tests the persistence assumption behind non-census years; it is not a test of the filled cells. |
| `coverage_outside_model.csv` | Census animals in the 552 EDs outside the 2,857-ED model universe, by county, WFD catchment and State. |
| `robustness_variants.csv`, `robustness_signature_agreement.csv` | Headline results under census-input variants A (v1.1 dairy-only reconciliation), B (this stage) and C (AIM evidence first in 2020), from `scripts/run_census_reconciliation_robustness.py`. |

`TEST_ERROR_PCT` is the weighted absolute error, sum of |predicted - observed| over sum of observed, of hidden test cells that used the same prior source at the selected lambda. It is a per-source error for small cells, not a confidence interval for one ED. `CONFIDENCE_CLASS` summarises it: HIGH up to 25%, MODERATE up to 50%, LOW above.

## Reading the evidence

- The hidden test cells are the smallest published cells, yet real suppressed cells are smaller still (2020 mean per blank cell: 188 dairy cows, 37 other cows, 147 cattle, 301 sheep). Errors measured on test cells are therefore indicative, and the test favours methods that do not overstate between-cell spread, which is what shrinkage does.
- Weighted by filled animals, `TEST_ERROR_PCT` is 24.5% for 2020 dairy cows, 26.8% other cows, 43.2% total cattle and 28.3% sheep. Total cattle errors are high because the 84 blank 2020 totals are mostly EDs without a 2010 total; together they hold 12,337 cattle (0.17% of the State).
- The temporal holdout places 11% of 2020 dairy cows in the wrong ED when ED shares are carried from 2010, and 1.5% across WFD catchments.
