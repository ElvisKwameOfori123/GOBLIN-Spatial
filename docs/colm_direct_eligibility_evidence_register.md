# Colm-direct Stage-A eligibility evidence register

## Purpose

This register is the scientific promotion gate between SC2 physical-resource
characterisation and SC3 target allocation. It deliberately contains **no
production suitability coefficients yet**.

The Colm-direct architecture permits a Stage-A eligibility coefficient only when
its physical interpretation and evidence are documented. A missing evidence base
must remain unresolved rather than being replaced by an intuitive or convenient
number.

Stage-A uses are:

1. AD grass;
2. biorefinery grass;
3. willow;
4. additional tillage;
5. forest.

Rewetting is excluded from this matrix because mapped soil alone cannot establish
drained agricultural organic-soil or rewettable capacity.

## Evidence hierarchy

For each use x Colm-soil combination, prefer evidence in this order:

1. authoritative Irish land-use, forestry, soil or agricultural guidance that
   directly addresses the physical limitation;
2. published Irish experimental or modelling evidence with a clear mapping to
   the Colm physical category;
3. GOBLIN/GeoGOBLIN source assumptions where their physical interpretation is
   explicit and transferable to GOBLIN-Spatial;
4. broader peer-reviewed evidence only where Irish evidence is unavailable and
   the transfer is scientifically justified.

Expert judgement alone may define a sensitivity case, but it must not silently
become the principal production rule.

## Coefficient discipline

The software accepts coefficients in [0, 1], but the production rule should
normally use:

```text
1 = physically eligible under the stated screen
0 = physically excluded under the stated screen
```

Use an intermediate value only when it has a defensible interpretation such as a
measured eligible fraction of a broad physical category. Do not use 0.5 merely
to express uncertainty or to improve national target closure.

Uncertainty should normally be handled through alternative documented rule
sets/sensitivity cases.

## Physical-soil evidence matrix

`UNRESOLVED` means that no production coefficient has yet been approved.

| Future use | Deep well drained | Shallow well drained | Poorly drained | Poorly drained peaty | Alluvium | Peat | Miscellaneous |
|---|---|---|---|---|---|---|---|
| AD grass | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Biorefinery grass | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Willow | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Additional tillage | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Forest | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |

For every resolved cell, the evidence record should contain:

- `USE`
- `CATEGORY`
- `ELIGIBILITY_COEFFICIENT`
- `RULE_VERSION`
- `EVIDENCE_NOTE`
- source citation / document identifier
- physical rationale
- whether the rule is principal or sensitivity-only

The runtime CSV intentionally keeps the compact five required fields. The full
scientific evidence record can remain in this register or a companion audit
file.

## Use-specific questions that must be answered

### AD grass and biorefinery grass

The rule should answer a physical question, not a market question:

> Can the released resource remain or be managed as productive grass supplying
> the relevant biomass system under the pathway assumptions?

Do not assume that existing LPIS grass automatically implies future feedstock
adoption. LPIS can describe existing grass context and later opportunity, while
physical eligibility needs a documented agronomic basis.

### Willow

The rule needs a defensible treatment of drainage/soil limitations and any other
physical exclusions required by the chosen production system. If slope,
protected habitat or other constraints are required but are not represented in
the Colm category, they should enter as separate evidence rather than being
hidden in a soil coefficient.

### Additional tillage

This is likely to require the strongest agricultural-soil screen. The rule must
be explicit about what the Colm drainage/physical categories can and cannot
establish. Existing LPIS tillage or grass context may support opportunity or a
separate management screen, but should not be used to invent parcel-level soil
provenance where the joint overlay is unavailable.

### Forest

Physical soil eligibility and productive forestry opportunity are different.
Colm soil can provide a physical screen. Forest Yield Class, statutory
exclusions, water/environment constraints or other forestry evidence should be
represented separately when required rather than collapsed into one soil rule.

## LPIS role

LPIS is retained as observed agricultural-use/management context. The current
compact runtime does not contain a measured parcel-level Colm-soil x LPIS joint
overlay. Therefore:

- LPIS does not change frozen SC1 release;
- LPIS does not change the seven-category Colm physical partition;
- LPIS can support transparent ED context and future use-specific opportunity;
- LPIS should enter hard eligibility only where the scientific rule can be
  implemented without pretending that soil and LPIS attributes are observed on
  the same released hectare.

A future validated joint Colm-soil x LPIS grassland overlay would allow this
boundary to be tightened.

## Rewetting is a separate control

The following implication is prohibited:

```text
Colm PEAT or POORLY_DRAINED_PEATY -> rewetting capacity
```

Instead SC3 requires an external validated ED-level capacity representing the
relevant drained agricultural organic-soil resource. LPIS peat/bog context and
Colm soil may support validation, but neither alone is treated as sufficient.

## Promotion test

A production Stage-A rule set may be added only when:

1. all 35 use x category cells have an explicit value;
2. every non-zero value has a documented physical rationale;
3. every intermediate coefficient has a defensible quantitative interpretation;
4. the complete matrix has one version identifier;
5. principal and sensitivity rule sets are clearly distinguished;
6. national eligible-capacity diagnostics are inspected before SC3 results are
   interpreted;
7. no coefficient has been selected simply to make a GOBLIN target close.

Until this register is resolved, SC3 should remain scientifically gated even
though the generic finite-resource optimiser is implemented and unit-tested.
