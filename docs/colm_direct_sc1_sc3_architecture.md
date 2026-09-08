# GOBLIN-Spatial Colm-direct SC1-SC3 architecture

## Status

This document defines the scientific architecture being promoted from the
parallel Colm prototype. It deliberately separates national pathway authority,
transition incidence, physical land-resource evidence, eligibility/opportunity
and realised land-use allocation.

The historical 2015-2025 ED baseline is unchanged. The legacy 08B/G1-G2-G3
architecture remains a benchmark/sensitivity implementation but is not part of
the Colm-direct production decision chain.

## Parent pathway authority

National GOBLIN remains authoritative for the pathway quantities supplied to
GOBLIN-Spatial:

- dairy and suckler endpoint;
- any explicit total-cattle or 21-cohort endpoint;
- target livestock-land area / authoritative gross livestock-land release;
- explicit national future land-use targets for AD grass, biorefinery grass,
  willow, additional tillage, forest and rewetting.

GOBLIN-Spatial resolves their geography. It does not infer national future-use
targets from local suitability and it does not reinterpret the GOBLIN `Available`
residual as gross livestock-land release.

## SC1: transition incidence and released-land geography

SC1 asks:

> Where does the nationally specified livestock transition fall, and where is
> the authoritative livestock-land release represented spatially?

Sequence:

```text
validated ED baseline
    -> adult dairy/suckler endpoint allocation
    -> 21 cattle cohorts + fixed sheep
    -> fixed-2020 Standard Output exposure
    -> pasture-DM transition signal
    -> authoritative national GOBLIN release spatialised to EDs
```

### SC1 land boundary

SC1 is soil-independent.

Colm mapped physical soil, LPIS and the legacy 08B/G1-G2-G3 capability system:

- do not change national livestock numbers;
- do not change ED livestock allocation;
- do not set the national released-land quantity;
- do not constrain the ED released-land vector.

The ED physical ceiling is `ALL_GRASSLAND`.

The required accounting identity is:

```text
sum(GOBLIN_RELEASED_GRASSLAND_HA) = authoritative national GOBLIN release
```

`POTENTIAL_SPARED_GRASSLAND_HA`, `SIGNED_GRASSLAND_BALANCE_HA` and
`ADDITIONAL_GRASSLAND_REQUIRED_HA` remain independent pasture-DM diagnostics.
They are never rescaled to the parent GOBLIN land control.

SC1 also retains the validated incidence measures and allocation policies,
including PRORATA, dairy protection, economic-capacity protection and social
vulnerability protection. Those policies are based on livestock, holding,
Standard Output and demographic structure, not soil suitability.

Once SC1 finishes, livestock and ED released hectares are frozen.

## SC2: Colm physical resource, LPIS context and eligibility

SC2 asks:

> What physical agricultural resource has become transition space, and what
> future uses could that resource physically support?

SC2 consumes the frozen SC1 release and only then attaches:

- Colm mapped physical-soil evidence;
- LPIS 2020 agricultural-use and management context.

The seven Colm physical categories are retained directly:

1. deep well drained;
2. shallow well drained;
3. poorly drained;
4. poorly drained peaty;
5. alluvium;
6. peat;
7. miscellaneous.

The current ED-level resource attribution is:

```text
COLM_RELEASED_<SOIL>_HA
    = frozen SC1 released hectares
      x Colm ED physical-soil share
```

This is explicitly a proportional within-ED characterisation of the physical
resource. It is not a claim that exact released parcels or their parcel-level
soil provenance have been observed.

LPIS remains a separate agricultural-context evidence layer. The current compact
controls do not contain a measured parcel-level Colm-soil x LPIS joint overlay,
so the model does not manufacture an independence-based cross-product. A future
joint overlay may replace the proportional ED attribution if a validated source
is built.

### Eligibility rules

There are no hard-coded scientific defaults. A production eligibility control
must explicitly cover all five Stage-A uses and all seven Colm physical-soil
categories, provide a version and provide an evidence note.

The model distinguishes:

```text
Potential release
    != physical resource
    != eligibility
    != opportunity
    != realised conversion
```

Mapped peat alone cannot generate rewetting capacity.

### Opportunity

LPIS and other context may support use-specific opportunity ranking, but no
arbitrary weighted composite is applied in the Colm-direct core. Until an
opportunity rule is evidence-backed, SC2 reports the component evidence and SC3
operates as a feasibility test rather than claiming a unique preferred spatial
allocation.

## SC3: spatial compatibility of the same national future

SC3 asks:

> Can the explicit national land-use requirements of the same GOBLIN pathway
> jointly fit within the finite released resource produced by SC1 and
> characterised in SC2?

The five Stage-A uses are:

- AD grass;
- biorefinery grass;
- willow;
- additional tillage;
- forest.

They compete simultaneously for the same ED x Colm-soil resource cells.
For every ED and Colm category:

```text
sum(all competing Stage-A allocations) <= released physical resource cell
```

Use-specific allocation is also bounded by the explicit eligibility rule.
National accounting is:

```text
realised use + unmet use = explicit GOBLIN target
```

No infeasible hectares are forced merely to close a target.

The optimisation is lexicographic:

1. minimise total unmet Stage-A target;
2. only if an explicit opportunity-score mapping is supplied, hold minimum
   shortfall fixed and maximise evidence-backed opportunity fit.

Without an evidence-backed opportunity mapping, the resulting allocation is a
feasibility solution and should not be interpreted as a unique predicted land-use
map.

## Rewetting

Rewetting remains a separately validated resource problem because:

```text
mapped peat != drained agricultural organic soil != rewettable capacity
```

A positive pathway rewetting target therefore requires an external, versioned
ED-level rewetting-capacity control with evidence notes. Rewetting is allocated
only from the residual released resource after Stage A and cannot exceed the
validated capacity intersected with that residual resource.

## Scientific invariants

### SC1

```text
sum(ED livestock endpoint) = GOBLIN national endpoint
sum(ED released hectares) = GOBLIN authoritative gross release
0 <= ED released hectares <= ALL_GRASSLAND
soil and LPIS cannot change SC1 output
```

### SC2

```text
sum(seven Colm released-resource cells within ED)
    = frozen SC1 released hectares
SC2 cannot alter livestock or release
G1/G2/G3 are not used
```

### SC3

```text
allocation in each ED x soil cell <= that finite released resource cell
realised + unmet = national target for every use
allocated + residual = frozen released land
no G1/G2/G3 capacity pool is used
```

## Relationship to the wider model ecosystem

```text
GOBLIN / OptiGob
    -> national pathway quantities

GOBLIN-Spatial
    -> SC1 spatial transition incidence
    -> SC2 released-resource eligibility/opportunity
    -> SC3 spatial compatibility

Agrisyn
    -> optional downstream synthetic-farm incidence within fixed ED endpoints

GeoGOBLIN
    -> optional downstream catchment/environmental consequences of the fixed
       spatial configuration
```

Agrisyn and GeoGOBLIN must not overwrite the national or ED endpoint accounting
already fixed upstream.

## Promotion gates

The branch should not replace the current production/main results until all of
the following are complete:

1. full automated tests and CI pass;
2. SC1 soil-independence is verified by an invariance test;
3. the complete Stage-A Colm eligibility matrix has a documented scientific
   evidence base;
4. the drained-organic/agricultural rewetting capacity control is validated;
5. SC3 feasibility is rerun for each principal scenario/allocation rule;
6. new outputs are compared with the frozen legacy 08B benchmark;
7. manuscript figures/results are regenerated only from the promoted
   Colm-direct production run.
