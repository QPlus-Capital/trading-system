# Evidence

## HEAD

HEAD: 3150515fc547930da4bb52ce0c988c8aacf24107

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_monitoring_dashboard_copy.py` | 1 | RED: rendered English risk label caused `StopIteration`; 1 failed |
| `red-first` | first full `just check` after German runtime literals | 1 | RED: legacy blanket-English guard rejected the constitution's dashboard exception |
| `format` | `just check-fast origin/main` | 0 | GREEN: all three changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_docs_language.py tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py` | 0 | GREEN: 128 architecture, language, constitution, and workflow-document tests passed |
| `check` | `uvx --from rust-just just check` with Git Bash on `PATH` | 0 | GREEN: Ruff, strict mypy over 161 files, vulture, and 846 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `just check-fast origin/main` | 0 | GREEN: all 85 direct post-P-14 dashboard and language tests passed after format, lint, and types |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: 13 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 846 passed with no live runner or account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-15` | 0 | GREEN: valid task with 5 acceptance criteria and 4 invariants |
| `adversarial-review` | `.ai/tasks/P-15/review.md` plus normalized-string AST/forbidden-path audits | 0 | GREEN: 11 counterexamples attempted; no unresolved finding |
| `impact` | `just impact origin/main` | 0 | GREEN: R2, one production file, three direct tests, no transitive/escalated/dynamic edge |
| `merge-main` | normalized-string AST comparison and shared-config diff against `origin/main` | 0 | GREEN: dashboard executable structure equals post-P-14 main; shared config and architecture/testing docs equal main byte-for-byte |
| `pr-ready` | `just pr-ready P-15 origin/main` | 0 | GREEN: valid R2 task, all eight required gates exit 0, and evidence is current |

## Coverage and mutation

The behavioral guard invokes post-P-14 `_live_view` with in-memory data and captures rendered
Streamlit calls. It covers determinate and indeterminate open risk, the blocked-risk error,
English exception-payload preservation, incomplete and hidden history, no closed trades, every
account/risk/floor metric, and no open positions while preserving interpolated values. Its import
bridge and the repository's autouse MT5 boundary prevent terminal access.

The language guard excludes German only inside direct `st.caption`, `st.error`, `st.info`,
`st.warning`, and column `metric` arguments in `monitoring/dashboard.py`. The copy guard
exact-ratchets every scoped post-P-14 literal, including metric labels, help, and deltas. Synthetic
counterexamples prove that German in a source comment, `log.warning`, or raised exception remains
visible to the ratchet. An AST comparison against post-P-14 `origin/main`, after normalizing string
values, is identical; production logic and structure did not change. Mutation testing is not
required for R2 and no mutation target changed.

`just impact` identifies exactly `monitoring/dashboard.py` and the three focused tests, with no
transitive test, critical escalation, unknown/dynamic edge, or additional possible test. The
forbidden-path diff confirms shared config and architecture/testing documentation equal main, and
no `research/stages/**`, core, research, live, or non-dashboard monitoring logic changed. No
reported number can move.

## Deferred checks

Claude's independent pull-request review is intentionally deferred to the PR review phase. No
implementation or required R2 gate is deferred.
