# Adversarial review

## Findings

Builder adversarial review is scheduled after implementation; the initial design review attempted
the required temporal, cost, path-sharing, and fail-closed counterexamples.

| ID | Severity | Finding | Counterexample | Status |
|---|---|---|---|---|
| F1 | P1 | The existing whole-day extrema erase H4 identity and position lifetime. | A 13:00-17:00 short is charged an unrelated 01:00 high. | OPEN |
| F2 | P1 | The fact sheet computes close-only drawdown independently of the Stage-3 breach path. | A recovered intraday dip produces different Stage-3 and fact-sheet max drawdowns. | OPEN |

## Dispositions

F1 and F2 are the package defects and remain open until their red-first behavioural guards pass on
the production entrypoints. Claude's independent review remains mandatory.
