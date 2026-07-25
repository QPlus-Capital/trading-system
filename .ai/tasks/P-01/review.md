# Adversarial builder preflight

## Findings

No findings; 12 counterexamples attempted.

## Counterexamples attempted

1. Followed every return consumer from the closed-position report through training Calmar,
   continuous OOS windows, candidate matrices, WFE, Sharpe, DSR/PBO, study rows, and rankings.
2. Compared equal-gross candidates whose only difference is negatively carried holding time.
3. Exercised positive short-index points carry to catch a reversed direction or sign.
4. Carried a position across a window boundary and verified no return or swap appears before close.
5. Counted close events to catch duplicate swap realization.
6. Mutated the sole statistical stream from `net_r` back to `r`; three behavioral tests failed.
7. Ran the real characterize CLI path twice with only a monkeypatched large swap changed.
8. Changed canonical snapshot bytes and verified direct-study provenance hashes differ.
9. Checked that one frozen broker object reaches all characterize worker recipes.
10. Checked Stage-3 fixed-stop extraction bypasses training optimization and keeps gross columns.
11. Audited the diff for live, signal, sizing, risk-limit, report, and regression-artifact changes.
12. Ran the full repository, property, invariant, and security suites.

## Dispositions

Claude's independent review and the deferred Stage-1 validation remain mandatory before this draft
can become ready for merge. No builder-preflight finding is unresolved.
