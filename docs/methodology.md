# GOBLIN-Spatial methodology

## 1. Scope

GOBLIN-Spatial is a constraint-preserving small-area representation of Irish agriculture. The active implementation reconstructs the agricultural system annually from 2015 to 2025 across 2,857 Electoral Divisions (EDs), adds biological livestock structure, derives county and Water Framework Directive (WFD) catchment views from the same ED foundation, and produces livestock signatures and an illustrative spatial-attribution perturbation.

The model distinguishes four kinds of information:

```text
observed evidence
        ↓
statistical controls
        ↓
reconstructed small-area structure
        ↓
derived indicators and reporting views
```

An ED-level result does not imply that every underlying quantity was independently observed at ED level in every year. The model therefore distinguishes reporting geography from the geographical resolution of the evidence used to support a variable.

## 2. Historical spatial baseline

### 2.0 Census input preparation (Stage 00)

The CSO Census of Agriculture ED livestock table (AVA42; 2000, 2010, 2020) contains published values, published zeros and blank cells withheld for confidentiality. A blank cell is not a zero: zeros are published separately, and a blank cell holds a small number of holdings. AVA42 also publishes exact State totals, so the number of animals in blank cells is known for every livestock type and census year. Before the model runs, `scripts/prepare_census_inputs.py` fills the blank cells of the 2010 and 2020 censuses under fixed rules.

1. Published values and published zeros are never changed.
2. State totals of total cattle, dairy cows, other cows and sheep are reproduced exactly.
3. In 2020, AAA10 county cattle and AAA09 regional sheep controls act as rounded constraints: the hidden total of a county or region is its control minus its published ED sum, moved by at most 50 head so that the State total closes. 2010 has no ED-compatible annual control and uses the State total only.
4. Fill order is total cattle, dairy cows, other cows, sheep. Other cattle is the residual \(O=T-D-S\) and is never negative. A filled total is never below the ED's published cows. Filled cows are capped at the 99th percentile of the cow share of cattle among published EDs with at least 200 cattle (0.540 in 2020, 0.497 in 2010); published cells are never capped. Animals a unit cannot hold under the cap pass to other units within their rounding tolerance (2020: 53 other cows from Cavan).
5. Within each control unit, the \(n\) blank cells share the hidden total in proportion to

\[
w_i=\lambda\frac{p_i}{\sum_j p_j}+(1-\lambda)\frac{1}{n},
\]

integerised by Hamilton largest remainder, where \(p_i\) is the ED prior: a count for total cattle and sheep, a share of the ED's total cattle for dairy and other cows.

Priors come from fixed chains, using the first source available for each ED. For 2020: total cattle from the 2010 census, then the DAFM/AIM cattle count, then 2000; dairy cows from the 2010 share, then the AIM dairy-type share, the 2000 share and the AIM county share; other cows from an equal blend of the 2010 share and the AIM beef by 36+ month proxy (blend weights of 30-70% give practically identical test error), then 2010, AIM, 2000 and AIM county; sheep from 2010, then 2000. For 2010 the chains are the 2000 census, then the 2020 census, then the national share. AIM rows are matched to census EDs by county and name only where the name is unique on both sides.

The shrinkage weight \(\lambda\) is selected per variable and census year by a hidden-cell test. In every unit, as many small published positive cells are hidden as the unit has blank cells (at least two), drawn from the smallest third, sixth and tenth of published cells (40 draws each, fixed seed). Their known total is reallocated and the error is the share of hidden animals placed in the wrong ED. \(\lambda\) is the grid value in \(\{0, 0.25, 0.5, 0.75, 1\}\) with the lowest mean error. Selected values are 0.5 (total cattle), 0.25 (dairy cows), 0.5 (other cows) and 0 (sheep) for 2020, and 0.75, 0.25, 0.5 and 0.25 for 2010. Shrinkage lowers the 2020 test error from 15.8% to 8.8% for dairy cows, 13.9% to 10.8% for other cows, 11.0% to 9.4% for total cattle and 31.2% to 14.2% for sheep; rank agreement with the hidden values rises for all three cattle variables and is unchanged for sheep. Blank cells lie below the publication threshold, so their values fall in a narrow range: ED evidence carries rank information but overstates their spread.

Each filled cell records its prior source, \(\lambda\) and `TEST_ERROR_PCT`, the weighted absolute error \(\sum|\hat{y}-y|/\sum y\) of hidden test cells that used the same source at the selected \(\lambda\). `CONFIDENCE_CLASS` (HIGH up to 25%, MODERATE up to 50%, LOW above) only summarises that number.

All 3,409 census EDs are reconciled. Animals filled into the 552 EDs outside the 2,857-ED model universe (2020: 7,666 cattle including 1,293 dairy and 851 other cows; 7,198 sheep) are reported by county and WFD catchment and are not moved into model EDs. The audit tables are in `data/inputs/baseline/census_reconciliation/`.

### 2.1 Cattle populations

Dairy cows, other/suckler cows and other cattle are reconstructed separately.

For 2015-2019, the within-county ED share of each cattle component moves linearly from its 2010 census share to its published 2020 census share:

\[
s_{i,k,t}=(1-\lambda_t)s_{i,k,2010}+\lambda_t s_{i,k,2020},
\qquad
\lambda_t=\frac{t-2010}{10}.
\]

The corresponding annual AAA10 county component total is then imposed exactly using proportional allocation with Hamilton largest-remainder integerisation.

The prepared 2020 ED values (Section 2.0) are retained unchanged. Model-universe 2020 ED sums sit slightly below the AAA10 county controls because census animals outside the model universe are not moved into it and AAA10 is rounded to 100 head; these differences are recorded and not spatially reassigned.

For 2021-2025, the published 2020 ED support and within-county share pattern are retained while the annual AAA10 county total changes. A cattle component published as zero in an ED in 2020 therefore remains zero there after 2020.

Total cattle is derived as:

\[
T_{i,t}=D_{i,t}+S_{i,t}+O_{i,t}.
\]

The surrounding-year ED values are census-anchored reconstructions rather than independently observed annual ED populations.

### 2.2 Cattle age-sex structure

The fixed ED `OTHER_CATTLE` population is divided into breeding bulls and six male/female age groups covering under one year, one-to-two years and two years or older.

AAA10 provides the authoritative county age-sex margins. The production prior uses the 2020 DAFM/AIM ED age profile only to shift the local odds of under-one versus one-to-two-year cattle relative to the county. Bulls, cattle aged two years or older and sex composition remain controlled by the county structure.

For ED \(e\) in county \(c\):

\[
\operatorname{logit}(p_e)
=
\operatorname{logit}(p_c)
+
[\operatorname{logit}(q_e)-\operatorname{logit}(q_c)].
\]

Iterative proportional fitting followed by exact integerisation reconciles the prior so that every ED age-sex row reproduces its fixed `OTHER_CATTLE` total and every county age-sex column reproduces its controlled margin.

### 2.3 Cattle biological cohorts

GOBLIN-Spatial represents 21 cattle cohorts: adult dairy cows, suckler cows and breeding bulls plus 18 follower cohorts.

Follower cohorts are defined by parental origin:

- DxD: dairy dam × dairy sire;
- DxB: dairy dam × beef sire;
- BxB: beef dam × beef sire;

and each origin is separated by sex and age class.

The age-sex table is fixed before parental-origin subdivision. GOBLIN/COHORTS provides the national age-sex-specific DxD, DxB and BxB margins. DAFM/AIM dairy-versus-beef composition provides a local spatial signal, with county fallback where a usable ED signal is unavailable. Adult dairy and suckler populations provide soft biological evidence for the DxB/BxB split, but adult-cow absence is not used as a structural gate on follower cohorts.

IPF and exact integerisation preserve both the fixed ED age-sex population and the national parental-origin margins. The resulting 21 cohorts therefore sum exactly to total cattle in every ED-year.

A follower population may occur in an ED where the corresponding adult-parent population is absent locally. This represents spatial separation between adult-parent and follower geography; it is not interpreted as an observed animal movement, purchase or farm-to-farm origin.

### 2.4 Sheep

The prepared 2020 ED sheep population (published values and zeros, plus filled suppressed cells; Section 2.0) is retained unchanged.

For 2015-2019, within-county ED shares move from the 2010 distribution toward the published 2020 distribution. DAFM breeding-ewe information modifies relative county weighting within each of the seven AAA09 regions, after which the official regional sheep total is imposed exactly.

For 2021-2025, the published 2020 ED support pattern is retained while the DAFM county-direction index and AAA09 regional controls determine higher-level annual change. An ED published with zero sheep in 2020 remains zero after 2020.

Sheep are subsequently divided into the 10 cohorts required by GOBLIN. DAFM county breed evidence informs broad lowland-type and mountain-type composition. All 10 cohorts reproduce total sheep exactly.

## 3. Land, farm structure and Standard Output

Livestock populations are combined with agricultural land and selected farm-structure variables on the same ED-year backbone.

The land identity is:

\[
AREA\_FARMED
=
ALL\_GRASSLAND
+
TOTAL\_CEREALS
+
OTHER\_CROPS\_HA.
\]

The 2020 ED state is retained and surrounding years follow the documented higher-level statistical controls. Reconciliation prevents negative components and preserves the land accounting identity.

Standard Output is calculated only after livestock and land quantities are fixed. Fixed 2020 Integrated Farm Statistics coefficients are applied throughout 2015-2025. Standard Output is therefore a fixed-coefficient production-value exposure indicator, not farm income, profit, welfare or an economic-impact estimate.

## 4. Multiscale reporting

The ED is the base modelling geography. County, WFD catchment, GOBLIN-compatible catchment and national views are derived from the same ED state rather than reconstructed independently.

For an additive quantity \(X\):

\[
X_g=\sum_i w_{ig}X_i,
\]

where \(w_{ig}\) is the ED-to-reporting-area weight. Complete EDs have unit weights for county aggregation. WFD catchment weights are derived from the frozen ED-catchment area intersection.

Ratios are never averaged across EDs. Numerators and denominators are aggregated separately and the ratio is recalculated at the target geography.

The WFD view is an environmental reporting geography. It does not imply exact within-ED locations of farms or livestock and it is not a water-quality impact model.

## 5. Livestock signatures and parent-follower geography

Livestock signatures describe agricultural organisation rather than livestock abundance alone. Implemented signature indicators include:

- dairy share of adult cows;
- DxD, DxB and BxB shares of followers;
- followers per adult cow;
- cattle per farmed hectare;
- covered Standard Output per farmed hectare;
- mountain-type share of sheep.

Each ratio is retained with its underlying numerator and denominator so that higher-scale signatures can be recomputed correctly.

For each follower cohort, the model records the finest spatial scale at which the corresponding adult-parent relationship is supported:

- `LOCAL_ED`: corresponding parent cows are present in the same ED;
- `COUNTY_RECEIVER`: followers are present locally, corresponding parent cows are absent locally, but occur elsewhere in the county;
- `NATIONAL_ORPHAN`: final fallback where the corresponding parent population is absent from the county.

These are relationship-support classes, not movement or trade classes.

## 6. Descriptive information tests

The released historical baseline supports four descriptive analyses of the information added by biological structure.

1. **Spatial concentration:** livestock populations are compared with the agricultural-land share of the most livestock-dense EDs.
2. **Matched ED contrasts:** within-county ED pairs with similar total cattle populations are compared on livestock signatures.
3. **Stable-abundance restructuring:** changes in signatures are examined among EDs whose total cattle population changes comparatively little between 2015 and 2025.
4. **Effective information geography:** a between-county variance measure identifies whether a signature varies mainly between counties or substantially among EDs within the same county.

These are descriptive diagnostics, not causal inference.

## 7. Evaluation and verification

Evaluation is separated according to the role of the evidence.

An independent coherence-audit module recomputes accounting, closure and aggregation identities from released outputs and raw inputs. This is verification rather than external validation.

DAFM sheep patterns and AIM cattle composition contribute to reconstruction, so comparisons back to those sources are treated as pattern-fidelity or information-retention diagnostics.

Published 2020 ED livestock-unit information is used as a prespecified plausibility/model-selection screen for the cattle age prior and is not treated as held-out validation.

The withheld 2022 sheep-composition observation provides the strongest holdout comparison in the historical evaluation set, while the Achill North benchmark provides an applied external comparison of livestock, land and ED-to-catchment representation.

## 8. Illustrative 30% spatial-attribution perturbation

The perturbation is applied to the frozen 2020 and 2025 baselines. It is an illustrative static endpoint experiment, not a forecast, scenario pathway, behavioural response, equilibrium model or MACC.

Two independent arms reduce adult dairy cows or adult suckler cows by 30%:

\[
P'_i=0.7P_i.
\]

Under the **signature-preserving representation**, linked followers remain in their reconstructed EDs and scale with the finest valid frozen parent relationship. Dairy changes are linked to DxD and DxB followers, and suckler changes to BxB followers.

The **headcount attribution benchmark** instead applies the national follower-per-parent coefficient to the geography of adult-parent change:

\[
\Delta n^{H}_{i,k}=\bar r_k\Delta P_i.
\]

Both representations impose the same national adult-parent reduction and the same national linked-follower reduction. They differ only in where that change is represented.

For ED \(i\):

\[
d_i=\Delta_i^{S}-\Delta_i^{H},
\]

and for nationally conserved quantities spatial displacement is:

\[
D=\frac{1}{2}\sum_i|d_i|.
\]

Displacement is calculated at ED, county and WFD catchment scales. Additional diagnostics distinguish the component associated with follower populations located in EDs without corresponding local adult parents from heterogeneity in follower-per-parent ratios.

The perturbation demonstrates the spatial information contributed by retaining biological livestock structure; it does not estimate realised behavioural or policy outcomes.

## 9. Interpretation boundary

The historical model does not directly observe or predict individual animal movements, farm-to-farm trade, exact parcel-level livestock location, water-quality impacts, farmer behaviour, adoption, market equilibrium, household welfare or future scenario outcomes.

Its purpose is to provide a transparent, constraint-preserving representation of agricultural abundance, biological composition and spatial organisation from which those questions can be investigated with additional models or evidence.
