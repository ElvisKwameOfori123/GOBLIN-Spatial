# GOBLIN-Spatial staged execution architecture

## Design principle

The model and the publication layer are deliberately separated. A user can stop after any scientific stage without being forced to run later stages, figures or maps.

```text
Historical baseline
    ↓
SC1 transition incidence and released-land geography
    ↓
SC2 natural-capital opportunity and physical eligibility
    ↓
SC3 feasible alternative land-use response
    ↓
Cross-run final results package
    ↓
Publication figures
    ↓
Maps
```

Later layers consume frozen outputs from earlier layers. They do not feed back into livestock allocation, released-land spatialisation, opportunity calculations or SC3 allocation.

## 1. Historical baseline only

```bash
goblin-spatial study --through baseline
```

This builds the validated 2015–2025 historical reconstruction and stops. No scenario is required.

## 2. Stop after SC1

```bash
goblin-spatial study \
  --through sc1 \
  --scenario SI_SG \
  --allocation-rule PRORATA
```

SC1 writes complete ED, county and national livestock-transition results and can be used independently. A 2025 SC1 sensitivity run is also supported.

## 3. Stop after SC2

```bash
goblin-spatial study \
  --through sc2 \
  --scenario SI_SG \
  --allocation-rule PRORATA
```

SC2 freezes the same SC1 result and adds the 2020 natural-capital, LPIS and physical-eligibility context. SC2/SC3 currently require the validated 2020 spatial baseline.

## 4. Stop after SC3

```bash
goblin-spatial study \
  --through sc3 \
  --scenario SI_SG \
  --allocation-rule PRORATA
```

SC3 allocates the pathway's alternative land-use targets subject to released-land budgets, physical eligibility, shared pools and sequential rewetting.

## 5. Full comparative study results

The final principal study is the 3 pathways × 4 incidence rules matrix. Once the 12 completed SC1–SC3 run folders exist, the reporting layer creates the workbook, SQLite database, map-ready CSV and transition-conditions table:

```bash
goblin-spatial-study-report data/processed/final_principal \
  --output-dir data/processed/final_results
```

This is the first layer that requires the complete 12-run matrix by default.

## 6. Publication figures

Figures are downstream of the frozen final SQLite results and can be regenerated without rerunning the model:

```bash
goblin-spatial-paper-figures \
  data/processed/final_results/GOBLIN_Spatial_Final_Results.sqlite
```

The diagnostic graph suite remains in `final_results/figures/`; the compact manuscript-facing suite is written to `final_results/paper_figures/`.

## 7. Maps

Maps are deliberately last. They consume `GOBLIN_Spatial_Map_Data.csv`, which already contains the frozen numerical ED results selected for cartography. A normal repository clone now also contains the frozen ED geometry at `data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg`, so no external Shapefile is required for the standard mapping workflow.

```bash
pip install -e '.[geo]'
goblin-spatial maps data/processed/final_results
```

An alternative Shapefile or GeoPackage can still be supplied explicitly with `--geometry` for robustness or sensitivity work.

### Why geometry remains outside the scientific runtime

Geometry is not needed to calculate the historical baseline, SC1, SC2 or SC3. Numerical result identifiers remain the authoritative scientific `CSOED` values. The map layer applies a separate deterministic cartographic normalisation only at join time, including first-code handling for composite source geographies and removal of leading zeroes. Original result and geometry identifiers are retained for audit.

Keeping geometry downstream preserves the scientific boundary: the model can complete without cartography, while the repository-contained GeoPackage makes the published maps reproducible from a normal clone.

### What the map renderer does

The map renderer:

1. reads `GOBLIN_Spatial_Map_Data.csv`;
2. resolves the repository-contained frozen ED GeoPackage, unless another geometry source is supplied explicitly;
3. identifies the geometry attribute matching the model's ED identifiers, or uses `--geometry-key` when supplied;
4. applies the deterministic cartographic ED-key normalisation without modifying the scientific result identifiers;
5. verifies that every model ED has exactly one geometry;
6. filters away non-model EDs because the national geometry contains more ED features than the 2,857 agricultural model EDs;
7. writes `GOBLIN_Spatial_Model_ED_Geometry.gpkg`, containing only the model ED universe;
8. writes `GOBLIN_Spatial_Map_Layer.gpkg`, containing geometry joined to all ED × pathway × rule map-ready results;
9. creates high-resolution PNG and vector SVG reference maps plus a map manifest.

Repository CI validates the frozen GeoPackage checksum, CRS, geometry validity and the exact 2,857-ED join against the 2020 agricultural baseline.

### Geometry resolution order

If `--geometry` is not supplied, mapping tries:

1. `files.ed_boundaries_frozen` from the study configuration;
2. `files.saps_ed_geography` from the study configuration.

The first configured source is now repository-contained. If geometry is deliberately removed, the numerical study still remains complete; only the optional mapping stage is unavailable until geometry is restored or supplied.

## 8. Re-running only what changed

This separation is intentional:

- change historical inputs → rebuild baseline and downstream science;
- change a scenario endpoint/rule → rerun the affected scenario stages and final reporting;
- change workbook formatting → rerun reporting only;
- change figure styling → rerun `goblin-spatial-paper-figures` only;
- change map styling or geometry presentation → rerun `goblin-spatial maps` only.

Publication code therefore never becomes part of the scientific model state.
