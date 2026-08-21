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
Livestock adjustment / destocking
        ↓
Potential land release
        ↓
Soil + parcel + land-use opportunity
        ↓
Alternative land-use allocation
        ↓
Realised transition + unmet opportunity
```

## What the model does

The historical engine reconstructs cattle, sheep, agricultural land, crops and selected farm-structure characteristics at ED level. Livestock are represented through **21 cattle cohorts and 10 sheep cohorts**, while fixed 2020 Standard Output coefficients provide a measure of agricultural production-value exposure.

The completed baseline then provides the spatial starting point for transition analysis. National livestock pathways are translated into geographically heterogeneous changes while preserving the underlying livestock structure and ED-specific cohort relationships.

This allows GOBLIN-Spatial to examine:

- where livestock adjustment is concentrated;
- which areas face the greatest production-value exposure;
- how much agricultural land could be released from livestock pressure;
- the soil, parcel and agricultural characteristics of that released land;
- which alternative land uses are spatially compatible;
- where national land-use targets can realistically be accommodated; and
- where high transition exposure coincides with limited alternative opportunity.

## From livestock adjustment to land-use opportunity

A central principle of GOBLIN-Spatial is that three different quantities must remain separate:

```text
PotentialRelease ≠ Opportunity ≠ RealisedConversion
```

**PotentialRelease** is land released from livestock pressure under a pathway.

**Opportunity** describes what that land could plausibly support given agricultural capability, physical soil characteristics, parcel structure and other spatial constraints.

**RealisedConversion** is the area actually allocated to an alternative land use after eligibility, capacity and national pathway constraints are applied.

This distinction prevents a national land-use target from being treated automatically as a spatially feasible outcome.

## Alternative land-use transitions

GOBLIN-Spatial can test several alternative or additional uses of released agricultural land:

| Land use | Role in the transition analysis |
|---|---|
| **AD grass** | Grassland supplying anaerobic-digestion feedstock |
| **Biorefinery** | Biomass/feedstock production associated with bioeconomy pathways |
| **Willow** | Short-rotation woody biomass on suitable land |
| **Additional tillage** | Expansion of crop production where agricultural capability permits |
| **Forest** | Additional afforestation subject to spatial eligibility and pathway targets |
| **Rewetting** | Restoration of eligible drained organic grassland |

The model does not force hectares into locations that cannot support them. Where an explicit national target exceeds spatially feasible capacity, GOBLIN-Spatial reports the **realised area and the unmet target**.

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

TRANSITION
      ↓
National GOBLIN pathways
      ↓
Spatial livestock adjustment
      ↓
Potential land release

OPPORTUNITY
      ↓
Agricultural capability + physical soil
      ↓
LPIS parcels + spatial constraints
      ↓
Alternative land-use opportunity

ALLOCATION
      ↓
National land-use targets
      ↓
Spatial eligibility + capacity
      ↓
Realised conversion
+ unmet target
+ residual available land
```

## Development status

GOBLIN-Spatial is being consolidated into a clean **v1 Python package**.

The **historical baseline through Stage 09 has been refactored and regression-verified in draft PR #1**. The downstream scenario architecture is part of the scientific model described above, while the SC1-SC3 implementation will undergo its own refactor and regression verification before the complete v1 release is frozen.

The development principle is simple:

> **Software structure may improve, but validated scientific mathematics must not change silently.**

Frozen model inputs are archived on Zenodo:

**Version DOI:** `10.5281/zenodo.22035538`
