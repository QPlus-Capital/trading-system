# Impact analysis

## Direct impact

- `docs/engineering/workflow.md` — new. States the board, the labels, the six phases, the per-class
  scaling table, and the three handover guards.
- `docs/engineering/constitution.md` — header gains a pointer to `workflow.md`; §9 gains the
  process-scaling rule; §16 gains the branch and worktree scheme, squash-on-merge, and the
  infrastructure-red merge rule; new §19 states workflow state and the handover guards.
- `CLAUDE.md` — new section "Where you act in the workflow" covering specifying, approval and review.
- `AGENTS.md` — "Development protocol" rewritten: permit check as step 0, the issue as the
  specification, worktree per issue, and the temporary pushed-branch review handover stated inline.
- `.ai/quality/workflow-contract.toml` — authoritative board, transition, builder-guard,
  activation, gate, ready-order, approval-order and transitional-review facts.
- `scripts/quality/workflow_contract.py` — narrow loader and renderer for the four workflow
  documents. It regenerates contract-owned blocks and compares the remaining document skeleton
  against exact digests; it does not operate on general documentation.
- `docs/architecture.md` — module map records the new quality module and workflow model.
- `tests/test_workflow_contract.py` — replaces prose parsers with regeneration/drift checks and
  commits all 16 semantic counterexamples.
- `tests/test_finding_registry.py` — makes every registry regression reference resolve.
- `tests/test_quality_validate_task.py` — resolves bare test-plan names and exposes the exact
  shrinking set of 14 legacy placeholders/stale names.
- `.ai/quality/finding-patterns.toml` — F-039 now names only current executable guards; four older
  entries gain concrete current test names so the new registry guard can bind them.

No trading, live, research, monitoring, CI, hook, dependency, gate-threshold, or mutation-baseline
file is touched.

## Transitive impact

- `tests/test_engineering_docs.py` reads all three role documents and asserts load-bearing phrases,
  role markers and forbidden stale markers; Jan's branch-protection decision is pinned by requiring
  every change, including R0, to reach `main` through a feature branch and pull request.
- `tests/test_engineering_workflow_docs.py` reads `branch-protection.md`, `reviewer-findings.md` and
  `sessions.md`. Untouched by this change. Verified passing.
- `tests/test_docs_language.py` enforces English across committed documentation, including the new
  file. Verified passing.
- `tests/test_docs_architecture_map.py` verifies that every path named in `docs/architecture.md`
  exists. The new renderer is added to the module map. Verified passing.
- `tests/test_claude_runtime_files.py` reads `.claude/**`, which is untouched. Verified passing.
- The classifier assigns R3 through the governance documents and `.ai/quality/**`; `pr_ready`
  therefore requires the full R3 gate set for this change.
- `scripts/quality/classify.py` is reused for `REPO_ROOT`; no second repository-root convention or
  matcher is introduced.

## Critical dependencies

`.ai/quality/critical-dependencies.toml` configures escalations for money-path modules. This change
touches no module named there, so no trading critical-path escalation applies. The new quality
module is exercised directly by the workflow contract suite, including 16 adversarial drift
fixtures. No mutation target is added because no production money-path function changes.

## Unknown or dynamic edges

- `docs/engineering/workflow.md` describes a GitHub project board and its built-in automations. That
  state lives outside the repository and cannot be asserted by any test here. Two automations
  (auto-add and item-closed) must be enabled in the project UI; until then cards are added by hand.
- Branch protection on `main` is not active: the repository is private on a plan that rejects
  protection rules. The document describes the intended merge discipline, which is currently enforced
  by convention and by the Claude pre-Bash hook only, not by GitHub.
- The pre-Bash hook binds Claude only. Codex has no equivalent enforcement path, so the permit check
  described in `AGENTS.md` is a procedural rule, not a technical guard, until #110 lands.
- The 14 unresolved bare task-plan names are pre-existing audit debt: two template placeholders and
  twelve names in ISSUE-62, ISSUE-91, P-03 and P-05. They are now an exact allowlist; a new stale
  name fails, and deleting or implementing one without shrinking the set also fails.

## Tool result

`just impact` (with the repository's Windows PowerShell shell override) classifies the change R3,
identifies only `scripts/quality/workflow_contract.py` as changed production code, finds no
critical-path escalation, and selects `test_engineering_docs.py`, `test_finding_registry.py`,
`test_github_templates.py`, `test_quality_pr_ready.py`, `test_quality_validate_task.py`,
`test_workflow_contract.py`, and `test_workflow_system_validation.py`. The full suite remains
mandatory because static impact analysis cannot prove the absence of dynamic edges.
