# Frozen spatial presentation inputs

## Electoral Division geometry

`SC2_ED_Boundaries_Frozen.gpkg` is the frozen Electoral Division geometry source used only by the downstream GOBLIN-Spatial cartographic layer. It does **not** enter baseline, SC1, SC2 or SC3 calculations.

Expected file contract:

- path: `data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg`
- source layer: `electoral_divisions`
- source features: 3,409
- geometry type: MultiPolygon
- CRS: EPSG:29902 (TM65 / Irish Grid)
- file size of the frozen source checked on 2026-08-30: 11,481,088 bytes
- SHA-256: `550b2ed967f5c5e7ecb9053586cf431df564d0a990f99f9f82eb8b8be44faca8`

The national geometry contains more ED features than the agricultural model universe. The cartographic renderer therefore treats the numerical results as authoritative, retains only model EDs and requires every model ED to match exactly one polygon.

### Cartographic ED key

The scientific model keeps its source `CSOED` values unchanged. Mapping uses a separate, deterministic cartographic normalisation only at join time:

- ordinary source code `01003` becomes cartographic key `1003`;
- a composite source code such as `08045/08046` uses the first listed code and becomes cartographic key `8045`;
- identifiers remain text, not measurements;
- the original result identifier is retained as `CSOED_SOURCE`;
- the original geometry identifier is retained as `CSOED_GEOMETRY_SOURCE`.

This rule is implemented and validated in `src/goblin_spatial/map_reporting.py`. It avoids any QGIS-side identifier editing and keeps the numerical science independent of cartography.

### Reproducible mapping

Once a complete final-results directory contains `GOBLIN_Spatial_Map_Data.csv`, maps can be generated directly with:

```bash
pip install -e '.[geo]'
goblin-spatial maps data/processed/final_results
```

The configured geometry path is already `files.ed_boundaries_frozen` in `configs/ireland_2015_2025.yaml`, so no `--geometry` argument is required when the frozen file is present at the path above.

The mapping stage writes:

- `GOBLIN_Spatial_Model_ED_Geometry.gpkg`, containing only the model ED universe;
- `GOBLIN_Spatial_Map_Layer.gpkg`, containing geometry joined to ED × pathway × allocation-rule results;
- high-resolution PNG and vector SVG reference maps;
- `GOBLIN_Spatial_Map_Manifest.csv` recording the mapping choices and source geometry.

QGIS can open the same output GeoPackage for visual inspection and publication polishing, but QGIS is not required to reproduce the numerical model or the Python reference maps.


## WFD catchment geometry

`WFD_Catchments_Frozen.gpkg` is an optional downstream aggregation input used by the catchment bridge. It does not enter baseline, SC1, SC2 or SC3 calculations.

Source: Environmental Protection Agency, Water Framework Directive Water Catchments, CC BY 4.0.

https://data.gov.ie/dataset/water-framework-directive-water-catchments

Expected path:

`data/inputs/spatial/WFD_Catchments_Frozen.gpkg`

The bridge uses the frozen ED geometry and this catchment geometry to construct a static ED-to-catchment crosswalk. Catchment weights are normalised within ED so additive livestock, land and Standard Output quantities preserve national totals exactly. See `docs/catchment_bridge.md`.
