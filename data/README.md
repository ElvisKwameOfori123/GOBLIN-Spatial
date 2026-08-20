# Data

GOBLIN-Spatial v1 uses a **hybrid scientific-data layout**.

The rule is deliberately simple:

- **compact baseline and control inputs are versioned directly in GitHub** so the 2015-2025 historical reconstruction is easy to inspect, test and rebuild;
- **large spatial inputs are fetched from the frozen Zenodo release** and verified by checksum;
- generated intermediate, validation and scenario-result files are never treated as required model inputs.

The historical baseline is anchored to the **2020 CSO Electoral Division agricultural census** and reconstructed through time using **2015-2025 official controls for livestock, crops and agricultural land**.

## Intended v1 layout

```text
data/
├── inputs/
│   ├── baseline/          # compact Git-tracked baseline inputs
│   ├── scenario/          # compact Git-tracked national scenario controls
│   └── spatial/           # large downloaded/fetched inputs, Git-ignored
│
├── interim/               # generated stage outputs, Git-ignored
└── outputs/               # generated final outputs, Git-ignored
```

## Git-tracked baseline inputs

These compact files form the reproducible input contract for rebuilding the historical baseline:

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

### Historical role of the inputs

`01_CSO_ED_Agricultural_Baseline_2020.csv` is the fine-scale spatial anchor. It contains the 2020 ED agricultural system from which the historical reconstruction begins.

`01_CSO_AAA10_Cattle_County_2015_2025.csv` supplies the annual county cattle controls used to reconstruct the 2015-2025 ED cattle panel.

`03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx` supplies the official sheep county/region controls. `03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv` supplies the DAFM county observations used by the validated sheep drift/control stage. `05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv` supplies breed composition only and does not replace CSO sheep population controls.

`05C_Cattle_Cohort_Relationships_2012_2020.csv` is the shared GOBLIN biological relationship source used for the 21 cattle cohorts and the downstream sheep cohort relationships.

`06_CSO_AQA06_Agricultural_Land_Use.xlsx` and `06_Farm_Structure_Demographic_Controls.csv` supply the crop, land and farm-structure temporal controls used around the fixed 2020 ED spatial state.

`08_IFS2020_Standard_Output_Mapping.xlsx` supplies the fixed 2020 Standard Output mapping used for production-value exposure.

## Compact scenario controls

The small national scenario controls are also suitable for GitHub:

```text
data/inputs/scenario/
├── SC1_Cattle_Scenario_Endpoints_2050.csv
└── SC1_ED_Rural_Mixed_Urban_2022.xlsx
```

These files control scenario endpoints and spatial policy context. They do not replace the historical baseline.

## Large spatial inputs from Zenodo

Large spatial files are not duplicated in normal Git history. They are fetched from the frozen Zenodo release:

**Version DOI:** `10.5281/zenodo.22035538`

**Concept DOI:** `10.5281/zenodo.22035537`

```text
data/inputs/spatial/
├── 08B_NFS_Agricultural_Soil_Capability.csv
├── 08C_IFS_Mapped_Physical_Soil_Package.zip
├── SC2_LPIS_2020_Frozen.parquet
├── SC2_LPIS_2025_Frozen.parquet
└── SC2_ED_Boundaries_Frozen.gpkg
```

The published Zenodo record also contains the complete frozen input inventory, README and SHA256 checksum list. The exact version DOI, not the moving concept DOI, is used for reproducible model execution.

## Soil boundary

The two soil systems remain separate:

- `08B_NFS_Agricultural_Soil_Capability.csv` provides the Cathal/NFS agricultural-capability representation;
- `08C_IFS_Mapped_Physical_Soil_Package.zip` provides the independent Colm/IFS mapped physical-soil representation.

They are not blended into one soil index.

## LPIS boundary

LPIS is downstream spatial evidence. It does not determine historical livestock numbers or the original SC1 livestock transition.

The principal scenario uses the 2020 baseline with `SC2_LPIS_2020_Frozen.parquet`. The 2025 LPIS snapshot is retained for optional updated-baseline and sensitivity applications.

## Generated files

Generated stages are not required downloads. Examples include:

```text
01_CSO_ED_2020_age_sex_baseline.csv
02_CSO_ED_cattle_panel_2015_2025.csv
03_0_DAFM_County_Sheep_Drift_2015_2025.csv
05A_DAFM_County_Sheep_Composition_2015_2025.csv
05B_* generated sheep outputs
05C_* generated cattle-cohort outputs
05D_* 31-cohort master
06_* historical master
07_* clean export
08_* Standard Output result
08B_* enriched baseline result
08C_* dual-soil baseline result
09_* frozen signatures
SC1_* scenario results
SC2_* opportunity results
SC3_* allocation results
```

A clean model run must recreate these from the Git-tracked compact inputs plus the checksum-pinned Zenodo spatial inputs.

## Data authority

The intended v1 hierarchy is:

```text
2020 CSO ED agricultural census
        ↓
fine-scale spatial anchor

2015-2025 official county/region controls
        ↓
annual livestock + crop + land reconstruction

GOBLIN biological relationships
        ↓
cohort representation

GOBLIN national scenarios
        ↓
scenario totals

GOBLIN-Spatial
        ↓
spatial allocation and feasibility
```

`data_manifest.yaml` is the machine-readable authority for exact paths, checksums and source locations. During the v1 migration the manifest and configuration are being updated only after the corresponding canonical input file has been placed and verified, so the working build is not broken by a path-only refactor.