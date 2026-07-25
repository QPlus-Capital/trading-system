# Evidence

## HEAD

HEAD: a87e5947cd69081231521e51c8fdaa8b00866ec3

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: classified R3 because the Romano-Wolf engine and edge-stage evidence govern methodology and result integrity |
| `red-first` | focused Romano-Wolf and stage-path tests before implementation | 1 | RED: the pure suite failed collection because `research.engine.romano_wolf` did not exist; the independent stage test then failed because `romano_wolf.json` was not published |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all seven changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 171 source files, vulture, and full pytest passed |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all 130 conservative impact-selected tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: all 15 deterministic properties passed twice with Hypothesis seed 20260721 |
| `integration-tests` | full pytest within `uvx --from rust-just just check` | 0 | GREEN: 933 passed; the sole local skip is the repository's Linux-only Mutmut execution on Windows |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-06` | 0 | GREEN: valid five-file task artifact with 11 acceptance criteria and 8 invariants |
| `adversarial-review` | `.ai/tasks/P-06/review.md` | 0 | GREEN: 16 counterexamples attempted; three builder-review weaknesses resolved and no finding remains |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: all 181 critical live, parity, sizing, research-integrity, registry, decision, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30165472874` | 0 | GREEN: weakened-test probe and ratchet passed; all 112 added P-06/shared-helper mutants were killed and the repository baseline is 1,893/2,178 killed with 285 unchanged classified survivors |
| `parity-where-applicable` | existing no-drift suites plus SPA reference-oracle and Stage-2 scope audits | 0 | GREEN: P-05 SPA output is bit-identical, an all-ineligible Romano-Wolf artifact does not affect selection, and no existing selection or portfolio number changes |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py research/stages/select.py` | 0 | GREEN: no live, account, order, sizing, risk, broker, instrument, signal, or selection-consumer path changed and no live system was invoked |
| `human-decision-escalation` | task-spec decision and open-question audit | 0 | GREEN: issue #48 fixes the hypotheses, statistic, bootstrap, stepdown rule, adjusted-p threshold, and additive boundary; Jan retains methodology and merge authority |
| `no-autonomous-merge` | branch and publication workflow audit | 0 | GREEN: ready pull request only; no merge or auto-merge action is permitted |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, dependency audit reports no known vulnerabilities, and high-signal Ruff security checks pass |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: R3; three direct research modules, eight directly related test modules, three critical escalations, and no discovered unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-06 origin/main` | 0 | READY: valid task, declared/classified R3, every mandatory gate exits 0, and evidence covers the code HEAD |

## Red-first proof

Before production implementation, the pure Romano-Wolf test run failed collection because
`research.engine.romano_wolf` did not exist. A separately collected edge-stage test failed with
`FileNotFoundError` because the stage did not publish `romano_wolf.json`. These independent
failures were observed before implementation made the same behavioural guards green.

## Numerical regression

No existing number changes. P-06 consumes the immutable P-03 daily net-R matrix, reuses P-05's
studentization and P-04's stationary-bootstrap draw, and writes only the new derived
`romano_wolf.json`. It does not modify Stage-1 scoring, ranking, Stage-2 selection consumption,
portfolio construction, or live execution. A fixed-family oracle produced a bit-identical P-05
SPA dictionary before and after the helper extraction, and an integration guard proves that even
an all-ineligible Romano-Wolf artifact does not yet change Stage-2 selection. P-08 is the explicit
future consumer.

## Coverage and mutation

The focused impact suite passed 130 tests. It covers the 36-candidate correlated global-null
calibration (10/200 families rejected, exactly 5.0%, inside the predeclared 2%-8% interval),
ordered adjusted-p monotonicity, adjusted p-values dominating marginal p-values, one strong edge,
two correlated edges recovered where single-step misses the weaker edge, exact statistic ties,
Decimal eligibility boundaries, malformed artifacts, fixed-seed determinism, shared P-05/P-06
stationary-bootstrap index draws, lineage-bound edge publication, and additive non-consumption.

Linux Critical workflow run `30165472874` executed against the committed ratchet. Its weakened-test
probe passed, all 112 newly added mutants in the Romano-Wolf and shared studentization targets were
killed, and the measured repository baseline matched exactly: 2,178 total, 1,893 killed, 285
previously classified survivors, and no unhealthy outcome.

## Deferred checks

None.
