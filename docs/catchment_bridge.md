# Catchment bridge

This is a downstream aggregation layer for the validated GOBLIN-Spatial historical baseline. It does not change the ED reconstruction, livestock cohorts, Standard Output, SC1, SC2 or SC3.

## Purpose

The same 2015-2025 livestock system can be viewed at four scales:

```text
ED -> county -> WFD catchment -> Ireland
```

The ED x year master remains authoritative. County and catchment tables are derived views.

## Catchment geography

Use the Environmental Protection Agency Water Framework Directive Catchments polygon dataset:

https://data.gov.ie/dataset/water-framework-directive-water-catchments

The EPA dataset is licensed CC BY 4.0. The current metadata identifies the catchments as polygon features in TM65 / Irish Grid (EPSG:29902), with the dataset page updated on 2 July 2026. The EPA download portal currently lists the **Catchments Data Package - April 2026** under Water / Water Framework Directive / General Information.

Freeze the downloaded geometry used for a release at:

```text
data/inputs/spatial/WFD_Catchments_Frozen.gpkg
```

The bridge harmonises catchment names to the 37-name system used by Colm Duffy's `GOBLIN-Proj/catchment_data_api`. Detailed Upper Shannon and Lower Shannon variants are collapsed to `Upper Shannon` and `Lower Shannon`.

## Method

A static ED-to-catchment overlay is calculated once. If an ED intersects more than one catchment, its additive quantities are distributed using the fraction of intersected ED area:

```text
ED_CATCHMENT_WEIGHT = ED/catchment intersection area / total mapped intersection area for that ED
```

Weights are normalised to sum to exactly 1 within each model ED. This guarantees national closure for additive variables.

The first implementation is deliberately area-weighted. A later agricultural-land or LPIS-weighted crosswalk can replace these weights without changing the aggregation architecture.

## Outputs

Running:

```bash
pip install -e '.[geo]'

python scripts/build_catchment_baseline.py \
  --catchment-geometry data/inputs/spatial/WFD_Catchments_Frozen.gpkg
```

writes:

```text
data/processed/ed_catchment_crosswalk.csv
data/processed/goblin_spatial_catchment_2015_2025.csv
data/processed/goblin_spatial_county_2015_2025.csv
data/processed/catchment_closure_diagnostics.csv
```

The catchment and county outputs contain the additive livestock cohorts, livestock totals, selected agricultural areas and additive Standard Output components already present in the ED master.

## Accounting rule

For every year and every additive variable:

```text
sum(ED) = sum(county) = sum(catchment) = Ireland
```

The build fails if catchment aggregation does not reproduce the ED national totals within numerical tolerance.

## Relationship to catchment_data_api

Colm's catchment package estimates catchment cohort populations from catchment dairy/suckler/sheep totals using national GOBLIN cohort coefficients. GOBLIN-Spatial now contains reconstructed cohort populations directly at ED level for 2015-2025. The bridge therefore aggregates those spatially explicit ED cohorts to catchments rather than re-estimating them from national ratios.

The existing package remains useful for catchment naming, 2020 comparison and later integration with catchment land-cover, soil and environmental data.

## Interpretation

These are derived catchment representations of the GOBLIN-Spatial ED baseline. Where an ED crosses a catchment boundary, animal numbers are fractionally allocated because individual herd coordinates are not available in the public baseline. They should not be interpreted as observed animal locations within the intersected part of an ED.
