# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| AR-01 | P1 | Equity exactly at the 2.5% or 3% daily floor was initially treated as safe, although `RiskController.must_flatten` breaches at `equity <= floor`. | Fixed the replay comparison to be inclusive and added exact-boundary safe/breach tests. | resolved |
| AR-02 | P1 | A later safe day could erase a prior prop trailing breach, and replacing accumulation with assignment could reduce time under water to the final day's state. | Added multi-day persistence and cumulative-water tests; the Linux mutation run kills both behavioural changes. | resolved |
| AR-03 | P1 | Invalid count types, `confidence` endpoints, nearest-rank ceiling, ES tail rounding, and inconsistent count/probability summaries were under-specified. | Added fail-closed validation and focused boundary tests; all statistic-changing mutants are killed. | resolved |
| AR-04 | P2 | The first real-verdict fixture had `P(profit)=100%`, so it did not behaviourally prove that a bad profit diagnostic no longer blocks or passes the verdict. | Changed the real Stage-4 fixture to `P(profit)=0` and asserted that no profit-probability decision reason exists. | resolved |
| AR-05 | P2 | The current P-10 baseline carries Stage-1 input lineage for an older `robustness.py`, so its existing manifests correctly prevent direct reuse under current main. | The regression uses a copied, manifest-free legacy inspection only; the candidate verdict is explicitly non-deployable and the original baseline is untouched. | resolved |
| AR-06 | P1 | Compounded Stage-3 absolute money deltas were replayed against unrelated path balances, producing 74.76%/33.63% daily-breach artifacts from a history with zero observed breach days. | Added the source opening balance to schema version 2, rejected legacy artifacts, replayed all deltas relatively, and added scale-invariance plus zero-observed-breach guards. | resolved |

## Dispositions

All six findings are resolved. AR-01 through AR-04 and AR-06 have executable regression guards.
AR-05 uses the framework's fail-closed legacy inspection on a copy and does not alter or certify
the baseline.

## Counterexamples attempted

Twenty-six adversarial counterexamples were attempted: exact daily and trailing limits, just-below
limits, profitable recovery after an intraday breach, later recovery after a trailing breach,
multiple underwater closes, zero/negative/NaN/unit start balances, negative and small-positive
subsequent balances, equal internal/prop limits, impossible aggregate ordering, flat final return,
non-integer and Boolean binomial counts, confidence zero/one, empty/mismatched horizons, nearest-rank
half ties, a 50-path ES tail, inconsistent event counts, zero `P(profit)` through the real verdict,
two path-balance scales, varied source balances with no observed breaches, unversioned/old schema
artifacts, invalid source opening balances, and independent-field/order mutations from the Critical
mutation report.

## Live-money review

No `live/**`, signal, order, account, sizing, or execution file changed. The registered constants
remain strictly tighter than the prop limits, are replay-only, and are checked against the live
inclusive boundary semantics. The corrected gate outcome is recorded after the Stage-3/4 rerun; no
threshold or bound is relaxed to change that outcome.

## Residual uncertainty

The path distribution inherits P-10's complete-day scenario model and P-09's H4 upper-bound
assumption. P-11 deliberately does not recalibrate either. The Clopper-Pearson equality survivor
can only return the adjacent higher 60-digit Decimal value and therefore cannot understate risk.
