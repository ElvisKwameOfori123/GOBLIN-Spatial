# GOBLIN-Spatial

**A constraint-preserving spatial foresight framework for agricultural transition incidence, response potential and land-system transformability.**

GOBLIN-Spatial is the spatial reconstruction and transition-analysis layer of the **GOBLIN AFOLU framework**. It combines a hierarchically constrained reconstruction of Irish agriculture with spatial analysis of nationally coherent livestock and land-use transition pathways.

The framework asks a deliberately spatial question:

> **When a nationally coherent AFOLU transition requires agricultural restructuring, where does transition pressure fall, which places are most structurally exposed, what response potential exists in the land released by that transition, and how much of the associated national land-use transformation can actually be accommodated?**

GOBLIN-Spatial does not determine the national future. National livestock endpoints, authoritative livestock-land release and future national land-use targets are supplied by GOBLIN and remain authoritative.

> **GOBLIN determines the national pathway. GOBLIN-Spatial resolves the geography, incidence and spatial feasibility of that transition.**

GOBLIN-Spatial is therefore a **place-based spatial stress-test of nationally coherent AFOLU pathways**, not a prediction of what individual farms, farmers or parcels will do.

---

## Current migration status

The `colm-direct-production-architecture` branch contains the new scientific architecture described below.

At present:

- the validated 2015–2025 historical baseline is unchanged;
- SC1 is soil-independent and no longer uses 08B/G1–G3, Colm soil or LPIS to move livestock or released land;
- SC2 characterises frozen SC1 release directly with the seven Colm physical-soil categories and retains LPIS as separate agricultural context;
- the generic SC3 shared-resource optimiser is implemented and unit-tested;
- the optional post-SC3 same-end-use feasible-geography analysis is implemented and tested;
- production SC3 runs remain scientifically gated until the Stage-A eligibility matrix and rewetting-capacity control are evidence-backed;
- the legacy 08B/G1–G3 implementation remains on `main` as a benchmark until the Colm-direct migration is fully promoted.

The latest CI on this branch passes the historical regression, Colm-direct unit tests, soil-independent SC1 smoke test and Colm+LPIS SC2 smoke test.

This README describes the **target Colm-direct architecture** and clearly marks the remaining production gates rather than presenting unresolved scientific assumptions as finished results.

---

# Scientific identity

GOBLIN-Spatial is designed to support analysis of **spatial transition resilience**.

Rather than collapsing resilience into a single composite score, the framework separates a sequence of observable and modelled dimensions:

```text
National AFOLU pathway
        ↓
TRANSITION PRESSURE
Where does nationally required adjustment fall?
        ↓
STRUCTURAL DEPENDENCE
Where may the same adjustment be more consequential?
        ↓
SPATIAL RESPONSE POTENTIAL
What can the released transition space plausibly support?
        ↓
TRANSFORMABILITY
Can the land-use requirements of the same future be jointly accommodated?
        ↓
SPATIAL FLEXIBILITY
Is one geography necessary, or can the same end use fit in several places?
        ↓
ROBUSTNESS ACROSS FUTURES
Which exposures, constraints and opportunities persist?
```

These dimensions collectively inform the resilience of places to agricultural and land-use transition.

GOBLIN-Spatial does not interpret resilience as recovery from a short-run shock and does not measure farmer willingness, psychological resistance or behavioural adoption.

---

# Model architecture

The production architecture is deliberately sequential.

```text
                    NATIONAL GOBLIN
                          │
             authoritative pathway controls
                          │
                          ▼
────────────────────────────────────────────
BASELINE
────────────────────────────────────────────
historical agricultural reconstruction
2015–2025
2,857 agricultural Electoral Divisions
livestock + land + farm structure
+ fixed-2020 Standard Output
                          │
                          ▼
────────────────────────────────────────────
SC1   TRANSITION INCIDENCE
────────────────────────────────────────────
national livestock pathway
        ↓
alternative spatial incidence principles
        ↓
adult livestock endpoints
        ↓
21 cattle cohorts + 10 sheep cohorts
        ↓
production-value exposure
        ↓
pasture-demand transition
        ↓
authoritative released-land geography
        ↓
FREEZE
                          │
                          ▼
────────────────────────────────────────────
SC2   SPATIAL RESPONSE POTENTIAL
────────────────────────────────────────────
frozen released land
        +
Colm physical soil
        +
LPIS agricultural context
        +
explicit evidence-backed eligibility
        ↓
physical transition resource
        ↓
land-use-specific response potential
        ↓
FREEZE
                          │
                          ▼
────────────────────────────────────────────
SC3   SPATIAL TRANSFORMABILITY
────────────────────────────────────────────
same-scenario national land-use targets
        +
finite ED × Colm-soil resource cells
        +
explicit eligibility
        ↓
joint competition for land
        ↓
REALISED spatial allocation
        +
UNMET national target
        +
RESIDUAL transition space
                          │
                          ▼
────────────────────────────────────────────
POST-SC3   SAME-END-USE SPATIAL FLEXIBILITY
────────────────────────────────────────────
hold the realised national hectares of each use fixed
        ↓
search alternative feasible geographies
        ↓
necessary / persistent geography
vs flexible / interchangeable geography
                          │
                          ▼
────────────────────────────────────────────
CROSS-SCENARIO SYNTHESIS
────────────────────────────────────────────
pathway uncertainty
×
spatial implementation uncertainty
×
eligibility / response uncertainty
        ↓
robust exposure
persistent constraint
robust opportunity
contingent geography
spatial flexibility
```

The stages answer different scientific questions and are deliberately prevented from silently altering one another.

A useful shorthand is:

```text
SC1: Where does the transition fall?
SC2: What can the resulting land resource support?
SC3: Does the rest of the same national future spatially fit?
Post-SC3: Could the same national end use fit in several different places?
```

---

# Historical spatial baseline

GOBLIN-Spatial reconstructs Irish agricultural activity from **2015 to 2025** across **2,857 Electoral Divisions with recorded agricultural activity**.

The **2020 CSO Census of Agriculture** provides the principal ED-level spatial benchmark. Repeated annual CSO agricultural statistics provide higher-level temporal controls for the surrounding years.

The reconstruction combines:

- cattle and sheep populations;
- 21 cattle cohorts and 10 sheep cohorts;
- grassland, cereals and other agricultural land;
- selected farm-structure characteristics;
- ED-specific livestock composition; and
- fixed-2020 agricultural Standard Output.

For cattle, annual county-level controls constrain the reconstruction. Sheep data are spatially coarser, so annual regional sheep totals and composition are reconciled through county to ED using the validated 2020 spatial structure.

The surrounding years are therefore not produced by simply projecting the 2020 ED distribution forwards or backwards. Higher-level annual observations constrain the reconstruction while the validated local agricultural structure provides the spatial pattern.

| Component | Representation |
|---|---|
| Spatial units | 2,857 EDs with recorded agricultural activity |
| Historical period | 2015–2025 |
| Principal ED benchmark | 2020 Census of Agriculture |
| Cattle | 21 cohorts |
| Sheep | 10 cohorts |
| Agricultural land | Grassland, cereals and other agricultural context |
| Farm structure | Holdings, holding size and selected demographic variables |
| Economic exposure | Fixed-2020 Standard Output |

The resulting baseline provides the common spatial system from which future GOBLIN pathways are evaluated.

---

# SC1: Transition incidence

SC1 asks:

> **Where does a nationally defined agricultural transition fall, and where is the authoritative livestock-land release represented spatially?**

National livestock quantities remain hard controls supplied by GOBLIN.

GOBLIN-Spatial determines **where the adjustment occurs**, not how large the national adjustment should be.

```text
National GOBLIN livestock endpoint
        ↓
Spatial incidence rule
        ↓
Adult dairy + suckler allocation
        ↓
ED livestock structure
        ↓
21-cohort cattle response
        ↓
National reconciliation
        ↓
Production-value exposure
        ↓
Pasture-DM transition signal
        ↓
Authoritative national release spatialised across EDs
```

### SC1 land boundary

SC1 is deliberately **soil-independent** in the Colm-direct architecture.

Colm soil, LPIS and the legacy 08B/G1–G3 capability structure do not determine:

- the national livestock pathway;
- ED livestock allocation;
- the national quantity of livestock land released; or
- the ED released-land vector.

The ED physical ceiling is `ALL_GRASSLAND`.

The principal accounting identity is:

```text
sum(GOBLIN_RELEASED_GRASSLAND_HA)
    = authoritative national GOBLIN release
```

The pasture-DM land balance is retained separately as a diagnostic. In particular:

```text
GOBLIN_RELEASED_GRASSLAND_HA
    ≠ POTENTIAL_SPARED_GRASSLAND_HA by definition
```

`POTENTIAL_SPARED_GRASSLAND_HA`, `SIGNED_GRASSLAND_BALANCE_HA` and `ADDITIONAL_GRASSLAND_REQUIRED_HA` are independent diagnostics and are not rescaled to the parent GOBLIN release.

If the primary livestock/pasture-pressure signal cannot spatially absorb the full parent release because local grassland ceilings bind, an explicit livestock-bearing grassland fallback is used and its hectares and national share are reported. The fallback is an accounting bridge, not a soil-suitability rule.

### Alternative spatial incidence principles

A fixed national pathway can be distributed under alternative implementation assumptions:

- `PRORATA`
- `DAIRY_PROTECTION`
- `ECONOMIC_CAPACITY_PROTECTION`
- `SOCIAL_VULNERABILITY_PROTECTION`

These rules alter the **geography of adjustment**, not the nationally specified pathway.

`SOCIAL_VULNERABILITY_PROTECTION` should be interpreted as the model's explicit demographic/farm-structure proxy based on the variables coded in the SC1 baseline, not as a complete measure of social vulnerability.

---

# Transition pressure and structural dependence

SC1 retains separate diagnostics rather than collapsing transition pressure into one opaque score.

These include, where relevant:

- livestock adjustment;
- dairy and suckler dependence;
- livestock concentration and specialisation;
- production-value exposure;
- pasture-demand pressure;
- released-land geography; and
- distributional concentration of adjustment.

Fixed-2020 **Standard Output** is used as a production-value exposure measure.

It is not interpreted as:

- profit;
- farm household income;
- welfare;
- compensation requirement;
- land value; or
- observed ability to absorb transition.

Structural dependence may indicate potential transition constraint or lock-in, but it does not measure farmer attitudes or psychological resistance.

---

# Release, eligibility, opportunity, allocation and adoption are different quantities

A central scientific rule is:

```text
Release
   ≠
Physical resource
   ≠
Eligibility
   ≠
Opportunity
   ≠
Allocation
   ≠
Adoption
```

### Release

Land no longer required for livestock pressure under the parent pathway.

It is a **transition-space budget**, not an assumed future land use.

### Physical resource

The physical composition of that released land as represented by the mapped Colm soil evidence.

### Eligibility

Whether a specific future use is physically permitted within the released resource under the stated evidence and rule set.

### Opportunity

How favourable an eligible location may be for a particular future use based on transparent agricultural or other contextual evidence.

### Allocation

The area assigned by SC3 when testing the national pathway's land-use requirements against finite spatial capacity.

### Adoption

An actual decision by a farmer or land manager.

**Adoption is not modelled by GOBLIN-Spatial.**

---

# SC2: Spatial response potential

SC2 begins only after SC1 livestock and released-land geography are frozen.

It asks:

> **What physical agricultural resource has become transition space, and what future uses could that resource plausibly support?**

SC2 does not change livestock numbers and does not create additional released land.

## Colm physical soil

The Colm-direct core retains seven physical categories directly:

```text
DEEP_WELL_DRAINED
SHALLOW_WELL_DRAINED
POORLY_DRAINED
POORLY_DRAINED_PEATY
ALLUVIUM
PEAT
MISCELLANEOUS
```

No synthetic G1/G2/G3 reconstruction is required in the Colm-direct decision chain, and the legacy assumed farmed-peat fraction is not used to create the physical resource.

The current ED-level attribution is:

```text
COLM_RELEASED_<SOIL>_HA
    = frozen SC1 released hectares
      × Colm ED physical-soil share
```

or conceptually:

```text
R_e → R_e,s
```

This is explicitly a **proportional within-ED physical-resource characterisation**. It does not claim that the exact released parcels or their parcel-level soil provenance have been observed.

## LPIS evidence

LPIS remains a **separate agricultural-use and management context layer**.

The current compact controls do not contain a measured parcel-level Colm-soil × LPIS joint overlay. GOBLIN-Spatial therefore does not manufacture an independence-based cross-product that would imply the soil and LPIS attributes are observed on the same released hectare.

LPIS:

- does not change frozen SC1 release;
- does not change the seven-category Colm physical partition;
- can support transparent agricultural context and future use-specific opportunity; and
- should enter hard eligibility only where the scientific rule can be implemented without inventing parcel-level joint provenance.

A future validated Colm-soil × LPIS grassland overlay could tighten this boundary without changing the SC1 logic.

## Eligibility evidence

Eligibility rules are treated as scientific assumptions and require explicit evidence.

For every Stage-A future use and every Colm physical category, the production rule must be complete, versioned and documented.

The preferred principal representation is:

```text
0 = physically excluded under the stated screen
1 = physically eligible under the stated screen
```

Intermediate coefficients are used only where they have a defensible quantitative interpretation. A value such as `0.5` is never used merely to mean "uncertain" or to improve target closure.

Scientific uncertainty should normally be handled through alternative documented rule sets rather than hidden inside arbitrary weights.

## Response potential and adaptive capacity

SC2 is best interpreted as measuring **spatial response potential**, representing an important biophysical and agricultural component of adaptive capacity.

It does not claim to measure complete adaptive capacity. A fuller assessment could additionally require information on capital, infrastructure, processing, markets, skills, institutions, tenure, finance and behaviour.

Those dimensions are outside the present GOBLIN-Spatial core.

---

# SC3: Spatial transformability

SC3 asks:

> **Can the explicit national land-use requirements associated with the same GOBLIN pathway actually be accommodated within the released transition space?**

The principal competing Stage-A uses are:

```text
AD grass
Biorefinery grass
Willow
Additional tillage
Forest
```

For ED `e`, Colm soil category `s`, and future use `u`, let:

```text
x[e,s,u]
```

denote allocated hectares.

The fundamental shared-land constraint is:

```text
sum_u x[e,s,u] <= R[e,s]
```

A hectare that is eligible for several alternatives remains **one hectare**. It cannot be independently allocated to forestry, willow and tillage.

For every national land-use target:

```text
Realised_u + Unmet_u = Target_u^GOBLIN
```

An unmet target is not treated as software failure. It is a substantive result showing that the national pathway cannot be fully accommodated under the stated spatial evidence and constraints.

The Stage-A optimiser is lexicographic:

1. minimise total unmet national target;
2. only when an explicit evidence-backed opportunity mapping is supplied, preserve that minimum shortfall and maximise opportunity fit.

Without such an opportunity mapping, the result is interpreted as a **feasibility solution**, not as a uniquely preferred or predicted future land-use map.

---

# Rewetting: restoration requirement, not automatic livelihood opportunity

Rewetting is treated separately because:

```text
Mapped peat
    ≠
Drained agricultural organic soil
    ≠
Rewettable capacity
```

A positive rewetting target therefore requires an explicit, versioned and scientifically defensible estimate of drained agricultural organic-soil capacity.

Mapped Colm peat or LPIS peat context alone is insufficient to define rewettable land.

Rewetting also has a different interpretation from the productive transition uses. In the present framework it is primarily an **environmental/restoration land requirement**, not an automatic alternative-income or livelihood opportunity.

Accordingly:

```text
productive transition opportunity
    ≠
restoration capacity
```

An ED should not be classified as having strong productive diversification opportunity merely because substantial rewetting capacity exists there.

---

# Same-end-use feasible geographies

A single SC3 solution is not automatically interpreted as "the future".

The optional post-SC3 spatial-flexibility layer asks:

> **Holding the realised national hectares of every land use fixed, what other spatial configurations could achieve the same national end-use outcome?**

For each future use `u`:

```text
sum_i AlternativeAllocation[i,u]
    = sum_i ReferenceSC3Allocation[i,u]
```

The analysis therefore preserves the same realised national end-use vector rather than allowing the optimiser to substitute one use for another.

It can produce:

- sampled alternative feasible geographies;
- sampled minimum and maximum ED allocation;
- allocation ranges and variability;
- allocation frequency across feasible solutions; and
- exact minimum/maximum feasible allocation for selected ED-use questions.

This supports a distinction between:

```text
narrow feasible range
    → more spatially necessary / persistent geography

wide feasible range
    → more spatially flexible / interchangeable geography
```

This analysis does not create a new GOBLIN pathway and does not represent farmer adoption probability.

See [`docs/sc3_feasible_geographies.md`](docs/sc3_feasible_geographies.md).

---

# Spatial transition resilience

The full framework distinguishes four related questions:

```text
SC1
Where does pressure fall?

SC2
What response potential exists?

SC3
What transformation is spatially feasible?

Post-SC3
How spatially necessary or interchangeable is that feasible geography?
```

A simple place-based interpretation is:

| Transition pressure | Productive response potential | Interpretation |
|---|---|---|
| High | Limited | Priority transition constraint |
| High | Stronger | Prepared transition potential |
| Lower / contingent | Stronger | Strategic transition opportunity |
| Lower / contingent | Limited | Lower immediate pressure but limited diversification capacity |

Rewetting/restoration capacity is reported separately from productive response potential unless a separate socioeconomic mechanism justifies treating it as a livelihood opportunity.

The purpose is not to label places as winners and losers. It is to identify where **anticipatory and place-sensitive transition policy may need to differ**.

---

# Cross-scenario robustness

GOBLIN-Spatial does not assume that one scenario map represents the future.

The resilience synthesis evaluates variation across:

```text
pathway
× spatial implementation rule
× evidence / eligibility sensitivity
```

This supports transparent classifications such as:

### Robust exposure

Areas that experience substantial transition pressure across many plausible pathway and implementation combinations.

### Persistent constraint

Areas where substantial exposure repeatedly coincides with limited productive response potential or spatial compatibility.

### Robust opportunity

Areas that repeatedly retain stronger productive transition-space opportunities.

### Contingent geography

Areas whose apparent exposure or opportunity depends strongly on the pathway, implementation assumption or eligibility evidence.

### Spatial flexibility

Areas that are interchangeable within multiple feasible configurations for the same realised national end-use outcome.

This ensemble perspective is preferred to claiming one correct 2050 spatial allocation.

---

# Active national pathways

The runtime reads active pathways from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

The current active 2050 pathways are:

```text
SI_SG
BE_SG
ALL_GAS_NZ
```

GOBLIN supplies the pathway-specific livestock, land-release and land-use target quantities. GOBLIN-Spatial must preserve scenario isolation throughout the full chain.

For example, `BE_SG` and `ALL_GAS_NZ` must never silently inherit livestock or land-use controls from one another.

The principal resilience application can focus on `BE_SG` and `ALL_GAS_NZ` as contrasting transition stresses, while `SI_SG` remains available as an additional supported pathway and validation/sensitivity case.

---

# Sources of uncertainty

GOBLIN-Spatial distinguishes uncertainty by mechanism rather than collapsing it into one score.

### Pathway uncertainty

How spatial outcomes change across nationally coherent GOBLIN futures.

### Spatial implementation uncertainty

How outcomes change under alternative incidence and protection principles.

### Land-response uncertainty

How eligibility and transformability change under alternative scientifically defensible land-response assumptions.

### Feasible-geography uncertainty

How many spatial configurations can deliver the same realised national end-use outcome after the pathway, incidence rule and eligibility evidence are fixed.

The central foresight question is:

> **Which spatial conclusions remain consequential despite these uncertainties?**

---

# Reporting and scientific outputs

GOBLIN-Spatial separates model execution from reporting.

```text
MODEL
  ↓
frozen scientific outputs
  ↓
REPORTING CODE
  ├── maps
  ├── graphs
  ├── tables
  ├── GIS exports
  └── publication figures
```

The reporting layer consumes scientific outputs. It does not determine model mathematics and must not independently recalculate SC1, SC2 or SC3 results.

Frozen outputs can be translated into:

- transition-pressure maps;
- protection-relief and displaced-exposure maps;
- released-land maps;
- Colm physical-resource maps;
- productive-response-potential maps;
- realised-allocation maps;
- target-versus-realised-versus-unmet charts;
- same-end-use spatial-flexibility maps;
- robustness and persistence maps;
- pathway and implementation comparisons;
- GIS-ready outputs;
- manuscript tables; and
- publication figures.

A useful reporting principle is:

> **Maps explain where. Charts explain how much. Cross-scenario synthesis explains how robust the geography is.**

Publication figures should be generated from frozen results rather than manually reconstructed in Excel or GIS software.

---

# Reproducibility and evidence provenance

Routine production execution is designed around repository-contained, versioned controls rather than silent external replacement of scientific inputs.

Every major spatial evidence source should document:

- source;
- year;
- native spatial resolution;
- target spatial resolution;
- aggregation method;
- units;
- scientific role;
- model stage;
- missing-data treatment;
- version; and
- integrity checksum where applicable.

The Colm-direct Stage-A evidence register is maintained at:

[`docs/colm_direct_eligibility_evidence_register.md`](docs/colm_direct_eligibility_evidence_register.md)

The architecture contract is maintained at:

[`docs/colm_direct_sc1_sc3_architecture.md`](docs/colm_direct_sc1_sc3_architecture.md)

The core development rule is:

> **Software structure may improve, but validated scientific mathematics must not change silently.**

The model is designed to fail transparently when required evidence or capacity is unavailable rather than silently inventing substitutes.

---

# Validation philosophy

Key scientific invariants include:

### National livestock closure

For each pathway `p` and livestock category `k`:

```text
sum_e H[e,p,k] = H_GOBLIN[p,k]
```

### Spatial-incidence closure

Alternative incidence principles redistribute the same national transition:

```text
sum_e DeltaH[e,p,r] = DeltaH[p]
```

### Released-land integrity

```text
0 <= R[e,p] <= ALL_GRASSLAND[e]
```

and:

```text
sum_e R[e,p] = authoritative GOBLIN gross release[p]
```

SC2 evidence must not change frozen SC1 release.

### SC2 physical-resource closure

```text
sum_s R[e,s] = R[e]
```

for the seven Colm physical categories.

### Eligibility consistency

```text
x[e,s,u] > 0  =>  E[e,s,u] > 0
```

### Shared land conservation

```text
sum_u x[e,s,u] <= R[e,s]
```

### Target accounting

```text
Target[p,u] = Realised[p,u] + Unmet[p,u]
```

### Final land accounting

```text
AllocatedLand[e] + ResidualLand[e] = FrozenRelease[e]
```

### Scenario isolation

No pathway may silently inherit livestock or land-use controls from another pathway.

---

# Running the model

GOBLIN-Spatial can be run through a guided interface or with explicit staged commands.

## Guided mode

```bash
goblin-spatial
```

In an interactive terminal, the model asks whether to stop after:

```text
1. Baseline
2. SC1
3. SC2
4. SC3
```

SC1 supports the reconstructed 2020 and 2025 livestock baselines. Colm-direct SC2 and SC3 currently require the validated 2020 spatial context.

## Verify repository inputs

```bash
goblin-spatial fetch-data --verify-only
```

## Build the historical baseline

```bash
goblin-spatial build \
  --config configs/ireland_2015_2025.yaml
```

## Baseline only

```bash
goblin-spatial study --through baseline
```

## Stop after SC1

```bash
goblin-spatial study \
  --through sc1 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

## Stop after SC2

```bash
goblin-spatial study \
  --through sc2 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

SC2 can run as physical-resource + LPIS context without applying unresolved future-use eligibility assumptions.

## Full study through SC3

SC3 deliberately has **no default suitability assumptions**. A validated Colm eligibility-rule control is required, and a validated rewetting-capacity control is also required whenever the selected pathway has a positive rewetting target.

```bash
goblin-spatial study \
  --through sc3 \
  --scenario ALL_GAS_NZ \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --colm-eligibility-rules path/to/validated_colm_rules.csv \
  --rewetting-capacity path/to/validated_rewetting_capacity.csv
```

Until those controls are scientifically approved, production SC3 scenario results remain gated even though the generic finite-resource allocator is implemented and tested.

## Direct principal runner

```bash
goblin-spatial-principal SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --stage SC2
```

---

# Reporting commands

Reporting is downstream of completed model runs.

## Build the cross-run result package

```bash
goblin-spatial report path/to/completed_study_root
```

This builds the cross-run workbook/SQLite result package from completed principal runs. Development subsets can be processed with `--allow-partial`.

## Generate publication figures

```bash
goblin-spatial figures \
  path/to/GOBLIN_Spatial_Final_Results.sqlite
```

## Generate maps / GIS outputs

```bash
goblin-spatial maps path/to/final_results_directory
```

The reporting code reads frozen outputs. It does not rerun or redefine the scientific model.

---

# Interpretation boundary

GOBLIN-Spatial can identify:

- where national transition pressure is spatially concentrated;
- where existing agricultural systems are structurally more exposed;
- where livestock contraction creates transition space;
- what physical characteristics that released resource contains;
- what alternative uses are scientifically eligible;
- how national future land-use requirements compete for finite land;
- where those requirements can or cannot be jointly accommodated;
- where the same end use has narrow or broad feasible spatial alternatives; and
- which spatial exposures, constraints and opportunities remain robust across plausible configurations.

GOBLIN-Spatial does **not** predict:

- which individual farmer will exit or diversify;
- farmer willingness to adopt;
- parcel-level future decisions;
- land prices;
- compensation requirements;
- farm household welfare;
- endogenous national demand; or
- the exact year-by-year path of land-system change.

These questions require additional farm-level, behavioural, market or dynamic modelling and are outside the v1 framework.

---

# Relationship to the wider modelling ecosystem

GOBLIN-Spatial occupies a specific position between national pathway modelling and downstream farm/environment analysis.

```text
GOBLIN / OptiGob
  │
  │ WHAT NATIONAL FUTURE / HOW MUCH?
  ▼
GOBLIN-SPATIAL
  │
  │ WHERE, UNDER WHAT CONSTRAINTS,
  │ AND WITH WHAT SPATIAL RESILIENCE?
  ▼
AGRISYN
  │
  │ optional synthetic-farm incidence within fixed ED endpoints
  ▼
farm-level structural analysis

GOBLIN-SPATIAL
  │
  └──────────────→ GEOGOBLIN
                    optional catchment/environmental consequences
                    of the frozen spatial configuration
```

Agrisyn and GeoGOBLIN are complementary downstream tools. They must not overwrite the national or ED endpoint accounting already fixed upstream by GOBLIN and GOBLIN-Spatial.

---

# When GOBLIN-Spatial v1.0 is complete

The Colm-direct framework is ready to freeze as v1.0 when:

1. the scientific transition-resilience question is fixed;
2. the historical spatial baseline remains validated;
3. national GOBLIN pathway authority is preserved;
4. SC1 closes exactly and remains independent of SC2 evidence;
5. all active SC2 Stage-A eligibility rules are evidence-backed and versioned;
6. rewetting uses independently defensible drained-organic/agricultural capacity;
7. SC3 conserves finite land and reports all realised, unmet and residual quantities;
8. the agreed pathway × implementation matrix is rerun with the validated Colm-direct controls;
9. the same-end-use feasible-geography analysis is run only on scientifically valid SC3 results;
10. legacy 08B and Colm-direct results are compared and documented;
11. cross-scenario robustness results are reproducible; and
12. tests, maps, tables, README and manuscript report the same scientific architecture.

At that point:

```text
GOBLIN-SPATIAL v1.0
        ↓
FROZEN SCIENTIFIC ARCHITECTURE
        ↓
publication
        ↓
future extensions become separate work
```

The existence of additional interesting datasets or modelling methods is not, by itself, a reason to change the frozen v1 architecture.

---

# Project context and contributors

**GOBLIN-Spatial is developed at the University of Galway within the wider LandingZoNES and FORESIGHT research programmes and the GOBLIN modelling framework.** It extends national agricultural and land-use modelling to a finer spatial scale by reconstructing agricultural activity across Electoral Divisions and spatialising nationally defined transition pathways.

GOBLIN-Spatial is developed by **Elvis Kwame Ofori** as part of his doctoral research at the University of Galway, under the supervision of **Professor David Styles** and **Professor Cathal O'Donoghue**.

The framework builds on contributions from the wider modelling team. **Dr Daniel Henn** developed the detailed national cattle cohort representation that provides an important livestock-structure input to the reconstruction. **Dr Colm Duffy** contributes modelling, spatial-data and software-development expertise, including methodological review, soil and land-context integration, and development of the wider GOBLIN/GeoGOBLIN modelling ecosystem.

---

# Summary

The defining logic of GOBLIN-Spatial is:

```text
GOBLIN national future
        ↓
local transition incidence
        ↓
structural exposure
        ↓
released transition space
        ↓
physical and agricultural response potential
        ↓
joint spatial transformability
        ↓
realised + unmet + residual
        ↓
same-end-use spatial flexibility
        ↓
robust versus contingent geography
        ↓
PLACE-BASED SPATIAL TRANSITION RESILIENCE
```

The framework is built around one central principle:

> **National pathways should remain nationally coherent, but their spatial consequences, constraints and possibilities must be made visible.**

---

# Citation

If you use GOBLIN-Spatial in research, please cite the associated software release, dataset record and methodological publication when available.
