# GOBLIN-Spatial Scientific Assumptions Register

This register records the principal assumptions and interpretation boundaries for the active GOBLIN-Spatial historical baseline and multiscale reporting products.

The controlling distinction is:

```text
Observed evidence
      !=
Statistical control
      !=
Reconstruction assumption
      !=
Derived indicator
      !=
Observed behaviour or impact
```

## Current assumptions and modelling choices

| ID | Component | Status | Current treatment | Scientific meaning |
|---|---|---|---|---|
| **A00a** | Census suppression | **Protected observation + reconstruction** | Before the model runs (Stage 00), blank AVA42 ED cells of 2010 and 2020 are filled. Published values and zeros are unchanged; exact Census of Agriculture county totals (and so State totals) of total cattle, dairy cows, other cows and sheep are reproduced in both years. | A blank cell is a withheld positive value, not a zero. Its county total is known exactly; only its ED placement within the county is reconstructed. |
| **A00b** | Suppressed-cell priors | **Evidence-informed reconstruction** | Fixed prior chains (earlier/later census, one-to-one matched DAFM/AIM evidence, county share), shrunk toward an equal split within each county by a weight selected per variable and year with the hidden-cell test. Every filled cell carries its prior source, measured hidden-cell error and a cow-cap flag. | Suppressed cells hold few holdings and lie in a narrow range, so ED-specific evidence informs rank more reliably than magnitude. |
| **A00c** | Model universe | **Accounting boundary** | Census animals in the 552 EDs outside the 2,857-ED model universe are reported by county and WFD catchment and not moved into model EDs. | Model-universe 2020 sums sit slightly below the State totals (cattle 0.12%, sheep 0.08%). |
| **A01** | 2010 and 2020 cattle geography | **Core reconstruction assumption** | For 2015-2019, within-county ED shares of dairy cows, other cows and other cattle move linearly from the 2010 to the published 2020 census distribution. | The two censuses inform small-area geography; the exact annual ED path is reconstructed rather than observed. |
| **A02** | 2020 cattle anchor | **Protected observation** | Prepared 2020 ED cattle values (published cells plus Stage 00 fills) are retained unchanged. | Remaining differences from AAA10 (outside-model animals; AAA10 is the census rounded to 100 head) are recorded rather than spatially reassigned. |
| **A03** | Post-2020 cattle geography | **Reconstruction assumption** | From 2021-2025, published 2020 component support and within-county shares are held while annual AAA10 county controls change. | No unobserved post-2020 within-county redistribution is invented. |
| **A04** | Cattle age-sex prior | **Evidence-informed reconstruction** | AAA10 county age-sex margins remain authoritative. DAFM/AIM ED evidence shifts only the under-one versus one-to-two-year odds; bulls, 2+ cattle and sex structure remain county-controlled. | DAFM/AIM adds fine-scale composition without replacing statistical population controls. |
| **A05** | Cattle parental-origin prior | **Evidence-informed reconstruction** | Fixed age-sex groups are subdivided into DxD, DxB and BxB using exact national GOBLIN/COHORTS margins and local AIM composition signals with county fallback. | Biological detail is added without moving cattle between EDs or changing fixed age-sex totals. |
| **A06** | Adult-cow absence | **Interpretation boundary** | Absence of adult dairy or suckler cows is not a structural gate on follower cohorts. | Adult-parent and follower geographies can differ; this is not direct evidence of movement or trade. |
| **A07** | Sheep 2020 state | **Protected observation** | Prepared 2020 ED sheep totals (published values and zeros plus Stage 00 fills of suppressed cells) are retained unchanged. | Remaining differences from AAA09 (outside-model sheep, rounding) are recorded, not spatially filled. |
| **A08** | Sheep annual geography | **Reconstruction assumption** | Pre-2020 ED shares move from the 2010 to the published 2020 pattern. DAFM breeding-ewe information modifies relative county weighting inside fixed AAA09 regions. Post-2020 support follows the published 2020 pattern. | DAFM informs pattern; AAA09 remains the controlling regional quantity. |
| **A09** | Sheep breed/system composition | **Evidence-informed reconstruction** | County breed anchors inform lowland-type and mountain-type composition. | The mountain-type indicator is a breed/system proxy, not an independently observed ED hill-farm classification. |
| **A10** | Land reconstruction | **Core reconstruction assumption** | Published 2020 ED land is retained and surrounding years follow AQA06 regional change while ED land accounting closes. | Annual small-area land is reconstructed under explicit higher-level controls. |
| **A11** | Farm structure | **Core reconstruction assumption** | Holdings and holder-age variables follow their documented official higher-level trajectories around the ED anchor. | Non-census ED values are reconstructed, not annual local observations. |
| **A12** | Standard Output | **Derived indicator** | Fixed 2020 coefficients are applied to reconstructed activities for every year. | Standard Output is production-value exposure, not income, profit, welfare, compensation need or land value. |
| **A13** | WFD catchment reporting | **Reporting transformation** | ED quantities are distributed using a frozen ED-to-WFD-catchment area crosswalk. Catchment signatures are recalculated from aggregated numerators and denominators. | The catchment view does not locate individual farms or animals within ED fragments and is not a water-quality impact model. |
| **A14** | Ratio aggregation | **Accounting rule** | Numerators and denominators are aggregated separately and ratios are recalculated at the target geography. | ED percentages are never averaged to produce higher-scale signatures. |
| **A15** | Parent-follower support | **Derived classification** | Relationships are labelled local ED, county-supported or national fallback according to where the corresponding adult-parent population exists. | These are support classes, not animal-movement, purchase, sale or origin classes. |
| **A16** | Livestock signatures | **Derived indicators** | Signatures quantify breeding orientation, follower composition, follower intensity, cattle and sheep density on farmed land, grassland and cereal shares, production-value intensity and sheep production type. | They describe livestock-system organisation and agricultural context in addition to abundance. |
| **A17** | Descriptive spatial analyses | **Descriptive diagnostics** | Concentration and matched-ED analyses use the reconstructed baseline, while local restructuring is assessed from comparable 2010 and 2020 census observations. | They reveal spatial structure and observed change but do not estimate causal effects. |
| **A18** | Between-county share of variation | **Diagnostic** | Between-county variance is reported for selected signatures as a descriptive measure of where spatial variation is organised. | It is not used as a measure of evidence provenance or as a validity threshold. |
| **A19** | DAFM/AIM evaluation | **Interpretation boundary** | Sources used in reconstruction are evaluated as pattern fidelity or coherence, not independent validation. | Model-input agreement is not overstated as predictive validation. |
| **A20** | 2020 livestock-unit screen | **Model-selection diagnostic** | Published 2020 ED LSU is used as a prespecified plausibility screen for age-prior selection. | It is not held-out validation. |
| **A21** | 2022 sheep comparison | **Holdout evaluation** | The 2022 sheep breed-composition observation is withheld from the interpolation used for the evaluation comparison. | This is the strongest holdout comparison in the current historical evaluation set. |
| **A22** | Coherence audit | **Verification** | A separate audit recomputes accounting, closure and aggregation identities from released outputs and raw inputs. | Passing the audit verifies internal consistency; it is not external validation. |
| **A23** | Within-catchment heterogeneity | **Derived reporting diagnostic** | Intersecting ED signatures are summarised with denominator-weighted P10, P50 and P90 values using the fractional ED-catchment crosswalk. | The distribution complements, but does not replace, the catchment accounting value. |
| **A24** | Behaviour and impacts | **Boundary** | The historical model does not predict individual farmer behaviour, farm-to-farm movement, exact parcel conversion, market equilibrium, water-quality impact or future scenario outcomes. | Additional models and evidence are required for those questions. |

## Required record for a scientific change

A scientifically meaningful change should state:

```text
What changed?
Why did it change?
What evidence supports the change?
Was the evidence an input, model-selection target or independent evaluation source?
Which outputs can change?
Which outputs must remain unchanged?
What reconciliation and audit checks were run?
```

Git history is the authoritative development record. Live documentation describes the current historical-baseline model rather than preserving superseded scenario architectures.
