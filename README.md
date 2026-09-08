# GOBLIN-Spatial

**A constraint-preserving spatial foresight framework for agricultural transition incidence, response potential and land-system transformability.**

GOBLIN-Spatial is the spatial reconstruction and transition-analysis layer of the **GOBLIN AFOLU framework**.

GOBLIN supplies the authoritative national livestock endpoints, livestock-land release and future land-use requirements. GOBLIN-Spatial does not create a new national future. It asks where that transition falls, what response potential exists within the resulting transition space, whether competing national land-use requirements can be accommodated, and how geographically flexible feasible outcomes are.

> **GOBLIN determines the national pathway. GOBLIN-Spatial resolves its geography, incidence and spatial feasibility.**

The framework is designed as a place-based stress-test of **spatial transition resilience**, not as a prediction of individual farmer or parcel decisions.

---

## Scientific question

GOBLIN-Spatial asks:

> **When a nationally coherent AFOLU transition requires agricultural restructuring, where does transition pressure fall, which places are more structurally exposed, what can the resulting transition space plausibly support, and where can the same national future be spatially accommodated?**

The analytical logic is:

```text
National GOBLIN pathway
        ↓
SC1
TRANSITION INCIDENCE
Where does adjustment fall?
        ↓
SC2
SPATIAL RESPONSE POTENTIAL
What can the released resource support?
        ↓
SC3
SPATIAL TRANSFORMABILITY
Can competing national land-use requirements fit?
        ↓
POST-SC3
SPATIAL FLEXIBILITY
Is one geography necessary,
or can the same outcome fit elsewhere?
        ↓
CROSS-SCENARIO ROBUSTNESS
Which constraints and opportunities persist?
```

These dimensions collectively inform **spatial transition resilience**.

---

## How GOBLIN-Spatial works

| Stage | Main question | Main role |
| --- | --- | --- |
| **Baseline** | What is the reconstructed agricultural geography? | 2015–2025 ED livestock, land, farm-structure and production-value structure |
| **SC1** | Where does the transition fall? | Livestock incidence, exposure and released-land geography |
| **SC2** | What can the released resource support? | Soil/drainage characterisation, LPIS context and evidence-backed eligibility |
| **SC3** | Can the same national future fit spatially? | Joint competition among future land-use requirements |
| **Post-SC3** | Is that geography necessary? | Alternative feasible geographies for the same national outcome |

### Baseline

The framework reconstructs Irish agriculture from **2015 to 2025** across **2,857 Electoral Divisions represented in the harmonised agricultural dataset**.

The 2020 Census of Agriculture provides the principal ED-level spatial anchor. Annual higher-level livestock controls constrain surrounding years while preserving validated local structure.

The baseline includes 21 cattle cohorts, 10 sheep cohorts, grassland and other agricultural land context, selected farm-structure indicators and fixed-2020 Standard Output.

### SC1: Transition incidence

SC1 spatialises the nationally fixed livestock pathway.

It determines where livestock adjustment, production-value exposure and authoritative livestock-land release are represented across EDs. Soil, LPIS and future land-use suitability do **not** influence SC1.

Alternative incidence rules can redistribute the same national adjustment across places, including:

- `PRORATA`
- `DAIRY_PROTECTION`
- `ECONOMIC_CAPACITY_PROTECTION`
- `SOCIAL_VULNERABILITY_PROTECTION`

These change the geography of adjustment, not the national pathway.

### SC2: Spatial response potential

SC2 starts only after the SC1 released-land geography is frozen.

It characterises that resource using:

- mapped physical soil and drainage classes;
- LPIS agricultural context;
- explicit evidence-backed eligibility controls.

SC2 represents **spatial response potential**, an important biophysical and agricultural component of adaptive capacity. It does not measure complete socioeconomic adaptive capacity.

### SC3: Spatial transformability

SC3 tests whether the land-use requirements associated with the same GOBLIN pathway can jointly fit within finite eligible released land.

The principal competing uses are:

- AD grass;
- biorefinery grass;
- willow;
- additional tillage;
- forest.

A hectare can be allocated only once.

For each use:

$$
Target_u = Realised_u + Unmet_u
$$

An unmet target is therefore a substantive spatial-feasibility result, not software failure.

Rewetting is treated separately and requires independently validated drained agricultural organic-soil capacity. Mapped peat alone is not interpreted as rewettable land.

### Post-SC3: Spatial flexibility

A single feasible SC3 solution does not necessarily represent a uniquely necessary geography.

The optional post-SC3 analysis therefore holds the realised national hectares of each land use fixed and searches for alternative feasible spatial allocations.

This distinguishes:

- **spatially necessary or persistent locations**;
- **flexible or interchangeable locations**.

The question becomes:

> **Can the same national end-use outcome be delivered through several different geographies?**

---

## Key scientific distinction

GOBLIN-Spatial keeps the following quantities separate:

$$
\boxed{
Release
\neq
Physical\ resource
\neq
Eligibility
\neq
Opportunity
\neq
Allocation
\neq
Adoption
}
$$

**Release** is the transition-space budget inherited from the national pathway. **Physical resource** is the mapped composition of that released land. **Eligibility** determines whether a future use is permitted under explicit evidence. **Opportunity** describes how favourable an eligible location may be where defensible evidence exists. **Allocation** is the area assigned when SC3 tests national pathway compatibility. **Adoption** is an actual land-manager decision and is not modelled by GOBLIN-Spatial.

---

## National pathways and baseline years

The current model supports:

```text
SI_SG
BE_SG
ALL_GAS_NZ
```

The principal resilience application focuses on:

```text
BE_SG
ALL_GAS_NZ
```

as contrasting national climate-neutrality transition contexts. The framework itself remains scenario-generic.

Baseline rules are:

- **2020**: complete Baseline → SC1 → SC2 → SC3 workflow;
- **2025**: SC1 livestock sensitivity only, unless a separately validated land-context bundle is available.

Scenario controls are never mixed across pathways.

---

## Quick start

### Guided interface

```bash
goblin-spatial
```

Choose:

```text
1. Baseline only
2. Through SC1
3. Through SC2
4. Full study through SC3
```

### Reproducible staged execution

Historical baseline only:

```bash
goblin-spatial study --through baseline
```

Example scenario run through SC2:

```bash
goblin-spatial study \
  --through sc2 \
  --scenario BE_SG \
  --baseline-year 2020 \
  --allocation-rule PRORATA
```

Replace `sc2` with `sc1` or `sc3` as required. SC3 additionally requires validated eligibility controls and, where relevant, validated rewetting capacity.

Verify repository-contained inputs with:

```bash
goblin-spatial fetch-data --verify-only
```

Build the historical baseline with:

```bash
goblin-spatial build \
  --config configs/ireland_2015_2025.yaml
```

For the exact SC3 control-file arguments, see [`docs/running.md`](docs/running.md).

---

## Core inputs

| Evidence | Role |
| --- | --- |
| CSO agricultural statistics | Historical reconstruction |
| GOBLIN scenario controls | National pathway authority |
| `ALL_GRASSLAND` | SC1 spatial land ceiling |
| Mapped soil/drainage classes | SC2 physical resource characterisation |
| LPIS | SC2 agricultural context |
| Eligibility controls | SC2/SC3 future-use constraints |
| Rewetting-capacity control | Rewetting feasibility where required |

Detailed provenance, aggregation rules and evidence boundaries are documented separately.

---

## Outputs and reporting

GOBLIN-Spatial separates the scientific engine from reporting:

```text
Baseline / SC1 / SC2 / SC3
            ↓
validated frozen outputs
            ↓
reporting layer
     ├── maps
     ├── charts
     ├── tables
     ├── GIS-ready layers
     └── publication figures
```

Reporting reads frozen outputs and does not recalculate model science.

Principal reporting products can include:

- transition-pressure maps;
- released-land maps;
- response-potential maps;
- pathway-difference maps;
- realised-allocation maps;
- target-versus-realised-versus-unmet charts;
- spatial-flexibility maps;
- robustness maps;
- publication-ready tables and figures.

---

## Validation and reproducibility

The core development rule is:

> **Software structure may improve, but scientific mathematics must not change silently.**

Production tests enforce, among other checks:

- national livestock closure;
- national released-land closure;
- ED grassland capacity;
- SC1 independence from soil and LPIS evidence;
- physical-resource conservation;
- finite shared-land allocation;
- pathway isolation;
- `Target = Realised + Unmet` accounting.

The model fails transparently when authoritative controls are internally inconsistent or required scientific evidence is absent.

---

## Interpretation and limitations

GOBLIN-Spatial can identify:

- where transition pressure is concentrated;
- where agricultural systems are more structurally dependent;
- where land is released;
- what response potential exists within that transition space;
- where national future land-use requirements can or cannot fit;
- where feasible outcomes are spatially necessary or flexible.

It does **not** predict:

- individual farmer behaviour;
- individual parcel conversion;
- farmer willingness to adopt;
- household welfare;
- future market prices;
- exact realised 2050 geography;
- complete socioeconomic adaptive capacity.

The model is therefore a **spatial foresight and transition-incidence framework**, not an agent-based or behavioural adoption model.

---

## Documentation

| File | Purpose |
| --- | --- |
| [`docs/running.md`](docs/running.md) | Guided and scripted execution |
| [`docs/methodology.md`](docs/methodology.md) | Scientific methodology and model architecture |
| [`docs/goblin_pathway_authority.md`](docs/goblin_pathway_authority.md) | National GOBLIN authority and transition accounting |
| [`docs/sc3_feasible_geographies.md`](docs/sc3_feasible_geographies.md) | Post-SC3 spatial-flexibility analysis |
| [`docs/SCIENTIFIC_ASSUMPTIONS.md`](docs/SCIENTIFIC_ASSUMPTIONS.md) | Scientific assumptions and interpretation boundaries |
| [`docs/validation.md`](docs/validation.md) | Validation and reproducibility checks |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Main model variables and interpretation |

---

## Relationship to the wider modelling framework

```text
GOBLIN
national pathway authority
        ↓
GOBLIN-Spatial
where does transition fall
and what spatial futures are feasible?
        ↓
downstream farm-level and environmental assessment
```

GOBLIN-Spatial is designed to complement farm-level analysis tools such as **Agrisyn** and to provide spatial outputs for downstream environmental assessment frameworks such as **GeoGOBLIN**, where appropriate.

---

## Project context

GOBLIN-Spatial is developed at the **University of Galway** within the wider GOBLIN modelling framework and related research programmes.

The framework is developed by **Elvis Kwame Ofori** as part of doctoral research under the supervision of **Professor David Styles** and **Professor Cathal O'Donoghue**.

The wider modelling work also builds on contributions from **Dr Daniel Henn** and **Dr Colm Duffy**.

---

## Citation

If you use GOBLIN-Spatial in research, please cite the associated software release, dataset record and methodological publication when available.
