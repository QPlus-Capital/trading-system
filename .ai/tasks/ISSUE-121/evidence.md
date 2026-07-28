# Evidence

## HEAD

HEAD: pending

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | pending | 1 | Not run. |
| `docs-consistency` | pending | 1 | Not run. |
| `check` | pending | 1 | Not run. |
| `impacted-tests` | pending | 1 | Not run. |
| `property-tests-where-applicable` | pending | 1 | Not run. |
| `integration-tests` | pending | 1 | Not run. |
| `artifact-schema` | pending | 1 | Not run. |
| `adversarial-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | Pending independent review. |
| `invariants` | pending | 1 | Not run. |
| `mutation-on-touched-critical` | pending | 1 | Not run. |
| `parity-where-applicable` | pending | 1 | Not run. |
| `live-money-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | Pending independent review. |
| `human-decision-escalation` | `.ai/tasks/ISSUE-121/spec.md` | 0 | Jan's decisions and merge authority are explicit. |
| `no-autonomous-merge` | requested draft-only delivery | 0 | No ready, merge, or auto-merge action is authorized. |

## Red-first proof

Pending.

## Impact

Pending.

## Security summary

Pending.

## Coverage and mutation

Focused behavioral coverage is implemented; full suite and Linux mutation results are pending.

## Live safety attestation

No real MT5 or runner interaction is permitted. All verification will use fakes.

## Deferred checks

Independent adversarial and live-money review remain deferred to Claude after the draft PR exists.
