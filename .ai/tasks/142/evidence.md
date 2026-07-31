# Evidence

## HEAD

HEAD: 90fdb041b7fc465c3d63d8a83b939c870e0b623a

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | six focused issue-142 mutation-policy and workflow tests against unchanged policy | 1 | RED: 6 failed; the board target, selector result, Mutmut path/test selection, baseline target, target-specific ratchet case, and production workflow predicate were all absent. |

## Coverage and mutation

The native Linux board survivor report is pending. No hand-built approximation will be recorded as
the baseline.

## Deferred checks

- Policy implementation, native Linux mutation, survivor classification, full R3 gates, and
  independent review are pending.
