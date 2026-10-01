# Catchment bridge

The catchment bridge is a downstream reporting layer for the validated GOBLIN-Spatial historical baseline. It does not change the ED reconstruction, livestock cohorts, land, farm structure or Standard Output.

## Purpose

The same 2015-2025 agricultural system is represented through parallel reporting geographies:

```text
                 -> county
ED (authority)  -> official WFD catchment
                 -> GOBLIN-compatible catchment
                 -> Ireland
```

County and WFD catchment are derived views of the common ED × year master rather than independently reconstructed agricultural systems.

## Catchment geography

The authoritative hydrological reporting geography is the Environmental Protection Agency Water Framework Directive Catchments polygon dataset. A frozen 46-feature copy is stored at:

```text
data/inputs/spatial/WFD_Catchments_Frozen.gpkg
```

Its SHA-256 is pinned in `data_manifest.yaml` and the adjacent checksum sidecar. The layer uses `CATCHMENTI` as the catchment identifier, `NAME` as the catchment name and EPSG:2157 geometry.

The bridge preserves all 46 official WFD catchments as the primary environmental reporting output. A secondary compatibility output collapses the detailed Upper and Lower Shannon units to the 37-name system used by `GOBLIN-Proj/catchment_data_api`. That compatibility table is derived from the official WFD result and is not the spatial authority.

## Frozen input contract

Normal production builds are offline with respect to catchment geography. `scripts/build_catchment_baseline.py` requires the frozen ED and WFD geometries and the WFD checksum sidecar. It verifies the WFD SHA-256 before reading the layer and fails if the file is missing or altered.

A different catchment file may be supplied explicitly with `--catchment-geometry`, but it must have a matching checksum sidecar. This prevents silent changes in the ED-to-catchment weights.

## Method

A static ED-to-catchment overlay is calculated. Where an ED intersects more than one catchment, additive quantities are distributed according to mapped ED area:

```text
ED_CATCHMENT_WEIGHT = ED/catchment intersection area / total mapped intersection area for that ED
```

Weights are normalised to sum to exactly 1 within each model ED. This preserves national totals for additive variables.

A small number of ED polygons may not intersect the WFD polygon layer. These are assigned deterministically to the nearest official WFD catchment in projected coordinates. Such rows are explicitly flagged as `nearest_catchment_fallback`, retain zero polygon coverage and record the nearest-distance value so that the fallback remains auditable.

This historical release uses an area-weighted bridge because the public ED baseline does not contain parcel-level livestock locations. The allocation therefore represents a reproducible reporting transformation rather than observed within-ED animal location.

## Outputs

Running:

```bash
pip install -e '.[geo]'
python scripts/build_catchment_baseline.py
```

writes:

```text
data/processed/ed_wfd_catchment_crosswalk.csv
data/processed/goblin_spatial_wfd_catchment_2015_2025.csv
data/processed/goblin_spatial_colm_catchment_2015_2025.csv
data/processed/goblin_spatial_county_2015_2025.csv
data/processed/goblin_spatial_national_2015_2025.csv
data/processed/catchment_closure_diagnostics.csv
```

The county, catchment and national outputs carry the CSO-controlled livestock groups, the full 31 GOBLIN cohorts, additive agricultural land, holdings and fixed-2020 Standard Output components.

Farm-structure averages are not summed. At higher scales:

```text
AVERAGE_SIZE_OF_HOLDINGS = AREA_FARMED / AGRICULTURAL_HOLDINGS
```

`AVERAGE_AGE_OF_HOLDER` is weighted by represented holdings. `MEDIAN_AGE_OF_HOLDER` remains ED-only because a valid higher-level median cannot be recovered from ED medians.

## Accounting rule

For every year and every additive variable:

```text
sum(ED) = sum(county) = sum(46 WFD catchments) = sum(37 compatibility catchments) = Ireland
```

The build fails if a derived geography does not reproduce the ED national total within numerical tolerance.

Ratios and shares are not averaged across EDs. Their numerators and denominators are aggregated separately and the ratio is then recalculated at the target geography.

## Interpretation

The WFD output connects agricultural structure to an environmentally relevant receiving geography. It is not a water-quality impact model.

Where an ED crosses a catchment boundary, livestock and other additive quantities are fractionally allocated because individual herd coordinates are not available in the public baseline. The resulting catchment population should therefore not be interpreted as an observed animal location within the intersected part of an ED.
