# Evidence

## HEAD

HEAD: 6405a2bc586c356cd05942c8e767ff575f6659c1

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py tests/test_quality_issue_body.py` | 1 | RED: collection stopped on `ModuleNotFoundError` for both new production modules; 2 errors |
| `format` | `uv run ruff format --check scripts/quality/board.py scripts/quality/issue_body.py tests/test_quality_board.py tests/test_quality_issue_body.py tests/test_workflow_contract.py` | 0 | GREEN: all five changed Python files formatted |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract && uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_workflow_contract.py` | 0 | GREEN: contract drift absent; 87 documentation/contract tests passed |
| `check-fast` | `uvx --from rust-just just check-fast` | 0 | GREEN: changed-file format, ruff, strict mypy, and 49 impact-selected tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: ruff, mypy, vulture; 1,613 tests passed, 1 platform skip |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_quality_issue_body.py tests/test_quality_process_scaling.py tests/test_gate_consistency.py` | 0 | GREEN: 44 focused quality tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: 21 property tests passed twice with the fixed seed |
| `integration-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_quality_issue_body.py tests/test_workflow_contract.py tests/test_docs_architecture_map.py tests/test_gate_consistency.py` | 0 | GREEN: 59 board/config/contract/integration tests passed |
| `artifact-schema` | `uvx --from rust-just just check-task-artifact 110` | 0 | GREEN: R3 artifact has all four required files and maps 6 AC plus 2 INV |
| `adversarial-review` | [Claude independent review](https://github.com/QPlus-Capital/trading-system/pull/132#pullrequestreview-4812992929), 2026-07-30 | 0 | GREEN: no findings after six concrete counterexamples |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: 529 critical-invariant tests passed |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, 0 known vulnerabilities, security lint clean |
| `impact` | `uvx --from rust-just just impact` | 0 | GREEN: R3; two production quality modules, three directly related tests, no critical mutation target |
| `project-add-dogfood` | `uv run python -m scripts.quality.board add 101` | 0 | GREEN: #101 moved from no project item to project status `Backlog`; no issue content or label changed |
| `real-cli-boundaries` | `uv run python -m scripts.quality.board status 110 && uv run python -m scripts.quality.issue_body validate --issue 110` | 0 | GREEN: runtime project metadata resolved by name; approved issue body valid for R3 |
| `mutation-on-touched-critical` | GitHub Actions run `30518789962`, `critical-change-filter` | 0 | GREEN: no critical production path changed and none of the three changed test files reaches a configured target through the import graph; mutation was correctly skipped |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring` | 0 | GREEN: no strategy, research, live, or monitoring path changed |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | NOT APPLICABLE: no live-money path changed; independent governance review remains required |
| `human-decision-escalation` | `uv run python -m scripts.quality.issue_body validate --issue 110` | 0 | GREEN: approved R3 issue has `Open decisions (Jan): None` |
| `no-autonomous-merge` | `gh pr view 132 --json isDraft,autoMergeRequest` | 0 | GREEN: ready transition is human-controlled and autoMergeRequest is null |
| `draft-ci` | GitHub Actions runs `30486212514` and `30486212491` | 0 | GREEN: `platform-quality` passed; critical filter passed; ready-only `full-quality` and mutation remained skipped |

## Coverage and mutation

The red-first suite pins every AC and both invariants through fake GitHub mutations. Production CLI
dogfooding additionally exercised the real ProjectV2 JSON shape, UTF-8 output, runtime option lookup,
and issue-body line wrapping.

The independent review verified that `board.py` takes statuses, transitions, approval steps, and
builder guards from `load_contract()` with no hardcoded project or option IDs. `_write_approved`
enforces AC-02 twice: the contract-derived ordering reaches the status step before `approved`, and
the final write re-reads the card and risk label as a precondition. `just new-task` calls
`required_files_for(risk_class)` instead of scaffolding four files unconditionally.

GitHub run `30518789962` evaluated the production mutation policy. It selected no target because no
critical production path changed and none of `tests/test_quality_board.py`,
`tests/test_quality_issue_body.py`, or `tests/test_workflow_contract.py` reaches a configured target
through the import graph. `mutation-critical` therefore skipped by #113's intended filter decision;
this is a vacuous gate, not omitted mutation evidence.

## Deferred checks

- The first ready-state `full-quality` run `30518789919` failed only because the pre-review
  `review.md` correctly did not claim that review had run. This artifact update supplies the now
  completed review record; the next push reruns the gate.
- The project card was already `Reviewing` when the explicit handover command ran, so the production
  tool correctly refused to invent a `Reviewing → Reviewing` transition; the final board state is
  verified as `Reviewing`.
