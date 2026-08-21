# GOBLIN-Spatial data contract

The repository separates **normal model runtime inputs** from **optional first-principles reconstruction sources**.

Normal 2020 scenario execution is designed to be reproducible from compact repository-contained inputs. It must not download LPIS parcels, soil packages or ED geometry and must not rebuild geospatial overlays automatically.

`data_manifest.yaml` is the machine-readable authority for data roles, paths, checksums and external provenance.

## 1. Historical baseline inputs

The validated 2015-2025 historical reconstruction uses the canonical files under `data/inputs/baseline/`:

```text
data/inputs/baseline/
├── 01_CSO_ED_Agricultural_Baseline_2020.csv
├── 01_CSO_AAA10_Cattle_County_2015_2025.csv
├── 03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx
├── 03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv
├── 05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv
├── 05C_Cattle_Cohort_Relationships_2012_2020.csv
├── 06_CSO_AQA06_Agricultural_Land_Use.xlsx
├── 06_Farm_Structure_Demographic_Controls.csv
└── 08_IFS2020_Standard_Output_Mapping.xlsx
```

The 2020 CSO ED agricultural census is the fine-scale spatial anchor. Official annual county or regional controls reconstruct 2015-2025 livestock and land totals. GOBLIN biological relationships provide the 21 cattle and 10 sheep cohorts. IFS-2020 Standard Output coefficients provide fixed-2020 production-value exposure.

The DAFM county sheep file is retained as hold-out validation evidence. It is not a production population control.

The historical pipeline ends at Stage 09:

```text
cattle -> sheep -> merge -> land/farm structure
       -> clean baseline -> Standard Output
       -> frozen ED cohort signatures
```

## 2. Principal national scenario controls

The active national pathway table is:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

It contains the national adult-cattle endpoints, target livestock land and explicit alternative-land targets used by the principal SC1-SC3 workflow.

The frozen pasture-DM control used for livestock-pressure spatialisation is:

```text
data/controls/pasture/GOBLIN_pasture_dm_2020_fixed.csv
```

These controls do not replace the historical ED baseline. They define the national future against which that baseline is spatially stressed.

## 3. Frozen 2020 ED land context

The normal 2020 spatial runtime uses one neutral compact control:

```text
data/controls/land/ED_Land_Context_2020/
```

The final logical object contains:

- 2,857 EDs;
- 40 fields;
- final 08B agricultural-capability evidence;
- independent 08C mapped physical-soil evidence;
- LPIS 2020 context;
- 08B provenance of 2,820 direct ED profiles and 37 county fallbacks.

Its canonical logical SHA256 is:

```text
6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d
```

The three evidence layers share one storage object but retain separate modelling roles:

- SC1 uses the frozen 08B fields to constrain released-land geography;
- SC2 attaches LPIS and independent 08C evidence after the SC1 release is frozen;
- SC3 uses the SC2 opportunity and physical-eligibility outputs to allocate explicit national land-use targets.

The land context never changes the livestock endpoint or adult allocation.

## 4. Optional spatial reconstruction sources

Large spatial files are provenance/reconstruction sources, not normal runtime dependencies. They include version-pinned soil, LPIS and ED-geography inputs such as:

```text
data/inputs/spatial/08B_NFS_Agricultural_Soil_Capability.csv
data/inputs/spatial/08C_IFS_Mapped_Physical_Soil_Package.zip
data/inputs/spatial/SC2_LPIS_2020_Frozen.parquet
data/inputs/spatial/SC2_LPIS_2025_Frozen.parquet
data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg
```

The frozen external release is documented in `data_manifest.yaml`, including the versioned Zenodo record and checksums.

Reconstruction workflows may use these files to reproduce the compact controls from first principles. Principal scenario execution must not require them to be present.

## 5. 2025 spatial status

The historical data contain a valid 2025 ED livestock state, so SC1 may use 2025 as an updated livestock baseline sensitivity.

A 2025 LPIS-dependent SC2/SC3 run is deliberately unavailable until a separately validated 2025 compact land-context control is created and frozen. The model will not reuse the 2020 LPIS snapshot as if it represented 2025.

## 6. Generated outputs

Historical stage outputs and SC1-SC3 scenario results are generated products, not mandatory inputs. Typical outputs are written beneath `data/interim/` and `data/processed/`.

The controlling distinction is therefore:

```text
canonical compact inputs
        -> reproducible model runtime

optional large provenance sources
        -> explicit first-principles rebuild only

interim / processed files
        -> generated outputs
```
