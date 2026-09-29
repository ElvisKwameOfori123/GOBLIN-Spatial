# GOBLIN-Spatial multi-agent workflow

This repository may be worked on by more than one AI coding assistant, including ChatGPT/Codex and Claude Code. They do not communicate directly. GitHub is the shared source of truth.

The purpose of this protocol is to make their work complementary, auditable and safe for a scientific codebase.

## 1. Core rules

1. Read the current branch, current pull request, this file, `AGENT_DECISIONS.md`, and task-relevant scientific documentation before proposing or changing anything.
2. Do not trust another agent's summary without checking the repository state.
3. Do not silently change scientific mathematics, calibration logic, controls, assumptions, denominators, validation definitions, or published outputs.
4. Separate scientific changes from software/interface/refactoring changes.
5. Keep changes scoped to the task. Do not fix unrelated code merely because it is visible.
6. Never merge with failing required checks.
7. Record unresolved uncertainty instead of guessing.
8. Human approval is required before any scientific-method change is accepted.
9. Repository files, commits, tests, CI results and PR discussion outrank prose summaries outside GitHub.
10. When a task is explicitly baseline-only, SC1, SC2 and SC3 are out of scope unless the human owner says otherwise.

## 2. Shared coordination surface

The pull request is the live coordination surface.

- The PR description holds the task frame and Agent A proposal.
- Top-level PR comments hold Agent B review, questions, responses, implementation notes and verification.
- Git commits provide the exact implementation history.
- CI provides machine-verifiable checks.
- `AGENT_DECISIONS.md` records durable project decisions only.

Do not use a single repository-wide handover file for live task state. Multiple branches may be active at once and a shared handover file would become stale or conflict.

Do not store a branch HEAD SHA in a committed coordination file. The PR and GitHub commit history already identify the current SHA.

## 3. Roles

The agents are peers, not a chain of command.

### Agent A: proposer or implementer
The first agent working on a task:
- inspects the current repository state;
- frames the problem and scope in the PR description;
- identifies scientific and implementation risks;
- proposes an approach when the risk level requires it;
- implements only within the accepted scope.

### Agent B: independent reviewer/challenger
The second agent:
- independently inspects the repository state and diff;
- checks Agent A's claims rather than accepting the summary;
- records a top-level PR comment with evidence;
- identifies disagreements, missing cases and unintended consequences;
- verifies the implementation after changes.

Either ChatGPT/Codex or Claude may be Agent A or Agent B.

## 4. Change classes and review depth

Every task must be labelled with one of these:

- `DOCS_ONLY`: prose or documentation only.
- `IMPLEMENTATION_ONLY`: software change intended to preserve scientific results.
- `VALIDATION_ONLY`: diagnostics/tests/metrics without changing reconstruction mathematics.
- `SCIENTIFIC_CHANGE`: changes model mathematics, controls, assumptions, calibration, allocation, denominators, cohort logic or interpretation.
- `MIXED`: contains more than one class.

Use one of two review modes.

### Full two-agent cycle

Required for:
- `SCIENTIFIC_CHANGE`;
- `MIXED`;
- validation changes that alter statistical definitions, uncertainty methods, benchmark construction, acceptance criteria or scientific interpretation;
- any change the human owner marks as high risk.

Sequence:
1. Agent A frames the task and posts its proposed approach.
2. Agent B independently inspects the repository and posts its own assessment.
3. The agents compare agreement, disagreement, evidence, risks and alternatives.
4. A scientific disagreement is marked `HUMAN DECISION REQUIRED`.
5. The accepted approach is implemented.
6. The other agent independently verifies the diff, tests, CI and relevant outputs.
7. The human owner approves scientific/publication-facing merge decisions.

### Light cycle

Appropriate for:
- `DOCS_ONLY`;
- routine `IMPLEMENTATION_ONLY` fixes intended not to change science;
- straightforward test additions or maintenance.

Sequence:
1. One agent implements the scoped change.
2. The other agent independently reviews the diff and evidence.
3. Required tests/CI pass.
4. Any discovered scientific implication escalates the task to the full cycle.

This keeps routine work efficient without weakening scientific review.

## 5. PR task frame

The PR description should contain:

- task;
- change class;
- scope;
- explicit non-goals;
- scientific invariants;
- proposed approach, when required;
- files expected to change;
- validation plan;
- human decisions already made.

The repository template in `.github/pull_request_template.md` provides the standard structure.

## 6. Questions between agents

Agents cannot directly message each other. Use a top-level PR comment beginning with:

`[QUESTION FOR OTHER AGENT]`

Include:
- exact file/function/data object;
- what is uncertain;
- why it matters;
- evidence already checked;
- the decision or opinion needed.

The responding agent posts a new top-level comment beginning with:

`[RESPONSE]`

and includes:
- answer;
- repository evidence;
- confidence;
- remaining uncertainty.

For a substantive review use:

`[AGENT REVIEW]`

For final verification use:

`[AGENT VERIFICATION: PASS]`,
`[AGENT VERIFICATION: PASS WITH NOTES]`, or
`[AGENT VERIFICATION: BLOCK]`.

## 7. Decision protocol

A scientific decision may be treated as accepted only when:
- both agents agree and the human owner has already authorised that class of change; or
- the human owner explicitly chooses between alternatives.

If agents disagree on a scientific issue, do not implement the disputed scientific change. Record the disagreement and request a human decision.

For implementation-only disagreements, prefer the option that:
1. preserves scientific outputs;
2. changes fewer surfaces;
3. is easiest to test;
4. is easiest to reverse;
5. leaves the repository clearer.

## 8. Baseline protection rules

For the historical 2015-2025 baseline:

- published 2020 ED values remain authoritative where defined;
- reconstruction and validation evidence must remain distinguishable;
- exact closure constraints must not be weakened;
- validation metric names must match their mathematics;
- uncertainty methods must be documented accurately;
- scenario stages SC1-SC3 are not part of a baseline-only task;
- scenario source code may remain in the repository without being exercised by a baseline-only PR.

Any proposed change that may alter historical baseline values must be explicitly identified before implementation.

## 9. Conflict and failure handling

If both approaches are valid but different:
- combine them only if the combination is simpler and safer than either alone;
- otherwise retain both options for human choice.

If one proposal is contradicted by code, tests or authoritative project documentation, record that evidence and reject that proposal.

If CI fails:
- do not broaden scope automatically;
- determine whether the failure is caused by the current change;
- fix only task-relevant failures unless the human owner authorises broader repair.

## 10. Decision ledger

Important decisions that should survive the current PR belong in `AGENT_DECISIONS.md`.

Examples:
- scientific definitions;
- frozen baseline conventions;
- validation terminology;
- decisions to defer scenario work;
- interface conventions affecting future agents.

When a decision has a canonical scientific home such as `docs/SCIENTIFIC_ASSUMPTIONS.md`, the ledger should link to that source rather than duplicate or reinterpret it.

Do not use the ledger for temporary debugging notes or branch status.

## 11. Merge readiness checklist

A task is merge-ready only when all applicable items are true:

- [ ] accepted scope implemented;
- [ ] no unrelated scientific changes;
- [ ] tests pass;
- [ ] required CI passes;
- [ ] validation outputs inspected where relevant;
- [ ] documentation matches implementation;
- [ ] durable decisions recorded if needed;
- [ ] reviewing agent records PASS or PASS WITH NOTES, or the human owner explicitly overrides;
- [ ] scientific changes have explicit human approval.
