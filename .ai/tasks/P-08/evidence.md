# Evidence

## HEAD

HEAD: pending

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | explicit planned-path `scripts.quality.classify` invocation | 0 | R3: selection methodology, config, lineage, and verdict integrity |
| `red-first` | P-08 focused tests before implementation | pending | Blocked by the missing pre-registered complexity mapping |
| `format` | `uvx --from rust-just just check-fast origin/main` | pending | Pending |
| `docs-consistency` | focused documentation and gate-consistency tests | pending | Pending |
| `check` | `uvx --from rust-just just check` | pending | Pending |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | pending | Pending |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | pending | Pending |
| `integration-tests` | full pytest within `just check` | pending | Pending |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-08` | pending | Pending |
| `adversarial-review` | `.ai/tasks/P-08/review.md` | pending | Pending |
| `invariants` | `uvx --from rust-just just check-invariants` | pending | Pending |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | pending | Pending |
| `parity-where-applicable` | historical-return and forced-path no-drift audit | pending | Pending |
| `live-money-review` | live/signal/risk scope diff audit | pending | Pending |
| `human-decision-escalation` | task-spec decision audit | pending | BLOCKED: complexity mapping absent |
| `no-autonomous-merge` | branch and publication audit | pending | Pending |
| `security` | `uvx --from rust-just just check-security` | pending | Pending |
| `impact` | `uvx --from rust-just just impact origin/main` | pending | Pending |
| `pr-ready` | `uvx --from rust-just just pr-ready P-08 origin/main` | pending | Pending |

## Red-first proof

Not started. The required tie-break oracle would invent the methodology answer if written before
Jan fixes the pre-registered complexity scores.

## Numerical regression

Expected historical trade/return effect is exactly none. Diagnostic values and automatic selection
may change by design.

## Coverage and mutation

Pending implementation after the human decision.

## Deferred checks

All implementation and readiness gates are deferred solely on the missing complexity mapping and
scope.
