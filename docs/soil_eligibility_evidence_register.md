# Stage-A soil eligibility evidence register

## Purpose

This register is the scientific evidence gate between SC2 physical-resource characterisation and SC3 target allocation.

The runtime accepts a Stage-A eligibility coefficient only when its physical interpretation and evidence are documented. A missing evidence base must remain unresolved rather than being replaced by an intuitive or convenient number.

The five competing Stage-A uses are:

1. AD grass;
2. biorefinery grass;
3. willow;
4. additional tillage;
5. forest.

Rewetting is excluded from this matrix because mapped physical soil alone cannot establish drained agricultural organic-soil or rewettable capacity.

## Physical soil/drainage classes

The current frozen ED physical-resource control contains seven classes:

```text
DEEP_WELL_DRAINED
SHALLOW_WELL_DRAINED
POORLY_DRAINED
POORLY_DRAINED_PEATY
ALLUVIUM
PEAT
MISCELLANEOUS
```

Internal source-provenance fields may retain the `COLM_` identifier, but the scientific object is the mapped physical soil/drainage class.

## Evidence hierarchy

For each future-use × soil-class combination, prefer evidence in this order:

1. authoritative Irish land-use, forestry, soil or agricultural guidance that directly addresses the physical limitation;
2. published Irish experimental or modelling evidence with a clear mapping to the physical class;
3. GOBLIN/GeoGOBLIN source assumptions where their physical interpretation is explicit and transferable;
4. broader peer-reviewed evidence only where Irish evidence is unavailable and the transfer is scientifically justified.

Expert judgement may define a sensitivity case but should not silently become the principal production rule.

## Coefficient discipline

The software accepts coefficients in `[0,1]`, but the principal rule should normally use:

```text
1 = physically eligible under the stated screen
0 = physically excluded under the stated screen
```

Use an intermediate value only when it has a defensible quantitative interpretation, such as an observed eligible fraction of a broad physical category. Do not use `0.5` merely to express uncertainty or to improve national target closure.

Uncertainty should normally be handled through alternative documented rule sets.

## Evidence matrix

`UNRESOLVED` means that no production coefficient has yet been approved.

| Future use | Deep well drained | Shallow well drained | Poorly drained | Poorly drained peaty | Alluvium | Peat | Miscellaneous |
|---|---|---|---|---|---|---|---|
| AD grass | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Biorefinery grass | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Willow | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Additional tillage | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Forest | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |

For every resolved cell, the evidence record should contain:

- `USE`;
- `CATEGORY`;
- `ELIGIBILITY_COEFFICIENT`;
- `RULE_VERSION`;
- `EVIDENCE_NOTE`;
- source citation/document identifier;
- physical rationale;
- whether the rule is principal or sensitivity-only.

## Use-specific questions

### AD grass and biorefinery grass

The rule should answer a physical question: can the released resource remain or be managed as productive grass supplying the relevant biomass system under the pathway assumptions?

Existing LPIS grass does not by itself imply future feedstock adoption.

### Willow

The rule requires a defensible treatment of drainage and soil limitations. Where slope, habitat or other constraints are required, they should enter as separate evidence rather than being hidden inside a soil coefficient.

### Additional tillage

This use is expected to require a relatively strong physical soil/drainage screen. Existing LPIS tillage or grass context can support agricultural context, but should not be used to invent parcel-level soil provenance where a joint overlay is unavailable.

### Forest

Physical soil eligibility and productive forestry opportunity are different. Forestry productivity, statutory exclusions and environmental constraints should be represented separately where required rather than collapsed into one soil rule.

## LPIS role

LPIS remains observed agricultural-use/management context.

The current compact runtime does not contain a measured parcel-level soil × LPIS joint overlay. Therefore:

- LPIS does not change frozen SC1 release;
- LPIS does not change the seven-class physical-resource partition;
- LPIS can support transparent ED context and future use-specific opportunity;
- LPIS should enter hard eligibility only where the scientific rule can be implemented without pretending soil and LPIS attributes are observed on the same released hectare.

## Rewetting is a separate control

The following implication is prohibited:

```text
PEAT or POORLY_DRAINED_PEATY -> rewetting capacity
```

SC3 instead requires an external validated ED-level control representing the relevant drained agricultural organic-soil resource.

Rewetting is treated primarily as an environmental/restoration requirement and should not automatically increase productive diversification or alternative-income opportunity.

## Promotion test

A production Stage-A rule set may be added only when:

1. all 35 use × class cells have an explicit value;
2. every non-zero value has a documented physical rationale;
3. every intermediate coefficient has a defensible quantitative interpretation;
4. the complete matrix has one version identifier;
5. principal and sensitivity rule sets are clearly distinguished;
6. national eligible-capacity diagnostics are inspected before SC3 results are interpreted;
7. no coefficient has been selected simply to make a GOBLIN target close.

Until this register is resolved, the generic SC3 optimiser is implemented and testable, but a final evidence-backed publication SC3 run remains scientifically gated.
