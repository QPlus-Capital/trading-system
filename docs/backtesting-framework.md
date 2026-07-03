# QPlus Backtesting Framework — Blueprint

**Status: working design (evolving).** This document captures the staged evaluation
pipeline a trading strategy should pass through, distilled from the exploratory work on
the RSI/WPR/BB strategy. The end goal is a **repeatable framework**: a new strategy is
plugged in, run through these stages in order, and at each stage weak variants / markets
/ risk settings are filtered out — so what survives is a genuinely tradeable, prop-firm
compliant configuration, not a curve-fit.

The exploration proved out each stage on one strategy; the stages below are the intended
reusable skeleton. Some stages already exist as committed modules; others still live as
throwaway analysis scripts and need to be formalized (marked ⚙️ = to formalize).

---

## The pipeline (each stage narrows the funnel)

### Stage 1 — Component ablation: *which signals actually help?*
- **Method:** run the full clean walk-forward for the baseline and for each variant with
  one signal switched off (a 2^n factorial of the confirmations), ranked by mean OOS
  return **averaged across instruments**.
- **Accept rule:** keep a component only if removing it does *not* improve OOS across
  markets. Reject components that brake more than they help.
- **Status:** built (`qplus.backtest.study`).
- **Finding (this strategy):** drop the Bollinger and Williams-%R buy-confirmations, keep
  the RSI filter (`no_bb_wpr` won). Longer training (36m) monotonically best.

### Stage 2 — Robustness: *does the edge generalize?*
- **Method:** rolling walk-forward (optimize on train, score on unseen test), across
  **many instruments** and **several training-window lengths**.
- **Metrics:** OOS return per test window, % profitable windows, **length-normalized
  WFE**, **Deflated Sharpe (DSR)** to rule out multiple-testing, **PBO** (CSCV).
- **Accept rule:** positive OOS on a large majority of markets/windows; normalized
  WFE ≳ 0.5; DSR high after deflation.
- **Status:** built (`walkforward`, `overfitting`, `study`).
- **Finding:** consistent positive OOS on all 12 markets; normalized WFE ~0.52–0.58
  (healthy); DSR saturates at ~1 (edge is real, but DSR then can't rank variants).

### Stage 3 — Realistic costs (always on, not a stage you can skip)
- Bid/ask spread reconstructed from the MT5 spread column (buys fill at ask, sells at
  bid), commission and leverage per instrument. Baked into every backtest.
- **Status:** built (`data_ingest.mt5_csv`, `instruments`, `recipe_factory`).

### Stage 4 — Risk budgeting: *what risk per trade fits a drawdown limit?*
- **Method:** `risk_per_trade` only *scales* trade PnL (does not change which trades
  happen), so from a base run the drawdown at any risk level can be recomputed exactly.
  Find, per instrument, the max risk whose drawdown stays under the target.
- **Accept / rank rule:** rank markets by **return per drawdown**, NOT raw return. (Raw
  return is misleading — e.g. silver had the highest raw return but must be throttled to
  ~0.07% risk, collapsing it down the ranking.)
- **Status:** ⚙️ analysis scripts only (`dd_budget.py`).

### Stage 5 — Portfolio drawdown vs the prop-firm rule (the feasibility gate)
- **The Trading Pit rule (confirmed 2026-07-03, 200k account) is a HYBRID** — this is the
  exact model to implement:
  - **Floor (the drawdown limit line):** trails the **high-water mark of end-of-day
    BALANCE (closed/realized P&L only)** minus 6% (12,000). It **stops rising once it
    reaches the starting balance** — so after you have locked in +6% realized, the floor
    is static at the starting balance (200k) forever.
  - **Breach test:** if **EQUITY (realized + floating unrealized of open positions)** ever
    falls to/below the floor → account breached. So floating losses *can* breach.
  - Daily drawdown 3% (6,000) is a secondary intraday limit (basis per product page —
    still to confirm; screenshot says "Kontostand"/balance).
- **Method:** ONE account. Track (a) the realized EOD-balance high-water-mark → floor
  (capped at start), and (b) the daily mark-to-market **equity** = start + realized +
  unrealized of open positions (unrealized is exact, linear in price for a fixed-size
  position). Breach if equity ≤ floor at any time.
- **Accept rule:** equity never breaches the floor over the whole OOS path (with margin).
- **Key consequence:** because the floor **caps at the starting balance**, the binding
  risk is entirely the **early phase** (before +6% realized is banked); afterwards you
  only must keep equity above the starting balance, which a grown account clears easily.
  This makes **dynamic drawdown-throttled sizing (Stage 6) the central tool** — be
  conservative early, scale up once the buffer is banked.
- **Status:** ⚙️ analysis scripts (`mtm2.py` computes the equity curve, validated vs
  `diag_mtm.py`) — but they used a *strict trailing-equity-peak* floor, which is TOO
  STRICT. Must be reworked to the hybrid model above (realized-balance floor capped at
  start, equity-based breach).
- **Findings so far (with the too-strict model, so pessimistic):** portfolio MTM DD at
  flat 1% ≈ 13% (diversification keeps it below the worst single market USTEC 15.6%).
  Under the correct hybrid model the feasible risk will be **higher** than the ~0.06–0.15%
  those runs implied. Best universe candidate: **clean8** (drop currency-approx FX +
  silver).

### Stage 6 — Position-sizing policy: *flat vs dynamic*
- **Idea (Jan):** drawdown-throttled sizing — full risk near equity highs, taper down as
  the account approaches the drawdown wall. Protects the hard limit while running higher
  base risk. Beats flat sizing at the same DD budget (the tighter the limit, the bigger
  the edge); the trade-off to measure is the "de-risk into the recovery" drag.
- **Status:** ⚙️ concept validated on realized-equity; **needs re-validation under the
  corrected MTM model** (next exploratory step).

### Stage 7 — Paper / live (future)
- Deploy the surviving config to paper on The Trading Pit MT5, then live. Not started.

---

## Methodology gotchas learned (do not re-step on these)
- **WFE is length-biased:** it compares a 6-month OOS return to a `train_months` IS
  return, so raw WFE looks ~4–6× too low. Normalize per month before judging.
- **Overlapping walk-forward windows** (step < test) smooth the *mean* but inflate
  significance stats and **double-count** pooled trades. Use non-overlapping (step = test)
  for drawdown / portfolio work.
- **NautilusTrader NETTING:** every closed round-trip except the last is flagged
  `is_snapshot=True` but is a **real trade** — do not filter it out.
- **Realized vs mark-to-market drawdown (RESOLVED for TTP, 2026-07-03):** the drawdown
  *floor* trails end-of-day **balance** (realized) and caps at the starting balance; the
  *breach* is tested on **equity** (incl. floating). It is a hybrid — model both. The
  practical upshot: the binding constraint is the early phase before +6% is banked.
- **datetime unit:** MT5 CSV parses to `datetime64[us]`; `.astype(int64)//DAY_NS` (ns)
  gives wrong days. Use unit-safe `((ts - epoch)//Timedelta(days=1))`.
- **Currency approximation:** USDCHF/USDJPY/USDCAD and DE40 are modelled USD-quoted.
  Percent metrics are fine; absolute $ are approximate — keep these out of the core
  tradeable universe if possible.
- **Gap / tail risk:** a single leveraged trade lost ~20% of the account on a gap through
  its stop. Real tail risk; account for it in the risk model.

## Open questions / next
1. ~~TTP trailing DD basis~~ — RESOLVED: hybrid (realized-balance floor capped at start,
   equity breach). See Stage 5. Next: rework `mtm2.py` to this hybrid model.
2. Dynamic drawdown-throttle benefit under the *hybrid* model (should be large, since the
   binding risk is the early phase).
3. Compounding vs fixed-notional sizing (fixed-notional makes early drawdowns bind
   hardest, forcing low risk).
4. Daily 3% drawdown limit — basis (balance vs equity) per product page; model as a
   secondary intraday guard.
5. Return magnitude still carries model optimism (leverage, walk-forward-selected params,
   ideal fills). Treat headline %/yr as an upper bound until paper-traded.

## Current best configuration (this strategy)
`no_bb_wpr` (RSI filter only, no Bollinger/WPR confirmation), 36-month training,
non-overlapping 6-month test windows, **clean8** universe (USTEC, DE40, US500, US30,
EURUSD, XAUUSD, AUDUSD, GBPUSD), ~0.15% risk/trade → MTM trailing DD < 6%.
