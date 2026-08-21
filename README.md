# GOBLIN-Spatial

**A constraint-preserving spatial framework for agricultural transition analysis.**

GOBLIN-Spatial is the spatial modelling layer of the **GOBLIN AFOLU framework**. It translates nationally defined agricultural and land-use pathways into geographically resolved outcomes while preserving national totals, historical livestock structure and spatial land constraints.

The current Irish implementation reconstructs agricultural activity across **2,857 Electoral Divisions (EDs) from 2015 to 2025**, anchored to the **2020 CSO Census of Agriculture**.

> **GOBLIN determines the national pathway. GOBLIN-Spatial resolves the geography of that transition.**

```text
Historical agricultural system
        ↓
Spatial livestock baseline
        ↓
National GOBLIN pathway
        ↓
Spatial livestock adjustment
        ↓
Potential land release
        ↓
Soil + parcel + land-use opportunity
        ↓
Alternative land-use allocation
        ↓
Realised transition + unmet opportunity
```

---

## What GOBLIN-Spatial does

The historical engine reconstructs:

- cattle and sheep populations;
- agricultural land and crop areas;
- selected farm-structure characteristics;
- livestock composition and cohort relationships; and
- fixed-2020 agricultural Standard Output.

Livestock are represented through **21 cattle cohorts and 10 sheep cohorts**. The resulting ED-level cohort signatures preserve the local demographic structure of livestock systems when national transition pathways are spatialised.

The framework can then examine:

- where livestock adjustment is concentrated;
- where production-value exposure is greatest;
- how much land is released from livestock pressure;
- the agricultural capability and physical characteristics of released land;
- which alternative land uses are spatially compatible;
- where national land-use targets can be accommodated;
- where targets remain spatially infeasible; and
- where high transition exposure coincides with limited alternative opportunity.

GOBLIN-Spatial is therefore a **spatial stress-test of plausible transition pathways**, not a prediction of what individual farms or parcels will do.

---

# Model architecture

GOBLIN-Spatial follows four linked stages.

```text
BASELINE
   │
   ├── Cattle + sheep
   ├── 31 livestock cohorts
   ├── Land + crops + farm structure
   ├── Standard Output
   └── ED cohort signatures
            │
            ▼
SC1 — LIVESTOCK TRANSITION
   │
   ├── National GOBLIN livestock controls
   ├── Spatial incidence of adjustment
   ├── Cohort propagation
   ├── National reconciliation
   └── Potential released land
            │
            ▼
SC2 — OPPORTUNITY
   │
   ├── Agricultural capability
   ├── Physical soil evidence
   ├── LPIS parcel context
   └── Land-use eligibility / opportunity
            │
            ▼
SC3 — ALLOCATION
   │
   ├── National land-use targets
   ├── Spatial eligibility
   ├── Shared capacity constraints
   └── Realised conversion
            │
            ├── Unmet target
            └── Residual available land
```

---

## Historical spatial baseline

The model reconstructs the agricultural system for **2015–2025** across the same 2,857-ED spatial universe.

The **2020 Census of Agriculture** is the principal spatial anchor. County-level agricultural series and other validated controls are used to reconstruct the surrounding years while preserving the observed 2020 ED structure.

The historical baseline contains:

| Component | Representation |
|---|---|
| **Spatial units** | 2,857 Electoral Divisions |
| **Historical period** | 2015–2025 |
| **Principal anchor** | 2020 Census of Agriculture |
| **Cattle** | 21 cohorts |
| **Sheep** | 10 cohorts |
| **Agricultural land** | Grassland, cereals and other agricultural context |
| **Farm structure** | Holdings, holding size and selected demographic variables |
| **Economic exposure** | Fixed-2020 Standard Output |

The final historical stage preserves **ED-specific livestock cohort signatures**, which provide the structural bridge between the historical reconstruction and future pathway analysis.

---

# SC1: Spatial livestock transition

SC1 converts nationally specified GOBLIN livestock pathways into geographically heterogeneous ED-level transitions.

National quantities remain authoritative.

GOBLIN-Spatial determines **where the adjustment occurs**, not how large the national adjustment should be.

The principal sequence is:

```text
National GOBLIN livestock endpoint
        ↓
Adult dairy + suckler allocation
        ↓
ED-specific cohort response
        ↓
National cohort reconciliation
        ↓
Spatial livestock-pressure change
        ↓
Authoritative national released land
        ↓
ED released-land allocation
```

### Adult livestock controls

Adult dairy and suckler populations are the principal spatial controls.

Follower cohorts respond through validated ED-specific relationships while preserving historical livestock structure and avoiding artificial cohort creation where the baseline provides no supporting livestock footprint.

Sheep are currently carried unchanged in the principal cattle-transition workflow unless an explicit national sheep control is supplied.

### Alternative incidence rules

A fixed national transition can be distributed spatially under alternative incidence assumptions, including:

- `PRORATA`
- `DAIRY_PROTECTION`
- `ECONOMIC_CAPACITY_PROTECTION`
- `SOCIAL_VULNERABILITY_PROTECTION`

These rules alter the **geography of adjustment**, not the nationally specified pathway.

Some EDs may therefore experience livestock expansion even where the **national pathway contracts overall**.

---

# Released land, opportunity and conversion are different quantities

A central accounting rule is:

```text
PotentialRelease ≠ Opportunity ≠ RealisedConversion
```

### PotentialRelease

Land released from livestock pressure under the national pathway.

It is a **spatial land budget**, not an assumed land-use change.

### Opportunity

The part of released land that could plausibly support a particular alternative use after considering spatial evidence such as:

- agricultural capability;
- physical soil characteristics;
- LPIS land and parcel context; and
- relevant land-use constraints.

### RealisedConversion

The area actually allocated after combining:

```text
released-land budget
        +
land-use eligibility
        +
spatial capacity
        +
national target
```

This distinction prevents a national land-use target from being interpreted automatically as a spatially feasible outcome.

When insufficient eligible land exists:

```text
RealisedConversion < NationalTarget
```

and GOBLIN-Spatial reports the **unmet target explicitly**.

---

# SC2: Land opportunity and eligibility

SC2 begins **after SC1 is frozen**.

It does not recompute livestock numbers or alter the released-land total.

Instead, it evaluates the characteristics and potential uses of the land released in SC1.

Three spatial evidence layers are kept conceptually distinct.

### 08B agricultural capability

The principal agricultural-capability layer contains:

- Soil Use Classes 1–6;
- GOBLIN soil groups G1–G3;
- forest yield-class context; and
- peat/cutover agricultural context.

08B may constrain the spatialisation of livestock-driven released land.

### 08C physical soil

08C provides an **independent mapped physical-soil representation**.

It is retained separately from 08B and is not blended into the agricultural-capability signal.

It therefore provides additional physical evidence without silently changing the SC1 livestock or released-land solution.

### LPIS

LPIS contributes parcel and land-use context, including grassland composition and other spatial characteristics.

LPIS does **not** replace the historical `ALL_GRASSLAND` accounting quantity and does not independently create released land.

---

# SC3: Alternative land-use allocation

SC3 tests whether explicit national GOBLIN land-use targets can be accommodated within the spatial opportunity identified in SC2.

Current transition categories include:

| Land use | Role |
|---|---|
| **AD grass** | Grassland supplying anaerobic-digestion feedstock |
| **Biorefinery** | Biomass/feedstock for bioeconomy pathways |
| **Willow** | Short-rotation woody biomass |
| **Additional tillage** | Expansion of crop production where agricultural capability permits |
| **Forest** | Additional afforestation subject to spatial eligibility |
| **Rewetting** | Restoration of eligible organic grassland |

Targets are read from the national GOBLIN scenario controls. They are **not generated or increased by the spatial allocator**.

SC3 respects:

- ED released-land budgets;
- land-use-specific eligibility;
- shared land-capacity constraints; and
- national target ceilings.

For each land use the model can therefore distinguish:

```text
Target
  ↓
Eligible spatial capacity
  ↓
Realised allocation
  ↓
Unmet target
```

Released land remaining after allocation is retained explicitly as residual available land rather than being forced into another use.

---

# Spatial transition foresight

The framework can combine **transition exposure** with **alternative opportunity**.

| Transition exposure | Alternative opportunity | Interpretation |
|---|---|---|
| **High** | **Stronger** | **Prepared transition potential** |
| **High** | **Limited** | **Priority transition constraint** |
| **Lower / contingent** | **Stronger** | **Strategic opportunity** |
| **Lower / contingent** | **Limited** | **Lower immediate priority / monitor** |

This helps distinguish areas where adjustment may be relatively compatible with alternative land uses from areas where substantial transition pressure coincides with relatively few alternatives.

The objective is not to label places as winners or losers, but to identify where **anticipatory transition policy may need to differ spatially**.

---

# Standard Output and transition exposure

GOBLIN-Spatial uses fixed **2020 Standard Output coefficients** to measure agricultural production-value exposure.

Standard Output is used as:

> **a production-value exposure indicator**

It is **not** interpreted as:

- farm profit;
- farm household income;
- welfare;
- compensation requirements; or
- land value.

This distinction is important when interpreting spatial exposure results.

---

# Scenario baseline years

The model supports two different uses of the reconstructed baseline.

### 2020

The **principal spatial scenario baseline**.

The complete:

```text
SC1 → SC2 → SC3
```

workflow is currently defined against the frozen 2020 land context.

### 2025

The reconstructed 2025 livestock state can be used for **SC1 livestock sensitivity analysis**.

SC2 and SC3 are intentionally not run against 2025 until a separately validated 2025 land-context bundle is frozen.

The model therefore does **not** silently substitute 2020 LPIS or soil context for a 2025 spatial state.

---

# Active national pathways

The production runtime reads active pathways directly from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

The current principal pathways are:

```text
SI_SG
BE_SG
ALL_GAS_NZ
```

GOBLIN supplies the national pathway quantities.

GOBLIN-Spatial spatialises those quantities under a common, transparent set of spatial rules.

---

# Reproducibility

The production workflow is **repository-contained**.

A normal repository clone contains the compact inputs required to:

1. verify the frozen input state;
2. rebuild the validated historical baseline; and
3. run the complete 2020 SC1–SC3 workflow.

Routine runtime does not require external-data downloads and has no external-data fallback.

```bash
goblin-spatial fetch-data --verify-only
```

verifies the repository-contained scientific inputs rather than downloading replacements.

First-principles reconstruction is outside the production runtime. Local reconstruction utilities may be used manually by researchers who possess the original source files, but reconstructed outputs cannot silently replace the frozen runtime controls.

---

## Frozen 2020 land context

The production 2020 spatial context is stored under:

```text
data/controls/land/ED_Land_Context_2020/
```

It contains the frozen components required by the scenario runtime:

```text
ED_Soil_Capability_08B.csv
ED_Physical_Soil_08C.csv
ED_LPIS_Context_2020_RUNTIME.csv
manifest.json
README.md
```

The three compact CSVs cover the same **2,857 ED** model universe. Runtime verifies their component checksums and joins only the required fields in memory to reproduce the validated:

```text
2,857 ED × 40-field
```

scientific land-context contract.

Canonical logical SHA256:

```text
6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d
```

The 08B provenance retains:

```text
2,820 direct ED profiles
37 county-fallback profiles
```

while 08C remains an independent physical-soil layer.

---

# Running the model

## Verify repository inputs

```bash
goblin-spatial fetch-data --verify-only
```

## Build the historical baseline

```bash
goblin-spatial build \
  --config configs/ireland_2015_2025.yaml
```

## Run SC1

```bash
goblin-spatial-principal SI_SG \
  --baseline-year 2020 \
  --stage SC1
```

## Run SC2

```bash
goblin-spatial-principal SI_SG \
  --baseline-year 2020 \
  --stage SC2
```

## Run the complete SC1–SC3 chain

```bash
goblin-spatial-principal SI_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA \
  --stage SC3
```

Equivalent runs can be made for the other active scenario IDs.

---

# Validation philosophy

The core development rule is:

> **Software structure may improve, but validated scientific mathematics must not change silently.**

Changes to the production model are checked against:

- the frozen historical baseline;
- livestock cohort relationships;
- national scenario controls;
- land-release accounting;
- 08B capability closure;
- independent 08C physical-soil evidence;
- LPIS accounting;
- SC2 opportunity logic; and
- SC3 target and residual-land closure.

The model deliberately fails when required data or spatial capacity are unavailable rather than silently inventing substitutes.

---

# Interpretation boundary

GOBLIN-Spatial should be interpreted as a framework for analysing:

> **transition exposure, spatial compatibility, opportunity and constraint.**

It does **not** predict:

- the behaviour of individual farmers;
- which individual parcel will convert;
- future market prices;
- farm household welfare; or
- the exact realised geography of future land-use change.

Instead, it asks a more defensible planning question:

> **If a nationally plausible agricultural transition occurred, where could its adjustment pressures and land-use opportunities plausibly be concentrated, and where might spatial constraints require different policy responses?**

---

# Citation

If you use GOBLIN-Spatial in research, please cite the associated software release, dataset record and methodological publication when available.
