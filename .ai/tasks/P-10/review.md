# Adversarial review

## Findings

Builder adversarial review completed after implementation; 16 calendar, accounting, path-bundle,
lineage, determinism, missing-artifact, and gate-isolation counterexamples were attempted.

| ID | Severity | Finding | Counterexample | Status |
|---|---|---|---|---|
| F1 | P1 | The old trade-slot bootstrap can stop before its target and fill the remainder with invented zero P&L. | A sampled multi-trade day overflows the remaining slots and the path silently becomes flat. | RESOLVED |
| F2 | P1 | Sampling scenario fields independently invents a daily minimum that never accompanied the sampled close. | Shuffle only close equity while leaving the source date and H4 minimum in place. | RESOLVED |
| F3 | P1 | A scenario builder could calculate another intraday path instead of using P-09's shared diagnostic. | Change only `DailyDiagnostics.minimum_equity`; the stored opening-to-minimum value must follow it exactly. | RESOLVED |
| F4 | P2 | Dropping a zero-trade day shortens drawdowns and changes dependence before resampling. | Remove the middle calendar row from a valid CSV. | RESOLVED |
| F5 | P2 | Separately accumulated float trade P&L can disagree with the authoritative realized balance. | Several same-day fractional P&Ls sum in a different binary order. | RESOLVED |
| F6 | P2 | Stage 4 could keep calling the old helper even after the scenario module is correct. | The new artifact exists but `monte_carlo_paths` remains on the verdict path. | RESOLVED |
| F7 | P2 | Validation branches and forwarding arguments could mutate without an observable test failure. | Change the empty-grid predicate, omit the seed, collapse two same-day closes, or move an error to the wrong loss day. | RESOLVED |
| F8 | P2 | P-04 RNG equivalents alternated between killed and survived under mutation-runner load, making the exact ratchet nondeterministic. | `Generator.integers(0, high, ...)` equals `Generator.integers(high, ...)`; the `<` versus `<=` restart boundary also lacked a deterministic exact-threshold fixture. | RESOLVED |

## Dispositions

F1 is removed from the Stage-4 path: every sampled path contains exactly the observed number of
calendar days. F2 is prevented structurally by one source-index draw selecting immutable complete
rows, with an independently shuffled-field oracle. F3 is resolved by accepting only
`DailyDiagnostics`, never H4 prices, in the builder. F4 is guarded by contiguous dates and exact
zero-day construction. F5 uses diagnostic balance movement as net realized P&L and subtracts the
separate swap leg, while independently validating the sized trade-P&L sum. F6 is covered by the
real stage wiring guard and the real Stage-3/4 rerun.

The review also exercised deterministic seeds, duplicate plug-in/fixed block labels, invalid CSV
schemas, non-finite money, trade/diagnostic length mismatches, closes outside the diagnostic grid,
discontinuous opening balances, source-index domain, P-04's fail-closed block estimator, and the
unchanged 0.60 verdict boundary. F7 was exposed by the first Linux mutation run and closed with
exact boundary, diagnostic, seed-forwarding, and same-day aggregation tests; no mutation-score
regression is accepted. F8 was diagnosed from alternating Linux runs: redundant zero-low RNG
arguments were removed, and a fake RNG at exactly the restart threshold now proves the specified
strict comparison. Fixed-seed and P-04 calibration tests preserve identical behaviour. No
unresolved in-scope P0-P3 builder finding remains. Claude's independent review remains mandatory.
