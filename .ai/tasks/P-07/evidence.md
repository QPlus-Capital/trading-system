# Evidence

## HEAD

HEAD: 8b5885dd2785ea556526d3fa62e4f39bfe6f9f91

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: classified R3 because MCS and the edge stage govern methodology and result integrity |
| `red-first` | focused MCS and stage-path tests before implementation | 1 | RED: two suites failed collection because `research.engine.mcs` did not exist; the independent edge-path test then failed because no `mcs.json` was published |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all seven changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 174 source files, Vulture, and full pytest passed |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all 148 conservative impact-selected tests passed after rebasing over P-06 |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: all 15 deterministic properties passed twice with Hypothesis seed 20260721 |
| `integration-tests` | full pytest within `uvx --from rust-just just check` | 0 | GREEN: 976 passed; the sole local skip is the repository's Linux-only Mutmut execution on Windows |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-07` | 0 | GREEN: valid five-file task artifact with 11 acceptance criteria and 8 invariants |
| `adversarial-review` | `.ai/tasks/P-07/review.md` | 0 | GREEN: 18 counterexamples attempted; three builder-review findings fixed; no unresolved finding |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: all 181 critical live, parity, sizing, research-integrity, registry, decision, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30173320379` | 0 | GREEN: merged P-06/P-07 ratchet passed; 2,207/2,498 unique mutants killed, with 291 fully classified survivors and no unhealthy outcome |
| `parity-where-applicable` | no-drift suite and artifact-nonconsumption test | 0 | GREEN: P-07 writes only derived MCS evidence; Stage 2 selection remains unchanged even when every fake membership flag is false |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | GREEN: no live, account, order, sizing, risk, broker, instrument, or signal path changed and no live system was invoked |
| `human-decision-escalation` | task-spec decision and open-question audit | 0 | GREEN: issue #49 fixes loss, statistic, resampling, confidence, elimination, persistence, and nonconsumption; Jan retains methodology and merge authority |
| `no-autonomous-merge` | branch and publication workflow audit | 0 | GREEN: ready pull request only; no merge or auto-merge action is permitted |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, dependency audit reports no known vulnerabilities, and high-signal Ruff security checks pass |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: R3; two production modules, seven directly related test modules, two critical escalations, and no discovered unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-07 origin/main` | 0 | READY: valid task, declared/classified R3, every mandatory gate exits 0, and evidence covers the code HEAD |

## Red-first proof

Before production implementation, the focused MCS and calibration suites failed collection twice
because `research.engine.mcs` did not exist. An independently collected edge-stage test then ran
through the existing SPA path and failed because `mcs.json` was absent. Those failures were
observed before the pure MCS engine, edge publication, and shared bootstrap helpers made the same
guards green.

## Numerical regression

P-07 is additive evidence only. It consumes the immutable P-03 daily net-R matrix and writes the
new lineage-bound `mcs.json`; it does not change Stage-1 scoring, SPA, DSR, PBO, ranking, selection,
portfolio construction, reporting, or live execution. The explicit nonconsumption test supplies an
MCS artifact with no eligible candidates and proves the existing Stage-2 choice is unchanged.

## Coverage and mutation

The focused impact suite passed 148 tests after rebasing over P-06. MCS-specific tests cover the independent pairwise
studentization oracle, current-family range statistic, coherent signed elimination, deterministic
ties and bootstrap draws, singleton and identical streams, exact 90% membership, monotone model
p-values, dominant-candidate power, true-best coverage, common-return-shift invariance, strict
serialization, lineage-bound publication, fail-closed stage errors, and P-08 nonconsumption.

Linux Critical workflow run `30173320379` executed on the covered P-06/P-07 code HEAD. Its
weakened-test probe and ratchet passed. The merged baseline has 2,498 unique mutants: 12 shared
SPA-helper mutants overlap across the packages and are counted once. The result is 2,207 killed,
291 fully classified survivors, and no unhealthy outcome.

## Deferred checks

None.
