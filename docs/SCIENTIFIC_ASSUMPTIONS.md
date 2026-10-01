# GOBLIN-Spatial Scientific Assumptions Register

This register records the principal assumptions and interpretation boundaries for the active GOBLIN-Spatial historical baseline and illustrative perturbation.

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
Illustrative perturbation
      !=
Observed behaviour or impact
```

## Current assumptions and modelling choices

| ID | Component | Status | Current treatment | Scientific meaning |
|---|---|---|---|---|
| **A01** | 2010 and 2020 cattle geography | **Core reconstruction assumption** | For 2015-2019, within-county ED shares of dairy cows, other cows and other cattle move linearly from the 2010 to the published 2020 census distribution. | The two censuses inform small-area geography; the exact annual ED path is reconstructed rather than observed. |
| **A02** | Published 2020 cattle | **Protected observation** | Published 2020 ED cattle values are retained unchanged. | Higher-level source differences are recorded rather than spatially reassigned. |
| **A03** | Post-2020 cattle geography | **Reconstruction assumption** | From 2021-2025, published 2020 component support and within-county shares are held while annual AAA10 county controls change. | No unobserved post-2020 within-county redistribution is invented. |
| **A04** | Cattle age-sex prior | **Evidence-informed reconstruction** | AAA10 county age-sex margins remain authoritative. DAFM/AIM ED evidence shifts only the under-one versus one-to-two-year odds; bulls, 2+ cattle and sex structure remain county-controlled. | DAFM/AIM adds fine-scale composition without replacing statistical population controls. |
| **A05** | Cattle parental-origin prior | **Evidence-informed reconstruction** | Fixed age-sex groups are subdivided into DxD, DxB and BxB using exact national GOBLIN/COHORTS margins and local AIM composition signals with county fallback. | Biological detail is added without moving cattle between EDs or changing fixed age-sex totals. |
| **A06** | Adult-cow absence | **Interpretation boundary** | Absence of adult dairy or suckler cows is not a structural gate on follower cohorts. | Adult-parent and follower geographies can differ; this is not direct evidence of movement or trade. |
| **A07** | Sheep 2020 state | **Protected observation** | Published 2020 ED sheep totals, including zeros, are retained unchanged. | Source differences with higher-level controls are not spatially filled. |
| **A08** | Sheep annual geography | **Reconstruction assumption** | Pre-2020 ED shares move from the 2010 to the published 2020 pattern. DAFM breeding-ewe information modifies relative county weighting inside fixed AAA09 regions. Post-2020 support follows the published 2020 pattern. | DAFM informs pattern; AAA09 remains the controlling regional quantity. |
| **A09** | Sheep breed/system composition | **Evidence-informed reconstruction** | County breed anchors inform lowland-type and mountain-type composition. | The mountain-type indicator is a breed/system proxy, not an independently observed ED hill-farm classification. |
| **A10** | Land reconstruction | **Core reconstruction assumption** | Published 2020 ED land is retained and surrounding years follow AQA06 regional change while ED land accounting closes. | Annual small-area land is reconstructed under explicit higher-level controls. |
| **A11** | Farm structure | **Core reconstruction assumption** | Holdings and holder-age variables follow their documented official higher-level trajectories around the ED anchor. | Non-census ED values are reconstructed, not annual local observations. |
| **A12** | Standard Output | **Derived indicator** | Fixed 2020 coefficients are applied to reconstructed activities for every year. | Standard Output is production-value exposure, not income, profit, welfare, compensation need or land value. |
| **A13** | WFD catchment reporting | **Reporting transformation** | ED quantities are distributed using a frozen ED-to-WFD-catchment area crosswalk. | The catchment view does not locate individual farms or animals within ED fragments and is not a water-quality impact model. |
| **A14** | Ratio aggregation | **Accounting rule** | Numerators and denominators are aggregated separately and ratios are recalculated at the target geography. | ED percentages are never averaged to produce higher-scale signatures. |
| **A15** | Parent-follower support | **Derived classification** | Relationships are labelled local ED, county-supported or national fallback according to where the corresponding adult-parent population exists. | These are support classes, not animal-movement, purchase, sale or origin classes. |
| **A16** | Livestock signatures | **Derived indicators** | Signatures quantify breeding orientation, follower composition, follower intensity, livestock density, production-value intensity and sheep production type. | They describe livestock-system organisation in addition to abundance. |
| **A17** | Descriptive matched/stable analyses | **Descriptive diagnostics** | Concentration, matched-ED and stable-abundance analyses compare reconstructed structures under explicit thresholds. | They reveal information content but do not estimate causal effects. |
| **A18** | Information geography | **Diagnostic** | Between-county variation is used to distinguish fine ED differentiation from attributes largely inherited from coarser evidence. | ED reporting resolution is not assumed to equal empirical evidence resolution for every variable. |
| **A19** | DAFM/AIM evaluation | **Interpretation boundary** | Sources used in reconstruction are evaluated as pattern fidelity or coherence, not independent validation. | Model-input agreement is not overstated as predictive validation. |
| **A20** | 2020 livestock-unit screen | **Model-selection diagnostic** | Published 2020 ED LSU is used as a prespecified plausibility screen for age-prior selection. | It is not held-out validation. |
| **A21** | 2022 sheep comparison | **Holdout evaluation** | The 2022 sheep breed-composition observation is withheld from the interpolation used for the evaluation comparison. | This is the strongest holdout comparison in the current historical evaluation set. |
| **A22** | Coherence audit | **Verification** | A separate audit recomputes accounting, closure and aggregation identities from released outputs and raw inputs. | Passing the audit verifies internal consistency; it is not external validation. |
| **A23** | Illustrative dairy/suckler perturbation | **Controlled experiment** | Adult dairy or suckler cows are reduced by 30% in the frozen 2020 and 2025 baselines. | This is an illustrative static endpoint perturbation, not a forecast or behavioural response. |
| **A24** | Signature-preserving representation | **Perturbation rule** | Linked follower change remains in reconstructed follower geography and follows the finest valid frozen parent relationship. | The representation preserves biological spatial structure. |
| **A25** | Headcount benchmark | **Attribution benchmark** | National follower-per-parent coefficients are applied to adult-parent change geography. | It is an unconstrained attribution benchmark, not a feasible alternative ED herd state. |
| **A26** | Perturbation interpretation | **Boundary** | Both representations impose the same national adult-parent and linked-follower changes; only spatial attribution differs. | Displacement measures information lost when follower geography is inferred from adult headcount. |
| **A27** | Behaviour and impacts | **Boundary** | The historical model does not predict individual farmer behaviour, farm-to-farm movement, exact parcel conversion, market equilibrium, water-quality impact or future scenario outcomes. | Additional models and evidence are required for those questions. |

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
