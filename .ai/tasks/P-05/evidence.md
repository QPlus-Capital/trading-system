# Evidence

## HEAD

HEAD: pending

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | planned-path `scripts.quality.classify` invocation | 0 | R3: selection, methodology, lineage, and critical quality paths |
| `red-first` | focused tests before implementation | pending | Pending |
| `format` | `uvx --from rust-just just check-fast origin/main` | pending | Pending |
| `docs-consistency` | focused documentation and gate-consistency tests | pending | Pending |
| `check` | `uvx --from rust-just just check` | pending | Pending |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | pending | Pending |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | pending | Pending |
| `integration-tests` | full pytest within `just check` | pending | Pending |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-05` | pending | Pending |
| `adversarial-review` | `.ai/tasks/P-05/review.md` | pending | Pending |
| `invariants` | `uvx --from rust-just just check-invariants` | pending | Pending |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | pending | Pending |
| `parity-where-applicable` | no-drift suite and scope audit | pending | Pending |
| `live-money-review` | live/signal/risk scope diff audit | pending | Pending |
| `human-decision-escalation` | task-spec decision audit | pending | Pending |
| `no-autonomous-merge` | branch and publication audit | pending | Pending |
| `security` | `uvx --from rust-just just check-security` | pending | Pending |
| `impact` | `uvx --from rust-just just impact origin/main` | pending | Pending |
| `pr-ready` | `uvx --from rust-just just pr-ready P-05 origin/main` | pending | Pending |

## Red-first proof

Pending.

## Numerical regression

No existing number may change. P-05 adds only SPA evidence and a selection gate; focused and
existing regression guards will verify the boundary.

## Coverage and mutation

Pending focused coverage and Linux critical-mutation evidence.

## Deferred checks

Linux mutation execution remains pending until the implementation and mutation scope exist.
