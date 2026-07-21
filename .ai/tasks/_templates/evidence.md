# Evidence

## HEAD

HEAD: replace-with-tested-commit-sha

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `replace with exact command` | 1 | RED: record the before-fix failure |
| `check` | `replace with exact command` | 0 | GREEN: required gate passed |

## Coverage and mutation

Record applicable coverage or mutation evidence, or a specific reason it is deferred.

## Deferred checks

List checks that require CI, production-like infrastructure, or a human decision; otherwise `None`.
