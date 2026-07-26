# Evidence

## HEAD

HEAD: 754f7e2b046ba34b1de2627b59a4aac8e4c1f33d

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | R3: selection methodology, result-integrity evidence, configuration, and verdict paths changed |
| `red-first` | inline pre-P-08 return-first/no-eligibility stub against the two focused P-08 guards | 1 | RED as required: SPA failure did not raise `NoAutomaticSelection`; the tie-break selected `baseline` instead of complexity-first `no_bb` |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | 13 changed files already formatted |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_docs_architecture_map.py tests/test_docs_language.py` | 0 | 132 passed |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, mypy, Vulture, and pytest passed; 1,041 passed, 1 platform-skipped |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | 275 focused tests passed; Ruff and mypy passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 17 properties passed twice with seed `20260721` |
| `integration-tests` | full `uv run pytest -q` executed by `just check` | 0 | 1,041 passed, including the real Stage-2 and lineage integration paths |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-08` | 0 | `Task P-08: valid (13 AC, 9 INV)` |
| `adversarial-review` | `.ai/tasks/P-08/review.md`, schema-checked by `validate_task P-08` | 0 | 20 counterexamples attempted; F1 resolved by Jan's exact complexity mapping; no unresolved P0-P3 builder finding |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 181 passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30197181802` | 1 | FAILED: 2,836/3,158 killed and 322 survived; unexpected equivalent MCS `range_decision mutmut_49`, while baseline-equivalent `pairwise_scores mutmut_5` and `_10` were killed |
| `parity-where-applicable` | forced-selection integration test, Stage-3 producer diff, and zero-threshold `research.regression` self-comparison of `run_20260724_1146` | 0 | Forced `--variation` remained exploratory and bypassed automatic evidence; Stage-3/trade producers matched main; 1,348→1,348 trades, 40.6%→40.6%, and `full_history_trades.csv` remained byte-identical at SHA-256 `27592D20DDA0FB3B31EB06DE69D4D760D0F16CD961F2872E4F6376ACB3DD90DC` |
| `live-money-review` | `git diff --quiet origin/main...HEAD -- research/stages/portfolio.py research/portfolio research/engine/walkforward.py research/engine/walkforward_runner.py research/engine/continuous.py core live` | 0 | No live, signal, order, sizing, risk, Stage-3, or historical-trade producer changed |
| `human-decision-escalation` | exact config and focused P-08 tests | 0 | Jan's twelve approved `COMPLEXITY_SCORES` are present exactly; no methodology question remains open |
| `no-autonomous-merge` | branch/PR state audit | 0 | Feature branch only; no PR, merge, or auto-merge exists |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and static security checks passed |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; seven production files, fifteen directly related test files, three critical escalations, no unknown/dynamic edge discovered |
| `pr-ready` | `uvx --from rust-just just pr-ready P-08 origin/main` | 1 | NOT READY because the required Linux Critical mutation gate has exit 1 |

## Red-first proof

The focused oracle was executed against an inline pre-P-08 stub that reproduced the old unsafe
shape: it ignored SPA/eligibility and always returned the high-return `baseline` candidate. The
command exited 1 with both intended failures:

- `test_spa_failure_blocks_selection_despite_diagnostics_and_returns`: `DID NOT RAISE
  NoAutomaticSelection`;
- `test_tie_break_order_is_complexity_then_return_then_train_then_name`: assertion failure because
  `baseline` was returned instead of complexity-first `no_bb`.

The unmodified production implementation then passed all 65 tests in
`tests/test_research_selection_protocol.py`.

## Numerical regression

Expected historical trade/return effect is exactly none. The explicit parity audit used the
completed Main-lineage baseline `run_20260724_1146` with zero tolerances. It reported 1,348 to
1,348 trades, annual return 40.6% to 40.6%, no bounded metric drift, and byte identity for
`full_history_trades.csv`. The branch changes no Stage-3 or trade-producing source relative to
`origin/main`.

Diagnostic values and automatic selection may change by design. No threshold was relaxed and no
historical figure moved.

## Coverage and mutation

The P-08 focused suite has 65 passing tests and the full suite has 1,041 passing tests. The Linux
Critical mutation run `30197181802` failed its exact-survivor ratchet despite killing 2,836 of
3,158 selected mutants. The reported differences are pre-existing equivalent NumPy-expression
mutants in P-07's MCS implementation, not P-08 selection survivors. Issue #89 tracks the
nondeterministic equivalent-mutant status. The baseline and gate were not weakened.

## Deferred checks

Readiness and PR publication are blocked on a real exit-0 Linux Critical mutation run. No other
validation is deferred.
