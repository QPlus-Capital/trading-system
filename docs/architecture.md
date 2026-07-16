# Architecture

The map of the system: what exists, how the pieces nest, and where the data flows.
Read this before diving into any module — every file below links back to a one-line
purpose, and the diagrams show the paths a bar of market data can take.

> Snapshot of the system **as it is** (2026-07-16, start of the repo cleanup).
> If structure changes, change this file in the same PR.

---

## 1. The three worlds

The repo is one Python package (`src/qplus/`) serving three loosely-coupled worlds
plus a shared core. Truth flows left to right: research validates a configuration,
the frozen config goes live, and monitoring compares live results back against the
research expectation.

```mermaid
flowchart LR
    subgraph CORE["Shared core"]
        STRAT["strategies/<br/>signal logic (single source of truth)"]
        INSTR["instruments.py<br/>venue instrument definitions"]
        BROKER["backtest/broker.py<br/>cost profiles (spread, commission, swap)"]
        INGEST["data_ingest/<br/>MT5 CSV → Parquet catalog"]
    end

    subgraph RESEARCH["Research — staged framework"]
        PIPE["backtest/<br/>stages 1–4"]
    end

    subgraph LIVE["Live trading"]
        RUN["live/<br/>MT5 runner + risk control"]
    end

    subgraph MON["Monitoring"]
        DASH["monitoring/<br/>Streamlit dashboard"]
    end

    CORE --> RESEARCH
    CORE --> LIVE
    RESEARCH -- "validated config<br/>(frozen in config/live/)" --> LIVE
    RESEARCH -- "backtest reference +<br/>Monte-Carlo band" --> MON
    LIVE -- "MT5 deals" --> MON
```

| World | Entry point | Output |
|---|---|---|
| Research | `uv run python -m qplus.backtest.stages.<stage>` | `reports/framework/run_*/` |
| Live | `uv run python -m qplus.live.run --account {mex,ttp} --mode {signal_only,execute}` | orders on MT5 + `reports/live/<account>/` |
| Monitoring | `uv run streamlit run src/qplus/monitoring/dashboard.py` | browser dashboard |

---

## 2. Research pipeline — the staged framework

One *framework run* is a directory under `reports/framework/run_*/`. Each stage
reads the previous stage's artifact from it and writes its own; every stage prints
the exact next command. Methodology behind it: [methodology.md](methodology.md).

```mermaid
flowchart TD
    CSV["MT5 CSV export<br/>(H4 bars per market)"] --> INGEST["data_ingest/mt5_csv.py"]
    INGEST --> CAT[("data/ Parquet catalog<br/>(never committed)")]

    CAT --> SWEEP["edge/characterize.py — walk-forward sweep<br/>every instrument × variation × training length<br/>(config/study/robustness.py; hours)"]
    SWEEP --> STUDY[/"study.csv"/]

    STUDY --> S1["STAGE 1 — EDGE (stages/edge.py)<br/>Is the edge real and robust?<br/>Decision table + eligibility gates"]
    S1 --> S2["STAGE 2 — SELECT (stages/select.py)<br/>Which variation, training length, markets?"]
    S2 --> SEL[/"selection.json"/]

    SEL --> S3["STAGE 3 — PORTFOLIO (stages/portfolio.py)<br/>Extract holdout trades, attach real TTP swap (swap_r),<br/>measure the crisis tail cap, size under a risk policy"]
    S3 --> PT[/"portfolio_trades.csv (holdout)<br/>full_history_trades.csv<br/>portfolio.json"/]

    PT --> S4["STAGE 4 — VERDICT (stages/verdict.py)<br/>Trade yes/no: gates + fact sheet"]
    S4 --> OUT[/"verdict.json + report.html<br/>(fact sheet: full history vs holdout,<br/>flat vs compound, per market, regimes)"/]
```

Cost model in research (matches the live TTP account):

- **In-engine** (during every backtest): spread, commission, slippage from the
  broker profile — `broker.standard_broker()` = TTP Markets.
- **After extraction**: overnight **swap** from the pulled snapshot
  (`config/broker/ttp_markets_swaps.json`) as a separate `swap_r` column per trade.
  `r` stays gross; swap is booked as a **realized** cost at close and never
  marked to market (see `portfolio/curves.py` — this split keeps the
  mark-to-market drawdown stable).
- The **study sweep is deliberately swap-free**: swap is near-uniform across
  variations, so it cannot change the selection — the money-true numbers come
  from stages 3–4.

### How a backtest actually executes (the nesting)

The call stack from a stage down to the strategy — this is where things are
"nested inside each other":

```text
stages/portfolio.py                      orchestrates the stage
└─ pipeline.make_extract_fn()            builds the per-market extractor
   └─ portfolio/trades.py                extracts the timed OOS trade stream
      └─ edge/engine.py                  drives walk-forward windows
         └─ edge/walkforward.py          splits history into train/test windows
            └─ foundation/grid.py        runs the parameter sweep per window
               └─ foundation/recipe.py   builds one NautilusTrader engine run
                  └─ NautilusTrader BacktestEngine
                     └─ strategies/rsi_wpr_bb.py        (thin Nautilus wrapper)
                        └─ strategies/rsi_wpr_bb_signals.py  (pure signal engine —
                                                          the SAME code live uses)
```

Everything above `trades.py` returns plain DataFrames; the portfolio math modules
(`curves`, `sizing`, `risk`, `tail`, `stress`, `factsheet`) are pure functions on
those frames — no engine, fully unit-tested.

---

## 3. Live path

One process per account, one MT5 terminal per process. The same pure signal engine
as the backtest, driven one closed H4 bar at a time.

```mermaid
flowchart TD
    CLI["live/run.py<br/>--account {mex,ttp} --mode {signal_only,execute}"]
    CLI --> ACC["live/accounts.py<br/>account profile: expected login/currency,<br/>terminal path, symbol overrides<br/>+ identity guard (refuses on mismatch)"]
    ACC --> BRIDGE["live/mt5_bridge.py<br/>data + orders against ONE terminal<br/>(symbol map, magic 770077)"]
    BRIDGE <--> MT5A["MT5 terminal mex (demo)<br/>C:\\Program Files\\MetaTrader 5"]
    BRIDGE <--> MT5B["MT5 terminal ttp (real $50k)<br/>C:\\Users\\jancw\\MT5\\ttp"]

    CLI --> RUNNER["live/runner.py — the H4 cycle"]
    RUNNER --> C1["1 fetch bars, drop the forming bar"]
    C1 --> C2["2 replay signals<br/>(rsi_wpr_bb_signals — backtest parity)"]
    C2 --> C3["3 size the order<br/>0.18% of equity, compounding"]
    C3 --> C4["4 risk gates<br/>live/risk_control.py"]
    C4 --> C5["5 place order with SL/TP,<br/>re-anchor exits to the actual fill"]
    C5 --> STATE[("reports/live/&lt;account&gt;/<br/>risk_state.json + logs")]
```

- **Risk limits** (`risk_control.py`, deliberately *stricter* than the prop rules):
  daily stop 2.5% (TTP hard limit 3%), trailing max drawdown 5% (TTP 6%),
  combined open-risk cap 2.0%.
- **`live/preflight.py`** — GO/NO-GO before going live: identity, algo trading
  enabled, all symbols resolve and are sizable.
- **`live/parity_check.py`** — does the broker feed produce the same signals as
  our research data?
- **Frozen config**: `config/live/paper_rsi_wpr_bb.py` (10 markets, per-market
  SL/TP). Promotion to live == adding a config here, never new code.

---

## 4. Monitoring

```mermaid
flowchart LR
    DEALS["MT5 deals<br/>(via the bridge)"] --> LIVEM["monitoring/live.py<br/>deals → round-trip trades<br/>+ realized equity"]
    REF["backtest reference run"] --> REFM["monitoring/reference.py<br/>expectation + Monte-Carlo band"]
    STUDY2["study.csv"] --> RES["monitoring/research.py<br/>study explorer"]
    LIVEM --> DASH["monitoring/dashboard.py<br/>Streamlit, account selector (default ttp)"]
    REFM --> DASH
    RES --> DASH
```

The question the dashboard answers: **is live behaving like the backtest said it
would** — or drifting outside the Monte-Carlo band?

---

## 5. Module map

One line per file. If a docstring and this table disagree, one of them is a bug.

### Shared core

| File | Purpose |
|---|---|
| `strategies/rsi_wpr_bb_signals.py` | Pure signal engine for RsiWprBb — single source of truth shared by backtest and live |
| `strategies/rsi_wpr_bb.py` | Thin NautilusTrader wrapper around the signal engine (backtest execution) |
| `instruments.py` | Instrument definitions for the venues we trade |
| `backtest/broker.py` | Swappable broker/market cost profiles; `standard_broker()` = TTP + real swap snapshot |
| `data_ingest/mt5_csv.py` | Import MT5 CSV exports into the Parquet catalog |
| `data_ingest/synthetic.py` | Deterministic synthetic data for offline tests |

### Research — foundation (single-backtest machinery)

| File | Purpose |
|---|---|
| `backtest/config.py` | High-level backtest runner (NautilusTrader wiring) |
| `backtest/foundation/recipe.py` | Factory for per-instrument sweep recipes (one engine run) |
| `backtest/foundation/grid.py` | Parameter sweep across combinations |
| `backtest/foundation/execution.py` | Monte-Carlo equity report for a single recipe |
| `backtest/foundation/montecarlo.py` | Monte-Carlo robustness from per-trade PnLs |
| `backtest/foundation/overfitting.py` | Selection-bias statistics (deflated Sharpe, PBO — Bailey & López de Prado) |
| `backtest/foundation/trial_budget.py` | Honest multiple-testing budget |

### Research — edge & selection

| File | Purpose |
|---|---|
| `backtest/edge/walkforward.py` | Walk-forward window scheme (train/test splits, purge/embargo) |
| `backtest/edge/engine.py` | Walk-forward runner (engine driver) |
| `backtest/edge/characterize.py` | The robustness study: walk-forward every instrument × variation, in parallel |
| `backtest/select/universe.py` | Universe selection + global structure choice |

### Research — portfolio math (pure, on DataFrames)

| File | Purpose |
|---|---|
| `backtest/portfolio/trades.py` | The timestamped OOS trade stream the portfolio consumes |
| `backtest/portfolio/curves.py` | Daily realized + mark-to-market equity curves (swap realized-only) |
| `backtest/portfolio/sizing.py` | Position-sizing simulation: per-trade risk + the daily path |
| `backtest/portfolio/risk.py` | The risk system: account context + pluggable tail-capped sizing policies |
| `backtest/portfolio/tail.py` | The crisis tail on the FULL history — the ceiling no policy may cross |
| `backtest/portfolio/stress.py` | Does the sized account survive a worse-than-history gap? |
| `backtest/portfolio/drawdown.py` | Prop-firm drawdown rule (trailing/hybrid) |
| `backtest/portfolio/factsheet.py` | End-of-run metrics matrix (full vs holdout, flat vs compound, net of swap) |
| `backtest/portfolio/html_report.py` | Self-contained `report.html` from a fact sheet |
| `backtest/portfolio/regime.py` | Does the edge hold across volatility/trend regimes? |
| `backtest/portfolio/correlation.py` | Are the markets really diversified; how crowded is the book? |
| `backtest/portfolio/equity_report.py` | Illustrative equity report for the frozen live config |
| `backtest/portfolio/swap_analysis.py` | Swap-cost report + snapshot refresh (`pull_swap_specs`) |

### Research — stages (the CLI)

| File | Purpose |
|---|---|
| `backtest/stages/_runbook.py` | Run directory + terminal UX (banner, next command) |
| `backtest/stages/edge.py` | Stage 1 — is the edge real, where, is it robust? |
| `backtest/stages/select.py` | Stage 2 — which structure and which markets? |
| `backtest/stages/portfolio.py` | Stage 3 — combine + size under a risk policy |
| `backtest/stages/verdict.py` | Stage 4 — trade yes/no + fact sheet + report |
| `backtest/pipeline.py` | The injected per-market trade extractor used by stage 3 |

### Live

| File | Purpose |
|---|---|
| `live/run.py` | Entry point: CLI, logging, account wiring, main loop |
| `live/accounts.py` | Account profiles (mex/ttp) + identity guard |
| `live/mt5_bridge.py` | Data + orders against a running MT5 terminal |
| `live/runner.py` | The H4 cycle: bars → signals → sizing → risk gates → orders |
| `live/risk_control.py` | Prop-firm limits: daily stop, trailing drawdown, open-risk cap |
| `live/preflight.py` | GO/NO-GO checks before going live |
| `live/parity_check.py` | Live feed vs research data: same signals? |
| `live/notify.py` | Signal notifications (optional Telegram) |

### Monitoring

| File | Purpose |
|---|---|
| `monitoring/dashboard.py` | Streamlit dashboard (account-aware, default ttp) |
| `monitoring/live.py` | MT5 deals → round-trip trades + realized equity + stats |
| `monitoring/reference.py` | Backtest reference + Monte-Carlo expectation band |
| `monitoring/research.py` | Study explorer: slice + aggregate study results |

---

## 6. Dependency rules

The import direction is strictly downward; nothing imports from `stages/`.

```mermaid
flowchart TD
    STAGES["backtest/stages (CLI orchestration)"] --> EDGE["edge / select / portfolio"]
    EDGE --> FOUND["foundation (engine machinery)"]
    FOUND --> STRAT["strategies (pure signals + Nautilus wrapper)"]
    LIVE2["live (runner, bridge, risk)"] --> STRAT
    MON2["monitoring"] -.reads artifacts, no code deps upward.-> STAGES
    EDGE --> CORE2["broker / instruments / data_ingest"]
    LIVE2 --> CORE2
```

- `strategies/rsi_wpr_bb_signals.py` is **pure** (no Nautilus, no MT5) — that is
  what makes backtest/live parity possible. Only the thin wrapper touches Nautilus;
  only the bridge touches MT5.
- The portfolio math never talks to an engine — stages pass it DataFrames.
- Live never imports from `backtest/` except the shared cost/instrument core.

---

## 7. Directories & artifacts

| Path | Contents | Versioned? |
|---|---|---|
| `data/` | Parquet catalog + raw CSV exports | no |
| `reports/framework/run_*/` | one framework run: study.csv, selection.json, trades, verdict, report.html | no |
| `reports/live/<account>/` | per-account live state: risk_state.json, logs | no |
| `config/study/` | study definition: variations, grid, instruments, account | yes |
| `config/live/` | frozen live configs (promotion == adding one) | yes |
| `config/broker/` | pulled swap snapshots per broker | yes |
| `docs/` | methodology (the spec), runbook, this file | yes |

## 8. Conventions that keep the numbers honest

- **R multiples everywhere**: a trade's result is measured in units of its own
  planned risk — scale- and sizing-invariant. Money enters only at the sizing step.
- **`r` is gross; `swap_r` is separate** and realized at close — never marked to
  market. Netting them would corrupt the floating-PnL interpolation.
- **Flat vs compound** are two lenses on the same trades; only annual return and
  max drawdown differ between them, and the fact sheet shows both side by side.
- **The holdout is sacred**: reserved months no stage selected on; stage 3 extracts
  it once, stage 4 judges on it.
- **Live mirrors research**: same signal code, same 0.18% risk, same TTP cost
  reality (engine costs + pulled swap snapshot), stricter internal limits than the
  prop firm's.
