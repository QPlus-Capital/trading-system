# Evidence

## HEAD

HEAD: 16f3c2ea667f4006db2c2e9ef40357051f639c6d

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_monitoring_dashboard_copy.py` | 1 | RED: rendered English risk label caused `StopIteration`; 1 failed |
| `red-first` | first full `just check` after German runtime literals | 1 | RED: legacy blanket-English guard rejected the constitution's dashboard exception |
| `format` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` | 0 | GREEN: 3 changed Python files already formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_language.py tests/test_engineering_docs.py` | 0 | GREEN: 121 language, constitution, and role-contract tests passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check` | 0 | GREEN: Ruff, strict mypy over 151 files, vulture, and 719 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` | 0 | GREEN: both directly related language/dashboard suites passed; 65 tests |
| `property-tests-where-applicable` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-properties` | 0 | GREEN: 8 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 719 passed with no live runner or account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-15` | 0 | GREEN: valid task with 5 acceptance criteria and 4 invariants |
| `adversarial-review` | `.ai/tasks/P-15/review.md` plus normalized-string AST/forbidden-path audits | 0 | GREEN: 7 counterexamples attempted; no unresolved finding |
| `impact` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile impact origin/main` | 0 | GREEN: R2, one production file, two direct tests, no transitive/escalated/dynamic edge |

## Coverage and mutation

The behavioral guard invokes `_live_view` with in-memory data and captures rendered Streamlit
calls. It covers determinate and indeterminate open risk, the blocked-risk error, incomplete and
hidden history, no closed trades, and no open positions while preserving interpolated values. Its
import bridge and the repository's autouse MT5 boundary prevent terminal access.

The language guard excludes German only inside direct `st.caption`, `st.error`, `st.info`,
`st.warning`, and column `metric` arguments in `monitoring/dashboard.py`. Synthetic counterexamples
prove that German in a source comment or `log.warning` remains visible to the ratchet. An AST
comparison against `origin/main`, after normalizing string values, is identical; production logic
and structure did not change. Mutation testing is not required for R2 and no mutation target changed.

`just impact` identifies exactly `monitoring/dashboard.py` and the two focused tests, with no
transitive test, critical escalation, unknown/dynamic edge, or additional possible test. The
forbidden-path diff confirms no governance, `research/stages/**`, core, research, or live file
changed. No reported number can move.

## Deferred checks

Claude's independent pull-request review is intentionally deferred to the PR review phase. No
implementation or required R2 gate is deferred.
