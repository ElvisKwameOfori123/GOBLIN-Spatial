# Claude Code instructions

This repository uses a shared multi-agent protocol.

Before making changes, read:

1. `AGENT_WORKFLOW.md`
2. `AGENT_DECISIONS.md`
3. the current pull request description and discussion
4. the current branch diff
5. task-relevant scientific documentation

Treat ChatGPT/Codex as a peer reviewer, not as an authority. Independently inspect repository evidence before agreeing or disagreeing.

Use the pull request as the live coordination surface. Put substantive questions, reviews, disagreements, implementation notes and verification results in top-level PR comments using the conventions in `AGENT_WORKFLOW.md`.

Do not silently change scientific mathematics, calibration, controls, assumptions, denominators or validation interpretation. Escalate unresolved scientific disagreements to the human owner.

Before stopping, leave the PR in a state where the other agent can determine what changed, what was checked and what remains unresolved.
