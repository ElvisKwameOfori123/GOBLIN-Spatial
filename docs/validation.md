# GOBLIN-Spatial validation and verification

Validation is organised around the role of each evidence source rather than treating every comparison as independent validation.

The development rule is:

> **Software structure may improve, but scientific mathematics must not change silently.**

## 1. Accounting and coherence verification

The historical panel covers 2,857 EDs for 2015-2025.

Core identities include:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

Reconstructed cattle years must reproduce their annual county controls by component. Reconstructed sheep years must reproduce the corresponding seven-region controls. Prepared 2020 ED livestock values (published AVA42 cells plus Stage 00 fills of suppressed cells) remain unchanged. County, WFD catchment, GOBLIN-compatible catchment and national views must reconcile to the common ED baseline for additive quantities.

A separate coherence-audit module recomputes the accounting, closure and aggregation identities from released outputs and raw inputs. This is **verification**, not external validation.

Run:

```bash
python scripts/audit_historical_baseline.py
```

The complete historical release runner executes the audit automatically:

```bash
python scripts/build_historical_release.py
```

## 2. Historical reconstruction diagnostics

The historical evaluation runner is:

```bash
python scripts/run_historical_validation.py
```

and writes diagnostics beneath:

```text
data/processed/validation/historical/
```

### Cattle two-anchor reconstruction

The 2010 and 2020 ED census distributions jointly inform 2015-2019 within-county shares, with annual AAA10 county totals imposed exactly. The prepared 2020 ED state is retained, and its support pattern is held for 2021-2025 while annual county totals change.

Protected checks include exact county closure, non-negativity, component accounting, valid within-county shares, bounded interpolation and preservation of the published 2020 support pattern after 2020.

These checks verify the reconstruction mathematics; they do not make the reconstructed annual ED path an observed annual series.

### Cattle age-sex plausibility screen

The flat county-composition prior is the null representation. The production representation uses DAFM/AIM evidence to shift the local under-one versus one-to-two-year composition while preserving the same ED `OTHER_CATTLE` totals and county age-sex margins.

Published 2020 ED livestock-unit information is used as a prespecified plausibility/model-selection screen. It is not treated as held-out validation.

### Cattle parental-origin coherence

The production genetics prior must preserve the frozen ED age-sex cells and the national GOBLIN DxD/DxB/BxB margins exactly.

Because AIM dairy/beef composition contributes to the spatial prior, agreement with AIM is reported as a **coherence/information-retention diagnostic**, not independent validation.

## 3. Sheep evaluation

### DAFM county-pattern fidelity

DAFM county sheep/ewe information contributes to relative county weighting within the fixed AAA09 regional totals. Comparison back to those data therefore measures **pattern fidelity**, not independent validation.

### 2022 sheep-composition holdout

The 2022 DAFM breed-composition observation is withheld from the interpolation used for the evaluation comparison. County-category composition is reconstructed from surrounding anchors and compared with the withheld 2022 observation.

This is the strongest holdout comparison in the current historical evaluation set.

## 4. Applied external benchmark

The Achill North sanitary-survey material provides an applied comparison of livestock, agricultural land and ED-to-catchment representation.

Because the survey and GOBLIN-Spatial share some underlying official agricultural evidence, the comparison is treated as an **external applied benchmark**, not a fully independent statistical validation sample.

The benchmark also checks reproduction of the published ED-area overlap treatment used in the catchment application.

## 5. Temporal coherence

Adjacent-year ED rankings are compared for principal livestock totals and transparent livestock-signature variables.

These diagnostics are intended to detect unintended temporal discontinuities in the reconstructed annual panel. They are not evidence that every annual ED value was directly observed.

## 6. Catchment reporting checks

The WFD catchment view is derived from a frozen ED-to-catchment area crosswalk.

Checks require:

- unique ED and catchment keys;
- valid non-negative area fractions;
- ED weights that close appropriately across intersecting catchments;
- national additive totals that reconcile between ED and WFD representations.

A true grassland-weighted ED-to-catchment allocation would require intersectable within-ED grassland geography. The historical release therefore uses the reproducible area crosswalk and does not infer within-ED livestock location from ED totals alone.

The within-catchment signature distribution is checked separately from the
accounting value. ED signature values are weighted by their signature
denominator multiplied by the same fractional ED-catchment area weight. This
ensures that the P10, P50 and P90 summaries describe heterogeneity inside the
catchment without changing any catchment total.

## 7. Repository-contained input verification

`data_manifest.yaml` is the machine-readable authority for production inputs.

Run:

```bash
goblin-spatial fetch-data --verify-only
```

The command verifies local repository files and checksums and downloads nothing.

## 8. Interpretation

Exact closure validates accounting, reconciliation and implementation boundaries. It is not independent empirical validation of every reconstructed non-census ED value.

The model should fail transparently when a required input is missing, a checksum fails, a controlling margin is impossible or an accounting identity is violated.
