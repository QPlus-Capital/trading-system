# Evidence

## HEAD

HEAD: 97ddc28d66b5be51e7b414aa7f14aba765a06b0f

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python scripts/quality/classify.py .ai/quality/task-artifacts.toml scripts/quality/pr_ready.py AGENTS.md tests/test_workflow_contract.py` | 0 | R3 from quality policy, readiness tooling, and the builder contract. |
| `red-first` | `uv run pytest -q tests/test_quality_process_scaling.py tests/test_finding_registry_split.py` | 1 | RED during collection: missing `pr_transition_decision` and missing `scripts.quality.finding_registry`; 2 collection errors. |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | 17 changed Python files formatted; Ruff and mypy passed. |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract` and `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_workflow_contract.py` | 0 | Generated contract matched its TOML facts; 92 documentation/contract tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, mypy, vulture, and full pytest passed after the draft-schema separation: 1573 passed, 1 Windows mutation skip. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative focused set passed: 178 tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Deterministic property replay passed twice: 21 + 21. |
| `integration-tests` | `uv run pytest -q tests/test_workflow_system_validation.py tests/test_quality_process_scaling.py tests/test_finding_registry_split.py` | 0 | 19 end-to-end workflow, scaling, and real-Git merge cases passed. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 124 --base origin/main` | 0 | Valid: 6 AC and 3 INV mappings; the schema permits an honest pending review while `pr_ready` still rejects it. |
| `adversarial-review` | [Claude independent review](https://github.com/QPlus-Capital/trading-system/pull/131#pullrequestreview-4811119024), submitted 2026-07-29 | 0 | **No finding.** Independently compared all 55 patterns field by field before and after the split migration with zero content differences; compared R3's required-section list literally with the old flat list and found it identical; and proved the 5/8/14/20 scaling monotone across all four classes. The activation rows, `transitional_review` validator, required-activation set, and constitution transitional rule were all removed together. Four commands exercised the production hook decision function: draft creation and branch push were allowed, non-draft creation was denied, and `gh pr ready` remained readiness-gated. `main_branch_decision` remained unloosened, `scripts/quality/classify.py` was absent from the diff, and the full suite passed 1,573 tests. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | GitHub Actions Critical mutation run `30472550163` | 0 | GREEN on reviewed head `2170237`: Linux killed 4,761 of 5,171 mutants, retained the 410 exact-name survivors, and passed the ratchet. No mutation target, baseline, threshold, or survivor classification changed in this PR. |
| `parity-where-applicable` | `git diff --name-only origin/main...HEAD` | 0 | No `core/**`, `research/**`, `live/**`, or `monitoring/**` path changed; trading parity is not applicable. |
| `live-money-review` | `git diff --name-only origin/main...HEAD` | 0 | No live-money or trading path changed; the R3 review is workflow-focused. |
| `human-decision-escalation` | `gh issue view 124 --comments --json body,comments,labels,projectItems` | 0 | No open Jan decision; the approved 5/8/14/20 workflow contract controls the stale AC-02 class name. |
| `no-autonomous-merge` | draft PR state and auto-merge inspection | 0 | PR #131 remains draft, auto-merge is disabled, and only Jan may make it ready or merge it. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found 0 known vulnerabilities, Ruff security checks passed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; 7 quality-tool production files and 11 directly related tests; no dynamic or critical-path edge discovered. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 124 --base origin/main` | 0 | READY: task artifacts and R3 classification pass, all 14 required gates have exit 0, and evidence covers reviewed head `2170237`. |

## Coverage and mutation

The focused red/green suite passed 110 tests and the complete focused workflow set
passed 178. The full suite passed 1573 with only the repository's intentional
Windows mutmut skip. No mutation target, pattern, threshold, baseline, or survivor
classification changed. The production mutation tree is therefore unchanged; the
required Linux job remains the authoritative ratchet observation.

Removing `push_readiness_decision` is safe specifically because branch protection on `main` now
has no bypass actors: a feature-branch push cannot reach protected `main`. The independent local
layer also remains intact: `main_branch_decision` is unchanged and still refuses R1+ commit or push
commands on `main`. The removed push-readiness layer was therefore the circular third layer, not
either protection that prevents unready work from reaching `main`.

## Deferred checks

Jan must still make the pull request ready and merge it. This evidence does not authorize a ready,
merge, or auto-merge action.
