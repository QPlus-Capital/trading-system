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
- **Method:** ONE account trading the chosen markets. Rebuild **daily mark-to-market
  equity = start + realized PnL + unrealized PnL of every open position** (unrealized is
  exact and linear in price for a fixed-size position). Measure the **trailing max
  drawdown** the way the prop firm does.
- **The Trading Pit rules (on a 200k account):** **max drawdown 6% (12,000) trailing on
  end-of-day; daily drawdown 3% (6,000).**
- **Accept rule:** trailing MTM drawdown ≤ limit (with margin, e.g. target ≤5%).
- **Status:** ⚙️ analysis scripts only (`mtm2.py`, validated against `diag_mtm.py`).
- **Finding:** realized-only DD (~13%) badly understates nothing here — the *portfolio*
  MTM DD at flat 1% is ~13% (diversification keeps it below the worst single market). To
  fit ≤6% MTM DD, the **clean8** universe (drop the currency-approximated FX + silver) at
  ~0.15% risk yields ~35%/yr (an upper estimate — see caveats).

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
- **Realized vs mark-to-market drawdown:** realized-only (balance) can hide large
  drawdowns from open positions; MTM (equity) captures them. **OPEN QUESTION:** does TTP's
  trailing limit use end-of-day *balance* or *equity*? This flips feasibility — confirm.
- **datetime unit:** MT5 CSV parses to `datetime64[us]`; `.astype(int64)//DAY_NS` (ns)
  gives wrong days. Use unit-safe `((ts - epoch)//Timedelta(days=1))`.
- **Currency approximation:** USDCHF/USDJPY/USDCAD and DE40 are modelled USD-quoted.
  Percent metrics are fine; absolute $ are approximate — keep these out of the core
  tradeable universe if possible.
- **Gap / tail risk:** a single leveraged trade lost ~20% of the account on a gap through
  its stop. Real tail risk; account for it in the risk model.

## Open questions / next
1. TTP trailing DD basis (balance vs equity) — confirm from the rules.
2. Dynamic drawdown-throttle benefit under the corrected MTM model.
3. Compounding vs fixed-notional sizing (fixed-notional makes early drawdowns bind
   hardest, forcing low risk).
4. Daily 3% drawdown limit — not yet checked.
5. Return magnitude still carries model optimism (leverage, walk-forward-selected params,
   ideal fills). Treat headline %/yr as an upper bound until paper-traded.

## Current best configuration (this strategy)
`no_bb_wpr` (RSI filter only, no Bollinger/WPR confirmation), 36-month training,
non-overlapping 6-month test windows, **clean8** universe (USTEC, DE40, US500, US30,
EURUSD, XAUUSD, AUDUSD, GBPUSD), ~0.15% risk/trade → MTM trailing DD < 6%.
