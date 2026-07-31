# Evidence

## HEAD

HEAD: bc4bc71c035b2d528f591a17d2d80250dfb5b6e9

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
| Review 4828407030 | Focused review-observation, validator, readiness, hook, and PR-body suite before the round-three production fix | 1 — 16 failed, 150 passed: 15 binding assertions exposed the orphaned blocker, approval rule, same-account diagnostic, emphasized severities, positional header, and hook codes; one temporary stale test-plan reference was corrected before implementation |

The new review-observation module did not exist on the original implementation base, so the first
combined focused run also failed during collection. The individual failures above are the
behavioural red proof and do not rely on that collection error.

## Commands

Required gate rows record only results actually observed on the code HEAD. A non-zero
`adversarial-review` row remains until Claude completes the required whole-change re-review.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `just check-fast origin/main` | 0 | All 12 changed Python files already formatted; Ruff and strict MyPy over 195 source files passed |
| `docs-consistency` | `uv run pytest -q tests/test_workflow_contract.py tests/test_engineering_docs.py tests/test_claude_runtime_files.py` | 0 | 99 passed |
| `check` | `just check` | 0 | Ruff, strict MyPy over 195 source files, Vulture, and pytest passed: 1,800 passed, 1 Mutmut-availability skip, 98 existing warnings |
| `impacted-tests` | `just check-fast origin/main` | 0 | All 289 directly and transitively impacted tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Two deterministic replays passed, 21 tests each |
| `integration-tests` | `just check` (`uv run pytest -q` subcommand) | 0 | Full suite: 1,800 passed, 1 Mutmut-availability skip |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 134 --base origin/main` | 0 | Task 134 valid; 7 AC and 3 INV mappings resolved |
| `adversarial-review` | Claude review `4828407030` of prior head `865a497` | 1 | D-01 through D-03, S-01 through S-03, and N-01 through N-07 are resolved; a complete independent re-review of material head `bc4bc71` remains required |
| `invariants` | `just check-invariants` | 0 | 543 critical-invariant tests passed |
| `mutation-on-touched-critical` | Production predicate over `changed_paths("origin/main")`, `select_fast_targets`, and `changed_tests_exercise_targets` | 0 | SKIPPED by the production selector: `targets=[]`, `dependent=False` |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean; pip-audit found 0 vulnerabilities; security lint passed |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | No live/backtest parity path is touched |
| `live-money-review` | `uv run python -m scripts.quality.classify` | 0 | Not applicable: no live-money or trading path is touched |
| `human-decision-escalation` | Jan's two review-state decisions in review `4828407030` | 0 | Per reviewer, the latest non-dismissed decisive state wins: later approval clears a change request, COMMENTED does not, and dismissal excludes the review. COMMENTED remains observable but same-account output says independence is not verified |
| `no-autonomous-merge` | `gh pr view 143 --json isDraft,autoMergeRequest` | 0 | Pull request remains draft and auto-merge is null |

## Additional probes

| Probe | Command | Exit | Result |
|---|---|---:|---|
| Focused post-fix suite | Focused review-observation, readiness, validator, hook, PR-body, CI-wiring, and registry tests | 0 | All 175 focused behavioural regressions passed; the complete impact-selected set passed 289 tests |
| Local Mutmut capability | `uv run --no-sync --with mutmut==3.5.0 python -m scripts.quality.mutation run --scope fast --base origin/main` | 1 | Windows cannot run Mutmut's fork-based worker; this is not a deferred required gate because impact selects no mutation target |
| Real local GitHub gateway | `uv run python -m scripts.quality.pr_ready 134 --base origin/main` before the remediation commit | 1 | The supported `gh` field set executed successfully and the old head was review-current; readiness failed only on the intentionally non-zero adversarial-review evidence row |
| Same-account diagnostic | Production `observe_independent_review(GhReviewGateway(), HEAD, "134")` on reviewed head `865a497` | 0 | Returned `verified` for review `4828407030` while explicitly stating that independence is not verified because the sole current review and last material commit use `JanQPlus` |

## Coverage and mutation

- Review 4823450100 D-01/D-02/D-03: the local gateway uses a CLI-supported exact argv and URL-derived
  base repository; every committed task evidence file parses a bare full SHA; blocking rows bind
  under Findings and Dispositions without a cell-level header escape.
- Review 4828407030 D-01: freshness uses only current reviews, while reviewer state is reduced over
  every non-dismissed record. The latest approval or change request wins by server timestamp and
  review id; COMMENTED cannot clear either decisive state.
- Review 4828407030 D-02/S-01/S-02: the installed CLI validates the production field list, both
  production entrypoints forward the observed task and verdict, and reduced CI rejects ambiguous or
  template task references.
- Review 4828407030 D-03/S-03: emphasized severity cells normalize before matching, only a table's
  first row can be its header, and an open Note remains non-blocking at R2 and R3.
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
- S-08: reviewer state is reduced deterministically per reviewer; comments cannot clear decisive
  states, later approvals can clear change requests, dismissed reviews are excluded, and equal
  timestamps use the later GitHub review id.
- S-09: only the four named files inside the current task id are artifact-only changes.

## Deferred checks

Only the complete independent re-review is outstanding. Mutation is a measured skip for this diff,
not a deferred execution.
