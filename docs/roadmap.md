# QPlus — Development Roadmap

The "what next, and why" overview. The authoritative *methodology* — how a strategy is validated
from idea to a tradeable, prop-firm-compliant config — is [methodology.md](methodology.md).

## End-state vision

- **Phased broker path:** a prop-firm demo (MEX Atlantic, MT5) to learn the mechanics → interim
  prop accounts (The Trading Pit) to earn while the GmbH is set up → long-term **own broker, own
  accounts, no prop firm**.
- **One server runs everything:** backtesting, live monitoring, and 24/7 execution on a VPS —
  broker-independent, always on.
- The constant across all of it is the **research core + strategies + signal engine**; only the
  broker layer swaps. That is where durable value compounds.

## Guiding principles

- **Durable vs ephemeral.** Invest in the durable core (research framework, strategies/edges,
  signal engine, analytics); keep the ephemeral broker-specific parts (MT5 bridge, prop-firm
  limits, VPS wiring) minimal and swappable.
- **Broker-agnostic keystone.** All broker/rule-specific assumptions (specs, spread, commission,
  swap, slippage) live behind ONE swappable profile (`core/broker.py`) — switching broker is a
  config change, not a code change.
- **Live data is out-of-sample — monitor & calibrate, do NOT retune.** Live results measure whether
  the edge still holds and calibrate the cost assumptions; they never feed back into parameter
  tuning except via a disciplined, validated, human-approved re-fit.
- **No overfitting, no gold-plating.** Every parameter change goes through the same staged
  validation (walk-forward + an untouched holdout).

## Where we are

- **Live on the real TTP CFD Prime $50k account** (USD), alongside the MEX Atlantic demo (EUR) as
  the parity shadow — two isolated runners, each on its own terminal, guarded against trading the
  wrong account. Strategy `no_bb_wpr`, 10 markets, 0.18% compounding.
- **The backtesting framework is complete and broker-agnostic:** one swappable market/cost profile
  (specs + spread + commission + swap + slippage + gap-through-stop), a staged walk-forward study
  with a reserved holdout, multiple-testing-honest selection (deflated Sharpe / PBO), plus regime
  and correlation checks. Every metric is net of the real TTP costs.
- **Repo restructured into three worlds + a shared core** (`core` / `research` / `live` /
  `monitoring`); TTP is the single source of truth; dead code and the pre-framework paths removed.

## Next

- **Two-agent build/review separation.** Codex builds; Claude turns the operator's intent into the
  specification and performs the independent review. Neither does the other's job, and the operator
  approves every merge. See [workflow.md](../workflow/workflow.md).
- **Slippage calibration.** Calibrate `prob_slippage` against the live accounts' actual fills as
  trades close — the one standing reason to keep the monitor alive.

## Later

- **Disciplined re-fit automation.** Periodic (~6mo) walk-forward re-fit of SL/TP on the trailing
  36 months, triggered by monitoring drift; never live-tuned, always validated, human-approved.
- **Dashboard polish.** Freshness indicators / saved snapshots; a "run a new study from the UI"
  button (heavy).
- **More instruments.** Add markets to the study as their data + specs arrive.

## Parked / future

- **Second, uncorrelated strategy (trend-following complement).** The biggest structural upgrade —
  it diversifies the single-strategy risk. Pending an operator decision; the pipeline is built to
  plug a new strategy in.
- **24/7 hosting (VPS).** Part of the end-state; defer the setup until stable on a real account.
