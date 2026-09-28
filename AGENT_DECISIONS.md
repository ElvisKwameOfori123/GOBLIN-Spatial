# Agent decision ledger

This file records durable project decisions that future AI agents must respect.

It is not a substitute for the scientific methodology or validation documentation. When a decision has a canonical scientific home elsewhere, link to that document instead of duplicating it here.

## D-001: GitHub is the inter-agent source of truth

**Status:** Accepted

**Decision:** ChatGPT/Codex and Claude Code coordinate asynchronously through the repository. They do not assume direct model-to-model communication.

**Operational consequence:** Agents use `AGENT_HANDOVER.md`, commits, pull requests, tests and CI to exchange state and evidence.

## D-002: Agents are peers and must independently verify

**Status:** Accepted

**Decision:** One agent's summary is not authoritative merely because it was written first. The reviewing agent checks the repository independently and may challenge the proposal.

**Operational consequence:** Non-trivial tasks use proposal, independent review, comparison, implementation and verification stages.

## D-003: Human control of scientific changes

**Status:** Accepted

**Decision:** Changes to scientific mathematics, calibration, controls, assumptions, denominators, validation interpretation or publication-facing scientific claims require explicit human approval.

**Operational consequence:** Agent disagreement on scientific questions is escalated rather than silently resolved.

## D-004: Historical baseline and scenario work can be scoped separately

**Status:** Accepted

**Decision:** A historical-baseline-only task does not require modifying, running or deleting SC1, SC2 or SC3. Scenario code may remain present while being outside the active task.

**Operational consequence:** Agents must not broaden baseline work into scenario-stage maintenance without explicit instruction.
