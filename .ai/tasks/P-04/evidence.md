# Evidence

## HEAD

HEAD: 2fcce0bc906ac155ba26c0171ed040f7697d7fce

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | focused resampling tests before the module existed | 1 | RED at collection: 2 missing-module errors |
| `red-first` | focused resampling tests against explicit stubs | 1 | RED: all 29 contracted tests failed with `NotImplementedError` |
| `red-first` | first separated-RNG AR(1) calibration | 1 | RED: 92.6% coverage missed the 95% +/- 2% acceptance band; the test harness's coupled RNG streams were separated |
| `red-first` | Linux Critical mutation workflow run `29923866491` | 1 | RED: 56 unexplained new survivors proved the original focused suite was insufficient |
| `format` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` | 0 | GREEN: 4 Python files formatted; Ruff and strict mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py` | 0 | GREEN: the architecture module-map guard passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check` | 0 | GREEN: Ruff, mypy over 154 files, vulture, and 760 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` | 0 | GREEN: impact selected all 3 resampling suites; 41 focused tests passed |
| `property-tests-where-applicable` | generic and resampling Hypothesis suites, each replayed twice with seed `20260721` | 0 | GREEN: 8 generic and 2 resampling properties passed on both deterministic replays |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 760 passed with no trading runner or account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-04` | 0 | GREEN: valid task with 8 acceptance criteria and 5 invariants |
| `adversarial-review` | `.ai/tasks/P-04/review.md` | 0 | GREEN: 7 counterexamples attempted; no unresolved finding |
| `invariants` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-invariants` | 0 | GREEN: 129 critical live-risk, parity, sizing, research-integrity, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29925803353` | 0 | GREEN: weakened-test probe and complete ratchet passed; 842/1,049 killed and all 207 survivors exact-name classified |
| `parity-where-applicable` | forbidden-path diff audit against `origin/main` | 0 | GREEN: no strategy signal, live, monitoring, Monte Carlo, lineage, or stage path changed |
| `live-money-review` | changed-path and import-consumer audit | 0 | GREEN: additive research utility has no consumer; no live path or live process was touched |
| `human-decision-escalation` | P-04 spec and issue build contract | 0 | GREEN: Jan retains methodology, scope, risk, and merge authority; no open human decision remains |
| `no-autonomous-merge` | branch and PR workflow audit | 0 | GREEN: no merge or auto-merge action was performed or configured |
| `security` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-security` | 0 | GREEN: secret scan, dependency audit, and static security checks passed |

## Coverage and mutation

The synthetic-null suite ran 1,000 experiments with 299 bootstrap replications for both IID and
AR(1) coverage. The fixed AR(1) estimator reference is `5.085266752079944`; the selected white-noise
length remains between 1 and 3. The first Linux measurement found 56 unexplained survivors. Added
boundary and deterministic-path tests killed 38 of them. Final Linux run `29925803353` passed at
842/1,049 killed (80.3%), with 11 new exact equivalences and 7 conservatively retained
floating-point boundary gaps. It covered code commit `b5933d970b8e664914d25f7b963be01363448701`;
the recorded HEAD differs only by this task's review and test-plan documentation.

`just impact` classifies the change R3 and identifies exactly the 3 resampling suites as direct
tests, with no transitive test, critical escalation, or dynamic edge. Repository search found no
consumer of the new API. No reported result can move in this additive package.

## Deferred checks

Claude's independent pull-request review is intentionally deferred to the PR review phase. No
implementation or gate check is deferred.
