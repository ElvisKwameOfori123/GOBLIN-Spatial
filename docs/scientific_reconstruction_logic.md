# Scientific reconstruction logic in GOBLIN-Spatial

## Purpose

GOBLIN-Spatial reconstructs a biologically structured small-area livestock system from complementary official evidence. The Electoral Division (ED) is the spatial accounting unit within which livestock populations are reconstructed. CSO livestock counts define the local population envelope, DAFM/AIM evidence provides small-area biological composition signals, county controls preserve official age-sex structure, and GOBLIN supplies nationally coherent biological relationships between adult populations and follower cohorts. These evidence layers are reconciled so that local accounting identities and higher-level biological margins hold simultaneously.

The scientific objective is to retain as much spatially specific agricultural information as the evidence supports while preserving the national and county totals required for coherent livestock accounting. The resulting ED representation therefore contains more information than a livestock headcount alone: it describes the composition and biological organisation of the herd within each place.

## 1. Evidence hierarchy

The reconstruction uses each source for the quantity it measures most directly.

| Evidence layer | Scientific role | Spatial role |
| --- | --- | --- |
| CSO Census of Agriculture ED cattle data | Total cattle, dairy cows, other cows and other cattle | Hard ED population envelope at the census anchor |
| CSO 2010 ED census | Earlier observed spatial distribution of cattle components | Pre-2020 spatial trajectory |
| CSO AAA10 annual cattle statistics | Annual dairy, other-cow, total-cattle and age-sex controls | Exact county control system |
| DAFM/AIM 2020 ED cattle age profile | Relative young-stock age composition | Local ED age signal |
| DAFM/AIM 2020 ED dairy/beef profile | Relative cattle-type composition | Local ED follower-type signal |
| ED adult dairy and suckler populations | Biological evidence on local breeding orientation | Local biological prior |
| GOBLIN cattle cohorts | National biological relationships among adult cows and DxD, DxB and BxB followers | Exact national cohort margins |
| IPF and exact integer reconciliation | Reconcile local priors with fixed row and column totals | Cross-scale accounting closure |

The design follows three principles:

1. **Local population conservation.** The cattle population assigned to an ED is fixed before biological subdivision.
2. **Evidence-informed composition.** Local AIM evidence and adult-cow structure shape how the fixed ED population is resolved biologically.
3. **Cross-scale closure.** County age-sex margins and national genetic margins are satisfied exactly while the ED totals remain unchanged.

## 2. The ED cattle population is established first

For ED \(i\) and year \(t\), the cattle accounting identity is

\[
T_{it}=D_{it}+S_{it}+O_{it},
\]

where

- \(D_{it}\) is dairy cows,
- \(S_{it}\) is other or suckler cows,
- \(O_{it}\) is other cattle, and
- \(T_{it}\) is total cattle.

The 2020 Census of Agriculture provides the ED anchor. Published ED values are retained as the spatial state for that year; cells withheld for confidentiality are filled beforehand to the exact census county totals (Stage 00, see `methodology.md` section 2.0).

For 2015-2019, each cattle component is reconstructed separately. Within each county, the ED share of dairy cows, other cows and other cattle moves from its 2010 census distribution towards its published 2020 distribution:

\[
s_{ict}= (1-\lambda_t)s_{ic,2010}+\lambda_t s_{ic,2020},
\]

with

\[
\lambda_t=\frac{t-2010}{10}.
\]

The annual county total for each component is then allocated across EDs in proportion to these shares and integerised by Hamilton allocation.

For 2021-2025, the published 2020 within-county component distribution provides the ED spatial pattern, while annual AAA10 county controls determine the quantity to be distributed. Each cattle component therefore retains its own spatial structure and closes exactly to the annual county control.

This stage establishes the local livestock envelope. All subsequent biological reconstruction takes place inside these fixed ED cattle populations.

## 3. Other cattle are resolved into seven age-sex containers

The ED quantity \(O_{it}\) is subdivided into seven age-sex groups:

1. bulls,
2. males under one year,
3. females under one year,
4. males aged one to two years,
5. females aged one to two years,
6. males aged two years and over, and
7. females aged two years and over.

For every county and year, AAA10 provides the corresponding seven-group age-sex composition. These county proportions are scaled to the county total of reconstructed ED other cattle, producing an exact county target vector

\[
\mathbf{C}_{ct}=(C_{1ct},\ldots,C_{7ct}).
\]

Every ED retains its own other-cattle row total:

\[
\sum_a N_{iat}=O_{it}.
\]

At the same time, each county closes to the seven AAA10 age-sex margins:

\[
\sum_{i\in c}N_{iat}=C_{act}.
\]

The allocation is therefore a constrained reconstruction rather than a uniform application of a county composition.

## 4. AIM supplies a local ED age signal

DAFM/AIM provides a 2020 ED cattle age profile. For each matched ED, the model forms a young-stock age ratio

\[
q_i^{A}=\frac{N_{i,<1}}{N_{i,<1}+N_{i,1-2}},
\]

where

\[
N_{i,<1}=N_{0-3m}+N_{3-6m}+N_{6-12m}
\]

and

\[
N_{i,1-2}=N_{12-18m}+N_{18-24m}.
\]

A corresponding county ratio \(q_c^{A}\) is calculated from all AIM records in the county. The local ED signal is expressed as a relative log-odds shift:

\[
\Delta_i^{A}=\operatorname{logit}(q_i^{A})-\operatorname{logit}(q_c^{A}).
\]

Let \(p_{ct}\) be the under-one share of the county young-stock target derived from AAA10 in year \(t\). The ED-specific prior becomes

\[
p_{it}=\operatorname{logistic}\left[
\operatorname{logit}(p_{ct})+\Delta_i^{A}
\right].
\]

This formulation preserves two pieces of information at once:

- the **annual county age structure** comes from AAA10, and
- the **relative spatial difference among EDs** comes from the AIM age profile.

The 2020 AIM age signature is therefore used as a local composition signal, while annual county totals continue to determine the age-sex margins in each year. Bulls, cattle aged two years and over, and sex shares within the young age groups retain the county CSO composition. The local AIM signal acts specifically on the under-one versus one-to-two-year balance.

A prior ED-by-age-sex matrix is built from these probabilities. Iterative proportional fitting then restores the exact ED row totals and county age-sex column totals, followed by integer reconciliation. The resulting age-sex population therefore satisfies both local cattle accounting and official county age structure.

## 5. GOBLIN supplies the national biological relationships

The six follower age-sex containers are subsequently subdivided into three biological origins:

- **DxD**: dairy-origin followers from dairy breeding,
- **DxB**: dairy-origin beef-cross followers from dairy cows, and
- **BxB**: beef-origin followers associated with suckler or beef breeding.

For each age-sex container \(a\), GOBLIN provides national cohort quantities together with national dairy- and suckler-cow populations. These are converted into per-cow biological coefficients:

\[
\beta_{a,DxD}=\frac{G_{a,DxD}}{G_D},
\]

\[
\beta_{a,DxB}=\frac{G_{a,DxB}}{G_D},
\]

and

\[
\beta_{a,BxB}=\frac{G_{a,BxB}}{G_S},
\]

where \(G_D\) and \(G_S\) are the GOBLIN dairy- and suckler-cow populations associated with the biological relationship.

The coefficients are applied to the national annual dairy and other-cow controls to form the expected national composition of each age-sex container. These expectations are then Hamilton-scaled to the exact national size of that container. The resulting target vector

\[
\mathbf{M}_{at}=(M_{a,DxD,t},M_{a,DxB,t},M_{a,BxB,t})
\]

is the national biological margin used in the ED reconstruction.

The important scientific separation is therefore explicit:

- **CSO determines how many animals occupy each ED age-sex container**, and
- **GOBLIN determines the nationally coherent biological composition of those containers**.

Both conditions are enforced simultaneously.

## 6. AIM also supplies a local cattle-type signal

The same 2020 AIM profile provides a second, independent local signal: the broad dairy/beef composition of cattle in each ED.

For a matched ED, let \(d_i^{A}\) denote the AIM dairy share of total cattle. The model places that composition on the fixed CSO cattle population and removes the fixed CSO dairy-cow population. The resulting dairy-type follower signal is

\[
q_i^{F}=\frac{T_i d_i^{A}-D_i}{O_i}.
\]

This quantity represents the local dairy-type tendency within the ED's fixed other-cattle population. A corresponding county signal is calculated from county AIM composition and county CSO cattle totals and supplies the reference value where an ED-specific signal is not available for direct use.

The model therefore uses AIM as a **composition signal** while CSO continues to determine the number of cattle in the ED.

## 7. The local genetic prior combines AIM, adult cows and national biology

For each age-sex container, the national target proportions are

\[
p_{a,g,t}^{N}=\frac{M_{a,g,t}}{\sum_g M_{a,g,t}}.
\]

The ED dairy-type follower signal modifies the national DxD probability through a log-odds spatial adjustment. If \(q^F_N\) is the national AIM-derived dairy-follower signal, then

\[
\Delta_i^{F}=\operatorname{logit}(q_i^{F})-
\operatorname{logit}(q_N^{F}),
\]

and the local DxD probability is

\[
p_{i,a,DxD,t}=
\operatorname{logistic}\left[
\operatorname{logit}(p_{a,DxD,t}^{N})+\Delta_i^{F}
\right].
\]

The remaining probability mass is

\[
r_{iat}=1-p_{i,a,DxD,t}.
\]

The split between DxB and BxB then combines local adult-cow structure with the national biological composition.

Local biological weights are formed as

\[
H_{i,a,DxB,t}=D_{it}\beta_{a,DxB},
\]

\[
H_{i,a,BxB,t}=S_{it}\beta_{a,BxB}.
\]

Let

\[
m_{a,DxB,t}=\frac{M_{a,DxB,t}}
{M_{a,DxB,t}+M_{a,BxB,t}}
\]

be the national DxB share of the non-DxD market component. The ED's remaining age-sex population contributes a national-market component

\[
P_{iat}=N_{iat}r_{iat}.
\]

The combined weights are then

\[
W_{i,a,DxB,t}=H_{i,a,DxB,t}+m_{a,DxB,t}P_{iat},
\]

\[
W_{i,a,BxB,t}=H_{i,a,BxB,t}+
(1-m_{a,DxB,t})P_{iat}.
\]

The conditional local DxB probability is

\[
c_{i,a,t}=\frac{W_{i,a,DxB,t}}
{W_{i,a,DxB,t}+W_{i,a,BxB,t}}.
\]

The complete local prior therefore becomes

\[
\mathbf{p}_{iat}=
\left(
 p_{i,a,DxD,t},
 r_{iat}c_{i,a,t},
 r_{iat}(1-c_{i,a,t})
\right).
\]

This construction uses all available biological information together:

- the ED's fixed age-sex population,
- its AIM cattle-type signal,
- its dairy-cow population,
- its suckler-cow population, and
- the national GOBLIN biological composition.

The result is an ED-specific biological prior inside a nationally coherent herd structure.

## 8. IPF reconciles local structure with national cohort margins

For each age-sex container, the prior probability vector is multiplied by the fixed ED row total to obtain an initial ED-by-genetic-origin matrix.

Iterative proportional fitting then reconciles this matrix to two exact sets of margins:

### ED row constraint

For every ED \(i\), age-sex container \(a\) and year \(t\),

\[
\sum_g N_{iagt}=N_{iat}.
\]

### National genetic constraint

For every age-sex container \(a\), genetic origin \(g\) and year \(t\),

\[
\sum_i N_{iagt}=M_{agt}.
\]

Exact integerisation follows the proportional reconciliation so that all livestock populations remain whole-animal counts.

This gives the central accounting property of GOBLIN-Spatial:

> **local rows close and national biological columns close simultaneously.**

The biological reconstruction therefore adds composition without altering the cattle populations already established by the spatial baseline.

## 9. The final 21-cohort cattle system

The reconstructed cattle population contains:

- dairy cows,
- suckler cows,
- bulls,
- DxD males and females under one year,
- DxB males and females under one year,
- BxB males and females under one year,
- DxD heifers and steers aged one to two years,
- DxB heifers and steers aged one to two years,
- BxB heifers and steers aged one to two years,
- DxD heifers and steers aged over two years,
- DxB heifers and steers aged over two years,
- BxB heifers and steers aged over two years.

For every ED and year,

\[
\sum_{k=1}^{21} C_{ikt}=T_{it}.
\]

The final cohort system is therefore a biological decomposition of the same ED cattle population rather than an additional cattle estimate.

## 10. Spatial heterogeneity and temporal propagation

The reconstruction separates the evidence used to describe differences among places from the controls used to propagate the annual panel.

The 2020 cross-section combines the strongest available small-area evidence:

- published CSO ED cattle totals and adult-cow populations,
- the AIM ED age profile,
- the AIM ED dairy/beef profile,
- county AAA10 age-sex controls, and
- GOBLIN national biological relationships.

The 2020 AIM age and cattle-type signatures provide persistent spatial composition signals. Across 2015-2025, annual county cattle and age-sex controls determine the changing quantity available to each ED, while the biological cohort system remains nationally coherent through the GOBLIN-derived margins.

This creates a consistent temporal architecture in which annual change and local structure are combined without breaking either the small-area cattle accounting or the higher-level livestock controls.

## 11. Livestock signatures are derived from additive cohort quantities

Once the 21 cattle cohorts are established, GOBLIN-Spatial derives livestock-system signatures such as dairy share, genetic-origin shares and follower-to-adult ratios.

At ED level these signatures are calculated from the reconstructed additive populations. For county, catchment and national reporting, additive livestock quantities are aggregated first and ratios are derived afterwards. This preserves the correct population weighting across spatial scales.

The signature system therefore describes agricultural function as well as abundance. Two EDs may contain similar numbers of cattle while differing substantially in adult-cow structure, follower composition and the relationship between parent and follower populations.

## 12. Spatial variation and evidence provenance are distinct scientific concepts

GOBLIN-Spatial keeps three concepts separate.

### Reporting resolution

The geography at which a model quantity is produced, for example ED, county or WFD catchment.

### Evidence provenance

The spatial scale and source of the evidence contributing to that quantity, for example a published ED census count, an ED AIM composition signal, a county age-sex control or a national biological margin.

### Spatial variation

The geographic distribution of the resulting quantity across places.

The between-county variation statistic

\[
R_B=\frac{V_{between\ county}}{V_{total\ ED}}
\]

describes the geography of variation. It quantifies how much of an ED-level pattern lies between counties rather than within counties. Evidence provenance is recorded separately through the source hierarchy used in the reconstruction.

This distinction is important because a strongly regional pattern can be based on direct ED evidence, while a locally variable pattern can still be constrained by higher-level margins. GOBLIN-Spatial therefore reports both the spatial pattern and the evidence architecture from which that pattern is reconstructed.

## 13. Scientific reconstruction sequence

The complete cattle reconstruction can be summarised as

```text
CSO 2010 and 2020 ED cattle structure
                  +
       annual AAA10 county controls
                  |
                  v
       fixed annual ED cattle envelope
                  |
                  +-----------------------------+
                  |                             |
                  v                             v
      AIM ED age signature          AIM ED cattle-type signature
                  |                             |
                  v                             |
       ED age-sex reconstruction                |
        under county controls                   |
                  |                             |
                  +-------------+---------------+
                                |
                                v
                    GOBLIN biological margins
                                +
                     adult dairy/suckler structure
                                |
                                v
                    ED biological cohort prior
                                |
                                v
                  IPF + exact integerisation
                                |
                                v
                    21 cattle cohorts by ED
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
            ED               County            Catchment
```

The scientific logic is therefore hierarchical and additive: the strongest local evidence fixes where livestock populations are represented, local biological signals refine their composition, and higher-level controls ensure that every reconstructed local system remains consistent with the official and biological totals of the wider livestock system.

## 14. Core scientific contract

GOBLIN-Spatial is built around the following identities and evidence relationships:

1. **Published ED cattle structure anchors the local population.**
2. **Annual county controls determine the quantity propagated through time.**
3. **AIM age information differentiates young-stock structure among EDs.**
4. **AIM dairy/beef information differentiates follower-type composition among EDs.**
5. **Adult dairy and suckler populations contribute biological evidence on local breeding orientation.**
6. **GOBLIN supplies nationally coherent DxD, DxB and BxB biological margins.**
7. **IPF reconciles local composition with fixed ED rows and exact higher-level columns.**
8. **Integerisation preserves whole-animal accounting.**
9. **The 21 cohorts sum exactly to the cattle population already assigned to each ED.**
10. **Higher-level livestock signatures are derived from aggregated additive quantities rather than averages of local percentages.**

Together, these rules make the ED a genuine spatial constraint on livestock reconstruction and allow national agricultural information to be represented as locally differentiated livestock systems suitable for place-based analysis.