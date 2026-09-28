# GOBLIN-Spatial multi-agent workflow

This repository may be worked on by more than one AI coding assistant, including ChatGPT/Codex and Claude Code. They do not communicate directly. GitHub is the shared source of truth.

The purpose of this protocol is to make their work complementary, auditable and safe for a scientific codebase.

## 1. Core rules

1. Read the current branch, current pull request, this file, `AGENT_HANDOVER.md`, and `AGENT_DECISIONS.md` before proposing or changing anything.
2. Do not trust another agent's summary without checking the repository state.
3. Do not silently change scientific mathematics, calibration logic, controls, assumptions, denominators, validation definitions, or published outputs.
4. Separate scientific changes from software/interface/refactoring changes.
5. Keep changes scoped to the task. Do not fix unrelated code merely because it is visible.
6. Never merge with failing required checks.
7. Record unresolved uncertainty instead of guessing.
8. Human approval is required before any scientific-method change is accepted.
9. Repository files, commits, tests and CI results outrank prose summaries.
10. When a task is explicitly baseline-only, SC1, SC2 and SC3 are out of scope unless the human owner says otherwise.

## 2. Roles

The agents are peers, not a chain of command.

### Agent A: proposer
The first agent working on a task:
- inspects the current repository state;
- states the problem;
- proposes one or more approaches;
- identifies scientific and implementation risks;
- recommends an approach;
- records the proposal in `AGENT_HANDOVER.md`.

### Agent B: reviewer/challenger
The second agent:
- independently inspects the same repository state;
- checks Agent A's claims;
- proposes its own approach before reading the recommendation as binding;
- identifies disagreements, missing cases and unintended consequences;
- records its review in `AGENT_HANDOVER.md`.

Either ChatGPT/Codex or Claude may be Agent A or Agent B.

## 3. Decision protocol

For non-trivial work, use the following sequence.

### Step 1: Frame
Record:
- task;
- branch and HEAD SHA;
- scope;
- explicit non-goals;
- files likely involved;
- scientific invariants that must remain true.

### Step 2: Independent approaches
Each agent writes a short proposal containing:
- approach;
- expected files changed;
- advantages;
- risks;
- validation plan;
- whether the change is scientific, implementation-only, documentation-only, or mixed.

Do not overwrite the other agent's proposal.

### Step 3: Compare
The reviewing agent writes a comparison under these headings:
- points of agreement;
- points of disagreement;
- evidence from the repository;
- safest option;
- strongest option;
- recommended combined approach.

### Step 4: Decide
A decision may be marked `ACCEPTED` only when:
- both agents agree; or
- the human owner explicitly chooses between alternatives.

If agents disagree on a scientific issue, mark it `HUMAN DECISION REQUIRED`. Do not implement the disputed scientific change.

For implementation-only disagreements, prefer the option that:
1. preserves scientific outputs;
2. changes fewer surfaces;
3. is easiest to test;
4. is easiest to reverse;
5. leaves the repository clearer.

### Step 5: Implement
The implementing agent:
- works only on the accepted scope;
- uses a dedicated branch for substantial changes;
- keeps commits small and descriptive;
- runs the agreed tests;
- updates `AGENT_HANDOVER.md`.

### Step 6: Verify
The other agent independently checks:
- diff;
- tests;
- CI;
- expected outputs;
- scientific invariants;
- whether unrelated files changed.

It records `PASS`, `PASS WITH NOTES`, or `BLOCK`.

### Step 7: Human merge
The human owner retains final merge authority for scientific or publication-facing changes.

## 4. Scientific change classes

Every task must be labelled with one of these:

- `DOCS_ONLY`: prose or documentation only.
- `IMPLEMENTATION_ONLY`: software change intended to preserve scientific results.
- `VALIDATION_ONLY`: diagnostics/tests/metrics without changing reconstruction mathematics.
- `SCIENTIFIC_CHANGE`: changes model mathematics, controls, assumptions, calibration, allocation, denominators, cohort logic or interpretation.
- `MIXED`: contains more than one class.

A `SCIENTIFIC_CHANGE` or `MIXED` task cannot be treated as routine refactoring.

## 5. Baseline protection rules

For the historical 2015-2025 baseline:

- published 2020 ED values remain authoritative where defined;
- reconstruction and validation evidence must remain distinguishable;
- exact closure constraints must not be weakened;
- validation metric names must match their mathematics;
- uncertainty methods must be documented accurately;
- scenario stages SC1-SC3 are not part of a baseline-only task;
- scenario source code may remain in the repository without being exercised by a baseline-only PR.

Any proposed change that may alter historical baseline values must be explicitly identified before implementation.

## 6. Questions between agents

Agents cannot directly message each other. Questions are written into `AGENT_HANDOVER.md` under `Open questions for the other agent`.

Each question should include:
- exact file/function/data object;
- what is uncertain;
- why it matters;
- evidence already checked;
- the decision needed.

The responding agent writes directly below the question with:
- answer;
- evidence;
- confidence;
- any remaining uncertainty.

## 7. Conflict handling

If both approaches are valid but different:
- prefer combining them only if the combination is simpler than either alone;
- otherwise retain both options for human choice.

If one proposal is contradicted by code, tests or authoritative project documentation, record that evidence and reject that proposal.

If CI fails:
- do not broaden scope automatically;
- determine whether the failure is caused by the current change;
- fix only task-relevant failures unless the human owner authorises broader repair.

## 8. Handover discipline

Before stopping work, update `AGENT_HANDOVER.md` with:
- timestamp;
- agent;
- branch;
- HEAD SHA;
- task status;
- files changed;
- tests run;
- CI status;
- outputs inspected;
- unresolved questions;
- exact next action.

Never write "done" unless the repository state and required checks support it.

## 9. Decision ledger

Important decisions that should survive the current task belong in `AGENT_DECISIONS.md`.

Examples:
- scientific definitions;
- frozen baseline conventions;
- validation terminology;
- decisions to defer scenario work;
- interface conventions affecting future agents.

Do not use the decision ledger for temporary debugging notes.

## 10. Merge readiness checklist

A task is merge-ready only when all applicable items are true:

- [ ] accepted scope implemented;
- [ ] no unrelated scientific changes;
- [ ] tests pass;
- [ ] required CI passes;
- [ ] validation outputs inspected where relevant;
- [ ] documentation matches implementation;
- [ ] handover updated;
- [ ] decision ledger updated if a durable decision was made;
- [ ] reviewer agent records PASS or human owner explicitly overrides;
- [ ] scientific changes have explicit human approval.
