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

Maps are deliberately last. They consume `GOBLIN_Spatial_Map_Data.csv`, which already contains the frozen numerical ED results selected for cartography.

```bash
goblin-spatial-maps data/processed/final_results \
  --geometry /path/to/Electoral_Divisions.shp
```

A GeoPackage can be supplied instead of an ESRI Shapefile.

### Why the model does not require a Shapefile

Geometry is not needed to calculate SC1, SC2 or SC3. The scientific join key is `CSOED`. Keeping geometry outside the scenario runtime avoids making a large, multi-file cartographic dataset a prerequisite for numerical reproducibility.

### What happens when a Shapefile is supplied

The map renderer:

1. reads `GOBLIN_Spatial_Map_Data.csv`;
2. reads the ED Shapefile/GeoPackage;
3. identifies the geometry attribute matching the model's `CSOED` values, or uses `--geometry-key` when supplied;
4. verifies that every model ED has exactly one geometry;
5. filters away non-model EDs if the national boundary source contains additional EDs;
6. writes `GOBLIN_Spatial_Model_ED_Geometry.gpkg`, a single-file frozen geometry package;
7. writes `GOBLIN_Spatial_Map_Layer.gpkg`, containing geometry joined to all ED × pathway × rule map-ready results;
8. creates high-resolution PNG and vector SVG maps.

Thus the original Shapefile is needed only as a geometry source. After the first successful map build, the compact GeoPackage can be archived with the final result bundle and used for later QGIS, ArcGIS or Python mapping.

### Geometry resolution order

If `--geometry` is not supplied, mapping tries:

1. `files.ed_boundaries_frozen` from the study configuration;
2. `files.saps_ed_geography` from the study configuration.

If neither file exists, the numerical study still remains complete; only the optional mapping stage is unavailable until geometry is supplied.

## 8. Re-running only what changed

This separation is intentional:

- change historical inputs → rebuild baseline and downstream science;
- change a scenario endpoint/rule → rerun the affected scenario stages and final reporting;
- change workbook formatting → rerun reporting only;
- change figure styling → rerun `goblin-spatial-paper-figures` only;
- change map styling or geometry presentation → rerun `goblin-spatial-maps` only.

Publication code therefore never becomes part of the scientific model state.
