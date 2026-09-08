# SC3 principal controls v1

This document records the scientific controls used to move the frozen SC3 optimiser into principal study runs. It does not change SC3 mathematics.

## Stage-A productive-use eligibility

Principal control:

`data/controls/sc3/SC3_StageA_Eligibility_Principal_v1.csv`

The matrix is binary. `1` means physically admissible at the broad mapped soil/drainage screening scale; `0` means excluded from the principal screen. No coefficient was selected to improve national target closure.

| Use | Deep well drained | Shallow well drained | Poorly drained | Poorly drained peaty | Alluvium | Peat | Misc. |
|---|---:|---:|---:|---:|---:|---:|---:|
| AD grass | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| Biorefinery grass | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| Willow | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| Additional tillage | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| Forest | 1 | 1 | 1 | 0 | 0 | 0 | 0 |

### Evidence logic

**Grass uses.** SC1's authoritative released resource is livestock grassland. AD grass and biorefinery grass therefore retain grass cover rather than requiring conversion to a new crop/forest system. Soil/drainage class is treated as affecting productivity/opportunity rather than binary physical continuation of grass. The uninterpretable `MISCELLANEOUS` class is excluded in the principal screen.

**Willow.** Teagasc short-rotation-coppice guidance states that most agricultural soils can support willow, while highly organic/peaty soils and boggy or frequently waterlogged sites should be avoided. Moisture-retentive soils are favourable and occasional inundation can be tolerated. Sources:

- Teagasc, *Short Rotation Coppice Best Practice Guidelines*: https://teagasc.ie/media/website/publications/2011/Short_Rotation_Coppice_Best_Practice_Guidelines.pdf
- Teagasc, *Willow Energy*: https://teagasc.ie/rural-economy/rural-development/diversification/willow-energy/

**Additional tillage.** Irish soil-use guidance identifies freely/well-drained mineral soils as the principal highly suitable tillage resource and describes increasing drainage, machinery and cultivation limitations as soils become wetter or more constrained. The principal screen therefore retains only deep and shallow well-drained classes. Sources:

- Teagasc, *Potential Land Use of Irish Soils*: https://teagasc.ie/wp-content/uploads/2025/05/General-1.pdf
- Teagasc county soil suitability reports: https://teagasc.ie/environment/soil/irish-soil-types-and-maps/soil-maps/

**Forest.** The principal physical screen separates broad soil admissibility from productivity, licensing and environmental constraints. Current Irish forestry guidance accepts free-draining agricultural soils and surface-water gleys without peat for productive forestry options, while peat-bearing sites are excluded from this principal productive screen. Source:

- Department of Agriculture, Food and the Marine, *Forestry for Fibre*: https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/services/forestry-for-fibre/

Alluvium and miscellaneous classes are excluded conservatively for additional tillage and forest because the broad categories do not resolve flood risk or the site-specific conditions required for a defensible principal productive allocation.

## Rewetting treatment

Rewetting remains separate from productive Stage-A eligibility. A validated national ED-level drainage-status map for agricultural peat is not currently available. Teagasc evidence indicates that only about 90,000-120,000 ha of the approximately 335,000 ha mapped grassland peat may be effectively drained, and the EPA D-TECT project is explicitly developing improved national drainage-status mapping.

Sources:

- Tuohy et al. (2023), *Drainage status of grassland peat soils in Ireland: Extent, efficacy and implications for GHG emissions and rewetting efforts*, Journal of Environmental Management 344, 118391. https://doi.org/10.1016/j.jenvman.2023.118391
- Teagasc summary: https://teagasc.ie/news--events/daily/important-new-study-shows-the-area-of-drained-grassland-peat-soils-is-grossly-overestimated/
- EPA D-TECT project: https://www.epa.ie/our-services/research/epa-funded-research/epa-funded-projects/research-data-table-dev/geospatial-drainage-status-detection-mapping-of-organic-rich-soils-for-nir-and-policy-support-needs.php

For current study execution, `scripts/build_rewetting_proxy_control.py` provides a transparent central proxy based on 105,000 / 335,000 of frozen SC2 released `PEAT` hectares. This is **not interpreted as an observed ED-level rewetting map**. Rewetting outputs are reported separately from productive response potential and productive transformability. Low (90,000 / 335,000) and high (120,000 / 335,000) sensitivity controls can be generated without changing SC3.

## Interpretation boundary

The principal productive SC3 result remains:

`Target = Realised + Unmet`

under the same finite released-land resource and the same Stage-A eligibility matrix for every pathway and allocation rule. Rewetting is an environmental/restoration layer and does not contribute to productive opportunity/adaptability scores.
