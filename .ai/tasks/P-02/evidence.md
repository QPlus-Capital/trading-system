# Evidence

## HEAD

HEAD: replace-with-tested-commit-sha

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | intended-path classifier | 0 | R3 for both training-selector production paths |

## Coverage

Pending red-first implementation and deterministic verification.

## Coverage and mutation

The two behavioral tests capture every training config built by the Stage-1 and Stage-3
optimizers. Focused existing suites cover continuous OOS configuration, real strategy stop
behavior, portfolio trade extraction, walk-forward window attribution, and parameter scheduling.
Mutation evidence is pending the required R3 gate and must not be inferred from ordinary coverage.

## Deferred validation

Stage 1 and the `research/regression.py` artifact are intentionally deferred until Claude and Jan
agree the regression thresholds. No result number is asserted in this package.

## Deferred checks

The approximately nine-hour Stage-1 validation, its before/after research-number comparison, and
the `research/regression.py` artifact are deliberately deferred by the package firewall. This
draft is not methodology-complete and must not merge until Claude and Jan set the thresholds and
the later validation satisfies them.
