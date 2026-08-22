# GOBLIN-Spatial Scientific Assumptions Register

This document records the principal scientific assumptions, modelling choices and interpretation boundaries used by the current production version of GOBLIN-Spatial.

It complements the README and the code. The README explains the model; this register identifies which parts are observed evidence, reconstruction assumptions, exogenous scenario controls, normative spatial experiments, feasibility rules or interpretation limits.

The guiding distinction is:

```text
Observed evidence
      !=
Reconstruction assumption
      !=
Exogenous national control
      !=
Normative spatial experiment
      !=
Feasibility rule
      !=
Interpretation
```

A change to any item marked **Core**, **Assumption**, **Normative**, **Temporary** or **Interpretation** should be recorded in `CHANGELOG.md` when it changes scientific meaning or published outputs.

---

## Historical reconstruction evidence hierarchy

The 2015–2025 historical baseline is **not a simple forward or backward extrapolation from the 2020 Census of Agriculture**.

The evidence hierarchy is:

```text
2020 CSO Census of Agriculture
        ↓
principal ED-level spatial benchmark

Annual CSO county cattle series, 2015–2025
        ↓
observed temporal controls for cattle
        ↓
county totals distributed through validated ED structure

Annual regional sheep series, 2015–2025
        ↓
observed temporal controls for sheep
        ↓
region → county → ED reconciliation
```

The reconstruction therefore combines **detailed 2020 ED geography with repeated annual official higher-level observations**. The surrounding years inherit spatial structure where direct ED observations are unavailable, but their higher-level livestock totals are constrained by the corresponding annual CSO series.

This distinction should be preserved in publications and documentation. The phrase **2020 spatial benchmark** or **2020 ED spatial anchor** does not mean that 2015–2025 values are projected from a single 2020 observation without annual controls.

---

## Current assumptions and modelling choices

| ID | Component | Type / status | Current treatment | Scientific meaning |
|---|---|---|---|---|
| **A01** | National pathway boundary | **Core** | National livestock and land-use quantities are supplied by GOBLIN and remain authoritative. | GOBLIN-Spatial resolves geography; it does not redefine the national pathway. |
| **A02** | Principal full scenario baseline | **Core** | The complete SC1 to SC3 workflow uses the frozen 2020 spatial land context. | 2020 is the principal spatial scenario baseline for the full scenario chain; this is separate from the annual controls used to reconstruct the 2015–2025 historical livestock panel. |
| **A03** | 2025 scenario use | **Temporary** | The reconstructed 2025 livestock state may be used for SC1 sensitivity only. SC2 and SC3 remain disabled for 2025 until a separately validated 2025 land-context bundle is frozen. | The model does not silently apply 2020 land evidence to a 2025 land state. |
| **A04** | Adult livestock controls | **Core** | Adult dairy and suckler populations are the principal spatial endpoint controls. | These categories anchor the spatial livestock transition. |
| **A05** | Follower cattle cohorts | **Assumption** | Remaining cattle cohorts respond using the livestock structure associated with each ED and are reconciled to national cohort controls. | Local livestock signatures are retained while national totals remain authoritative. |
| **A06** | Spatial support | **Assumption** | A cohort or category is not artificially seeded in an ED where the baseline provides no supporting livestock footprint. | The scenario preserves observed spatial support rather than inventing new local livestock systems. |
| **A07** | Local expansion | **Core** | Category-level and ED-level expansion may occur inside an overall nationally contracting pathway where required by the endpoint allocation. | National contraction does not imply that every category or every ED must decline. |
| **A08** | Sheep | **Replaceable assumption** | Sheep remain fixed in the principal cattle-transition workflow unless an explicit national sheep control is supplied. | Current livestock scenarios should not be interpreted as sheep destocking scenarios. |
| **A09** | Spatial incidence rules | **Normative** | `PRORATA`, `DAIRY_PROTECTION`, `ECONOMIC_CAPACITY_PROTECTION` and `SOCIAL_VULNERABILITY_PROTECTION` redistribute where adjustment occurs without changing the national endpoint. | Protection rules are policy incidence experiments, not estimated behavioural responses. |
| **A10** | Protection strength | **Sensitivity parameter** | The principal protection strength is `0.50`. | This is a modelling parameter and should be tested in sensitivity analysis rather than interpreted as an observed coefficient. |
| **A11** | National released land | **Core** | The national gross livestock-land release is supplied by GOBLIN. GOBLIN-Spatial spatialises that quantity rather than deriving a new national release total from ED livestock change. | The spatial layer cannot silently redefine the national land budget. |
| **A12** | Released-land geography | **Assumption / allocation rule** | Spatial livestock pressure, pasture demand and land capability are used to locate the authoritative national release across EDs. | This determines geography of release, not its national magnitude. |
| **A13** | SC1, SC2 and SC3 accounting | **Core** | `PotentialRelease != Opportunity != RealisedConversion`. | Released land is not automatically eligible land, and eligible land is not automatically converted land. |
| **A14** | 08B capability | **Core evidence layer** | 08B provides agricultural capability, GOBLIN soil groups and related land-capability context. | Capability can constrain the geography and opportunity of released land. |
| **A15** | 08C physical soil | **Core evidence layer** | 08C is retained as an independent mapped physical-soil representation and is not silently blended into 08B. | Distinct evidence sources remain auditable rather than being collapsed into one opaque soil signal. |
| **A16** | LPIS | **Core evidence layer** | LPIS contributes land-use, parcel and grassland context but does not replace historical `ALL_GRASSLAND` accounting or independently create released land. | LPIS informs spatial compatibility rather than redefining the livestock land budget. |
| **A17** | SC2 opportunity | **Interpretation** | SC2 opportunity and eligibility scores represent relative compatibility under stated evidence and rules. | They are not adoption probabilities and do not predict that a land-use change will occur. |
| **A18** | SC3 allocation | **Core feasibility rule** | Competing land uses are allocated jointly under shared physical land pools, ED released-land budgets, eligibility constraints and national target ceilings. | The same hectare cannot be allocated twice. |
| **A19** | SC3 infeasibility | **Core feasibility rule** | Infeasible hectares are not forced into allocation; unmet national targets are reported explicitly. | `RealisedConversion` may be lower than the national target where spatial capacity is insufficient. |
| **A20** | Rewetting stock | **Assumption / external anchor** | Rewetting is constrained by the externally anchored national drained-organic grassland stock and by post-allocation residual availability. | Rewetting cannot exceed the relevant physical stock or reuse land already allocated elsewhere. |
| **A21** | Standard Output | **Interpretation** | Fixed-2020 Standard Output is used as a production-value exposure indicator. | It is not profit, household income, welfare, compensation need or land value. |
| **A22** | Scenario time interpretation | **Interpretation** | Current production controls primarily spatialise the specified pathway endpoint rather than predicting a fully dynamic annual ED trajectory. | Results are endpoint spatial stress tests unless intermediate controls are supplied explicitly. |
| **A23** | Behavioural interpretation | **Interpretation** | GOBLIN-Spatial is deterministic and assumption-explicit. | It does not predict individual farmer behaviour, parcel conversion decisions or exact future ED outcomes. |

---

## How to classify future changes

When a new model choice is introduced, classify it before implementation where possible:

### Observed evidence
A quantity taken directly from an authoritative source or frozen spatial input.

### Reconstruction assumption
A rule needed because the source data do not directly contain the required spatial or cohort detail.

### Exogenous national control
A national livestock, land-use or release quantity supplied by GOBLIN or another explicitly authoritative control source.

### Normative spatial experiment
A deliberate policy-incidence assumption such as protecting a particular class of area from a larger share of contraction.

### Calibration choice
A parameter deliberately selected against a stated target. Calibration targets should be named explicitly and should not later be presented as independent validation.

### Validation evidence
Evidence not used to construct or tune the quantity being evaluated.

### Sensitivity parameter
A value whose uncertainty should be explored rather than treated as an observed truth.

### Interpretation boundary
A statement limiting what the resulting quantity can legitimately be claimed to represent.

---

## Required record for a scientific change

A scientifically meaningful change should state, at minimum:

```text
What changed?
Why did it change?
What evidence supports the change?
Was the evidence an input, calibration target or independent validation check?
Which stages or outputs can change?
Which stages or outputs must remain unchanged?
What tests or reconciliation checks were run?
```

The corresponding dated entry belongs in `CHANGELOG.md`.
