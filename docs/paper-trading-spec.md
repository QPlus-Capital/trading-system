# Paper-Trading Spec — RsiWprBb (no_bb_wpr) on The Trading Pit

**Status: research complete, ready to wire for paper trading.** This is the concrete,
frozen configuration the pipeline selected and validated. Machine-readable version:
`config/live/paper_rsi_wpr_bb.py`.

## The chosen strategy
- **`RsiWprBb`** (`src/qplus/strategies/rsi_wpr_bb.py`) — a 4H long/short mean-reversion /
  reversal system. Buys a green candle bouncing off the lower Bollinger band while RSI < 40;
  sells overbought Williams-%R reversals with EMA-trend / RSI-exhaustion logic.
- **Variant `no_bb_wpr`:** the Bollinger and Williams-%R *buy-confirmations* are OFF; the RSI
  filter is kept. (All four indicators are still used — only the two extra buy filters are
  dropped.) This was the best **risk-adjusted** variant across 12 markets and survived the
  untouched holdout.

## Sizing & risk
- **Flat** position sizing (the dynamic drawdown-throttle added nothing once the daily limit
  is enforced): **~0.20% risk per trade** to start (holdout tolerated ~0.24% under both
  limits; we keep margin and tune live).
- One 200,000 USD account, all 9 markets combined.
- **The Trading Pit drawdown limits:** max **6%** trailing (12,000, floor caps at the
  starting balance) + **3%** daily (6,000). Both were enforced in the feasibility scoring.

## The 9 markets and their fixed parameters
SL/TP fit on the most recent 36 months (re-fit periodically). Leverage per the broker specs.

| market | leverage | stop-loss % | take-profit % |
|---|---|---|---|
| XAUUSD | 10 | 1.0 | 3.0 |
| EURUSD | 50 | 0.5 | 3.0 |
| GBPUSD | 50 | 0.5 | 1.0 |
| AUDUSD | 50 | 0.5 | 2.0 |
| USDJPY | 50 | 0.5 | 1.0 |
| US30 | 15 | 0.5 | 3.0 |
| DE40 | 15 | 1.5 | 2.0 |
| US500 | 15 | 1.0 | 3.0 |
| USTEC | 15 | 1.0 | 4.0 |

(Training 36 months, 4H bars. USDCHF/USDCAD/XAGUSD/GBPUSD-adjacent weak markets were dropped
in selection; GBPUSD is kept as the 9th market from the no_bb_wpr universe.)

## Validation evidence (honest)
- Holdout (last ~1.5 years, never used for any selection), one account, both DD limits:
  **flat 0.24% → +132% total, VERDICT PASS** (positive return, feasible risk, 100% MC
  probability of profit).
- Full-period walk-forward (Stage 1, ~12 years, ~200k trades): consistent positive OOS,
  normalized WFE ~0.55–0.58 (generalizes).
- **Caveats:** the holdout is short; returns carry leverage / ideal-fill optimism (treat as
  an upper bound); the daily-limit check is end-of-day resolution (a lower bound on the true
  intraday daily drawdown).

## Remaining before paper trading
1. **Live wiring (awaiting Jan's approach):** attach the 9 strategy configs to a
   NautilusTrader live `TradingNode` with the MT5 / The Trading Pit adapter + account, and
   enforce the DD limits as live cut-offs. Same 4H bar feed as the backtest.
2. **Optional rigor:** an H4-resolution daily-drawdown check (vs the current end-of-day proxy)
   to confirm the daily 3% limit holds intraday for the fixed config.
3. **Re-fit cadence:** decide how often SL/TP are re-optimized on the trailing 36 months.
