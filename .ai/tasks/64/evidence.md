# Evidence

## HEAD

HEAD: dfa70635e4ca3c6599991cd1a59cdf899bbc9a76

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | initial focused collection | 1 | RED: three new modules absent |
| `red-first` | adversarial validator bypass cases | 1 | RED: empty sections and command evidence passed |
| `red-first` | repository-wide format check | 1 | RED: 42 untouched baseline files failed |
| `red-first` | impact determinism test | 1 | RED: path order changed the JSON |
| `red-first` | F1/F2/F3 review guards before fixes | 1 | RED: four selected counterexamples failed as expected |
| `format` | `just check-fast origin/main` (changed-file format phase) | 0 | Six changed Python files formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py` | 0 | 56 passed |
| `check` | `just check` via `uvx rust-just` | 0 | Ruff, mypy, 618 tests, and vulture passed |
| `impacted-tests` | `just check-fast origin/main` via `uvx rust-just` | 0 | 40 focused tests passed |
| `property-tests-where-applicable` | applicability review | 0 | No numerical/stateful property target in workflow parsing |
| `integration-tests` | `uv run pytest -q` | 0 | 618 passed; 86 pre-existing warnings tracked in #68 |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 64` | 0 | Four ACs and four INVs valid |
| `adversarial-review` | Claude adversarial review on PR #69 | 0 | F1-P1, F2-P2, and F3-P3 attempted and dispositioned |
| `invariants` | focused validator, impact, and readiness suite | 0 | 40 tests passed |
| `mutation-on-touched-critical` | deferred to workflow issue #65 | 1 | BLOCKED: no mutation runner; the stub is not evidence of success |
| `parity-where-applicable` | applicability review | 0 | No signal, backtest, or live adapter changed |
| `live-money-review` | live-path scope review | 0 | No live-money module changed; quality-gate semantics reviewed as R3 |
| `human-decision-escalation` | Jan's issue #64 and PR #69 scope decisions | 0 | Scope and no-merge decision remain human-owned |
| `no-autonomous-merge` | `gh pr view 69 --json isDraft,state` | 0 | PR remains open, draft, and unmerged |
| `readiness-audit` | `uv run python -m scripts.quality.pr_ready 64 --base origin/main` | 1 | Expected NOT READY: mutation gate is non-zero; every other readiness check passed |

## Coverage and mutation

Behavioural coverage includes malformed task artifacts, missing and failed cumulative gates, a
clean full R3 gate run, empty/zero-counterexample R3 reviews, direct/transitive/inheritance/dynamic
impact edges, ignored-artifact enforcement, stale SHA, and the evidence-only commit rule. No
mutation pass is claimed.

## Deferred checks

- Mutation testing remains blocked on workflow issue #65; therefore the real R3 task is NOT READY.
- Dedicated security scanning remains a later workflow PR per issue scope.
- Claude re-review of the F1/F2/F3 fixes is pending on PR #69.
