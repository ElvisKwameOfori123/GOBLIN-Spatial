# GOBLIN-Spatial

**A constraint-preserving spatial framework for reconstructing agricultural systems, spatialising livestock transition pathways, identifying released-land opportunities, and testing feasible alternative land-use transitions.**

GOBLIN-Spatial provides the spatial layer linking the national **GOBLIN AFOLU modelling framework** to fine-scale agricultural geography. The current Irish implementation reconstructs agricultural activity across **2,857 Electoral Divisions (EDs) from 2015 to 2025**, anchored to the **2020 CSO Census of Agriculture**, and uses this spatial baseline to examine where future livestock adjustment, land release and alternative land-use transitions could occur.

GOBLIN determines the **national pathway**. GOBLIN-Spatial resolves the **geography of that transition**.

```text
Historical agricultural system
        ↓
Spatial livestock baseline
        ↓
National GOBLIN pathway
        ↓
SC1 cattle transition + exposure + released land
        ↓
08B agricultural capability + 08C physical soil + LPIS
        ↓
SC2 overlapping alternative-land opportunity
        ↓
SC3 constrained national-target allocation
        ↓
Realised transition + unmet target + residual available land
```

## What the model does

The historical engine reconstructs cattle, sheep, agricultural land, crops and selected farm-structure characteristics at ED level. Livestock are represented through **21 cattle cohorts and 10 sheep cohorts**, while fixed 2020 Standard Output coefficients provide a measure of agricultural production-value exposure.

The completed baseline then provides the spatial starting point for transition analysis. National cattle pathways are translated into geographically heterogeneous changes while preserving the underlying livestock structure and ED-specific cohort relationships. Scenario analysis can start from either the **2020 anchor** or the complete reconstructed **2025 baseline state**. Sheep remain unchanged context in the principal cattle-transition study.

This allows GOBLIN-Spatial to examine:

- where adult-cattle and complete cohort adjustment are concentrated;
- which areas face the greatest fixed-2020 Standard Output production-value exposure;
- how concentrated transition incidence is across EDs and counties using Gini and concentration diagnostics;
- how much agricultural land could be released from livestock pressure;
- the soil, parcel and agricultural characteristics of that released land;
- which alternative land uses are spatially compatible;
- where national land-use targets can realistically be accommodated; and
- where high transition exposure coincides with limited alternative opportunity.

## Editable scenario controls

National 2050 endpoints and alternative-land targets are read from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

The control table is deliberately data-driven. `SCENARIO_NO`, `SCENARIO_ID`, `SCENARIO_NAME`, `ACTIVE` and endpoint values can be edited without hard-coding scenario names in the principal runner. Only active rows are selectable.

The control table does **not** contain a fixed baseline-land total. A run first selects the 2020 or 2025 ED baseline and obtains starting land from that actual baseline:

```text
BaselineGrassland = sum(ALL_GRASSLAND for selected baseline year)
RunGrossRelease   = BaselineGrassland - TARGET_LIVESTOCK_LAND_HA
```

The national 2050 endpoint therefore stays fixed while the selected 2020 or 2025 spatial starting state changes appropriately.

## SC1: cattle transition, exposure and released land

SC1 is the complete pre-opportunity transition stage.

```text
selected 2020/2025 ED baseline
        +
selected national scenario endpoint
        ↓
adult-cattle spatial allocation
        ↓
exact national dairy:suckler composition
        ↓
Stage 09 ED cohort relationships
LOCAL_ED / COUNTY_RECEIVER / NATIONAL_ORPHAN
        ↓
complete 21-cohort cattle endpoint
        ↓
sheep unchanged
        ↓
fixed-2020 Standard Output exposure
        ↓
Gini + spatial concentration + county/ED incidence metrics
        ↓
GOBLIN pasture-DM pressure change
        ↓
ED released grassland with exact national closure
        ↓
FREEZE SC1
```

Standard Output is calculated only after the physical cattle state is solved. It reports production-value exposure and is not interpreted as farm income, profit or welfare.

SC1 distributional diagnostics are reporting outputs only. They include Gini coefficients for baseline and scenario livestock Standard Output, positive SO-loss exposure, cattle reduction and released grassland, together with top-10%/top-20% ED concentration and the number of EDs accounting for 50% and 80% of national incidence. These diagnostics never feed back into cattle allocation.

## From livestock adjustment to land-use opportunity

A central principle of GOBLIN-Spatial is that three different quantities must remain separate:

```text
PotentialRelease ≠ Opportunity ≠ RealisedConversion
```

**PotentialRelease** is land released from livestock pressure under a pathway.

**Opportunity** describes what that land could plausibly support given agricultural capability, physical soil characteristics, parcel structure and other spatial constraints.

**RealisedConversion** is the area actually allocated to an alternative land use after eligibility, capacity and national pathway constraints are applied.

This distinction prevents a national land-use target from being treated automatically as a spatially feasible outcome.

Once SC1 is frozen, soil and LPIS may interpret or constrain the use of released land but must not change the solved cattle transition or move released hectares between EDs.

## SC2: soil + LPIS opportunity

SC2 combines the frozen SC1 released-land geography with three independent evidence layers:

```text
08B agricultural capability
+ 08C physical soil context
+ selected-year LPIS
```

08B remains the principal agricultural capability layer, with `C1+C2 -> G1`, `C3+C4 -> G2`, and `C5+C6 -> G3`. `fsizuaa` is only a weighting denominator and never replaces `ALL_GRASSLAND`.

08C remains independent physical-soil context. In particular, `G3 != peat`, mapped peat is not automatically farmed peat, and mapped peat is not automatically rewettable grassland.

LPIS is matched to the selected scenario baseline year. It provides a parcel-informed capacity/opportunity envelope but does not identify the exact parcel from which cattle were removed.

SC2 produces overlapping opportunity envelopes for:

- AD grass;
- biorefinery grass;
- willow;
- additional tillage;
- forest; and
- rewetting.

These envelopes are not additive and are not final conversion hectares.

## SC3: constrained national-target allocation

SC3 reads the explicit national land-use targets from the same editable scenario row and allocates only within SC2 eligible capacity.

Stage-A released-land uses are AD grass, biorefinery grass, willow, additional tillage and forest. Rewetting is retained as a separate organic-soil control and is tested against remaining eligible organic agricultural land so physical conversion is not double counted.

For every land use:

```text
RealisedConversion <= NationalTarget
UnmetTarget = NationalTarget - RealisedConversion
```

The model does not force hectares into locations that cannot support them. Final reporting distinguishes the pre-rewetting Stage-A available balance from the final post-rewetting residual and preserves:

```text
GrossRelease ≠ ResidualAvailableLand
```

## Alternative land-use transitions

GOBLIN-Spatial can test several alternative or additional uses of released agricultural land:

| Land use | Role in the transition analysis |
|---|---|
| **AD grass** | Grassland supplying anaerobic-digestion feedstock |
| **Biorefinery** | Grass/feedstock production associated with bioeconomy pathways |
| **Willow** | Short-rotation woody biomass on suitable land |
| **Additional tillage** | Expansion of crop production where agricultural capability permits |
| **Forest** | Additional afforestation subject to spatial eligibility and pathway targets |
| **Rewetting** | Restoration of eligible drained organic grassland |

## Spatial transition foresight

The model is intended as a **spatial stress-test of plausible agricultural transition pathways**, rather than a prediction of exactly what individual places will do.

A useful interpretation combines transition exposure with alternative land-use opportunity:

| Transition exposure | Alternative opportunity | Interpretation |
|---|---|---|
| High | Stronger | **Prepared transition potential** |
| High | Limited | **Priority transition constraint** |
| Lower / contingent | Stronger | **Strategic opportunity** |
| Lower / contingent | Limited | **Lower immediate priority / monitor** |

This provides a way to identify not only where adjustment may be concentrated, but also where transition may be easier, where it may be constrained, and where additional policy support or alternative development options may be most important.

Standard Output contributes to the **exposure** dimension by representing production-value exposure. It is not interpreted as farm income, profitability or household welfare.

## Model progression

```text
BASELINE
Cattle + Sheep
      ↓
31 livestock cohorts
      ↓
Land + crops + farm structure
      ↓
Standard Output
      ↓
ED cohort signatures

SC1
      ↓
Select 2020 or 2025 ED baseline
      ↓
Editable national cattle endpoint
      ↓
Adult-cattle allocation + 21-cohort propagation
      ↓
Standard Output loss/exposure
      ↓
Gini + concentration + county/ED incidence
      ↓
Pasture-DM pressure + frozen ED released land

08B + 08C + LPIS
      ↓
SC2 overlapping land-use opportunity

SC3
      ↓
Editable national land-use targets
      ↓
Spatial eligibility + mutually exclusive capacity
      ↓
Realised conversion
+ unmet target
+ residual available land
```

The detailed current contract is documented in `docs/sc1_sc2_sc3_pipeline.md`.

## Development status

GOBLIN-Spatial is being consolidated into a clean **v1 Python package**.

The **historical baseline through Stage 09 is regression-verified and merged into `main`**. A permanent `baseline-v1-verified` checkpoint records that frozen baseline state. The downstream scenario architecture is being refactored on `scenario-v1-refactor`.

The editable scenario-control loader and expanded SC1 reporting layer are now separated from the historical baseline. The generic runner deliberately gates SC2/SC3 until the 08B, 08C, selected-year LPIS and absolute-target eligibility/allocation rules are frozen together. This prevents older provisional opportunity weights from silently becoming the v1 science.

The development principle is simple:

> **Software structure may improve, but validated scientific mathematics must not change silently.**

Frozen model inputs are archived on Zenodo:

**Version DOI:** `10.5281/zenodo.22035538`
