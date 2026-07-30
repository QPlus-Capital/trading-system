# Adversarial review

## Findings

No findings; 6 counterexamples attempted

## Dispositions

Claude completed the independent R3 review on 2026-07-30:
https://github.com/QPlus-Capital/trading-system/pull/132#pullrequestreview-4812992929

The six counterexamples were:

1. A gateway reported false success across all five operations; `arm` refused and never added
   `approved`.
2. `arm` ran with the card in `Backlog`; AC-01 refused it before any mutation.
3. `start` ran while the status move never landed; AC-03 refused and retained the permit.
4. `move` targeted `Done`; INV-01 refused the target explicitly.
5. `arm` ran without a `risk:Rn` label; the re-read precondition refused approval.
6. The contract contained an approval step with no implementing board operation; dispatch raised
   instead of silently skipping it.

No disposition or code change was required.
