# ISSUE-62: Add behavioural signal-adapter parity

## Problem

`tests/test_import_boundaries.py::test_both_execution_adapters_construct_the_shared_signal_engine`
proves only that both adapters instantiate `RsiWprBbSignals`; it cannot detect divergent adapter
behaviour after construction.

## Goal

Drive one deterministic H4 bar fixture and one signal parameter set through the real Nautilus
wrapper and live-runner replay paths, then compare the emitted raw buy/sell decision for every bar.

## Non-goals

- No signal, order, sizing, risk, scheduling, position-management, or live-runner behaviour change.
- No MetaTrader 5 initialization, connection, account read, order placement, modification, close,
  or runner-process interaction.
- No replacement of the existing AST construction guard or the live-feed parity checker.
- No Stage 1-4 rerun or methodology/result change.

## Behavioural requirements

- The shared fixture is converted losslessly into each adapter's native bar type.
- The backtest sequence is observed by invoking the real `RsiWprBb.on_bar` method on every bar.
- The live sequence is observed by invoking the real `LiveRunner._replay_signal` method for every
  fixture prefix, matching the runner's restart-safe full-history replay semantics.
- The harness compares equal-length sequences bar-for-bar and identifies the first mismatching bar.
- The fixture contains pre-indicator warm-up, both buy and sell signals, and a signal on its final
  boundary bar, preventing vacuous parity.
- A bridge fake raises on every attribute access, proving the harness cannot touch a terminal.

## Acceptance criteria

- AC-01: Both real adapters emit an identical `(buy, sell)` sequence for all shared fixture bars.
- AC-02: Replacing only the live adapter's signal engine with a deliberately buy/sell-swapped stub
  makes the parity oracle fail at the first genuine signal.
- AC-03: Every pre-warm-up bar emits `(False, False)` through both adapters.
- AC-04: The final fixture bar is processed by both adapters and emits the expected boundary sell
  signal.
- AC-05: The harness runs in `just check-invariants` and is a critical dependency of the shared
  signal engine, the Nautilus wrapper, and the live runner.
- AC-06: Every locally executable cumulative R3 gate passes; the unavailable Linux Critical
  mutation gate is reported as infrastructure-blocked, never as passed or pending.

## Invariants

- INV-01: `core/**`, `live/**`, `research/**`, and `monitoring/**` production bytes do not change.
- INV-02: Both adapters receive one shared OHLC fixture and one `SignalParams` value; no direct call
  to the shared signal engine is used as the parity result.
- INV-03: The test creates no `Mt5Bridge`, calls no terminal method, and cannot place, modify, or
  close an order.
- INV-04: The existing AST construction guard and live-feed/data parity tests remain active.
- INV-05: No reported number or artifact changes; the current baseline trade CSV hashes remain
  unchanged because no producer changes.
- INV-06: The branch remains draft-only and cannot be marked ready while the required mutation
  evidence is unavailable.

## Assumptions

- `LiveRunner._replay_signal` is the authoritative live signal boundary used by
  `_process_market`.
- With `trade_from_ns=0`, no schedule, and `long_only=False`, the Nautilus wrapper's `_go_long` and
  `_go_short` dispatches expose its raw mutually-exclusive buy/sell decision without requiring a
  backtest engine, portfolio, or order factory.
- The shared engine never intentionally emits simultaneous buy and sell signals.

## Open questions

None. The issue fixes the adapters, fixture shape, raw comparison, warm-up/final boundaries, and
R3 classification. The test-only probe is the narrowest seam and does not alter either adapter.

## Expected artifacts

- `tests/test_signal_adapter_parity.py`
- Critical-invariant recipe and dependency-map registrations for all three signal-path modules.
- Five validated `.ai/tasks/ISSUE-62/` files with truthful build-only evidence.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because signal parity is a live-money boundary and the
critical dependency map and invariant recipe govern future changes.

## Human decisions required

Jan directed build-only operation while GitHub Actions quota is exhausted through 2026-08-01.
The pull request must remain draft, mutation evidence must remain blocked, and Jan alone decides
when it may proceed after quota reset and independent Claude review.
