# SC3 alternative feasible geographies for the same national end use

## Purpose

A completed SC3 run provides one feasible spatial allocation of the national land-use outcome. That map should not automatically be interpreted as the only geography capable of delivering the same outcome.

The optional **post-SC3 spatial flexibility analysis** asks:

> Holding the national realised hectares of every future land use fixed, what other spatial allocations remain feasible within the same released-land, eligibility and rewetting-capacity constraints?

This is a downstream analytical layer. It is **not SC4**, does not alter SC1, SC2 or SC3, and does not generate a new GOBLIN pathway.

## Why the national realised vector is fixed by use

The analysis fixes the national realised hectares separately for:

- AD grass;
- biorefinery grass;
- willow;
- additional tillage;
- forest;
- rewetting.

This is stricter than merely fixing total allocated land or total unmet target. If only the total were held fixed, an alternative solution could replace forest shortfall with willow shortfall and would no longer represent the **same national end-use outcome**.

For every use `u`:

```text
sum(alternative allocation for u)
    = reference SC3 national realised hectares for u
```

Every ED × physical soil-resource cell also retains the existing finite shared-land constraint and the same use-specific eligibility rule.

## Two complementary outputs

### 1. Sampled feasible-geography ensemble

The model can solve a deterministic ensemble of alternative linear objectives while holding the complete national realised vector fixed. The reference SC3 map is always retained as one ensemble member.

Outputs include, for each ED and future use:

- reference allocated hectares;
- sampled minimum and maximum hectares;
- sampled mean and standard deviation;
- sampled allocation range;
- frequency with which the use receives positive allocation;
- whether allocation is positive in every sampled feasible solution.

These are **sampled flexibility diagnostics**, not the mathematical bounds of the entire feasible set. The output metadata states this explicitly.

A wide sampled range indicates that the same national end use can be delivered through substantially different local geographies. A narrow range suggests a more spatially constrained outcome.

### 2. Exact ED-use bounds for selected questions

For a shortlist of scientifically important ED-use pairs, the model can solve two additional linear programmes:

```text
minimum feasible hectares in ED i for use u
maximum feasible hectares in ED i for use u
```

while keeping the full national realised vector fixed.

These exact bounds are intended for selected hotspots, robust-exposure areas or important land uses. Computing them for every ED × use pair would require many thousands of additional optimisation solves and is not necessary for the main workflow.

## Interpretation

The analysis distinguishes **spatial necessity** from **spatial flexibility**.

```text
same national end-use vector
        +
same released-land resource
        +
same eligibility constraints
        ↓
multiple feasible geographies?
        │
        ├─ yes -> spatially flexible / contingent allocation
        └─ no or narrow range -> spatially constrained / more necessary geography
```

It does not estimate adoption probability and should not be interpreted as a forecast of which ED will actually convert land.

This strengthens the foresight interpretation of GOBLIN-Spatial because a single solver map is no longer treated as *the* future. The model can instead identify which spatial conclusions persist even when the same national future can be implemented through alternative feasible geographies.

## Relationship to the core architecture

```text
SC1
transition incidence + frozen release
        ↓
SC2
physical resource + eligibility/opportunity
        ↓
SC3
one joint feasible allocation
        ↓
POST-SC3 SPATIAL FLEXIBILITY
same end use, alternative feasible geographies
        ↓
robust versus contingent spatial requirements
```

This capability should be used only after the eligibility rules and rewetting-capacity controls used by the reference SC3 run are scientifically validated.
