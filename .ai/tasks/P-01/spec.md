# P-01: Apply net swap costs to Stage-1 selection

## Problem

Stage 1 scores gross realized price R while the methodology requires selection net of overnight
swap, systematically favouring candidates whose positions remain open longer.

## Goal

Attach the standard TTP swap snapshot to every realized Stage-1 trade at close and make
`net_r = r + swap_r` the sole return stream used by training selection, OOS window metrics,
Sharpe, WFE, DSR/PBO, and return/drawdown ranking inputs.

## Non-goals

- Running the approximately nine-hour Stage-1 validation or creating, filling, or changing a
  `research/regression.py` comparison artifact.
- Choosing regression thresholds, fabricating expected deltas, or claiming numerical validation
  against baseline `run_20260723_1540`.
- Changing signal logic, spreads, commission, slippage, sizing, live trading, risk limits,
  holdout boundaries, trial counts, DSR/PBO formulas, or Stage-3 fixed portfolio outputs.
- Marking the pull request ready, merging it, or enabling auto-merge.

## Behavioural requirements

- Stage 1 constructs one `standard_broker()` snapshot and uses that same in-memory profile for
  every worker task in the study.
- Every closed training and OOS trade retains gross `r`, receives a separate realized `swap_r`,
  and derives `net_r = r + swap_r`.
- Training Calmar scores and in-sample returns use net trade outcomes.
- Chosen OOS window return, per-trade return, drawdown, candidate-matrix return, WFE, Sharpe,
  DSR/PBO streams, and `study.csv`/ranking inputs all derive from `net_r`.
- Swap is realized exactly once at the trade's close timestamp. It is never marked through the
  holding period and never folded into gross `r`.
- Positive short-index carry remains a positive `swap_r` credit; otherwise net return cannot
  exceed gross return.
- Directly generated study provenance records the content hash of the exact canonical swap
  snapshot input, including the `absent` state.
- The fixed-parameter Stage-3 path remains numerically unchanged and continues to attach swap
  through its existing realized-at-close portfolio convention.

## Acceptance criteria

- AC-01: Two equal-gross candidate streams with different overnight duration rank by net return,
  with the longer negatively carried stream ranked lower.
- AC-02: A short index trade with a positive snapshot rate receives positive `swap_r` and
  `net_r > r`.
- AC-03: A trade held through an earlier window contributes no swap or return before close and
  contributes its swap exactly once in the close-owning window.
- AC-04: Training return, OOS return, market summary, Sharpe/WFE inputs, and return/drawdown inputs
  are traceable to the same net trade fixture.
- AC-05: Running the real `research.engine.characterize` CLI path twice against the same synthetic
  market produces different `study.csv` output when only a deliberately large swap snapshot is
  changed.
- AC-06: Changing the canonical swap snapshot content changes the hash stored in the directly
  generated study provenance.
- AC-07: Fixed Stage-3 extraction bypasses re-optimization and preserves its gross trade stream;
  the existing portfolio layer remains the only place that attaches its realized swap.
- AC-08: `just check` passes without a Stage-1 validation run or committed generated report.

## Invariants

- INV-01: `r` remains gross price R; `swap_r` remains separate; `net_r` is their exact sum.
- INV-02: Swap uses `core.broker.standard_broker()` and `swap_r_per_trade`; no second rate,
  rollover, direction, or sign convention is introduced.
- INV-03: One closed position produces one swap realization at its close timestamp.
- INV-04: Fixed Stage-3 `portfolio_trades.csv`, `full_history_trades.csv`, and portfolio metrics
  are outside the changed numerical path.
- INV-05: Study selection remains pre-holdout and uses the same constant account basis introduced
  by P-02.
- INV-06: No money, price, or quantity is newly represented as `float`; dimensionless R and
  statistical returns may remain NumPy/Python floats at their existing boundaries.
- INV-07: No live, order, account, signal, sizing, or risk-limit code changes.

## Assumptions

- The canonical persisted TTP snapshot is the cost input chosen by the existing
  `standard_broker()` convention; a missing snapshot remains the existing explicit zero-swap
  fallback and is recorded as `absent` in lineage.
- `timed_trades_from_report` is the authoritative close-time, direction, entry, exit, and
  stop-distance extraction already used by Stage 3.
- The current fixed Stage-3 invocation supplies fixed stops and therefore bypasses its
  `_optimize` path.

## Open questions

Claude and Jan must agree the regression thresholds against baseline `run_20260723_1540` before
the deferred Stage-1 run. No threshold or numerical magnitude is inferred in this code package.

## Expected artifacts

- Stage-1 net-return plumbing and direct study provenance.
- Focused red-first unit and real-entrypoint integration tests.
- Updated architecture text describing Stage 1 as net of realized swap.
- This task artifact and a draft pull request titled `[P-01]`.

## Risk class

R3. The classifier assigns R3 because the change touches Stage-1 selection, parameter search,
continuous OOS attribution, and the trade-return stream that controls every downstream research
decision.

## Human decisions required

Claude and Jan decide the pre-run regression thresholds and later accept or reject the numerical
validation. Jan alone decides whether and when to merge. This code-only pull request remains draft.
