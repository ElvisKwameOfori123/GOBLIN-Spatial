# Standard Output integration

## Role in GOBLIN-Spatial

Standard Output (SO) is a **valuation and exposure layer**. It is not income,
profit or welfare and it does not determine livestock allocation, biological
cohort closure, pasture dry-matter demand or spared grassland.

The build sequence is:

```text
cattle + sheep + land + socioeconomic ED baseline
        -> baseline validation
        -> fixed-2020 Standard Output mapping
        -> Stage-08 accounting/invariance checks
        -> processed Stage-08 export + final clean workbook
```

The top-level pipeline calls `add_baseline_standard_output()` only after the
physical livestock, cohort, land and socioeconomic modules are complete and
validated. The same fixed coefficient set is applied to every baseline year so
changes reflect physical activity/structure rather than price drift. Stage 08
is enrichment-only: it must not change any pre-existing livestock, land,
socioeconomic or identifier value. The final clean workbook is written after
these Stage-08 checks, with Standard Output on a dedicated `Standard_Output`
sheet rather than folded into the CSO-13 or GOBLIN-31 biological definitions.

Recommended interpretation:

> Fixed-IFS-2020 Standard-Output-weighted production-value exposure at ED level.

This is not a reconstruction of official holding-level Total Standard Output,
not farm income and not a farm welfare measure.

## Runtime mapping control

The configured runtime crosswalk is:

`data/inputs/baseline/08_IFS2020_Standard_Output_Mapping.xlsx`, sheet
`SO_Mapping`.

It contains one row for each of the 31 GOBLIN livestock cohorts plus land and
control variables. A readable CSV representation is also retained under
`data/controls/standard_output/GOBLIN_SO_mapping.csv` for audit. Runtime
valuation uses the configured workbook, so product-code crosswalks, regional
coefficients, imputation flags and the other-crop sensitivity remain auditable
without editing Python.

The original numerical SO source remains:

`IFS_T_MAIN_SOC_2020.xlsx`, sheet `SOC2020`

and the exact Irish source subset used for audit is versioned as:

`data/controls/standard_output/IFS_SOC2020_IE_model_controls.csv`

The source workbook SHA256 is:

`f9341129f63eb19bf3e37f0c655d1e3399ad013d1fc81d88922fdd5d4963f561`

## Historic Irish SO regions

The Irish SOC2020 table uses two historic regional codes for coefficient
lookup. These are deliberately kept separate from the current three-region NUTS
II geography used in modern NFS reporting.

- `381`: Border, Midland and Western (IE01)
  - Cavan, Donegal, Galway, Leitrim, Laois, Longford, Louth, Mayo,
    Monaghan, Offaly, Roscommon, Sligo, Westmeath
- `382`: Southern and Eastern (IE02)
  - Carlow, Clare, Cork, Dublin, Kerry, Kilkenny, Kildare, Limerick,
    Meath, Tipperary, Waterford, Wexford, Wicklow

County is therefore mapped first to `381` or `382`, and the corresponding fixed
SO coefficient is then applied.

## Livestock cohort crosswalk

The 31 GOBLIN livestock cohorts are valued through the IFS product classes:

| GOBLIN-Spatial activity | IFS product code |
|---|---|
| dairy cows | `A2300F` |
| suckler cows | `A2300G` |
| bulls | `A2130` |
| all DxD/DxB/BxB calves | `A2010` |
| all heifers <2 yr | `A2220` |
| all steers <2 yr | `A2120` |
| all heifers >2 yr | `A2230` |
| all steers >2 yr | `A2130` |
| lowland ewes | `A4110K` |
| upland ewes | `A4110K` |
| all other lowland/upland sheep cohorts | `A4120` |

`A4100` is the parent **all sheep** category and is never assigned to an
individual GOBLIN sheep cohort. This prevents double counting and fixes the
previous draft mapping of upland ewes.

`TOTAL_CATTLE`, `OTHER_CATTLE` and `TOTAL_SHEEP` are control totals only and are
not multiplied by an SO coefficient after the detailed cohorts are valued.

## Cereals

The ED baseline contains `TOTAL_CEREALS`, not crop-specific cereal hectares.
The runtime mapping therefore carries a fixed 2020 regional area-weighted
composite derived from:

- common wheat/spelt (`C1110T`)
- barley (`C1300T`)
- oats/spring cereal mixtures (`C1400T`)

The fixed coefficients are:

- region 381: EUR 1,582.156794611131/ha
- region 382: EUR 1,786.1348808802604/ha

The original source controls and frozen 2020 crop-area weights can reproduce
these values independently.

## Other crops

In the land module:

```text
OTHER_CROPS_HA = AREA_FARMED - ALL_GRASSLAND - TOTAL_CEREALS
```

It is therefore a broad residual of non-grass, non-cereal agricultural land,
not simply the single CSO row named `Other crops`.

The main fixed 2020 regional composite is:

- region 381: EUR 1,915.1395145631068/ha
- region 382: EUR 3,160.0518068965516/ha

The composite is flagged `IMPUTED=YES`. It is built from the documented 2020
residual crop/fruit/horticulture basket. Because the raw CSO `Other crops`
component includes miscanthus, fallow land and wild-bird cover, the model also
carries a conservative sensitivity:

- region 381: EUR 1,190.5161650485436/ha
- region 382: EUR 2,902.2530344827587/ha

The main baseline output reports both the main and conservative other-crop
valuation so the imputation is transparent.

## Grassland and area farmed

`ALL_GRASSLAND` is retained in the physical feed/land account and is not added
to the livestock production-value total. Directly adding a grassland SO value
on top of animal SO would mix the feed base with livestock output.

`AREA_FARMED` is a land-accounting total/denominator and receives no coefficient.

## Baseline formulas

For ED `e` in historic SO region `r`:

```text
SO_LIVESTOCK_e = sum_k(activity_e,k * SOC_k,r)
SO_CEREALS_e = TOTAL_CEREALS_e * CEREAL_SOC_r
SO_OTHER_CROPS_e = OTHER_CROPS_HA_e * OTHER_CROP_SOC_r
SO_COVERED_TOTAL_e = SO_LIVESTOCK_e + SO_CEREALS_e + SO_OTHER_CROPS_e
```

The conservative total substitutes the conservative other-crop coefficient.

## Output contract

The baseline/panel valuation exposes at least:

- `FADN_REGION`
- `FADN_REGION_LABEL`
- `SO_DAIRY_COWS_2020_EUR`
- `SO_SUCKLER_COWS_2020_EUR`
- `SO_BULLS_2020_EUR`
- `SO_FOLLOWERS_2020_EUR`
- `SO_SHEEP_2020_EUR`
- `SO_LIVESTOCK_2020_EUR`
- `SO_CEREALS_2020_EUR`
- `SO_OTHER_CROPS_2020_EUR`
- `SO_OTHER_CROPS_CONSERVATIVE_2020_EUR`
- `SO_OTHER_CROPS_IMPUTED_HA`
- `SO_COVERED_TOTAL_2020_EUR`
- `SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR`
- `SO_COVERED_PER_HOLDING_2020_EUR` when holdings are available

Scenario valuation currently applies the same mapping to baseline and scenario
livestock cohorts and reports:

- `SO_LIVESTOCK_CHANGE_2020_EUR` = scenario - baseline
- `SO_LIVESTOCK_EXPOSURE_2020_EUR` = baseline - scenario
- `SO_LIVESTOCK_CHANGE_PCT`

Land scenario valuation can be added when the pathway contains explicit
scenario crop areas; the baseline integration does not assume those changes.
