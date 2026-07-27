# Impact analysis

## Direct impact

- `tests/test_signal_adapter_parity.py` drives the real `RsiWprBb.on_bar` and
  `LiveRunner._replay_signal` paths with synthetic bars and compares their bar-level output.
- `justfile::check-invariants` runs that harness on every critical-invariant execution.
- `.ai/quality/critical-dependencies.toml` maps the harness to
  `core/strategies/rsi_wpr_bb_signals.py`, `core/strategies/rsi_wpr_bb.py`, and
  `live/runner.py`.
- `.ai/tasks/ISSUE-62/` records specification, traceability, review, and evidence.

## Transitive impact

The harness protects the raw signal sequence consumed by:

1. `core/strategies/rsi_wpr_bb.py::RsiWprBb.on_bar`, which dispatches buy/sell signals to reversal
   and position-management actions in research backtests.
2. `live/runner.py::LiveRunner._process_market`, which calls `_replay_signal`, then
   `_act_on_signal`, sizing, risk gates, and the live order boundary.
3. Research Stage 1 and Stage 3, which execute the Nautilus wrapper through the recipe/continuous
   backtest path.
4. `live/parity_check.py`, which separately checks broker-feed versus research-data parity at the
   shared-engine level but not adapter behaviour.

No production consumer changes. The new guard makes a future divergence in any of the three
signal-path modules select and run the behavioural parity test.

## Critical dependencies

- `core/strategies/rsi_wpr_bb_signals.py` remains the one pure signal source.
- `core/strategies/rsi_wpr_bb.py::RsiWprBb.on_bar` remains the real Nautilus adapter path.
- `live/runner.py::LiveRunner._replay_signal` remains the real live adapter path.
- Nautilus native `Bar`/`Price` objects and the live `Bar` dataclass receive the same rounded OHLC
  values.
- The no-terminal fake raises on any bridge access, so an accidental live dependency fails loudly.

## Unknown or dynamic edges

The adapters are dynamically instantiated by Nautilus configuration and the live CLI, but the
tested methods are direct and require no dynamic import. `just impact origin/main` is rerun after
registration; its output is recorded in evidence. No terminal, account, output artifact, or
external service is in the test path.

## Coupled parity axis

The coupled quantity is the complete raw signal sequence, not merely construction of the shared
engine. Every producer/consumer on that axis is enumerated above. Parameter conversion, bar order,
warm-up, final-bar handling, and buy/sell orientation are held common in one harness.

## Stage and artifact impact

No Stage 1-4 code or configuration changes, so no research stage needs rerunning. The current
baseline trade artifacts remain authoritative. A production-path diff and the recorded SHA-256
hashes prove that neither `portfolio_trades.csv` nor `full_history_trades.csv` can move in this
test-only package.

## Failure modes

- Calling `RsiWprBbSignals` twice directly and claiming adapter parity.
- Comparing only the final signal and missing an earlier divergent bar.
- Using a flat fixture that produces no signals.
- Omitting warm-up or silently dropping the final bar.
- Stubbing both adapters symmetrically, allowing the same wrong behaviour to agree.
- Constructing a real bridge or calling `run_once`, which could touch a running terminal.
- Registering only the signal engine and leaving adapter changes outside the critical mapping.

## Measured impact

`just impact origin/main` reports R3, no changed production file, exactly the new parity harness as
the direct test, and no transitive, unknown, or dynamically affected edge. The explicit critical
registrations are prospective: a future change to the signal engine or either adapter selects the
harness even though none of those sources changes in this package.

`git diff --exit-code origin/main...HEAD -- core live research monitoring pyproject.toml uv.lock`
passes. No Stage 1-4 producer, dependency, configuration, signal, runner, or monitoring byte moves,
so the existing research artifacts need no rerun.
