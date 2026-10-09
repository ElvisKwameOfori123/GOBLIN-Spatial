# Human-edible protein metrics

This reference module adds transparent protein-security accounting helpers to
GOBLIN-Spatial without changing the validated historical baseline.

## Why it is useful

Henn et al. (2026) use **net human-edible protein production** as a key
sustainability and resilience indicator. In their national scenario analysis,
positive values indicate that more human-edible protein is utilised as food
and exports than is imported. Their circularity analysis shows that changing
feed allocation can alter this balance.

The module therefore exposes:

- `net_human_edible_protein_production()`
- `net_export_human_edible_protein()`
- `edible_protein_conversion_ratio()`
- `land_use_ratio()`

The last two follow Hennessy et al. (2021), who assess feed-food competition
for Irish livestock systems using human-digestible protein.

## Important boundary

GOBLIN-Spatial does not yet contain all inputs required to calculate a
defensible ED-level net human-edible protein balance. In particular, spatial
human-edible fractions of feed imports, crop opportunity protein, digestibility
and product protein quality are not part of the frozen historical baseline.

Accordingly, these helpers are **reference calculations only**. They accept
already harmonised protein flows from a future data layer or scenario module.

No national or ED protein result is generated automatically.

## Suggested future spatial use

A defensible spatial implementation could combine:

1. ED livestock product output from GOBLIN-Spatial;
2. explicit protein coefficients for milk, meat and crops;
3. human-edible fractions and digestibility;
4. ED or regional feed demand and imported-feed allocation;
5. crop opportunity on land that is physically suitable for cropping.

This would allow separate reporting of:

- gross human-edible protein output;
- human-edible protein consumed in livestock feed;
- EPCR;
- land-use ratio;
- net human-edible protein production;
- contribution to net protein exports.

## Sources

- Henn, D. et al. (2026). *Circularity measures enhance resilience of net zero
  pathways for agriculture*. Communications Earth & Environment, 7, 772.
- Hennessy, D. P. et al. (2021). *The net contribution of livestock to the
  supply of human edible protein: the case of Ireland*. The Journal of
  Agricultural Science, 159, 463-471.
