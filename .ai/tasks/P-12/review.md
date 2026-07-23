# Adversarial review

## Findings

No findings; 20 counterexamples attempted

## Dispositions

The builder pre-PR review attempted: same bytes under different paths; one changed stop; changed
signal code; omission of each of the seven input hashes; reordered threshold keys and safety
reasons; non-ASCII hypothesis text; malformed and missing input paths; missing/short strategy git
SHA; naive timestamps; zero, fractional, non-Decimal, NaN, and infinite counts/returns; numeric
account IDs; credential-shaped participant IDs; disk leakage after rejected registration; cohort
definition tampering; observation cohort tampering; live/paper append mixing; live/paper pooling;
cross-cohort pooling; duplicate loss days; JSON numeric storage; and accidental stage/live
integration.

The first Linux mutation measurement exposed 12 identity-test gaps. Known-vector, Unicode, invalid
path, and diagnostic tests killed 11; the sole survivor removes explicit `ensure_ascii=True`, which
is equivalent because that is `json.dumps`' default. A security preflight also rejected a
high-entropy synthetic test literal; the fixture now constructs non-secret test values and the
scanner passes. No unresolved P0-P3 finding remains. Claude's independent R3 review is still
required; no live runner, account, order, stage, or reported-result path was touched.
