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

For cattle, the 2010 and 2020 ED census distributions jointly inform 2015-2019 within-county geography through temporal-proximity weighting, with AAA10 county totals imposed exactly. The published 2020 ED state is retained unchanged. A separate 2020 reference composition guides component reconstruction in years without ED observations, while annual AAA10 county totals continue to change. The exact ED path between censuses is therefore a reconstruction assumption rather than directly observed annual ED evidence.

### Historical validation evidence

The publication validation separates **verification**, **independent or held-out tests**, **cross-source consistency checks** and **diagnostics**. Exact closure to an imposed control verifies implementation; it is not treated as empirical validation of values that were forced to match.

The two reproducible runners are:

```bash
python scripts/run_historical_validation.py
python scripts/run_baseline_validation.py
```

The second runner writes the publication-oriented suite to `data/processed/validation/historical/baseline_suite/`.

| Test | Evidence class | Question |
| --- | --- | --- |
| T1: 2020 ED livestock units | Held-out derived indicator | Does the derived cattle age structure reproduce a published ED livestock-unit quantity that was not used in fitting? Published cattle and sheep totals are inputs, so this is not independent validation of the whole ED livestock population. |
| T2: 2010-to-2020 cross-census temporal transfer | Independent | Given the observed 2020 county level, how well does the 2010 within-county ED pattern predict the independently observed 2020 ED pattern, and does it outperform simple equal-share and grassland-share alternatives? |
| T3: withheld DAFM ewe years | Independent for that interpolation step | Can county ewe-share interpolation recover omitted 2016 and 2022 observations better than freezing the 2020 pattern? |
| T4: withheld 2022 sheep breed composition | Independent for that interpolation step | Can interpolation from the surrounding breed anchors recover omitted 2022 upland/lowland composition? |
| T5: 2020 Census versus AIM ED cattle totals | Cross-source consistency | Do the June Census anchor and the AIM annual/two-snapshot register geography agree despite different statistical concepts? |
| T6: reconstructed county sheep versus DAFM sheep census | Pattern fidelity / consistency | Is the CSO-controlled reconstruction coherent with DAFM county sheep geography? DAFM ewe information enters the production allocation, so this is not independent validation. |
| T7: national reconstructed cohorts versus COHORTS | Biological-system consistency | Are the CSO-controlled cohort totals coherent with the separate COHORTS representation despite classification differences? |
| T8: adjacent-year spatial rank continuity | Diagnostic | Does the reconstruction introduce unintended year-to-year spatial jumps, including around the deliberately unreconciled published 2020 anchor? |

The historical runner additionally retains the Achill North applied ED-to-catchment benchmark and implementation checks for accounting closure, support rules and temporal stability.

For count-like comparisons the publication suite reports Lin's concordance correlation coefficient (CCC), Spearman rank correlation, Pearson correlation on `log(1+x)`, MAE, RMSE, mean bias, normalised RMSE and Nash-Sutcliffe efficiency (NSE). Where a simple alternative is available, skill is

[
Skill = 1 - \frac{RMSE_{model}}{RMSE_{baseline}}.
]

Zero/non-zero agreement is reported where support is scientifically relevant. MAPE is not used because livestock distributions contain many zeros and small values. ED-level confidence intervals use a county-cluster bootstrap so EDs sharing county controls are not treated as independent resampling units.

For the cattle two-anchor reconstruction, protected implementation checks additionally require exact county closure by component and year outside the observed 2020 anchor, unchanged published 2020 ED values, non-negative ED values, component accounting closure, within-county shares summing to one, no support where both census anchors are structural zero, bounded intermediate shares and the specified temporal weighting between the two census anchors. These checks verify reconstruction mathematics; they do not independently validate the exact 2015-2019 ED path.

For Step 3 cattle age-sex disaggregation, A0 is the flat county-composition null and A1 is the DAFM-informed log-odds prior. Both preserve every ED `OTHER_CATTLE` row and the same rescaled AAA10 county age-sex columns exactly. Published ED LSU is held out from fitting, but because published cattle and sheep totals already constrain much of that quantity, LSU is interpreted primarily as a test of the derived age-sex representation. The existing plausibility screen and five fixed county folds are retained as diagnostics rather than substituted for the publication agreement metrics.

For Step 4 cattle genetics, G0 is the legacy adult-cow-support allocator and G1 is the production AIM-hierarchical prior. The fixed ED age-sex containers are preserved exactly. GOBLIN/COHORTS per-cow relationships are scaled by AAA10 national dairy- and other-cow totals in every year, including 2020, to derive the national DxD/DxB/BxB expectations before exact allocation to the fixed containers. G1 agreement with AIM is a calibration/coherence diagnostic, not independent validation, because AIM supplies the spatial cattle-type prior. The 2020 change from the earlier panel-cow denominator is therefore documented as a source-consistency correction to a derived layer, not as evidence of improved predictive accuracy.

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
