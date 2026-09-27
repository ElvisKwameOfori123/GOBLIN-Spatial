# GOBLIN-Spatial data contract

The production model is repository-contained. `data_manifest.yaml` is the machine-readable authority for the inputs required to build the validated historical baseline and run the principal 2020 SC1-SC3 chain.

No normal model command downloads or reconstructs external spatial inputs. Scientific controls are read from frozen, checksum-verified repository files.

## 1. Historical baseline inputs

The validated 2015-2025 reconstruction uses the canonical inputs under `data/inputs/baseline/` together with fixed Standard Output controls under `data/controls/standard_output/`.

For cattle, the cleaned 2010 CSO AVA42 ED extract and the 2020 CSO Census of Agriculture jointly inform fine-scale historical geography. The 2010 model input is a rearranged, model-ready representation of CSO table AVA42 with published blanks preserved as blanks; it is not labelled as the untouched raw CSO workbook. For 2015-2019, the two census distributions are combined by temporal proximity and constrained to exact annual AAA10 county totals. From 2021-2025, 2020 within-county shares are held while AAA10 continues to supply annual county totals. Official annual county or regional controls reconstruct the remaining livestock and land quantities. GOBLIN biological relationships provide the 21 cattle and 10 sheep cohorts. Fixed 2020 Standard Output coefficients provide production-value exposure.

The historical baseline is complete before any scenario soil or LPIS evidence is attached.

## 2. National scenario controls

National pathway controls are stored in:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

Pasture dry-matter controls are stored in:

```text
data/controls/pasture/GOBLIN_pasture_dm_2020_fixed.csv
```

These controls define the national livestock endpoint, target livestock-land area and future national land-use requirements used by the scenario engine.

## 3. Frozen 2020 spatial land context

The complete production SC2/SC3 spatial context is:

```text
data/controls/land/ED_Land_Context_2020/
├── ED_Colm_Physical_Soil_2020.csv
├── ED_LPIS_Context_2020.csv
├── manifest.json
└── README.md
```

The two scientific controls cover the same **2,857-ED** model universe and are verified against frozen SHA-256 values before use. The merged runtime contract contains 2,857 rows and 26 fields.

Their roles are deliberately separate:

- **mapped physical soil and drainage classes** describe the physical composition of the frozen released-land resource;
- **LPIS 2020** describes current agricultural-use and management context;
- neither layer is read by SC1;
- neither layer can change the national livestock pathway or the frozen ED released-land vector;
- future-use eligibility is supplied separately through explicit, versioned scientific controls.

The source-specific `Colm` identifier in the physical-soil filename and internal provenance fields identifies the source preparation route. Scientific interpretation should use the neutral terms **mapped physical soil**, **soil/drainage class** or **physical land-resource evidence**.

The current compact controls are ED-level. They do not provide an observed parcel-level soil × LPIS joint overlay, so the model does not manufacture one by assuming statistical independence.

## 4. Stage boundary

```text
Baseline + GOBLIN controls
        ↓
SC1
livestock transition + authoritative released-land geography
        ↓
FREEZE
        ↓
SC2
mapped physical soil + LPIS + explicit eligibility
        ↓
SC3
finite shared-resource allocation
```

`ALL_GRASSLAND` is the only spatial land-capacity ceiling used in SC1.

## 5. 2025 status

The historical model contains a reconstructed 2025 livestock state, so SC1 may use 2025 as a sensitivity baseline. SC2 and SC3 remain restricted to 2020 until a separately validated 2025 soil/LPIS context is frozen.

The model never silently applies 2020 spatial land evidence to a 2025 SC2/SC3 run.

## 6. Generated outputs

Historical and scenario outputs are generated products rather than inputs. They are written beneath `data/interim/` and `data/processed/`.

The controlling distinction is:

```text
repository-contained canonical inputs
        -> reproducible scientific runtime

interim / processed files
        -> generated outputs

reporting geometry
        -> downstream presentation only
```

The frozen ED geometry listed in the manifest is reserved for the reporting/cartography layer and does not enter baseline, SC1, SC2 or SC3 calculations.


## 7. External validation and application benchmarks

External datasets used only for validation, method comparison or application testing are stored separately from canonical model inputs under:

```text
data/validation/external/
```

The Achill North benchmark is located at:

```text
data/validation/external/achill_north/
```

It contains extracted 2020 ED livestock and agricultural-land information from the Achill North sanitary survey, together with a validation plan and agriculture Source-Pathway-Receptor context. These files are **not** read by the historical baseline or SC1-SC3 runtime and do not alter controlling livestock, land or scenario quantities.

Their intended role is to test reproducibility of ED-to-catchment livestock allocation, broad livestock-system geography and alternative spatial weighting assumptions such as simple area versus agricultural-land or grassland weighting.
