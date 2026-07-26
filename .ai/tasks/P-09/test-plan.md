# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | 13:00-17:00 short plus catastrophic 01:00 high | RED: whole-day high is consumed | Pending |
| AC-02 | profitable boundary/same-observation short plus later high | RED: later daily high is consumed | Pending |
| AC-03 | two trades in disjoint H4 observations | RED: their daily extrema are summed | Pending |
| AC-04 | two trades in one H4 observation | RED: interval identity is absent | Pending |
| AC-05 | reset-straddling bar with overlapping and non-overlapping positions | RED: loader duplicates the bar before lifetime filtering | Pending |
| AC-06 | non-zero swap and H4 adverse marks | RED: no shared diagnostic proves one close realization | Pending |
| AC-07 | daily and trailing limits around exact boundaries | RED: no reusable diagnostic object owns all gate fields | Pending |
| AC-08 | real Stage-3/Stage-4/fact-sheet integration fixture | RED: fact sheet uses close-only max drawdown | Pending |
| AC-09 | prescribed six-short retired-structure synthetic fixture | RED: whole-day reconstruction remains near 3.20% | Pending |
| AC-10 | real entrypoints on copied `run_20260724_1146` | RED: entrypoints still load daily extrema | Pending |
| AC-11 | zero-threshold regression plus SHA-256 comparison | RED: no P-09 comparison artifact exists | Pending |
| AC-12 | exact non-path statistics snapshot | RED: no P-09 parity guard exists | Pending |
| AC-13 | cumulative R3 gates | RED: implementation/evidence absent | Pending |
| INV-01 | market/timestamp/direction/lifetime parameterization | RED: daily collapse destroys interval identity | Pending |
| INV-02 | same-vs-different H4 aggregation | RED: all same-day extrema co-move | Pending |
| INV-03 | equality-boundary parameterization | RED: boundary semantics unavailable | Pending |
| INV-04 | Chicago reset across summer/winter | RED: only daily duplicated extrema exist | Pending |
| INV-05 | balances/sizes/equity/swap exact comparison | RED: no H4 path available for isolated comparison | Pending |
| INV-06 | monkeypatch old close-only path to raise | RED: fact sheet calls it | Pending |
| INV-07 | asynchronous bar carry plus wholly missing lifetime evidence | RED: daily alignment silently fills | Pending |
| INV-08 | changed-path and producer guard | RED: no P-09 scope guard exists | Pending |
| INV-09 | regression CLI with exact zero thresholds | RED: artifact absent | Pending |

## Statistical and temporal boundaries

- Open strictly before the H4 observation; close at or after the observation.
- Same timestamp open/close, one-observation, multi-observation, and no-observation lifetimes.
- Long/short adverse direction and positive/negative/zero price spans.
- One market, simultaneous markets, disjoint markets, and missing bars.
- Bar wholly before reset, wholly after reset, and straddling 16:15 Chicago under CST/CDT.
- First simulated day, new balance HWM, exact daily limit, exact trailing floor, and recovered close.
- Positive/negative/zero swap with close-day realization only.

## Regression

Copy the immutable current baseline to a new P-09 run directory, remove only Stage-3/4 publications
from the copy, rerun the real Stage-3/4 entrypoints with the prescribed arguments, and compare with:

`uv run python -m research.regression --issue 35 --pair
run_20260724_1146=<candidate> --out reports/research/regression/35-comparison.json
--trade-count-pct 0.0 --annual-return-pp 0.0`

The report must contain no unexpected changes and the full-history trade artifact must be
byte-identical. Record before/after path metrics separately.

## Mutation targets

- Entry/exit inequality directions and timestamp ordering.
- Direction-adverse low/high selection.
- Same-timestamp aggregation and cross-timestamp minimum.
- Reset-straddle day assignment and overlap filtering.
- Daily-loss denominator, trailing floor, and breach boundaries.
- Swap exclusion from H4 marks and single close realization.
- Policy/fact-sheet consumption of `DailyDiagnostics`.

## Red-first status

Not yet executed.
