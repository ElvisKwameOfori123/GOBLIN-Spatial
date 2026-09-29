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

For cattle, the 2010 and 2020 ED census distributions jointly inform 2015-2019 within-county shares through temporal-proximity weighting, with AAA10 county totals imposed exactly. The 2020 ED state is locked as the census anchor, and its within-county shares are held for 2021-2025 while annual AAA10 county totals continue to change. The exact ED path between censuses is therefore a reconstruction assumption rather than directly observed annual ED evidence.

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

For the cattle two-anchor reconstruction, protected implementation checks additionally require exact county closure by component and year, exact 2020-2025 invariance relative to the fixed-2020 panel, non-negative ED values, component accounting closure, within-county shares summing to one, no support where both anchors are zero, bounded intermediate shares, and equal yearly share increments between the two census anchors. These checks verify the reconstruction mathematics; they do not constitute independent ED-level validation for 2015-2019.

For the Step 3 cattle age-sex split, A0 is the flat county-composition null and A1 is the DAFM-informed log-odds prior. Both must preserve every ED \`OTHER_CATTLE\` row and the same rescaled AAA10 county age-sex columns exactly. The pre-specified LSU plausibility screen is cattle > 0, LSU > 0 and \(LSU \le LSU_{\max}+1\), where \(LSU_{\max}=D+0.8S+O+0.1\,sheep\). A1 is retained unless its eligible share is more than one percentage point below A0. Median absolute LSU residual is reported as a diagnostic, pooled and across the fixed five county folds, but is not substituted for the pre-specified gate. This 2020 LSU comparison was used as a plausibility screen during model selection and is therefore not a held-out validation test. DAFM linkage coverage and the neutral fallback for unmatched EDs are also regression-tested.

For Step 4 cattle genetics, G0 is the legacy adult-cow-support allocator and G1 is the production AIM-hierarchical prior. Both must reproduce the same frozen ED age-sex cells and the same national GOBLIN DxD/DxB/BxB margins exactly. The DAFM broad dairy/beef comparison is reported using DxD as the broad dairy-type young-stock component and DxB + BxB as the broad beef-type young-stock component. Because G1 uses this AIM cattle-type information in its prior, G1 agreement with AIM is a calibration/coherence diagnostic, not independent validation. G0 remains a structural sensitivity. Additional diagnostics report the number of EDs using a coherent local AIM signal versus county fallback, genetic shares placed in zero-origin-cow EDs, no-adult-cow receiver/rearing EDs, concentration and adjacent-year rank stability.

A true grassland-weighted ED-to-catchment sensitivity requires spatial information on where grassland lies within each ED-catchment intersection. The current compact LPIS/land context is ED-level, so the repository does not pretend that an ED total alone provides that within-ED geography. Simple area weighting is reproducible now; agricultural-land or grassland-weighted allocation should be added only when a defensible intersectable spatial layer is frozen.


### Separate coherence audit

The release pipeline also runs a separate audit module that recomputes 45
accounting, closure and aggregation identities from the released outputs and
raw inputs. The audit shares input readers and cohort definitions with the
reconstruction, so it is described as a **separate coherence audit**, not as
statistically independent validation. Its purpose is to detect implementation
or reporting inconsistencies after the baseline has been built.

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
