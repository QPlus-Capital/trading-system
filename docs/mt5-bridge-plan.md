# MT5 Live/Paper Bridge — Implementation Plan

**Goal:** run the frozen strategy (`config/live/paper_rsi_wpr_bb.py`) on The Trading Pit MT5,
automated (Option 1) or signal-only (Option 2). Test on a **$200k MT5 demo** (paper money,
same broker) for 1-2 weeks first, then go live on a real TTP account.
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
3. **Demo-first (decided):**
   - **MT5 DEMO account (paper money) first** — ideally with TTP's broker (MEX Atlantic) so
     symbols / spreads / commissions match the real thing, **balance set to $200,000** (as
     designed -> no min-lot distortion, 0.24%/trade clean). Build the bridge + risk layer +
     runner against this; run 1-2 weeks. Real spreads / commissions / bar timing, ZERO money
     at risk. This IS the original paper-trading idea.
   - **Then a real TTP account** once the demo proves the system + strategy behave.
   - Caveat: demo fills are somewhat idealized (no real liquidity / rejections) -> demo ~ live
     but slightly optimistic; a real funded account remains the final check.

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

## Phase 3 — Risk-control layer (THE #1 PRIORITY — keep the account alive)
`qplus/live/risk_control.py`, driven by the **actual account size**. Multiple layered
safeguards, each conservative:
1. **Own, stricter limits (margin):** stop well before TTP's hard limits — e.g. ~2.5% daily /
   ~4.5-5% trailing — so their server-side auto-liquidation never triggers.
2. **Total-open-risk cap (the key guarantee):** cap the SUM of all open positions' stop-risk
   to a fraction of the daily limit (e.g. <= 1.5%). Then even if EVERY open position stops out
   the same day, the loss stays under the daily limit (modulo gaps).
3. **Pre-trade worst-case check:** before every order, compute "this trade + all open
   positions at their stops" — if that would breach a (margined) limit, DON'T open.
4. **Real-time monitoring + auto-flatten:** track equity vs the trailing floor; as it
   approaches, close positions and halt.
5. **Fail-safe defaults:** on disconnect / error / uncertainty -> open nothing (doing nothing
   is safe).
6. **Position sizing:** volume from (equity, SL distance, target risk %); respect the min lot.
7. **Kill switch:** on any limit hit, stop for the day/session and log loudly.

> **NUMBERS: ask Jan first.** Before hard-coding any figure — per-trade risk %, the daily /
> trailing safety margins, the total-open-risk cap — STOP and ask Jan for the exact values he
> wants. Do not just pick them.

## Phase 4 — Live runner
`qplus/live/runner.py` (or script), mode `EXECUTE` | `SIGNAL_ONLY`:
- On each new **H4 bar close**, for each configured market: pull bars -> compute signal
  (Phase 1) -> check risk control (Phase 3) -> if allowed: place order (Phase 2) OR send a
  notification (Telegram/log). Uses `config/live/paper_rsi_wpr_bb.py` for the per-market
  params (SL/TP/risk/switches).

## Phase 5 — Test & dry-run (prove the risk layer before the 200k account)
1. Unit-test the signal module (Phase 1) and risk control (Phase 3) with synthetic data —
   include cases that MUST block trades / flatten / hit the open-risk cap.
2. Run the bridge in `SIGNAL_ONLY` for a few days -> sanity-check signals + sizing vs the live
   market (no orders).
3. `EXECUTE` on the **MT5 demo** (200k balance) for 1-2 weeks; explicitly verify the risk
   cut-offs fire correctly (block, flatten, cap) and check fills / spreads / commissions.
4. ONLY after the demo proves the system + risk layer -> go live on a real TTP account.

## Phase 6 — Monitoring
Log every signal, order, account state and limit status. (A dashboard is the later roadmap
item.)

---

## Suggested build order (next session)
Phase 1 (extract signals + verify) -> Phase 3 (risk control, pure, testable) ->
Phase 2 (bridge, needs the terminal) -> Phase 4 (runner) -> Phase 5 dry-run.
Phases 1 and 3 are pure Python and unit-testable without the terminal, so start there.

---

## Status (built)
- **Phase 1 DONE** — `qplus.strategies.rsi_wpr_bb_signals` (pure engine); strategy delegates to
  it, so live == backtest.
- **Phase 3 DONE** — `qplus.live.risk_control`: daily 2.5% / trailing 5% floors, 1.5% open-risk
  cap, worst-case pre-trade gate, `position_volume` sizing. Unit-tested.
- **Phase 2 DONE** — `qplus.live.mt5_bridge`: attach to a logged-in terminal, resolve symbols
  (USTEC->UT100, broker suffixes), H4 bars, account/positions, place/close orders.
- **Phase 4 DONE** — `qplus.live.runner.LiveRunner`: per-H4-bar signal -> risk -> order/notify;
  SIGNAL_ONLY | EXECUTE; recomputes open-risk from live positions; must_flatten -> halt.
- **Phase 5 IN PROGRESS** — `qplus.live.run` entry point (default SIGNAL_ONLY). Next: run the
  dry-run on the demo terminal, verify signals/sizing, then a supervised EXECUTE run.

### To launch (Jan, on this Windows PC)
1. Open the MT5 terminal, log into the MEX Atlantic demo (creds from the password manager).
2. Enable **Algo Trading** (toolbar) and confirm all 9 symbols incl. **UT100** are in Market
   Watch. Verify DE40 is the **cash** index.
3. `uv run python -m qplus.live.run --once` (one cycle, logs only) to sanity-check the wiring,
   then `uv run python -m qplus.live.run` to loop in SIGNAL_ONLY. Logs -> `reports/live/live.log`.
4. Only after the dry-run looks right: `--mode execute` for paper orders on the demo.
