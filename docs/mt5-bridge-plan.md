# MT5 Live/Paper Bridge — Implementation Plan

**Goal:** run the frozen strategy (`config/live/paper_rsi_wpr_bb.py`) on The Trading Pit MT5,
automated (Option 1) or signal-only (Option 2). Prove the bridge + risk layer on a cheap
**$5,000** account first, then run the real test on a **$200,000** account.
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
3. **Two accounts, two roles (decided):**
   - **$5,000 account = plumbing + risk-layer PROVING GROUND.** Cheap way to prove the bridge,
     signals, orders AND the risk cut-offs work with real (tiny) money. Do NOT judge strategy
     performance here — min-lot forces >0.2% risk and the tiny limits ($150 daily) can't hold
     9 markets, so it would trip the limits for mechanical reasons.
   - **$200,000 account = the real strategy test** (matches the research: 0.2% achievable,
     min-lot non-binding, limits $6,000 daily / $12,000 trailing). Costs ~1,000 EUR, so it
     goes live ONLY after the risk layer is proven on the $5k account.

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
3. `EXECUTE` on the **$5,000** account; explicitly verify the risk cut-offs fire correctly
   (block, flatten, cap) with real money.
4. ONLY after the risk layer is proven on $5k -> go live on the **$200,000** account.

## Phase 6 — Monitoring
Log every signal, order, account state and limit status. (A dashboard is the later roadmap
item.)

---

## Suggested build order (next session)
Phase 1 (extract signals + verify) -> Phase 3 (risk control, pure, testable) ->
Phase 2 (bridge, needs the terminal) -> Phase 4 (runner) -> Phase 5 dry-run.
Phases 1 and 3 are pure Python and unit-testable without the terminal, so start there.
