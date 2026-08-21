# GOBLIN-Spatial data contract

The production model is repository-contained. `data_manifest.yaml` is the machine-readable authority for the inputs required to build the validated historical baseline and run the principal 2020 SC1-SC3 chain.

No normal model command downloads LPIS parcels, soil packages, ED geometry or any other model input from an external service.

## 1. Historical baseline inputs

The validated 2015-2025 reconstruction uses the canonical files under `data/inputs/baseline/`:

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

The DAFM county sheep file is retained as hold-out validation evidence and is not a production population control.

## 2. Principal scenario controls

National scenario controls are stored in:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

Pasture dry-matter controls are stored in:

```text
data/controls/pasture/GOBLIN_pasture_dm_2020_fixed.csv
```

Fixed Standard Output coefficients are stored in:

```text
data/controls/standard_output/IFS_SOC2020_IE_model_controls.csv
```

These controls define the national future and exposure accounting. They do not replace the historical ED baseline.

## 3. Frozen 2020 ED land context

The principal 2020 runtime uses:

```text
data/controls/land/ED_Land_Context_2020/
├── ED_Soil_Capability_08B.csv
├── ED_Physical_Soil_08C.csv
├── ED_LPIS_Context_2020_RUNTIME.csv
├── manifest.json
└── README.md
```

The three CSVs each cover the same 2,857 ED model universe and are verified against their frozen SHA256 values before use. Runtime joins only the required fields in memory to form the validated 40-field land-context object.

The evidence layers retain separate roles:

- 08B agricultural capability may constrain SC1 released-land geography;
- LPIS 2020 enters only after SC1 is frozen to describe opportunity and eligibility;
- 08C mapped physical soil enters only after SC1 as independent physical context;
- none of the three can alter the historical livestock baseline or national scenario endpoint.

The canonical logical land-context SHA256 is:

```text
6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d
```

The 08B provenance is fixed at 2,820 direct ED profiles and 37 county-fallback profiles.

## 4. Reconstruction boundary

First-principles GIS reconstruction is not part of the production runtime or CI acceptance gate. Local reconstruction utilities remain available for provenance work when a researcher already possesses the required source files.

A reconstructed control must never silently replace the frozen runtime controls. Replacement requires deliberate validation of ED universe, schema, accounting closures and checksums.

## 5. 2025 spatial status

The historical model contains a valid 2025 ED livestock state, so SC1 may use 2025 as a livestock-baseline sensitivity. LPIS-dependent 2025 SC2/SC3 remains disabled until a separately validated compact 2025 land-context bundle is created.

## 6. Generated outputs

Historical stage outputs and SC1-SC3 results are generated products, not mandatory inputs. They are written beneath `data/interim/` and `data/processed/`.

The controlling distinction is:

```text
repository-contained canonical inputs
        -> reproducible model runtime

local/manual reconstruction sources
        -> provenance work only

interim / processed files
        -> generated outputs
```
