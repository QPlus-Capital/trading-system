# Evidence

## HEAD

HEAD: 612303f1ff05c82cee2a884a97f92003d662442a

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: classified R3 because the SPA engine and Stage-2 selection gate govern methodology and result integrity |
| `red-first` | focused SPA and stage-path tests before implementation | 1 | RED: the pure suite failed collection because `research.engine.spa` did not exist; five stage tests then failed because no SPA artifact or fail-closed gate existed |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all nine changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 168 source files, vulture, and full pytest passed |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all 100 conservative impact-selected tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: all 14 deterministic properties passed twice with Hypothesis seed 20260721 |
| `integration-tests` | full pytest within `uvx --from rust-just just check` | 0 | GREEN: 901 passed; the sole local skip is the repository's Linux-only Mutmut execution on Windows |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-05` | 0 | GREEN: valid five-file task artifact with 11 acceptance criteria and 8 invariants |
| `adversarial-review` | `.ai/tasks/P-05/review.md` | 0 | GREEN: 14 counterexamples attempted; no unresolved finding |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: all 181 critical live, parity, sizing, research-integrity, registry, decision, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30160601449` | 0 | GREEN: weakened-test probe and ratchet passed; all 155 new SPA mutants were killed and the repository baseline is 1,781/2,066 killed with 285 unchanged classified survivors |
| `parity-where-applicable` | existing no-drift suites plus production-path scope audit | 0 | GREEN: P-01/P-03 return streams and all existing trading metrics are unchanged; P-05 adds only derived SPA evidence and gating |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | GREEN: no live, account, order, sizing, risk, broker, instrument, or signal path changed and no live system was invoked |
| `human-decision-escalation` | task-spec decision and open-question audit | 0 | GREEN: issue #47 fixes the estimator, recentering, bootstrap, seed, sensitivities, and threshold; Jan retains methodology and merge authority |
| `no-autonomous-merge` | branch and publication workflow audit | 0 | GREEN: ready pull request only; no merge or auto-merge action is permitted |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, dependency audit reports no known vulnerabilities, and high-signal Ruff security checks pass |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: R3; four direct research modules, six directly related test modules, three critical escalations, and no discovered unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-05 origin/main` | 0 | READY: valid task, declared/classified R3, every mandatory gate exits 0, and evidence covers the code HEAD |

## Red-first proof

Before production implementation, the pure SPA test run failed collection because
`research.engine.spa` did not exist. The collected stage-path run had five independent failures:
the edge stage did not publish lineage-bound SPA evidence, auto-selection did not fail closed on a
missing matrix or failed sensitivity, forced selection did not record an exploratory SPA failure,
and the cumulative verdict did not require SPA. These failures were observed before the
implementation made the same guards green.

## Numerical regression

No existing number changes. The implementation consumes the immutable P-03 daily net-R matrix,
writes only the new derived `spa.json`, and does not modify Stage-1 scoring, candidate ranking,
portfolio construction, or live execution. Existing research regression and stage tests pass; a
current run may newly fail auto-selection at the fixed SPA threshold, which is the intended gate
outcome rather than numerical drift.

## Coverage and mutation

The focused impact suite passed 100 tests. It covers correlated and independent null calibration,
power, consistent recentering versus Reality Check contamination, positive-scale invariance,
paired stationary-bootstrap indices, exact Decimal gate boundaries, deterministic output,
5/10/20/60 sensitivity, strict P-03 input validation, lineage-bound publication, missing and stale
artifacts, auto/forced selection, and the cumulative verdict path.

Linux Critical workflow run `30160601449` executed on the covered code HEAD. Its weakened-test probe
passed, all 155 mutants in the new `spa-family-gate` target were killed, and the ratchet matched the
measured repository baseline: 2,066 total, 1,781 killed, 285 previously classified survivors, and
no unhealthy outcome.

## Deferred checks

None.
