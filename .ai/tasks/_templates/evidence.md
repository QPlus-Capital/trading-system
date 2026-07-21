# Evidence

## HEAD

HEAD: replace-with-tested-commit-sha

## Commands

| Command | Exit status | Result |
|---|---:|---|
| `replace with exact command` | 1 | RED: record the before-fix failure |
| `replace with exact command` | 0 | GREEN: record the after-fix result |

## Coverage and mutation

Record applicable coverage or mutation evidence, or a specific reason it is deferred.

## Deferred checks

List checks that require CI, production-like infrastructure, or a human decision; otherwise `None`.
