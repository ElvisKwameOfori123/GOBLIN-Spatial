# GOBLIN-Spatial validation

Validation is designed around protected scientific boundaries rather than visual agreement with expected maps.

The development rule is:

> **Software structure may improve, but scientific mathematics must not change silently.**

## Historical baseline

The validated historical panel covers 2,857 EDs for 2015-2025.

Core identities include:

```text
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

The 2020 ED baseline is locked as the principal fine-scale spatial anchor. Surrounding years are controlled reconstructions using repeated official higher-level statistics.

The cattle anchor has an additional pre-registered Stage A validation. The current positive-only dairy reconciliation is retained as a reference, while suppression-aware alternatives preserve published positive dairy values and place the known 2020 county dairy residual only into published-zero EDs with explicit support. The selected V1b anchor uses a support mask from the 2010 AVA42 Census and published 2020 `OTHER_CATTLE` as within-county weights. Published ED livestock units are used as an unused same-census benchmark for choosing among the pre-registered anchor candidates; they are not an external source and are not used by the reconstruction itself.

The 2010 Census also provides an out-of-sample check of the fixed-2020 within-county spatial-share assumption. The primary 2015-2025 model retains the 2020 within-county shares, while the earlier census is used to quantify how well that assumption reconstructs an observed earlier spatial state. A separate two-anchor interpolation may be retained as sensitivity analysis rather than replacing this out-of-sample check.

### Historical validation evidence

The current model-paper validation deliberately avoids a composite or "fanciful" validation score. It separates accounting verification from empirical and applied evidence.

The historical validation runner is:

```bash
python scripts/run_historical_validation.py
```

after building the canonical baseline with:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

It writes diagnostics beneath `data/processed/validation/historical/`.

Four additional checks are implemented.

1. **Independent DAFM county sheep comparison.** Reconstructed county sheep totals are compared with the retained DAFM National Sheep and Goat Census totals for 2015, 2020, 2022 and 2025. CSO remains the controlling model source. DAFM is used only as independent validation evidence. Diagnostics report county-level error and spatial-rank agreement.

2. **2022 sheep-composition holdout.** The observed 2022 DAFM breed-composition anchor is omitted. County-category breed shares are reconstructed by interpolation from the 2020 and 2025 anchors and then compared with the withheld 2022 observations. This tests reconstruction performance rather than accounting closure.

3. **Achill North applied benchmark.** The 23-ED livestock and land tables extracted from the 2026 Achill North sanitary survey are compared with the 2020 GOBLIN-Spatial anchor. Because both ultimately use Census of Agriculture 2020, this is an external applied implementation benchmark rather than statistically independent validation. The survey's published ED-area overlap correction for cattle and sheep is also reproduced as a spatial-transfer check.

4. **Temporal spatial-rank stability.** Adjacent-year ED rankings are checked for total cattle, total sheep and transparent livestock-system signature indicators. This is a diagnostic for accidental discontinuities in the reconstructed panel, not independent empirical validation.

The validation suite therefore distinguishes:

```text
accounting closure
    -> verifies implementation and conservation identities

independent / holdout comparisons
    -> validate reconstruction performance where external evidence exists

applied benchmark reproduction
    -> demonstrates that the model can reproduce a real Irish ED-to-catchment workflow

temporal stability diagnostics
    -> detect unintended spatial discontinuities
```

No arbitrary pass/fail thresholds are imposed on independent empirical discrepancies. The raw diagnostics and conventional statistics are reported so the scientific interpretation remains visible.

A true grassland-weighted ED-to-catchment sensitivity requires spatial information on where grassland lies within each ED-catchment intersection. The current compact LPIS/land context is ED-level, so the repository does not pretend that an ED total alone provides that within-ED geography. Simple area weighting is reproducible now; agricultural-land or grassland-weighted allocation should be added only when a defensible intersectable spatial layer is frozen.

## Downstream scenario-module validation

SC1, SC2 and SC3 are retained as downstream/future modules. They are not required to define or validate the current historical GOBLIN-Spatial model paper. Their protected tests remain in the repository so future scenario work cannot silently break scientific boundaries.

## SC1 validation

SC1 must preserve the national GOBLIN pathway while resolving its geography.

For every authoritative livestock control supplied by the selected pathway:

```text
sum_e scenario_livestock[e,k] = national_target[k]
```

For released land:

```text
sum_e GOBLIN_RELEASED_GRASSLAND_HA[e]
    = authoritative national gross release
```

and for every ED:

```text
0 <= GOBLIN_RELEASED_GRASSLAND_HA[e] <= ALL_GRASSLAND[e]
```

The independent pasture-DM diagnostic is checked separately and is not rescaled to the parent release.

### Soil/LPIS invariance

A protected regression test deliberately changes downstream mapped-soil and LPIS fields and verifies that the SC1 released-land vector is unchanged.

This is a causal-boundary test:

```text
change soil / LPIS evidence
        ↓
SC1 livestock and released-land geography must remain identical
```

## SC2 validation

SC2 may characterise the frozen release but may not change it.

For every ED:

```text
sum_s ReleasedPhysicalResource[e,s]
    = GOBLIN_RELEASED_GRASSLAND_HA[e]
```

The seven mapped physical-soil shares must close to one and all physical-resource areas must be finite and non-negative.

The frozen soil and LPIS controls must:

- cover the same 2,857-ED universe;
- contain unique canonical ED keys;
- match the frozen SHA-256 values;
- use the validated 2020 context year.

Eligibility controls must explicitly cover every required future use × soil-class combination and contain only finite coefficients in `[0,1]`. Rewetting is rejected from the generic soil-only eligibility matrix.

## SC3 validation

SC3 treats released land as a finite shared resource.

For every ED × physical-resource cell:

```text
sum_u allocation[e,s,u] <= released_resource[e,s]
```

For every national use target:

```text
Realised_u + Unmet_u = Target_u
```

The allocator must never create negative allocation, exceed physical released resource or double-count the same hectare across competing uses.

A positive rewetting target requires an explicit validated capacity control. Mapped peat alone cannot create rewetting capacity.

## Post-SC3 flexibility validation

Alternative feasible geographies must preserve the same realised national end-use vector as the reference SC3 solution.

For every use `u`:

```text
sum_e AlternativeAllocation[e,u]
    = sum_e ReferenceAllocation[e,u]
```

while retaining the same physical-resource and eligibility constraints.

Exact ED-use minimum/maximum bounds are therefore interpreted within the same national realised outcome, not as different scenarios.

## Scenario isolation

Scenario IDs are hard boundaries. Livestock endpoints, target livestock-land area and future land-use requirements for one pathway must never be combined with another pathway.

The scenario-control loader and reconciliation tests enforce this boundary.

## Repository-contained input verification

`data_manifest.yaml` is the machine-readable authority for frozen production inputs. `goblin-spatial fetch-data --verify-only` verifies required repository files and checksums rather than downloading or rebuilding model inputs.

## Continuous integration

The CI workflow covers:

- Python compilation;
- repository input verification;
- frozen 2020 soil + LPIS context checks;
- historical baseline unit tests;
- complete 2015-2025 regression;
- independent DAFM sheep validation diagnostics;
- 2022 sheep-composition holdout validation;
- Achill North livestock, land and spatial-transfer benchmark checks;
- adjacent-year livestock/signature stability diagnostics;
- SC1 endpoint, release, comparison and metric tests;
- SC2 physical-resource and eligibility tests;
- SC3 finite-resource and feasible-geography tests;
- canonical baseline rebuild;
- real end-to-end SC1;
- real end-to-end SC2 physical-resource preparation.

A real SC3 publication run is deliberately not fabricated in CI because SC3 requires an explicit scientifically approved eligibility control and, where relevant, rewetting-capacity evidence.

## Interpretation of validation

Exact closure validates accounting, reconciliation and implementation boundaries. It is not independent empirical validation of every reconstructed non-2020 ED value, nor does it validate actual future farmer behaviour.

The model should fail transparently rather than silently continue when authoritative controls are internally impossible, required scientific evidence is absent or an accounting identity is violated.
