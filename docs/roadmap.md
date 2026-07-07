# QPlus — Development Roadmap

Living plan for developing the trading system between now and the GmbH transition.
Ordered by what we do next; update the `[STATUS]` markers as we go. This is the
single reference for "what are we building and why".

## Guiding principles

- **Durable vs ephemeral.** The current prop-firm / MetaTrader 5 setup is an *interim
  bridge* until the GmbH is founded — the broker layer will change. Invest in the durable
  parts (research framework, strategies/edges, analytics/dashboard, the pure signal engine)
  and keep the ephemeral parts (MT5 bridge, prop-firm risk limits, VPS/hosting) minimal.
- **Live data is out-of-sample — monitor, do NOT retune.** Continuously tweaking parameters
  from live results is live curve-fitting and the classic way systematic edges break. Live
  data measures whether the edge still holds; it never feeds back into tuning except via a
  disciplined, walk-forward-validated re-fit (Phase 3).
- **No overfitting.** Any parameter change goes through the same staged validation
  (walk-forward + untouched holdout) that produced the current live config.
- **Broker-agnostic core.** The signal engine and research are broker-independent; only the
  bridge is swappable.

## Workstreams (in order)

### Phase 1 — Swap-cost quantification   `[NEXT]`

**Goal:** measure how much overnight swap/financing costs erode the backtest edge. The
strategy holds positions over multiple days, and swaps are the one real cost NOT modelled in
the backtest.

**Why:** the last honest gap between backtest and live before real money — could meaningfully
reduce the edge, especially on indices and gold.

**Approach:**
1. Pull per-symbol swap rates from the MT5 terminal (`symbol_info`: `swap_long`,
   `swap_short`, `swap_mode`, `swap_rollover3days`) via the bridge; snapshot to a small table.
2. For each backtest trade (equity-report / holdout stream), compute nights held (from
   `ts_opened`→`ts_closed`, including the triple-swap rollover day) and the swap cost =
   nights × swap-per-lot × volume, per side.
3. Deduct swaps from each trade's PnL and re-compute the key metrics (total/annual return,
   profit factor, expectancy, Sharpe) — with vs without swaps.
4. Report the impact per market + overall.

**Done when:** a clear number exists — "swaps cost ~X%/yr; the edge survives / is marginal on
markets Y" — and we know whether any market should be dropped or its holding time capped.

**Notes:** swap rates change over time and are broker-specific (TTP Markets ≠ MEX Atlantic);
treat as an order-of-magnitude estimate, not a precise historical cost.

### Phase 2 — Live-vs-backtest monitoring dashboard   `[AFTER P1]`

**Goal:** an interactive dashboard that shows how live/paper trading tracks the backtest
expectation, and is the seed of the broader analytics dashboard.

**Why:** turns the demo phase into structured learning, catches edge decay early, and is the
trigger signal for Phase 3 (re-fit). Durable — survives the GmbH transition.

**Tech:** **Streamlit** (Python-native, fast to iterate, no web stack needed; `streamlit run`).
Reads the existing backtest artifacts + live data; needs no changes to the live runner.

**Data sources:**
- *Live:* closed trades from MT5 (`history_deals_get` via the bridge) + the runner's
  `reports/live/signals.log`; current open positions + account state.
- *Backtest reference:* the equity-report artifacts (`reports/equity/`), the holdout stats,
  and the Monte-Carlo distribution.

**Build (incremental):**
- **v0 — the core comparison:**
  - Live equity curve overlaid on the backtest Monte-Carlo fan (is live inside the band?).
  - Live vs backtest table: hit rate, payoff, profit factor, expectancy — overall + per market.
  - Per-market drift flags (which markets under/over-perform their backtest expectation).
  - Current risk usage: open-risk vs the 1.5% cap, equity vs the daily/trailing floors.
- **v1 — the research selector (the dashboard vision):** pick strategy / variant / training
  length / instrument → render that config's backtest charts (equity, scorecard, market
  contributions, heatmaps). Reuses `equity_report` + the `validation/` tools as backends.
- **v2 — freshness:** on-demand refresh of live data; optional scheduled snapshot so history
  persists across runs.

**Done when:** the dashboard shows live-vs-backtest at a glance and lets you drill into any
market / config — without touching code.

**Plumbing to build first:** a clean reader for the MT5 deal history (bridge method) and a
loader that packages the backtest reference into a comparable form.

### Phase 3 — Disciplined re-fit automation   `[LATER]`

**Goal:** periodically (≈ every 6 months, matching the validated 6-month test-window length)
re-fit the per-market SL/TP on the most recent 36 months, walk-forward-validated, triggered
when Phase-2 monitoring shows real drift.

**Why:** markets' volatility/regime shift; a stop optimal on old data may not be on new data.
Keeps the config current WITHOUT live curve-fitting.

**Guardrails (critical):**
- Never tune on live / forward-test data — that is the monitoring signal, not training data.
- Re-fit only on the disciplined rolling window via the existing study pipeline; re-validate
  on a fresh, untouched holdout.
- Human-in-the-loop: the pipeline proposes new params + evidence; a person approves the swap.
  No silent auto-deploy.

**Approach (sketch):** re-seed the catalog with updated data → run `edge.characterize` +
`pipeline` on the trailing window → diff new vs current SL/TP → if materially better AND
validated, present for approval.

**Done when:** re-fitting is a one-command, validated, reviewable process — not a manual re-run.

## Parked / future

- **Second, uncorrelated strategy (trend-following complement).** The biggest structural
  upgrade — diversifies the single-strategy risk and smooths combined equity. Pending Jan's
  discussion with his partner. The pipeline is already built to plug a new strategy in.
- **24/7 hosting (VPS).** Needed for real-money operation, but ephemeral (prop phase) — defer
  until live on a real account.

## Status log

- **2026-07-07** — Plan created. Live paper-trading (EXECUTE) running on the MEX Atlantic demo;
  strategy = `no_bb_wpr`, 9 markets, 0.15% flat risk. Next up: Phase 1 (swaps).
