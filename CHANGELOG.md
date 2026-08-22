# GOBLIN-Spatial Changelog

This changelog records changes that matter for scientific interpretation, reproducibility or the supported user workflow.

It is not intended to duplicate every Git commit. Small refactors, formatting edits and implementation details that do not alter scientific meaning remain available in the repository history.

The log begins with the August 2026 v1 finalisation period. Earlier development history remains available through Git and the merged pull-request record.

Each entry should identify whether a change is primarily **SCIENTIFIC**, **INPUT**, **CALIBRATION**, **REPORTING**, **SOFTWARE**, **INTERFACE** or **DOCUMENTATION**.

For current scientific assumptions and interpretation boundaries, see [`docs/SCIENTIFIC_ASSUMPTIONS.md`](docs/SCIENTIFIC_ASSUMPTIONS.md).

---

## 2026-08-22 — Add scientific assumptions register

**Type:** DOCUMENTATION / SCIENTIFIC GOVERNANCE

### Changed
- Added `docs/SCIENTIFIC_ASSUMPTIONS.md`.
- Separated observed evidence, reconstruction assumptions, exogenous national controls, normative spatial experiments, feasibility rules, sensitivity parameters and interpretation boundaries.
- Added a minimum reporting template for future scientific changes.

### Scientific effect
- None. This change documents the current model contract; it does not alter calculations or outputs.

---

## 2026-08-22 — Clarify scenario spatialisation and staged workflow

**Type:** DOCUMENTATION

**Commit:** `4a7ddba32cdb4f3dcff5d075139da9ef7025bb5c`

### Changed
- Expanded the README explanation of how SC1 spatialises a national GOBLIN pathway.
- Clarified that protection rules alter spatial incidence, not national endpoints.
- Clarified that the national gross released-land quantity is supplied by GOBLIN and only its geography is resolved by GOBLIN-Spatial.
- Clarified that SC2 opportunity represents compatibility rather than adoption probability.
- Clarified that SC3 allocates competing land uses jointly under shared physical capacity.
- Updated the README to show the guided and explicit staged-run interfaces.

### Scientific effect
- None. Documentation was aligned with the existing validated implementation.

---

## 2026-08-22 — Add guided baseline-to-SC3 study runner

**Type:** INTERFACE / SOFTWARE

**Principal commits:**
- `7450590b878d614a09decf27915b5ea77cd4d5f1` — add guided baseline-to-SC3 study runner
- `22bcb0ecf964d31c47465619b52f8849c9d8bb0b` — add staged-run tests
- `9c3ec2d03544a6b5a779efe2a0dc82d3312d1a75` — gate the wrapper in CI
- `8f3988bd44747d6525efd53638d0ce74ce1cd2ff` — fail invalid staged requests before baseline build

### Changed
- Added a guided `goblin-spatial` menu.
- Added explicit stopping points at `baseline`, `SC1`, `SC2` and `SC3`.
- Added `goblin-spatial study --through ...` for reproducible non-interactive runs.
- The wrapper rebuilds the validated baseline and delegates scenario execution to the existing principal scenario runner.
- Invalid SC2/SC3 requests using the 2025 land context are rejected before the baseline build begins.

### Scientific effect
- None.

### Unchanged
- National scenario controls.
- Adult livestock endpoint allocation mathematics.
- Follower-cohort propagation.
- National released-land accounting.
- SC2 opportunity logic.
- SC3 allocation mathematics.

### Validation
- Added focused CLI tests.
- Existing end-to-end SC1-to-SC3 CI remains part of the production test workflow.

---

## 2026-08-21 — Finalise repository-contained GOBLIN-Spatial v1 runtime

**Type:** SCIENTIFIC RUNTIME / SOFTWARE / INPUT GOVERNANCE

**Main commit after merge:** `e047a0d3bcfaf6cb0f1231f782ce38bbdeb848f5`

### Frozen production contract
- Historical reconstruction covers 2015–2025 across 2,857 EDs.
- 2020 remains the principal full spatial scenario baseline.
- The principal livestock representation contains 21 cattle cohorts and 10 sheep cohorts.
- GOBLIN supplies the national pathway; GOBLIN-Spatial resolves its geography.
- SC1 spatialises livestock adjustment and authoritative national released land.
- SC2 evaluates released-land capability, physical soil evidence and LPIS opportunity without changing SC1.
- SC3 tests alternative land-use feasibility under shared physical capacity and reports unmet targets explicitly.
- The production runtime is repository-contained and verifies frozen inputs rather than downloading replacements.

### Interpretation boundary
- GOBLIN-Spatial is a deterministic spatial stress-test and feasibility framework, not a behavioural forecast of individual farms, parcels or future ED outcomes.

---

## 2026-08-21 — Report local cattle expansion without changing pathway totals

**Type:** REPORTING

**Commit:** `264e8b8e61262961a9e175377f60946ae5cac415`

### Changed
- Preserved signed ED cattle change.
- Added explicit reduction and expansion diagnostics rather than rejecting negative `BASE - SCENARIO` values.

### Reason
- Local ED expansion can be scientifically valid even when the national pathway contracts overall.

### Scientific effect
- Reporting semantics corrected.
- National endpoints, cohort propagation, released-land calculations, SC2 and SC3 mathematics were unchanged.

---

## 2026-08-21 — Canonicalise compound ED identifiers in the land context

**Type:** INPUT / DATA INTEGRITY

**Commit:** `b66d531b1d63849c079a2a1df7c4dd04379cdadd`

### Changed
- Canonicalised compound ED identifier forms such as `8045/8046` during land-context joining.

### Effect
- Restored the intended 2,857 unique ED spatial universe in the frozen land-context join.
- No scenario endpoint or allocation rule was redefined.

---

# Template for future entries

```text
## YYYY-MM-DD — Short title

Type: SCIENTIFIC / INPUT / CALIBRATION / REPORTING / SOFTWARE / INTERFACE / DOCUMENTATION

Changed
- ...

Reason
- ...

Evidence
- Source or control used.
- State whether it is an input, calibration target or independent validation check.

Affected
- Model stages and outputs that may change.

Unchanged
- Model stages and outputs that must remain invariant.

Validation
- Reconciliation, regression, sensitivity or independent checks performed.
```
