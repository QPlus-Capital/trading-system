# Evidence

## HEAD

HEAD: 58d424db2a0cb7397eae23bbf4b653986d46b084

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: classified R3 with all 14 mandatory gates; six Stage-1/result-integrity production files changed |
| `red-first` | `uv run pytest -q tests/test_research_candidate_artifacts.py` before implementation | 1 | RED: all 10 focused tests failed because the canonical payload and four artifacts did not exist |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all nine changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 165 files, vulture, and full pytest passed |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all 279 conservative direct and transitive impact-selected tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: 13 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `uvx --from rust-just just check` | 0 | GREEN: 871 passed; the sole local skip is the repository's Linux-only Mutmut execution on Windows |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-03` | 0 | GREEN: valid P-03 task artifact with 12 acceptance criteria and 8 invariants |
| `adversarial-review` | `.ai/tasks/P-03/review.md` | 0 | GREEN: 12 counterexamples attempted; no unresolved finding |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: all 178 critical live, parity, sizing, research-integrity, registry, decision, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30156890398` | 0 | GREEN: weakened-test probe and ratchet passed; 1,626/1,911 mutants killed, 285 allowed survivors, and no unhealthy outcome |
| `parity-where-applicable` | zero-threshold `research.regression` self-comparison of `run_20260724_1146` | 0 | GREEN: 1348 to 1348 trades, 40.6% to 40.6% annual return, zero drift in every bounded metric, and byte-identical `full_history_trades.csv` |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | GREEN: no live, account, order, sizing, risk, broker, or signal path changed and no live system was invoked |
| `human-decision-escalation` | task-spec human-decision and open-question audit | 0 | GREEN: all methodology choices were fixed by issue #45; Jan retains merge authority and no unresolved choice was guessed |
| `no-autonomous-merge` | branch and publication workflow audit | 0 | GREEN: ready PR only; no merge or auto-merge action is permitted |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, dependency audit reports no known vulnerabilities, and high-signal Ruff security checks pass |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: R3; six direct research modules, conservative focused tests, one critical escalation, and no discovered unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-03 origin/main` | 0 | READY: valid task, declared/classified R3, all 14 required gates exit 0, and evidence current for code HEAD |

## Red-first proof

The first focused run collected ten guards and all ten failed before production implementation.
The missing candidate module, canonical chosen-path payload, exact aggregations, hashes,
provenance, immutable edge publication, and no-drift hook were therefore each observed red before
the implementation made them green.

## Regression

`research.regression` compared `run_20260724_1146` with itself using zero trade-count and
annual-return tolerances. It reported "Every change is inside the announced range": 1348 to 1348
trades, 40.6% to 40.6% annual return, -4.14% to -4.14% max drawdown, and 60.8% to 60.8% total
return. The invariant `full_history_trades.csv` is byte-identical.

## Coverage and mutation

The focused P-03, Stage-1 swap, and lineage suite passed 64 tests. It covers formal candidate
identity, the Chicago loss-day boundary, zero days, exact Decimal equality, missing-market
omission, P-04 input shape, lineage drift, canonical P-01 event reuse, timestamp validation,
existing-metric immutability, optional/partial provenance, and byte-exact edge publication.

Three new `window_returns` guards were run against the exact generated mutants before the baseline
was changed: `_18` failed on a losing close at the inner boundary, `_20` failed on positive
fractional opening equity, and `_22` failed on the corrupted post-ruin diagnostic. Linux Critical
run `30156890398` then measured 1,911 mutants, killed 1,626, retained 285 classified survivors,
reported zero unhealthy outcomes, and passed the tightened ratchet. The guards also killed all
five previously allowed `window_returns` survivors, so that function now has no survivor allowlist.

## Deferred checks

None.
