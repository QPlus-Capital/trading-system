# Adversarial review

## Findings

| ID | Severity | Counterexample | Disposition |
|---|---|---|---|
| AR-01 | P1 | Equity exactly at the 2.5% or 3% daily floor was initially treated as safe, although `RiskController.must_flatten` breaches at `equity <= floor`. | Fixed the replay comparison to be inclusive and added exact-boundary safe/breach tests. |
| AR-02 | P1 | A later safe day could erase a prior prop trailing breach, and replacing accumulation with assignment could reduce time under water to the final day's state. | Added multi-day persistence and cumulative-water tests; the Linux mutation run kills both behavioural changes. |
| AR-03 | P1 | Invalid count types, `confidence` endpoints, nearest-rank ceiling, ES tail rounding, and inconsistent count/probability summaries were under-specified. | Added fail-closed validation and focused boundary tests; all statistic-changing mutants are killed. |
| AR-04 | P2 | The first real-verdict fixture had `P(profit)=100%`, so it did not behaviourally prove that a bad profit diagnostic no longer blocks or passes the verdict. | Changed the real Stage-4 fixture to `P(profit)=0` and asserted that no profit-probability decision reason exists. |
| AR-05 | P2 | The current P-10 baseline carries Stage-1 input lineage for an older `robustness.py`, so its existing manifests correctly prevent direct reuse under current main. | The regression uses a copied, manifest-free legacy inspection only; the candidate verdict is explicitly non-deployable and the original baseline is untouched. |

## Counterexamples attempted

Twenty-two adversarial counterexamples were attempted: exact daily and trailing limits, just-below
limits, profitable recovery after an intraday breach, later recovery after a trailing breach,
multiple underwater closes, zero/negative/NaN/unit start balances, negative and small-positive
subsequent balances, equal internal/prop limits, impossible aggregate ordering, flat final return,
non-integer and Boolean binomial counts, confidence zero/one, empty/mismatched horizons, nearest-rank
half ties, a 50-path ES tail, inconsistent event counts, zero `P(profit)` through the real verdict,
and independent-field/order mutations from the Critical mutation report.

## Live-money review

No `live/**`, signal, order, account, sizing, or execution file changed. The registered constants
remain strictly tighter than the prop limits, are replay-only, and are checked against the live
inclusive boundary semantics. The new gate fails closed on the current baseline; no threshold or
bound was relaxed to change that outcome.

## Residual uncertainty

The path distribution inherits P-10's complete-day scenario model and P-09's H4 upper-bound
assumption. P-11 deliberately does not recalibrate either. The Clopper-Pearson equality survivor
can only return the adjacent higher 60-digit Decimal value and therefore cannot understate risk.
