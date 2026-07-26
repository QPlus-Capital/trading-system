# Evidence

## HEAD

HEAD: pre-implementation

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python scripts/quality/classify.py ...` | 0 | R3 as expected |
| `red-first` | pending | pending | pending |
| `format` | pending | pending | pending |
| `docs-consistency` | pending | pending | pending |
| `check` | pending | pending | pending |
| `impacted-tests` | pending | pending | pending |
| `property-tests-where-applicable` | pending | pending | pending |
| `integration-tests` | pending | pending | pending |
| `artifact-schema` | pending | pending | pending |
| `adversarial-review` | pending | pending | pending |
| `invariants` | pending | pending | pending |
| `mutation-on-touched-critical` | pending | pending | pending |
| `parity-where-applicable` | pending | pending | pending |
| `live-money-review` | pending | pending | pending |
| `human-decision-escalation` | pending | pending | pending |
| `no-autonomous-merge` | pending | pending | pending |
| `security` | pending | pending | pending |
| `impact` | pending | pending | pending |
| `pr-ready` | pending | pending | pending |

## Red-first proof

Pending execution against the pre-implementation state.

## Coverage and mutation

Pending.

## Deferred checks

None planned. P-11/#52 owns the new scenario breach gate; P-10 deliberately changes no threshold
or verdict criterion.
