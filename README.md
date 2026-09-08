# GOBLIN-Spatial

**A constraint-preserving spatial foresight framework for agricultural transition incidence, response potential and land-system transformability.**

GOBLIN-Spatial is the spatial reconstruction and transition-analysis layer of the **GOBLIN AFOLU framework**. It combines a hierarchically constrained reconstruction of Irish agriculture with spatial analysis of nationally coherent livestock and land-use transition pathways.

The framework asks a deliberately spatial question:

> **When a nationally coherent AFOLU transition requires agricultural restructuring, where does transition pressure fall, which places are most structurally exposed, what response potential exists in the land released by that transition, and how much of the associated national land-use transformation can actually be accommodated?**

GOBLIN-Spatial does not determine the national future. National livestock endpoints, authoritative livestock-land release and future national land-use targets are supplied by GOBLIN and remain authoritative.

> **GOBLIN determines the national pathway. GOBLIN-Spatial resolves the geography, incidence and spatial feasibility of that transition.**

GOBLIN-Spatial is a **place-based spatial stress-test of nationally coherent AFOLU pathways**, not a prediction of what individual farms, farmers or parcels will do.

---

## Production status

The Colm-direct SC1–SC3 architecture is the production scientific architecture of GOBLIN-Spatial.

The validated 2015–2025 historical reconstruction is retained. The scenario chain is now deliberately separated into three scientific stages:

- **SC1** spatialises the livestock transition and authoritative national livestock-land release without using soil suitability or LPIS to move livestock or released land;
- **SC2** characterises frozen SC1 release directly using the seven mapped Colm physical-soil categories and retains LPIS as separate agricultural-use context;
- **SC3** tests the explicit land-use requirements of the same GOBLIN pathway against finite released-land resource cells using complete, versioned, evidence-backed eligibility controls;
- an optional **post-SC3 spatial-flexibility analysis** holds the realised national hectares of each end use fixed and searches for alternative feasible geographies.

Legacy 08B/G1–G3 code and data are retained only for provenance, comparison and sensitivity work. They are not part of the Colm-direct production decision chain.

The model deliberately provides **no hidden default Stage-A suitability assumptions**. SC3 therefore requires an explicit eligibility-control file. A positive rewetting target also requires an explicit validated rewetting-capacity control. This is a scientific safeguard, not an incomplete fallback.

Publication reporting, figure regeneration and manuscript-result replacement are downstream tasks. Existing legacy reporting assets must not be interpreted as Colm-direct results until the reporting layer is explicitly migrated and rerun from frozen Colm-direct outputs.

---

# Scientific identity

GOBLIN-Spatial supports analysis of **spatial transition resilience** without collapsing resilience into one composite score.

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

The framework does not measure farmer willingness, psychological resistance or behavioural adoption.

---

# Model architecture

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
2,857 EDs with recorded agricultural activity
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
REALISED allocation
+ UNMET target
+ RESIDUAL transition space
                          │
                          ▼
────────────────────────────────────────────
POST-SC3   SAME-END-USE SPATIAL FLEXIBILITY
────────────────────────────────────────────
hold realised national hectares of each use fixed
        ↓
search alternative feasible geographies
        ↓
necessary / persistent geography
vs flexible / interchangeable geography
```

The shorthand is:

```text
SC1: Where does the transition fall?
SC2: What can the resulting land resource support?
SC3: Does the rest of the same national future spatially fit?
Post-SC3: Could the same national end use fit in several different places?
```

---

# Historical spatial baseline

GOBLIN-Spatial reconstructs Irish agricultural activity from **2015 to 2025** across **2,857 Electoral Divisions with recorded agricultural activity**.

The **2020 CSO Census of Agriculture** provides the principal ED-level spatial benchmark. Annual county cattle controls and regional sheep controls constrain the surrounding years while preserving validated ED spatial structure.

The baseline includes:

- 21 cattle cohorts and 10 sheep cohorts;
- grassland, cereals and other agricultural land context;
- selected farm-structure variables;
- ED-specific livestock composition; and
- fixed-2020 agricultural Standard Output.

The surrounding years are hierarchically constrained reconstructions, not simple projections of the 2020 ED distribution.

---

# SC1: Transition incidence

SC1 asks:

> **Where does a nationally defined agricultural transition fall, and where is the authoritative livestock-land release represented spatially?**

National livestock quantities remain hard controls supplied by GOBLIN. GOBLIN-Spatial determines **where the adjustment occurs**, not how large the national adjustment should be.

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

## SC1 land boundary

SC1 is deliberately **soil-independent**.

Colm soil, LPIS and legacy 08B/G1–G3 capability do not determine:

- the national livestock pathway;
- ED livestock allocation;
- the national quantity of livestock land released; or
- the ED released-land vector.

The ED physical ceiling is `ALL_GRASSLAND`.

```text
sum(GOBLIN_RELEASED_GRASSLAND_HA)
    = authoritative national GOBLIN release
```

The pasture-DM land balance remains a separate diagnostic:

```text
GOBLIN_RELEASED_GRASSLAND_HA
    ≠ POTENTIAL_SPARED_GRASSLAND_HA by definition
```

`POTENTIAL_SPARED_GRASSLAND_HA`, `SIGNED_GRASSLAND_BALANCE_HA` and `ADDITIONAL_GRASSLAND_REQUIRED_HA` are not rescaled to the parent GOBLIN release.

If the primary livestock/pasture-pressure signal cannot absorb the full parent release because local grassland ceilings bind, a documented fallback reallocates the remainder across available livestock-bearing grassland. Fallback hectares and shares are reported explicitly.

## Alternative spatial incidence principles

The principal incidence rules are:

- `PRORATA`
- `DAIRY_PROTECTION`
- `ECONOMIC_CAPACITY_PROTECTION`
- `SOCIAL_VULNERABILITY_PROTECTION`

These alter the **geography of adjustment**, never the nationally specified pathway.

`SOCIAL_VULNERABILITY_PROTECTION` is a coded demographic/farm-structure proxy, not a complete measure of social vulnerability.

---

# Transition pressure and structural dependence

SC1 retains separate diagnostics for livestock adjustment, production-value exposure, structural dependence, pasture-demand pressure and distributional concentration.

Fixed-2020 **Standard Output** is used only as a production-value exposure measure. It is not interpreted as profit, household income, welfare, compensation requirement or land value.

---

# Release, eligibility, opportunity, allocation and adoption are different quantities

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

- **Release** is the frozen transition-space budget created by the parent pathway.
- **Physical resource** is the mapped composition of that release.
- **Eligibility** is whether a future use is permitted under an explicit evidence-backed rule.
- **Opportunity** is how favourable an eligible location may be under transparent contextual evidence.
- **Allocation** is the area assigned by SC3 when testing pathway compatibility.
- **Adoption** is an actual land-manager decision and is not modelled.

---

# SC2: Spatial response potential

SC2 starts only after SC1 livestock and released-land geography are frozen.

It asks:

> **What physical agricultural resource has become transition space, and what future uses could that resource plausibly support?**

The Colm-direct core retains seven physical categories:

```text
DEEP_WELL_DRAINED
SHALLOW_WELL_DRAINED
POORLY_DRAINED
POORLY_DRAINED_PEATY
ALLUVIUM
PEAT
MISCELLANEOUS
```

The ED-level physical attribution is:

```text
COLM_RELEASED_<SOIL>_HA
    = frozen SC1 released hectares × Colm ED physical-soil share
```

This is a **proportional within-ED characterisation**, not a claim that the exact released parcels are observed.

LPIS remains a separate agricultural-use and management context layer. It does not alter frozen SC1 release or the seven-category Colm physical partition.

The current controls do not contain a validated parcel-level Colm-soil × LPIS joint overlay, so the framework does not manufacture one by assuming statistical independence.

## Eligibility evidence

Every Stage-A use must have a complete, versioned and documented rule across all seven Colm categories.

The preferred principal representation is:

```text
0 = physically excluded under the stated screen
1 = physically eligible under the stated screen
```

Intermediate coefficients are allowed only when they have a defensible quantitative interpretation. A value such as `0.5` is never used merely to mean uncertainty or to improve target closure.

SC2 is interpreted as **spatial response potential**, an important biophysical and agricultural component of adaptive capacity, not complete adaptive capacity.

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

For ED `e`, Colm soil category `s`, and future use `u`, the shared resource constraint is:

```text
sum_u x[e,s,u] <= R[e,s]
```

A hectare eligible for several alternatives remains one hectare.

For every national target:

```text
Realised_u + Unmet_u = Target_u^GOBLIN
```

Unmet target is a substantive spatial-compatibility result, not software failure.

The Stage-A optimiser is lexicographic:

1. minimise total unmet national target;
2. only when an explicit evidence-backed opportunity mapping is supplied, preserve minimum shortfall and maximise opportunity fit.

Without an explicit opportunity mapping, the output is a **feasibility solution**, not a uniquely preferred or predicted future land-use map.

---

# Rewetting: restoration requirement, not automatic livelihood opportunity

```text
Mapped peat
    ≠
Drained agricultural organic soil
    ≠
Rewettable capacity
```

A positive rewetting target requires an explicit validated rewetting-capacity control. Mapped Colm peat or LPIS peat context alone is insufficient.

Rewetting is treated primarily as an **environmental/restoration requirement**. It does not automatically increase productive diversification or alternative-income opportunity.

---

# Post-SC3: same-end-use spatial flexibility

A single LP solution need not represent a uniquely necessary geography.

The optional post-SC3 analysis therefore holds the national realised hectares of **each individual land use** fixed and searches for alternative feasible spatial allocations under the same frozen resource and eligibility constraints.

It provides:

- sampled alternative feasible geographies for national flexibility summaries; and
- exact minimum/maximum ED-use bounds for selected questions.

This analysis distinguishes **necessary or persistent geography** from **flexible or interchangeable geography**. It does not create new pathways, change national targets or estimate adoption probabilities.

---

# Scenario baseline years

- **2020** is the principal complete SC1→SC2→SC3 spatial baseline.
- **2025** may be used for SC1 livestock sensitivity only until a separately validated 2025 Colm+LPIS land-context bundle exists.

The model never silently applies 2020 LPIS or soil context to a 2025 SC2/SC3 run.

---

# Active national pathways

Active pathway controls are read from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

The current active pathways are:

```text
SI_SG
BE_SG
ALL_GAS_NZ
```

Scenario IDs must remain internally consistent. Livestock endpoints, released-land controls and future land-use targets for one pathway are never mixed with another pathway.

---

# Running the scientific model

Verify repository-contained inputs:

```bash
goblin-spatial fetch-data --verify-only
```

Build the historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Run through SC1:

```bash
goblin-spatial study \
  --through sc1 \
  --scenario SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

Run through SC2:

```bash
goblin-spatial study \
  --through sc2 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

SC3 requires an explicit validated Colm eligibility-control file:

```bash
goblin-spatial study \
  --through sc3 \
  --scenario ALL_GAS_NZ \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --colm-eligibility-rules path/to/validated_colm_rules.csv \
  --rewetting-capacity path/to/validated_rewetting_capacity.csv
```

The rewetting-capacity argument is required only where the selected pathway has a positive rewetting target.

---

# Validation philosophy

The development rule is:

> **Software structure may improve, but scientific mathematics must not change silently.**

Production tests enforce, among other checks:

```text
sum_e livestock[e,k] = authoritative GOBLIN livestock endpoint[k]
```

```text
sum_e released_land[e] = authoritative national GOBLIN release
```

```text
released_land[e] <= ALL_GRASSLAND[e]
```

```text
sum_s ColmReleased[e,s] = released_land[e]
```

```text
sum_u allocation[e,s,u] <= ColmReleased[e,s]
```

```text
Realised_u + Unmet_u = Target_u^GOBLIN
```

SC1 also has invariance tests proving that changing Colm, LPIS or legacy 08B fields cannot change the SC1 release vector.

The model deliberately fails when authoritative upstream controls are internally impossible, required scientific controls are absent, or accounting closure is violated.

---

# Reporting boundary

The scientific model and the reporting layer are separate:

```text
SC1 / SC2 / SC3
        ↓
validated frozen outputs
        ↓
reporting code
        ├── maps
        ├── charts
        ├── tables
        └── publication figures
```

Reporting code must **read frozen scientific outputs and never recalculate the model science**.

The legacy reporting modules and workflows remain available for provenance but are not yet the authoritative Colm-direct publication layer. They will be migrated only after the scientific engine and controls are frozen.

---

# Relationship to the wider modelling ecosystem

```text
GOBLIN
national pathway authority
        ↓
GOBLIN-Spatial
ED transition incidence + land-system compatibility
        ↓
Agrisyn
possible within-ED farm-structure incidence

and/or

GOBLIN-Spatial spatial outputs
        ↓
GeoGOBLIN
catchment/environmental consequence assessment
```

GOBLIN-Spatial does not duplicate the national pathway role of GOBLIN, the farm-synthesis role of Agrisyn or the catchment environmental role of GeoGOBLIN.

---

# Interpretation boundary

GOBLIN-Spatial analyses:

> **transition exposure, structural dependence, spatial response potential, transformability, spatial flexibility and robustness.**

It does **not** predict:

- individual farmer behaviour;
- which individual parcel will convert;
- future market prices;
- farm household welfare;
- the exact realised geography of future land-use change; or
- complete socioeconomic adaptive capacity.

Its planning question is:

> **If a nationally coherent agricultural transition occurred, where could adjustment pressure and response potential be concentrated, where would the same future face spatial constraints, and which places remain consequential across alternative plausible implementation conditions?**

---

# Project context and contributors

GOBLIN-Spatial is developed at the University of Galway within the wider LandingZoNES and FORESIGHT research programmes and the GOBLIN modelling framework.

The framework is developed by **Elvis Kwame Ofori** as part of doctoral research at the University of Galway, under the supervision of **Professor David Styles** and **Professor Cathal O'Donoghue**.

The wider modelling work also builds on contributions from **Dr Daniel Henn**, including national cattle cohort structure, and **Dr Colm Duffy**, including spatial-data, modelling and software-development contributions.

---

# Citation

If you use GOBLIN-Spatial in research, please cite the associated software release, dataset record and methodological publication when available.
