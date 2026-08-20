# Data

GOBLIN-Spatial v1 uses a **hybrid scientific-data layout**.

The rule is deliberately simple:

- **compact historical-baseline inputs are versioned directly in GitHub** so the 2015-2025 reconstruction is easy to inspect, test and rebuild;
- **large spatial/scenario-preparation inputs are fetched from the frozen Zenodo release** and verified by checksum;
- generated intermediate, validation and scenario-result files are never treated as required model inputs.

The historical baseline is anchored to the **2020 CSO Electoral Division agricultural census** and reconstructed through time using **2015-2025 official controls for livestock, crops and agricultural land**.

## Packaged baseline status

The compact historical input package under `data/inputs/baseline/` is generated from the pinned Zenodo v1 record by `scripts/package_baseline_inputs.py`. The packaging helper verifies every file against the SHA256 recorded in `data_manifest.yaml` before the file is accepted in GitHub. Once all packaged files pass, only those historical-baseline manifest entries are activated from `git_pending` to `git`.

The package includes the eight production inputs used by Stages 01-08 plus the separate DAFM county-sheep hold-out validation file. Soil, LPIS, ED geometry and SC1-SC3 controls are deliberately excluded from this packaging step.

## Intended v1 layout

```text
data/
├── inputs/
│   ├── baseline/          # compact Git-tracked historical inputs
│   ├── scenario/          # compact Git-tracked future-scenario controls
│   └── spatial/           # large Zenodo-backed soil/LPIS/geography inputs
│
├── interim/               # generated stage outputs, Git-ignored
└── outputs/               # generated final outputs, Git-ignored
```

## Historical baseline inputs

The production historical baseline uses these compact inputs:

```text
data/inputs/baseline/
├── 01_CSO_ED_Agricultural_Baseline_2020.csv
├── 01_CSO_AAA10_Cattle_County_2015_2025.csv
├── 03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx
├── 05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv
├── 05C_Cattle_Cohort_Relationships_2012_2020.csv
├── 06_CSO_AQA06_Agricultural_Land_Use.xlsx
├── 06_Farm_Structure_Demographic_Controls.csv
└── 08_IFS2020_Standard_Output_Mapping.xlsx
```

`01_CSO_ED_Agricultural_Baseline_2020.csv` is the fine-scale spatial anchor.

`01_CSO_AAA10_Cattle_County_2015_2025.csv` supplies the annual county cattle controls. The 2020 ED cattle pattern is reconciled to AAA10, and the fixed 2020 within-county spatial support is then used for reconstructed non-2020 ED years.

`03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx` supplies the sheep hierarchy. `County_WIDE` is used for the county-to-region/NUTS2 crosswalk, while `Region_WIDE` provides the raw AAA09 detailed-region population and demographic controls. County sheep totals are reconstructed from the corrected 2020 ED anchor and AAA09 regional totals; the old `County_WIDE` sheep numbers are not treated as independent population controls.

`05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv` supplies sheep breed composition only. It does not replace the CSO/AAA09 sheep population.

`05C_Cattle_Cohort_Relationships_2012_2020.csv` is the shared GOBLIN biological relationship source used to construct both the 21 cattle cohorts and the 10 sheep cohorts. The published filename is retained for reproducibility even though the source contains both cattle and sheep series.

`06_CSO_AQA06_Agricultural_Land_Use.xlsx` and `06_Farm_Structure_Demographic_Controls.csv` supply crop, land, holding-size and holder-demographic controls.

`08_IFS2020_Standard_Output_Mapping.xlsx` supplies the fixed IFS-2020 Standard Output mapping used to calculate agricultural production-value exposure.

## DAFM county sheep hold-out

The frozen bundle also retains:

```text
03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv
```

This file is retained for independent/hold-out validation of the reconstructed sheep geography. It is **not** allowed to replace the production CSO/AAA09 sheep population controls unless a separately validated production algorithm is explicitly adopted in a future version.

## Final historical-baseline boundary

The historical model finishes at **Stage 09**:

```text
cattle
  ↓
sheep
  ↓
merge
  ↓
land + crops + farm structure / SE
  ↓
07 clean validated baseline
  ↓
08 Standard Output
  ↓
09 frozen ED cohort signatures
  ↓
HISTORICAL BASELINE COMPLETE
```

Stage 09 freezes the pre-scenario ED cohort relationships required by later transition analysis. It does not run a scenario.

## Scenario-preparation spatial inputs

Stages **08B and 08C begin the downstream scenario-preparation side**, rather than the historical reconstruction itself.

Large spatial files are fetched from the frozen Zenodo release:

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

The two soil systems remain independent:

- `08B_NFS_Agricultural_Soil_Capability.csv` provides the Cathal/NFS agricultural-capability representation;
- `08C_IFS_Mapped_Physical_Soil_Package.zip` provides the independent Colm/IFS mapped physical-soil representation.

They are not blended into one soil index, and neither is used to reconstruct historical livestock numbers.

LPIS is also downstream spatial evidence. It does not determine historical cattle or sheep populations.

## Compact scenario controls

Small future-scenario controls can remain in GitHub:

```text
data/inputs/scenario/
├── SC1_Cattle_Scenario_Endpoints_2050.csv
└── SC1_ED_Rural_Mixed_Urban_2022.xlsx
```

They are not read by the historical `run_baseline()` workflow.

## Generated files

Generated stages are recreated by the package and are not mandatory downloads. Examples include:

```text
01_CSO_ED_2020_age_sex_baseline.csv
02_CSO_ED_cattle_panel_2015_2025.csv
03A_* corrected sheep county/anchor outputs
03B_* ED sheep panel
05A_* annual sheep composition
05B_* sheep breed/type enrichment
05C_* cattle-cohort outputs
05D_* 31-cohort livestock master
06_* land/farm-structure master
07_* clean historical export
08_GOBLIN_Spatial_Standard_Output_2015_2025.csv
09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv
```

Future 08B/08C/SC1/SC2/SC3 outputs are likewise generated rather than model inputs.

## Data authority

The historical hierarchy is:

```text
2020 CSO ED agricultural census
        ↓
fine-scale spatial anchor

2015-2025 official county/region controls
        ↓
annual livestock + crop + land reconstruction

GOBLIN biological relationships
        ↓
31-cohort livestock representation

IFS-2020 Standard Output coefficients
        ↓
production-value exposure

Stage 09
        ↓
frozen pre-scenario ED cohort signatures
```

Only after this historical baseline is complete do soil, LPIS and future scenario controls enter the transition-analysis workflow.

`data_manifest.yaml` is the machine-readable authority for exact paths, checksums and source locations.
