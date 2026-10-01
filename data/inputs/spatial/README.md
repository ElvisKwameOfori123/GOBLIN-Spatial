# Frozen spatial reporting inputs

These files support reproducible mapping and ED-to-catchment aggregation of the historical baseline. They do not alter livestock, land, farm-structure or Standard Output reconstruction.

## Electoral Division geometry

`ED_Boundaries_Frozen.gpkg` is the frozen Electoral Division geometry used to match the model ED universe and construct the ED-to-WFD-catchment crosswalk.

File contract:

- path: `data/inputs/spatial/ED_Boundaries_Frozen.gpkg`
- checksum sidecar: `data/inputs/spatial/ED_Boundaries_Frozen.gpkg.sha256`
- source layer: `electoral_divisions`
- source features: 3,409
- geometry type: MultiPolygon
- CRS: EPSG:29902 (TM65 / Irish Grid)
- SHA-256: `550b2ed967f5c5e7ecb9053586cf431df564d0a990f99f9f82eb8b8be44faca8`

The national geometry contains more ED features than the 2,857-ED agricultural model universe. Spatial joins therefore retain only the model EDs and require each model ED to resolve to its corresponding geometry.

The numerical ED results remain authoritative. Geometry is a reporting and crosswalk resource, not a source of livestock quantities.

## WFD catchment geometry

`WFD_Catchments_Frozen.gpkg` is the frozen hydrological reporting geography used by the catchment bridge.

File contract:

- path: `data/inputs/spatial/WFD_Catchments_Frozen.gpkg`
- checksum sidecar: `data/inputs/spatial/WFD_Catchments_Frozen.gpkg.sha256`
- source features: 46 official WFD catchments
- catchment identifier: `CATCHMENTI`
- catchment name: `NAME`
- CRS: EPSG:2157
- SHA-256: `d9b00e1732f4f6a711c7edfb9d4d3348efe8150efd60280361f217d8a2602b65`

The production catchment build is offline and checksum-controlled.

## ED-to-catchment allocation

Where an ED intersects more than one WFD catchment, additive quantities are allocated using the fraction of mapped ED area falling within each catchment. Weights are normalised within ED so that national additive totals are preserved.

This provides a reproducible environmental reporting geography. It does not identify the exact location of farms or animals inside an ED and should not be interpreted as a parcel-level livestock allocation.

See `docs/catchment_bridge.md` and `scripts/build_catchment_baseline.py`.
