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
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: 529 critical-invariant tests passed |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, 0 known vulnerabilities, security lint clean |
| `impact` | `uvx --from rust-just just impact` | 0 | GREEN: R3; two production quality modules, three directly related tests, no critical mutation target |
| `project-add-dogfood` | `uv run python -m scripts.quality.board add 101` | 0 | GREEN: #101 moved from no project item to project status `Backlog`; no issue content or label changed |
| `real-cli-boundaries` | `uv run python -m scripts.quality.board status 110 && uv run python -m scripts.quality.issue_body validate --issue 110` | 0 | GREEN: runtime project metadata resolved by name; approved issue body valid for R3 |
| `mutation-on-touched-critical` | GitHub Actions run `30486212491`, `critical-change-filter` | 0 | GREEN: production policy selected no touched critical target; `mutation-critical` was correctly vacuous/skipped for this draft |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring` | 0 | GREEN: no strategy, research, live, or monitoring path changed |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | NOT APPLICABLE: no live-money path changed; independent governance review remains required |
| `human-decision-escalation` | `uv run python -m scripts.quality.issue_body validate --issue 110` | 0 | GREEN: approved R3 issue has `Open decisions (Jan): None` |
| `no-autonomous-merge` | `gh pr view 132 --json isDraft,autoMergeRequest` | 0 | GREEN: draft is true and autoMergeRequest is null |
| `draft-ci` | GitHub Actions runs `30486212514` and `30486212491` | 0 | GREEN: `platform-quality` passed; critical filter passed; ready-only `full-quality` and mutation remained skipped |

## Coverage and mutation

The red-first suite pins every AC and both invariants through fake GitHub mutations. Production CLI
dogfooding additionally exercised the real ProjectV2 JSON shape, UTF-8 output, runtime option lookup,
and issue-body line wrapping.

No configured mutation target under `core/`, `research/`, `live/`, or `monitoring/` changed. GitHub
run `30486212491` evaluated the production policy, passed the critical-change filter, and skipped
the vacuous mutation job. Native Windows also refused mutmut as designed because it requires
`fork`; no Linux mutation result is claimed where no target was selected.

## Deferred checks

- Independent adversarial review runs on the draft pull request after this builder handover.
- The draft pull request opened as #132, auto-merge is disabled, and its draft-eligible checks are
  green. Ready-only full-quality and PR-evidence validation wait for the post-review transition.
- The project card was already `Reviewing` when the explicit handover command ran, so the production
  tool correctly refused to invent a `Reviewing → Reviewing` transition; the final board state is
  verified as `Reviewing`.
