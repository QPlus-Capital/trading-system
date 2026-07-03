# QPlus Backtesting Framework — Blueprint

**Status: agreed design (2026-07-03), now being built into modules.** A new strategy is
plugged in and run through the staged pipeline below; each stage filters on a
risk-adjusted criterion, so what survives is a genuinely tradeable, prop-firm compliant
configuration — not a curve-fit. The exploratory work on the RSI/WPR/BB strategy proved
out every stage; the stages here are the reusable skeleton.

---

## Core principle: risk lives on THREE levels (do not conflate them)

1. **Trade-level risk controls (SL/TP)** — part of the *strategy itself*; tuned inside the
   walk-forward.
2. **Risk as the evaluation LENS** — every ranking / selection uses a **drawdown-adjusted
   metric (return per unit of drawdown)**, from the very first stage. **Raw return is
   never a selection criterion.** (In the exploration we wrongly ranked the ablation by
   raw OOS return — a component that lifts return but wrecks drawdown must not win.)
3. **Capital sizing (`risk_per_trade`, dynamic throttle)** — a *pure scaling transform*
   applied at the end: it changes only trade size, not which trades happen, and is defined
   against the portfolio-level, prop-firm-specific drawdown limit.

## Ordering principles
1. **Validity before optimization** — prove an edge generalizes OOS before fine-tuning it,
   else you optimize noise.
2. **Cheap & universal before expensive & specific** — per-instrument before portfolio;
   structure before fine parameters.
3. **Every selection is multiple testing** — count the "trials" across *all* stages and
   deflate (DSR); keep a final **holdout period no stage ever sees for selection**.

## Design decision (locked): **global structure, not per-market.**
One component structure / parameter policy that is robust across the chosen universe —
not a different structure per market. Rationale: per-market tailoring multiplies
overfitting and the trial count. Per-market deviation only with strong, pre-registered
justification.

---

## The pipeline

### Stage 0 — Foundation (always on, not a filter)
Realistic costs (bid/ask spread from the MT5 spread column, commission, leverage) and
correct instrument specs in **every** backtest. Precondition for everything below.
**Built:** `data_ingest.mt5_csv`, `instruments`, `recipe_factory`.

### Stage 1 — Robust edge characterization (per instrument, risk-adjusted)
Rolling walk-forward: parameters chosen on each train window by a **drawdown-adjusted
score (Calmar)**, then scored on the unseen test window. Run for the baseline **and the
component ablation** (a 2^n factorial of the signal confirmations) across **many
instruments** and **several training-window lengths** — ablation and validation share one
engine.
- **Metrics:** OOS return per window, **OOS max drawdown**, **return-per-drawdown**
  (the ranking key), % profitable windows, **length-normalized WFE**, **DSR**, PBO.
- **Accept rule:** rank variants by **return-per-drawdown across instruments**; keep a
  component only if removing it does not improve the risk-adjusted OOS. Require a positive,
  generalizing edge (normalized WFE ≳ 0.5, DSR high after deflation).
- **Built:** `walkforward`, `overfitting`, `study` — *being upgraded* to rank
  risk-adjusted (was raw return) and to surface OOS drawdown + normalized WFE.

### Stage 2 — Universe selection + global structure
From Stage 1, keep instruments with a robust risk-adjusted edge and cross-instrument
consistency; drop weak / wild / currency-approximated markets. Pick the single **global**
structure that is most robust across the kept universe.
- **Status:** ⚙️ to formalize (`universe_select`).

### Stage 3 — Portfolio drawdown under the real prop-firm rule (feasibility gate)
ONE account trading the selected universe. Implement **The Trading Pit's HYBRID rule**:
- **Floor:** trails the high-water mark of **end-of-day BALANCE (realized P&L)** minus the
  limit, and **stops rising once it reaches the starting balance** (after +limit% is
  banked, the floor is static at the starting balance).
- **Breach:** if **EQUITY (realized + floating open positions)** ever falls to/below the
  floor. So floating losses can breach; floating gains do not raise the floor.
- Limits (200k account): **max DD 6% / 12,000; daily 3% / 6,000** (daily = secondary
  intraday guard).
- **Key consequence:** because the floor caps at the starting balance, the binding risk is
  the **early phase** (before +limit% is banked). This is what makes Stage 4 central.
- **Status:** ⚙️ to formalize (`portfolio_dd`); scratch `mtm2.py` computes the equity
  curve (validated) but used a too-strict trailing-equity-peak floor — rework to the hybrid.

### Stage 4 — Position-sizing policy (the final transform)
Flat vs **dynamic drawdown-throttled** sizing (Jan's idea: conservative early, scale up as
the buffer is banked), optimized to the prop limit with margin.
- **Status:** ⚙️ to formalize (`sizing`); concept validated on realized equity, needs
  re-validation under the hybrid model.

### Stage 5 — Final validation, stress, acceptance
Stress (extra slippage, crisis windows), Monte-Carlo on the final config, the untouched
**holdout** check, scorecard → paper/live decision.
- **Built (partly):** `stress`, `montecarlo`, `scorecard`, `report` — to be wired into a
  final gate.

### Stage 6 — Paper → live (future).

### Cross-cutting (not a stage)
Multiple-testing accounting across all stages (total trials → DSR) and a final holdout
period reserved from all selection.

---

## Methodology gotchas learned (do not re-step on these)
- **WFE is length-biased:** it compares a `test_months` OOS return to a `train_months` IS
  return. Normalize per month (`normalized_wfe = raw_wfe * train_months / test_months`).
- **Overlapping walk-forward windows** (step < test) smooth the mean but inflate
  significance and **double-count** pooled trades. Use non-overlapping (step = test) for
  drawdown / portfolio work.
- **NautilusTrader NETTING:** every closed round-trip except the last is flagged
  `is_snapshot=True` but is a **real trade** — do not filter it out.
- **TTP drawdown = hybrid** (resolved): realized-balance floor capped at start, equity
  breach. See Stage 3.
- **datetime unit:** MT5 CSV parses to `datetime64[us]`; use unit-safe
  `((ts - epoch)//Timedelta(days=1))` for day numbers, not `.astype(int64)//DAY_NS`.
- **Currency approximation:** USDCHF/USDJPY/USDCAD and DE40 modelled USD-quoted; percent
  metrics fine, absolutes approximate — prefer keeping them out of the core universe.
- **Gap / tail risk:** a single leveraged trade lost ~20% of the account on a gap through
  its stop. Real; the sizing model must account for it.

## Current best configuration (this strategy, provisional)
`no_bb_wpr` **(to be re-checked under risk-adjusted ranking)**, 36-month training,
non-overlapping 6-month test windows, **clean8** universe (USTEC, DE40, US500, US30,
EURUSD, XAUUSD, AUDUSD, GBPUSD). Feasible under the (too-strict) MTM model at ~0.15% risk;
the hybrid rule is more lenient, so the tradeable risk will be higher.

## Open items
- Rework portfolio DD to the hybrid model; measure the dynamic-throttle benefit under it.
- Daily 3% limit basis per product page.
- Return magnitude still carries model optimism (leverage, walk-forward-selected params,
  ideal fills) — treat headline %/yr as an upper bound until paper-traded.
