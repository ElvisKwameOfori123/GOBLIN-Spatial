# Standard Output integration

## Role in GOBLIN-Spatial

Standard Output (SO) is a **valuation and exposure layer**. It is not an income,
profit or welfare measure and it does not determine livestock allocation,
biological cohort closure, pasture dry-matter demand or spared grassland.

The sequence is therefore:

```text
physical ED livestock/cohort state
        -> fixed-2020 Standard Output valuation
        -> production-value exposure diagnostics
```

For scenario analysis the physical pathway is solved first. The same 2020
coefficient set is then applied to the baseline and scenario states. This keeps
SO changes interpretable as structural/activity change rather than a mixture of
physical change and changing prices.

Recommended interpretation:

> Standard Output is expressed using fixed 2020 regional coefficients to isolate
> structural changes in livestock and land-use activity from changes in
> valuation coefficients.

## Numerical coefficient source

The numerical source is `IFS_T_MAIN_SOC_2020.xlsx`, sheet `SOC2020`. The model
uses the Irish rows (`COUNTRY = IE`, `YEAR = 2020`) and the original `SOC_EUR`
field. The source workbook is not required at runtime: the exact subset used by
the model is versioned as:

`data/controls/standard_output/IFS_SOC2020_IE_model_controls.csv`

The source workbook SHA256 used to prepare the extract is:

`f9341129f63eb19bf3e37f0c655d1e3399ad013d1fc81d88922fdd5d4963f561`

The coefficient loader can also read the original workbook directly, allowing
the compact control extract to be audited against the source.

## Irish FADN regions

The 2020 Irish SOC table contains two historic FADN regions:

- `381`: Border, Midland and Western
- `382`: Southern and Eastern

The corresponding county mapping used here is:

**381 (BMW):** Cavan, Donegal, Galway, Laois, Leitrim, Longford, Louth, Mayo,
Monaghan, Offaly, Roscommon, Sligo and Westmeath.

**382 (Southern & Eastern):** Carlow, Clare, Cork, Dublin, Kerry, Kildare,
Kilkenny, Limerick, Meath, Tipperary, Waterford, Wexford and Wicklow.

This mapping is tested explicitly because older development scripts contained
comments that reversed the human-readable labels even where their numerical
coefficient pairs remained correct.

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
| upland ewes | `A4100` |
| other lowland/upland sheep cohorts | `A4120` |

Genetic origin does not alter the SO coefficient where the IFS product class is
defined by age/sex rather than breeding origin.

## Cereals

The ED baseline contains `TOTAL_CEREALS` rather than individual cereal crops.
A fixed regional composite €/ha coefficient is therefore calculated from the
2020 regional crop mix and the SOC values for:

- common wheat/spelt (`C1110T`)
- barley (`C1300T`)
- oats/spring cereal mixtures (`C1400T`)

The resulting fixed coefficients are approximately:

- FADN 381: EUR 1,582.1568/ha
- FADN 382: EUR 1,786.1349/ha

The crop-area weights are fixed at the 2020 base so annual and scenario SO
changes do not contain a changing valuation mix.

## Other crops

`OTHER_CROPS_HA` is a heterogeneous residual that can contain activities with
very different SO coefficients. GOBLIN-Spatial does **not** assign it an
invented cereal-equivalent coefficient. Until a documented crop crosswalk is
available, the model reports:

- `SO_COVERED_TOTAL_2020_EUR` = livestock SO + cereal SO
- `SO_OTHER_CROPS_UNVALUED_HA` = residual crop area not yet valued

The word `COVERED` is deliberate: this is not claimed to be complete total farm
SO where other crops are present.

## Teagasc National Farm Survey 2020

The Teagasc National Farm Survey 2020 is used as methodological evidence and a
validation benchmark, not as an ED-level input. NFS applies Standard Output to
animal and crop activities for farm-system classification. Table 08A reports
mean Total Standard Output for the represented commercial-farm population.
Those benchmark values are stored in:

`data/controls/standard_output/NFS_2020_TSO_benchmarks.csv`

They are diagnostic benchmarks only; GOBLIN-Spatial is not calibrated to force
ED values to reproduce the NFS farm-system means.

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
- `SO_COVERED_TOTAL_2020_EUR`
- `SO_OTHER_CROPS_UNVALUED_HA`
- `SO_COVERED_PER_HOLDING_2020_EUR`

Scenario valuation adds baseline and scenario livestock SO plus:

- `SO_LIVESTOCK_CHANGE_2020_EUR` = scenario - baseline
- `SO_LIVESTOCK_EXPOSURE_2020_EUR` = baseline - scenario
- `SO_LIVESTOCK_CHANGE_PCT`

The existing clean biological CSO/GOBLIN workbook sheets remain unchanged; SO
is exported separately so valuation cannot silently alter the validated
livestock/land data contract.
