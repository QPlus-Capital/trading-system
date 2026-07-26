# Evidence

## HEAD

HEAD: d1752ffbf02bc28958a28ac3f1ef2aa804a7d5a3

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | R3: selection methodology, result-integrity evidence, configuration, and verdict paths changed |
| `red-first` | inline pre-P-08 return-first/no-eligibility stub against the two focused P-08 guards | 1 | RED as required: SPA failure did not raise `NoAutomaticSelection`; the tie-break selected `baseline` instead of complexity-first `no_bb` |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | 13 changed files already formatted |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_docs_architecture_map.py tests/test_docs_language.py` | 0 | 132 passed |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 175 files, Vulture, and pytest passed; 1,049 passed, 1 platform-skipped |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | 275 focused tests passed; Ruff and mypy passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 17 properties passed twice with seed `20260721` |
| `integration-tests` | full `uv run pytest -q` executed by `just check` | 0 | 1,045 passed, including the real Stage-2, MCS, and lineage integration paths |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-08` | 0 | `Task P-08: valid (13 AC, 9 INV)` |
| `adversarial-review` | `.ai/tasks/P-08/review.md`, schema-checked by `validate_task P-08` | 0 | 20 selection counterexamples plus the exact MCS and resampler dtype equivalences were reviewed; F1/F2/F3 resolved and no P0-P3 builder finding remains |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 181 passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30206406306` on `50d3b7b88f309a86bb98034e2b113b252729e763` | 0 | GREEN: weakened-test probe and exact ratchet passed; 2,828/3,145 killed, 317 exactly classified survivors, and no unhealthy outcome |
| `resample-equivalence` | `uv run pytest -q tests/test_research_resample.py tests/test_research_resample_properties.py tests/test_research_resample_calibration.py` | 0 | 45 passed; fixed-seed determinism and P-04 calibration stayed green, and float64 output is byte-identical to the removed return cast for list/int32/float32/float64 inputs |
| `parity-where-applicable` | forced-selection integration test, Stage-3 producer diff, and zero-threshold `research.regression` self-comparison of `run_20260724_1146` | 0 | Forced `--variation` remained exploratory and bypassed automatic evidence; Stage-3/trade producers matched main; 1,348→1,348 trades, 40.6%→40.6%, and `full_history_trades.csv` remained byte-identical at SHA-256 `27592D20DDA0FB3B31EB06DE69D4D760D0F16CD961F2872E4F6376ACB3DD90DC` |
| `live-money-review` | `git diff --quiet origin/main...HEAD -- research/stages/portfolio.py research/portfolio research/engine/walkforward.py research/engine/walkforward_runner.py research/engine/continuous.py core live` | 0 | No live, signal, order, sizing, risk, Stage-3, or historical-trade producer changed |
| `human-decision-escalation` | exact config and focused P-08 tests | 0 | Jan's twelve approved `COMPLEXITY_SCORES` are present exactly; no methodology question remains open |
| `no-autonomous-merge` | branch/PR state audit | 0 | Feature branch and human-reviewed PR workflow only; merge and auto-merge remain disabled |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and static security checks passed |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; nine production files, twenty-two directly related test files, four critical escalations, no unknown/dynamic edge discovered |
| `pr-ready` | `uvx --from rust-just just pr-ready P-08 origin/main` | 0 | READY: task, R3 classification, every required gate, and evidence currency passed |

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

The P-08 focused suite has 65 passing tests and the full suite has 1,049 passing tests. Exact
inspection showed that MCS `range_decision mutmut_49` removed only the explicit integer dtype from
a validated integer array used exclusively for indexing. A behavioural test proves identical
statistics, p-values, and elimination decisions for inferred and explicit `int64` indexing across
active subsets, order permutations, and the tie boundary. The redundant MCS dtype expressions were
removed at source, eliminating nine equivalent Mutmut candidates without changing MCS output.

The remaining `stationary_bootstrap mutmut_64` diagnosis is candidate (a): a true no-op whose
alternating killed/survived label came from unrelated per-mutant pytest instability under parallel
runner load, not from nondeterministic resampling. `_validated_returns` always materializes a
float64 array and integer fancy indexing preserves that dtype; Hypothesis is derandomized and every
resample/calibration fixture uses a fixed seed. Mutmut does not retain the identity of the unrelated
foreign test that produced its intermittent non-zero exit, but the mutant itself cannot change the
test process semantically. The redundant return cast was therefore removed at source. The focused
45-test run proves float64 output and byte identity with the former cast across list, int32,
float32, and float64 inputs; it also keeps fixed-seed determinism and P-04 calibration green.

Linux Critical mutation workflow `30206406306` passed independently on the root-cause commit:
2,828 of 3,145 selected mutants were killed, all 317 survivors matched their exact classifications,
and no no-test, timeout, suspicious, skipped, or unchecked outcome occurred. The weakened-test
probe also passed. Four redundant resampler wrapper candidates, including `mutmut_64`, no longer
exist; no tolerance or survivor classification was added, and the exact ratchet was not weakened.

## Deferred checks

None.
