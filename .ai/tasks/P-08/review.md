# Adversarial review

## Findings

Builder adversarial review completed after implementation; 20 counterexamples attempted.

| ID | Severity | Finding | Counterexample | Status |
|---|---|---|---|---|
| F1 | P1 | Issue #50 requires complexity-first automatic selection, but no pre-registered complexity score existed in config or documentation. | Two candidates cannot be ordered by the mandatory first key without inventing methodology. | RESOLVED |

## Dispositions

Jan supplied the exact per-variation mapping on 2026-07-26. The production config and an exact
coverage test now bind all twelve scores; training length remains a later tie-break.

The review exercised missing SPA/Romano-Wolf/MCS artifacts, malformed strict evidence, family
identity drift, resampling-identity drift, SPA failure with excellent returns, each successive
empty intersection, exact Decimal thresholds, partial complexity config, invalid complexity
values, unsupported training length, row-order permutations, every tie-break layer, 35/36/37
candidate shapes, constant and non-finite window streams, odd/even PBO windows, failed DSR/PBO with
valid family evidence, forced selection with failed automatic evidence, and a verdict attempting
to retain the old DSR/PBO vetoes.

No unresolved P0-P3 builder finding remains. Claude's independent review is still mandatory.
