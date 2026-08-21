# External spatial inputs

Raw national GIS files are kept outside ordinary Git history because some
members exceed normal GitHub file-size limits.  Their canonical project paths
and SHA256 checksums are recorded in `data_manifest.yaml`.

Expected local layout after running `scripts/install_spatial_inputs.py`:

```text
data/external/spatial/
├── ed/
│   ├── Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shp
│   ├── Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shx
│   ├── Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.dbf
│   └── Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.prj
├── sis_soils/
│   ├── INSM250k_ING_1b.zip
│   ├── INSM250k_ING.shp
│   ├── INSM250k_ING.shx
│   ├── INSM250k_ING.dbf
│   ├── INSM250k_ING.prj
│   └── other source metadata distributed in the SIS archive
└── lpis/
    └── LPIS_2020_audit.xlsx
```

The ED shapefile is a geometry source only.  It does **not** define the
GOBLIN-Spatial ED universe.  The authoritative livestock baseline is filtered
onto this geometry first; extra SAPS ED polygons are ignored.

The first soil product is intentionally neutral: a long-form
`ED x SIS_ASSOCIATION` hectare/share table.  Functional land-use classes and
GOBLIN G1/G2/G3 production groups are downstream, separately documented
crosswalks.
