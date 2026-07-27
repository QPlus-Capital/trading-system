# Impact analysis

## Direct impact

- `docs/engineering/workflow.md` — new. States the board, the labels, the six phases, the per-class
  scaling table, and the three handover guards.
- `docs/engineering/constitution.md` — header gains a pointer to `workflow.md`; §9 gains the
  process-scaling rule; §16 gains the branch and worktree scheme, squash-on-merge, and the
  infrastructure-red merge rule; new §19 states workflow state and the handover guards.
- `CLAUDE.md` — new section "Where you act in the workflow" covering specifying, approval and review.
- `AGENTS.md` — "Development protocol" rewritten: permit check as step 0, the issue as the
  specification, worktree per issue, card moved to `Reviewing` on PR.

No source, test, configuration or workflow file is touched.

## Transitive impact

- `tests/test_engineering_docs.py` reads all three role documents and asserts load-bearing phrases,
  role markers, forbidden stale markers, and the R0-only direct-to-main exception. Verified passing.
- `tests/test_engineering_workflow_docs.py` reads `branch-protection.md`, `reviewer-findings.md` and
  `sessions.md`. Untouched by this change. Verified passing.
- `tests/test_docs_language.py` enforces English across committed documentation, including the new
  file. Verified passing.
- `tests/test_docs_architecture_map.py` verifies that every path named in `docs/architecture.md`
  exists. `workflow.md` is not listed there and does not affect it. Verified passing.
- `tests/test_claude_runtime_files.py` reads `.claude/**`, which is untouched. Verified passing.
- The classifier assigns R3 to all four changed paths; `pr_ready` therefore requires the full R3
  gate set for this change.

## Critical dependencies

`.ai/quality/critical-dependencies.toml` configures escalations for money-path modules. This change
touches no module named there, so no critical-path escalation applies. Governance documents are
covered by the documentation consistency tests listed above rather than by a runtime test.

## Unknown or dynamic edges

- `docs/engineering/workflow.md` describes a GitHub project board and its built-in automations. That
  state lives outside the repository and cannot be asserted by any test here. Two automations
  (auto-add and item-closed) must be enabled in the project UI; until then cards are added by hand.
- Branch protection on `main` is not active: the repository is private on a plan that rejects
  protection rules. The document describes the intended merge discipline, which is currently enforced
  by convention and by the Claude pre-Bash hook only, not by GitHub.
- The pre-Bash hook binds Claude only. Codex has no equivalent enforcement path, so the permit check
  described in `AGENTS.md` is a procedural rule, not a technical guard, until #110 lands.
