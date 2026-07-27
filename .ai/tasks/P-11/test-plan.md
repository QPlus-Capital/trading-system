# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | deterministic all-flat paths | RED: P-11 module absent | GREEN: raw zero, upper bound positive |
| AC-02 | one `-3%` minimum among ten, block length 1 | RED: no breach replay | GREEN: frequency within `0.02` of `1 - 0.9^10` |
| AC-03 | path and aggregate dominance guards | RED: no four-limit result | GREEN: internal >= prop or fail closed |
| AC-04 | profitable close after `-3%` minimum | RED: old gate sees profit only | GREEN: internal daily breach remains true |
| AC-05 | trusted beta-quantile fixtures | RED: no exact-binomial bound | GREEN: `x=0,1,5`, `n=10` within `1e-12` |
| AC-06 | verdict source and behavioural check list | RED: `prob_profit >= 0.6` present | GREEN: only exact `0.01`/`0.05` bounds gate |
| AC-07 | summary JSON key set and exact values | RED: only `P(profit)` exists | GREEN: all requested fields serialize |
| AC-08 | repeated seeded summary and block labels | RED: no path-risk summary | GREEN: exact equality, plug-in + 5/10/20/60 |
| AC-09 | temporary legacy run through real `verdict.main` | RED: real entrypoint has old gate | GREEN: new checks and artifacts execute |
| AC-10 | real Stage-4 rerun and issue-52 regression | RED: no comparison | GREEN: empty unexpected changes at zero tolerances |
| AC-11 | SHA-256 and metric comparison | RED: no P-11 run | GREEN: both trade files and non-path metrics exact |
| AC-12 | cumulative R3 gates | RED: implementation absent | GREEN: every required gate has exit 0 |
| INV-01 | monkeypatched P-10 sampler call oracle | RED: no consumer | GREEN: P-10 sampler receives every block choice |
| INV-02 | intraday recover fixture | RED: old gate uses final profit | GREEN: opening-to-minimum controls breach |
| INV-03 | constants and strict ordering guard | RED: no limit set | GREEN: `0.025<0.03`, `0.05<0.06` |
| INV-04 | impossible constructed aggregate | RED: no invariant | GREEN: raises before JSON/verdict |
| INV-05 | Decimal types and no-normal source guard | RED: no bounds | GREEN: gate values are Decimal exact-binomial |
| INV-06 | zero-event analytical fixture | RED: no bound | GREEN: positive conservative upper bracket |
| INV-07 | real Stage-4 check list | RED: old diagnostic gates | GREEN: only selected plug-in bounds gate |
| INV-08 | zero-tolerance regression and live diff | RED: no proof | GREEN: no protected quantity or live path moves |

## Statistical procedures

- Clopper-Pearson trusted values are independently generated from the Beta quantile identity
  `BetaInv(0.95, x+1, n-x)`: `0.258865550893052`, `0.394163302436505`, and
  `0.777558898991871` for `x=0,1,5`, `n=10`.
- The one-in-ten bootstrap fixture uses 4,000 reduced test replications. Its two-standard-error
  Monte-Carlo uncertainty is below `0.016`; tolerance is fixed at `0.02`.
- Production remains 10,000 replications at seed `20260719`.

## Integration and regression

- Invoke the real Stage-4 entrypoint on a temporary lineage-compatible fixture while using the
  real P-10 sampler and P-11 replay at reduced test replications.
- Rerun Stage 4 on the current P-10 baseline. Stage 3 is rerun only if lineage requires republishing
  the unchanged upstream bundle under the branch code.
- Generate issue 52's comparison with exact zero tolerances, hash both trade artifacts, and record
  old/new path estimates and verdict states.

## Mutation focus

Mutate the four thresholds, strict daily comparison, same-day trailing HWM update, intraday minimum
source, unions, dominance invariant, negative-return sign, quantile ranks, ES tail count,
time-under-water predicate, binomial CDF/tail inversion, bisection direction, confidence, gate
boundaries, selected-block choice, and Stage-4 check wiring. Any unexplained survivor blocks.
