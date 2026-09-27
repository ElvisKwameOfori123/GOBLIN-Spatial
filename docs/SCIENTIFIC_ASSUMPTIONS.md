# GOBLIN-Spatial Scientific Assumptions Register

This register records the principal scientific assumptions, exogenous controls, normative spatial experiments, feasibility rules and interpretation boundaries used by GOBLIN-Spatial v1.

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

## Historical reconstruction evidence hierarchy

The 2015-2025 baseline is not a simple projection from 2020. For cattle, the 2010 and 2020 CSO Census of Agriculture ED distributions jointly inform the within-county geography of 2015-2019 through time-weighted interpolation. The 2020 ED distribution is held for 2021-2025 because no later ED census is available. Annual official higher-level livestock and land controls constrain surrounding years.

```text
2010 + 2020 CSO ED cattle structure
        ↓
time-weighted within-county cattle geography, 2015-2019
        ↓
2020 ED cattle structure held, 2020-2025

annual county cattle controls
        ↓
annual regional/county sheep controls
        ↓
annual land and farm-structure controls
        ↓
reconciled 2015-2025 ED panel
```

## Current assumptions and modelling choices

| ID | Component | Status | Current treatment | Scientific meaning |
|---|---|---|---|---|
| **A01** | National pathway authority | **Core** | GOBLIN supplies authoritative national livestock endpoints, target livestock-land area and future land-use requirements. | GOBLIN-Spatial resolves geography and feasibility; it does not redefine the national pathway. |
| **A02** | Full spatial baseline | **Core** | The complete Baseline → SC1 → SC2 → SC3 workflow uses the validated 2020 spatial land context. | 2020 is the principal full spatial scenario anchor. |
| **A03** | 2025 scenario use | **Temporary boundary** | The reconstructed 2025 livestock state may be used for SC1 sensitivity only. | The model does not silently apply 2020 soil/LPIS evidence to a 2025 SC2/SC3 run. |
| **A04** | Adult livestock endpoints | **Core** | Dairy and suckler endpoints anchor the principal cattle transition. | Adult controls determine the national direction of structural change. |
| **A05** | Follower cattle cohorts | **Assumption** | Remaining cattle cohorts respond through the validated biological cohort structure and are reconciled to any explicit national controls. | Local livestock structure is preserved without inventing a second national authority. |
| **A06** | Spatial support | **Assumption** | Livestock categories are not artificially seeded into EDs without baseline support, except for the validated receiver/rearing logic where required for cohort closure. | The scenario respects observed local livestock structure while allowing known rearing/finishing geography. |
| **A07** | Sheep | **Replaceable assumption** | Sheep remain fixed in the principal cattle-transition workflow unless an explicit national sheep control is supplied. | Current pathway runs are not sheep-destocking scenarios. |
| **A08** | Spatial incidence rules | **Normative** | `PRORATA`, `DAIRY_PROTECTION`, `ECONOMIC_CAPACITY_PROTECTION` and `SOCIAL_VULNERABILITY_PROTECTION` redistribute where the same national adjustment falls. | These are policy-incidence experiments, not estimated behavioural responses. |
| **A09** | Protection strength | **Sensitivity parameter** | The principal protection strength is `0.50`. | It is a modelling choice and should be sensitivity-tested rather than interpreted as an observed coefficient. |
| **A10** | National released land | **Core** | Gross livestock-land release is derived from the selected baseline `ALL_GRASSLAND` and the pathway `TARGET_LIVESTOCK_LAND_HA`, then frozen as the authoritative national release quantity for that run. | Local pasture-DM calculations do not create a competing national release total. |
| **A11** | Released-land geography | **Allocation rule** | SC1 spatialises the authoritative release using the solved livestock/pasture-DM transition signal, bounded only by ED `ALL_GRASSLAND`. | Soil, LPIS and future-use suitability do not determine SC1 release geography. |
| **A12** | Pasture-DM land balance | **Diagnostic** | `POTENTIAL_SPARED_GRASSLAND_HA`, `SIGNED_GRASSLAND_BALANCE_HA` and `ADDITIONAL_GRASSLAND_REQUIRED_HA` remain independent diagnostics and are not rescaled to the parent release. | The diagnostic can disagree with the authoritative GOBLIN release without creating a second land authority. |
| **A13** | Physical soil evidence | **Core SC2 evidence** | Seven mapped physical-soil/drainage categories characterise the frozen ED released-land resource proportionally. | This is physical resource evidence, not a land-use decision. |
| **A14** | Soil attribution | **Assumption** | Within each ED, frozen release is proportionally distributed across the ED mapped physical-soil shares. | The model does not claim to observe the exact parcels released from livestock use. |
| **A15** | LPIS | **Core SC2 evidence** | LPIS supplies current agricultural-use and management context after SC1 is frozen. | LPIS does not change livestock, national release or the physical-soil partition. |
| **A16** | Soil × LPIS relationship | **Interpretation boundary** | The compact runtime does not contain an observed parcel-level soil × LPIS joint overlay and does not manufacture one through an independence assumption. | ED-level soil and LPIS evidence remain distinct unless a validated joint overlay is supplied in future. |
| **A17** | Eligibility | **Core feasibility rule** | Stage-A land-use eligibility must be explicit, complete, versioned and evidence-backed across the seven physical-soil categories. | No hidden default suitability coefficients are permitted. |
| **A18** | Fractional eligibility | **Sensitivity rule** | Coefficients in `(0,1)` are allowed only when they have a defensible quantitative interpretation. | Intermediate values are not used merely to express uncertainty or improve target closure. |
| **A19** | Opportunity | **Interpretation** | Opportunity remains separate from eligibility. No arbitrary weighted composite is applied by default. | SC2 currently measures biophysical/agricultural response potential, not complete socioeconomic adaptive capacity. |
| **A20** | SC3 land competition | **Core feasibility rule** | AD grass, biorefinery grass, willow, additional tillage and forest compete jointly for finite released-resource cells. | The same hectare cannot be allocated twice. |
| **A21** | SC3 infeasibility | **Core feasibility rule** | Infeasible hectares are reported as unmet rather than forced into allocation. | For every use, `Target = Realised + Unmet`. |
| **A22** | Rewetting | **Separate environmental requirement** | A positive rewetting target requires an independently validated drained agricultural organic-soil capacity control. Mapped peat alone is insufficient. | Rewetting is not automatically interpreted as productive diversification or alternative-income opportunity. |
| **A23** | Standard Output | **Interpretation** | Fixed-2020 Standard Output is a production-value exposure indicator. | It is not profit, household income, welfare, compensation need or land value. |
| **A24** | Scenario time | **Interpretation** | Current pathway runs primarily spatialise specified endpoints rather than predicting annual ED transitions to 2050. | Results are endpoint spatial stress tests unless intermediate controls are explicitly supplied. |
| **A25** | Post-SC3 flexibility | **Core foresight analysis** | The model may hold realised national hectares of each use fixed and search alternative feasible geographies. | One solver map is not automatically treated as the uniquely necessary geography. |
| **A26** | Behaviour and adoption | **Interpretation boundary** | GOBLIN-Spatial is deterministic and assumption-explicit. | It does not predict individual farmer behaviour, parcel conversion, willingness to adopt or exact realised future geography. |
| **A27** | Historical cattle ED weights | **Reconstruction assumption** | For 2015-2019, within-county ED shares of dairy cows, other cows and other cattle are a temporal-proximity-weighted combination of the 2010 and 2020 census shares. Annual AAA10 county totals are imposed exactly. Published 2010 zeroes remain zeroes; a blank 2010 component retains its reconciled 2020 share. From 2021-2025 the 2020 within-county shares are held while AAA10 continues to provide annual county totals. | The two censuses inform the geography but do not observe the exact ED path between them. Post-2020 within-county change is not extrapolated in the main model; trend continuation is a sensitivity only. |

## Core scientific sequence

```text
Release
    !=
Physical resource
    !=
Eligibility
    !=
Opportunity
    !=
Allocation
    !=
Adoption
```

## Required record for a scientific change

A scientifically meaningful change should state:

```text
What changed?
Why did it change?
What evidence supports the change?
Was the evidence an input, calibration target or independent validation check?
Which stages or outputs can change?
Which stages or outputs must remain unchanged?
What tests or reconciliation checks were run?
```

Git history is the authoritative development record. The live scientific documentation should describe the current model rather than preserve superseded architectures.
