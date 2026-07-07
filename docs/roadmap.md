# QPlus — Development Roadmap

Living plan for developing the trading system. Ordered by what we do next; update the
`[STATUS]` markers as we go. This is the single reference for "what are we building and why".

## End-state vision

- **Phased broker path:** now a prop-firm demo (MEX Atlantic, MT5) to learn the mechanics →
  interim prop accounts (The Trading Pit) to earn while the GmbH is set up → long-term **own
  broker, own accounts, no prop firm**.
- **One server runs everything:** backtesting, live monitoring, and 24/7 trade execution on a
  VPS — broker-independent, always on.
- The constant across all of it is the **research framework + strategies + signal engine**;
  only the broker layer swaps. So the framework is where durable value compounds.

## Guiding principles

- **Durable vs ephemeral.** Invest in the durable core (research framework, strategies/edges,
  signal engine, analytics); keep the ephemeral broker-specific parts (MT5 bridge, prop-firm
  limits, VPS wiring) minimal and swappable.
- **Broker-agnostic keystone.** All broker/rule-specific assumptions (specs, spread, commission,
  swap, slippage) live behind ONE swappable profile — switching broker/prop/own-account is a
  config change, not a code change.
- **Live data is out-of-sample — monitor & calibrate, do NOT retune.** Live results measure
  whether the edge still holds and calibrate the framework's cost assumptions; they never feed
  back into parameter tuning except via a disciplined, validated re-fit.
- **No overfitting, no gold-plating.** Every parameter change goes through the same staged
  validation (walk-forward + untouched holdout). The methodology goal is *no material blind
  spots + swappable* — not theoretical perfection (a bottomless pit).

## Current focus

### Framework hardening — the swappable broker/market model   `[CURRENT FOCUS]`

**Goal:** a methodically complete, broker-agnostic backtesting framework — a swappable **market
model** (specs + ALL costs) so switching broker / prop / instrument is a config change, and
every metric is automatically net of every real cost. No material blind spots.

**Keystone:** one swappable **broker/market profile** carrying instrument specs (tick, contract,
leverage, min-lot) AND all costs applied *net-in-backtest*: spread, commission, swap, slippage,
gap-through-stop.

**Sub-steps (ordered by leverage):**
1. **Unify all costs, net-in-backtest.** Today: spread + commission are in the engine, swap is
   post-hoc (done in the swap phase), slippage only in the stress test. Bring swap + slippage
   into the backtest so every metric is automatically net. Introduce a `BrokerProfile` /
   `MarketModel` abstraction as the single home for all cost/spec params.
2. **Broker profile as a swappable config.** Extract the hardcoded specs (`instruments.py`) +
   costs into a per-broker profile; "switch broker" = swap the profile and re-run the study net
   of that broker's costs. Enables prop → TTP Markets → own broker with one change.
3. **Execution realism, standard (not just stress).** Model gap-through-stop (weekend/news gaps
   that jump the SL — the risk flagged on the live runner) and partial fills, in every backtest.
4. **Multiple-testing budget.** Track the running count of everything ever tried and deflate
   (DSR/PBO) accordingly — as instruments/variants/params grow, the selection-bias burden grows.
5. **Regime robustness.** Break the edge down by volatility/trend regime + crisis windows: is it
   a broad plateau or a fragile peak?
6. **Close the fixed-vs-walk-forward gap.** We validate walk-forward-optimised params but trade
   fixed SL/TP — validate the actually-traded config directly (or trade the re-fitted params).
7. **Portfolio-level modelling.** Correlation / concurrent-drawdown across the simultaneously-
   traded markets in sizing (partly in the DD feasibility already).

**Guardrail:** calibrate the cost assumptions against the live demo's actual fills/swaps as they
arrive (the one reason to keep the monitor alive). Close material blind spots, not chase
completeness.

**Done when:** you can drop in a new instrument / training length / variant / SL-TP AND swap the
broker profile, and get a fully net-of-cost, multiple-testing-honest, regime-checked verdict —
without touching framework code.

**Start with:** sub-steps 1 + 2 (the unified cost layer + broker profile) — the keystone that
closes the two most material gaps and delivers the swappability.

## Done

### Swap-cost quantification   `[DONE 2026-07-07]`
Swaps cost **~7% of gross profit / ~2 pp of annual return** (full history), **~4.7% on the
holdout**; the edge survives comfortably (PF 1.80→1.73). No market becomes unprofitable; index
shorts even earn a credit. Tool: `swap_analysis.py`. (Feeds sub-step 1 above — the swap logic
becomes part of the unified cost layer.)

### Live-vs-backtest monitoring dashboard   `[PAUSED at v1 — enough for now]`
Streamlit dashboard (`uv run streamlit run src/qplus/monitoring/dashboard.py`): **v0** live-vs-
backtest monitor (equity, KPI tiles, cumulative-R vs Monte-Carlo band, per-market table, risk
floors) + **v1** research explorer (variation × instrument heatmap, variation ranking, over the
study results). Paused deliberately — low value until the demo has traded and the real server
exists. Its live-data feed stays useful as the **calibration** input for the framework's costs.

## Later

- **Disciplined re-fit automation.** Periodic (~6mo) walk-forward re-fit of SL/TP on the trailing
  36 months, triggered by monitoring drift; never live-tuned, always validated, human-approved.
- **Dashboard v2.** Freshness / saved snapshots; a "run a new study from the UI" button (heavy).

## Parked / future

- **Second, uncorrelated strategy (trend-following complement).** The biggest structural upgrade
  — diversifies the single-strategy risk. Pending Jan's discussion with his partner. The pipeline
  is built to plug a new strategy in.
- **24/7 hosting (VPS).** Part of the end-state, but defer the setup until live on a real account.

## Status log

- **2026-07-07** — Swap phase done; dashboard v0+v1 built then PAUSED. Reprioritised (Jan): the
  swappable broker/market cost model is now the focus — durable, broker-agnostic, closes the
  material gaps. Live paper-trading (EXECUTE) running on the MEX Atlantic demo (`no_bb_wpr`,
  9 markets, 0.15% flat). Next up: unified net-in-backtest cost layer + broker profile.
