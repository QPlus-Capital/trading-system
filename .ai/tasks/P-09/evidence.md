# Evidence

## HEAD

HEAD: pending

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | planned-path `scripts.quality.classify` invocation | 0 | R3 |
| `red-first` | focused P-09 tests against pre-implementation code | pending | pending |
| `format` | `uvx --from rust-just just check-fast origin/main` | pending | pending |
| `docs-consistency` | focused engineering documentation tests | pending | pending |
| `check` | `uvx --from rust-just just check` | pending | pending |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | pending | pending |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | pending | pending |
| `integration-tests` | real Stage-3/4 fixture and full pytest | pending | pending |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-09` | pending | pending |
| `adversarial-review` | `.ai/tasks/P-09/review.md` | pending | pending |
| `invariants` | `uvx --from rust-just just check-invariants` | pending | pending |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | pending | pending |
| `parity-where-applicable` | exact Stage-3/4 regression | pending | pending |
| `live-money-review` | production-scope diff and review | pending | pending |
| `human-decision-escalation` | spec decision audit | pending | pending |
| `no-autonomous-merge` | branch/PR state audit | pending | pending |
| `security` | `uvx --from rust-just just check-security` | pending | pending |
| `impact` | `uvx --from rust-just just impact origin/main` | pending | pending |
| `pr-ready` | `uvx --from rust-just just pr-ready P-09 origin/main` | pending | pending |

## Red-first proof

Pending.

## Numerical regression

Pending.

## Coverage and mutation

Pending.

## Deferred checks

None.
