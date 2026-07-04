# MT5 Live/Paper Bridge — Implementation Plan

**Goal:** run the frozen strategy (`config/live/paper_rsi_wpr_bb.py`) on a small
(~$5,000) The Trading Pit MT5 account, automated (Option 1) or signal-only (Option 2).
Both share the same base; only the last step differs (send order vs send notification).
**Risk control to enforce: the daily 3% limit and the 6% trailing limit — nothing else**
(news/gap/volume rules intentionally out of scope).

Tech note: NautilusTrader has **no MT5 adapter**, so we use the official Windows-only
`MetaTrader5` Python package as a bridge to a running MT5 terminal logged into TTP. We reuse
the strategy's signal logic (not NautilusTrader live). His machine is Windows -> fine.

---

## Phase 0 — Prep (Jan, before coding)
1. Confirm with TTP support: **Python-API automation (own code) allowed on the $5,000
   product?** (Rules say "own EAs allowed"; the API-vs-in-terminal-EA point is the only
   ambiguity.)
2. Create the $5,000 TTP account, install the MT5 terminal, log in. Credentials -> password
   manager (never committed).
3. **Small-account reality check (important):** the whole research (0.2% risk, 9 markets) was
   on $200k. On $5,000 the limits are tiny (3% = $150, 6% = $300, 0.2% = $10/trade), and the
   broker's **minimum lot (0.01)** may already risk MORE than 0.2% (e.g. gold 0.01 lot ~ $20
   stop = 0.4% of $5k). => decide: trade **fewer markets** and/or accept a higher per-trade
   risk on the small account, or scale risk to the min-lot floor. Resolve in Phase 3.

## Phase 1 — Single source of truth for the signal (the linchpin)
The signal logic currently lives inside the NautilusTrader `RsiWprBb` strategy. Live must be
**identical** to the backtest, so extract it:
1. New pure module `qplus/strategies/rsi_wpr_bb_signals.py`: functions over a bar history
   (open/high/low/close arrays + config) -> `buy`, `sell`, and the SL/TP price levels. No
   NautilusTrader dependency. Reuse the existing `williams_r` / `bollinger` helpers.
2. Refactor `rsi_wpr_bb.py` (the NautilusTrader strategy) to call this module.
3. **Verify:** existing backtest tests + a spot backtest give **identical** results (a pure
   refactor). This guarantees live == backtest.

## Phase 2 — MT5 bridge (data + orders)
`qplus/live/mt5_bridge.py` using `MetaTrader5`:
- `connect()` (init + login), `latest_bars(symbol, n)` (H4 bars from the broker's feed),
  `account()` (balance, equity, open positions), `place_order(symbol, side, volume, sl, tp)`,
  `close_position(...)`.
- **Symbol map**: our names (XAUUSD, US30, ...) -> the broker's MT5 symbol names (may carry a
  suffix). A small table, verified against the live terminal.

## Phase 3 — Risk-control layer
`qplus/live/risk_control.py`, driven by the **actual account size** (not $200k):
- **Position sizing**: volume from (equity, SL distance, target risk %). Respect the min lot;
  if the min lot exceeds the target risk, either skip the trade or flag it (Phase 0 decision).
- **Daily 3% limit**: track the day-start balance; **block new entries** (and optionally
  flatten) once the day's loss reaches a safety fraction of 3% (e.g. 2.5%).
- **Trailing 6% limit**: track the EOD-balance high-water mark (capped at start); block new
  entries / flatten as equity approaches the floor.
- **Kill switch**: on any limit hit, stop trading for the day/session and log loudly.

## Phase 4 — Live runner
`qplus/live/runner.py` (or script), mode `EXECUTE` | `SIGNAL_ONLY`:
- On each new **H4 bar close**, for each configured market: pull bars -> compute signal
  (Phase 1) -> check risk control (Phase 3) -> if allowed: place order (Phase 2) OR send a
  notification (Telegram/log). Uses `config/live/paper_rsi_wpr_bb.py` for the per-market
  params (SL/TP/risk/switches).

## Phase 5 — Test & dry-run
1. Unit-test the signal module (Phase 1) and risk control (Phase 3) with synthetic data.
2. Run the bridge in `SIGNAL_ONLY` for a few days -> sanity-check signals + sizing vs the live
   market (no orders).
3. Switch to `EXECUTE` on the $5,000 account; watch the first sessions closely.

## Phase 6 — Monitoring
Log every signal, order, account state and limit status. (A dashboard is the later roadmap
item.)

---

## Suggested build order (next session)
Phase 1 (extract signals + verify) -> Phase 3 (risk control, pure, testable) ->
Phase 2 (bridge, needs the terminal) -> Phase 4 (runner) -> Phase 5 dry-run.
Phases 1 and 3 are pure Python and unit-testable without the terminal, so start there.
