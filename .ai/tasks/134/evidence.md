# Evidence

## HEAD

HEAD: 21d374f4506ec7d0b2e97c13eb508459f4d2f978

The later evidence-only commit is permitted by the observed-review currency rule; it changes no
production, gate, or test behaviour.

## Red-first proof

The guards were exercised against pre-fix HEAD
`842431d0f661aa583abffc38820011f242c35d7f`.

| Counterexample | Command/result | Exit |
|---|---|---:|
| D-01/D-02/D-03 | Focused `validate_task` counterexamples for unresolved R2/R3 findings, empty R2/R3 reviews, strict R2 observation, and legacy severity vocabulary | 1 — 10 failed, 1 passed |
| D-01 readiness | Focused `pr_ready` counterexamples for unresolved R2/R3 review dispositions and advisory labelling | 1 — 3 failed |
| D-02 hook | Staged empty `review.md` fixtures for R2 and R3 | 1 — 2 failed |
| D-03 PR-body path | `pr_body.main` verified/rejected/unverifiable strict cases | 1 — 3 failed |
| S-07 workflow wiring | Exact command-wiring guard | 1 — 1 failed |
| S-08 state reduction | A `COMMENTED` review after `CHANGES_REQUESTED` was asserted to remain rejected | 124 — assertion failed before the timeout: old code returned `verified` |
| S-09 artifact scope | Assert `_templates/review.md` is not a task artifact | 1 — old code returned true |
| D-05 freshness | A stale review between two deliberately out-of-timestamp-order code commits was asserted rejected | 1 — old code trusted `relevant[-1]` and returned `verified` |
| Review 4823450100 D-03 / S-01 | Focused production-path regressions over the review observer, disposition scanner, evidence parser, and PR-body validator | 1 — 5 failed, 112 passed: cross-window change requests and both disposition placements escaped |
| Review 4823450100 D-01 | `gh pr view 143 --json number,headRefOid,baseRepository` against the installed CLI | 1 — `Unknown JSON field: "baseRepository"` |
| Review 4823450100 D-02 | Production `_recorded_head` over task 134's former `Code HEAD: \`...\`` spelling | 1 — returned `None`; the repository-wide parser guard identified task 134 |
| Review 4823450100 S-02 to S-07 | Distinguishing rename-into-artifacts, real PR-body hop, artifact-only history, approval tie, local head mismatch, and malformed resolved-row regressions | 0 on fixed code; each input is the review's verified counterexample and now reaches the production decision |

The new review-observation module did not exist on the original implementation base, so the first
combined focused run also failed during collection. The individual failures above are the
behavioural red proof and do not rely on that collection error.

## Commands

Required gate rows record only results actually observed on the code HEAD. A non-zero
`adversarial-review` row remains until Claude completes the required whole-change re-review.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | All 12 changed Python files already formatted |
| `docs-consistency` | `uv run pytest -q tests/test_workflow_contract.py tests/test_engineering_docs.py tests/test_claude_runtime_files.py` | 0 | 99 passed |
| `check` | PowerShell: `$env:PYTHONUTF8='1'; just --shell "C:\Program Files\Git\bin\sh.exe" check` after rebasing onto `origin/main` at `90fdb04` | 0 | Ruff passed; mypy passed over 195 source files; Vulture passed; pytest: 1,776 passed, 1 Mutmut-availability skip |
| `impacted-tests` | `uv run python -m scripts.quality.impact --base origin/main --run-focused` | 0 | 201 directly and transitively impacted tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Two deterministic replays passed, 21 tests each |
| `integration-tests` | Rebased `just check` (`uv run pytest -q` subcommand) | 0 | Full suite: 1,776 passed, 1 Mutmut-availability skip; #136 registry and audit-reference guards remain active |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 134 --base origin/main` | 0 | Task 134 valid; 7 AC and 3 INV mappings resolved |
| `adversarial-review` | Complete independent re-review by Claude after review 4823450100 | 1 | Pending on the remediated head; the builder does not self-certify |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 542 critical-invariant tests passed |
| `mutation-on-touched-critical` | Production predicate over `changed_paths("origin/main")`, `select_fast_targets`, and `changed_tests_exercise_targets` | 0 | SKIPPED by the production selector: `targets=[]`, `dependent=False` |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean; pip-audit found 0 vulnerabilities; security lint passed |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | No live/backtest parity path is touched |
| `live-money-review` | `uv run python -m scripts.quality.classify` | 0 | Not applicable: no live-money or trading path is touched |
| `human-decision-escalation` | Jan's S-01 decision recorded in the request and implemented literally | 0 | Undismissed `CHANGES_REQUESTED` remains blocking across commit windows; only explicit GitHub dismissal clears it |
| `no-autonomous-merge` | `git status --short --branch` | 0 | Feature branch only; merge and auto-merge remain disabled |

## Additional probes

| Probe | Command | Exit | Result |
|---|---|---:|---|
| Focused post-fix suite | Focused review-observation, readiness, validator, hook, PR-body, CI-wiring, and registry tests | 0 | All focused behavioural regressions passed; the complete impact-selected set passed 201 tests |
| Local Mutmut capability | `uv run --no-sync --with mutmut==3.5.0 python -m scripts.quality.mutation run --scope fast --base origin/main` | 1 | Windows cannot run Mutmut's fork-based worker; this is not a deferred required gate because impact selects no mutation target |
| Real local GitHub gateway | `uv run python -m scripts.quality.pr_ready 134 --base origin/main` before the remediation commit | 1 | The supported `gh` field set executed successfully and the old head was review-current; readiness failed only on the intentionally non-zero adversarial-review evidence row |

## Coverage and mutation

- Review 4823450100 D-01/D-02/D-03: the local gateway uses a CLI-supported exact argv and URL-derived
  base repository; every committed task evidence file parses a bare full SHA; blocking rows bind
  under Findings and Dispositions without a cell-level header escape.
- Review 4823450100 S-01: freshness proves a current non-dismissed review exists, while each
  reviewer's undismissed change request remains blocking across commit windows.
- Review 4823450100 S-02 through S-07: the rename flag, real PR-body call chain, artifact-only
  outcome, decisive tie, local head check, and malformed resolved row each have a distinguishing
  executable counterexample.
- Earlier D-01/D-02/D-03: R2 and R3 independently require the observed GitHub review, review
  structure, and resolved dispositions. `resolved_review_statuses`, `unresolved-review`, and
  `[sections]."review.md"` all execute on the readiness path.
- D-04: synchronize scope is derived from `git diff --no-renames`; the GitHub commit boundary also
  unions `filename` and `previous_filename`.
- D-05: review freshness is bound to GitHub `commit_id` and verified against ordered commit
  ancestry. Client timestamps and `relevant[-1]` are not freshness anchors.
- S-06/S-07/S-10/S-12: the strict PR-body path and real `gh` process boundary are exercised,
  pagination and malformed/unreachable inputs fail closed, and the CI command invokes the tested
  entrypoint exactly.
- S-08: reviewer state is reduced deterministically per reviewer; comments cannot clear change
  requests, later approvals can, dismissed reviews are excluded, and ties remain blocking.
- S-09: only the four named files inside the current task id are artifact-only changes.

## Deferred checks

Only the complete independent re-review is outstanding. Mutation is a measured skip for this diff,
not a deferred execution.
