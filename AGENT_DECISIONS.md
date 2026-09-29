# Agent decision ledger

This file records durable project decisions that future AI agents must respect.

It is not a substitute for the scientific methodology or validation documentation. When a decision has a canonical scientific home elsewhere, link to that document instead of duplicating or reinterpreting it.

## D-001: GitHub pull requests are the inter-agent coordination surface

**Status:** Accepted

**Decision:** ChatGPT/Codex and Claude Code coordinate asynchronously through the repository. They do not assume direct model-to-model communication.

**Operational consequence:** The PR description frames the task and proposal; top-level PR comments carry peer review, questions, responses and verification; commits and CI provide implementation evidence. A single global handover file is not used.

## D-002: Agents are peers and must independently verify

**Status:** Accepted

**Decision:** One agent's summary is not authoritative merely because it was written first. The reviewing agent checks the repository independently and may challenge the proposal.

**Operational consequence:** Scientific, mixed and high-risk validation work uses the full proposal/review/decision/verification cycle. Routine documentation and implementation-only work may use a lighter implement-then-verify cycle.

## D-003: Human control of scientific changes

**Status:** Accepted

**Decision:** Changes to scientific mathematics, calibration, controls, assumptions, denominators, validation interpretation or publication-facing scientific claims require explicit human approval.

**Operational consequence:** Agent disagreement on scientific questions is escalated rather than silently resolved.

## D-004: Historical baseline and scenario work can be scoped separately

**Status:** Accepted

**Decision:** A historical-baseline-only task does not require modifying, running or deleting SC1, SC2 or SC3. Scenario code may remain present while being outside the active task.

**Operational consequence:** Agents must not broaden baseline work into scenario-stage maintenance without explicit instruction.

## Scientific decisions

Durable baseline scientific decisions should be added here only after their canonical documentation is current on the target branch. The ledger should link to the relevant section of `docs/SCIENTIFIC_ASSUMPTIONS.md`, `docs/methodology.md` or `docs/validation.md` rather than restating the science independently.
