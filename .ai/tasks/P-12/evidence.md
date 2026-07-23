# Evidence

## HEAD

Pending final implementation commit.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | explicit intended-path classifier | 0 | R3 after the required mutation-policy path; semantic R3 upgrade recorded |
| `red-first` | focused registry + property tests against importable stubs | 1 | RED: all 11 new guards failed at their target operation |
| `red-first` | Decimal-artifact guard against first implementation | 1 | RED: a JSON float was accepted until the read path was tightened |
| `check` | `just check` | pending | required |
| `invariants` | `just check-invariants` plus registry invariant suite | pending | required |
| `mutation-on-touched-critical` | Linux mutation workflow | pending | required |
| `parity-where-applicable` | changed-path and number-impact audit | pending | required |
| `adversarial-review` | `.ai/tasks/P-12/review.md` | pending | required |
| `live-money-review` | registry security and no-live-path audit | pending | required |
| `human-decision-escalation` | open-question and authority audit | pending | required |
| `no-autonomous-merge` | branch/PR settings audit | pending | required |

## Coverage and mutation

Pending red-first, property, and Linux mutation evidence.

## Deferred checks

None at specification time.
