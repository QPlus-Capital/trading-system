# ISSUE-58: Remove Stage-1 running-equity ruin checks

## Problem

`research/engine/continuous.py::window_returns` scores every trade against a constant basis but
still reconstructs cumulative running equity before each window and raises when it is non-positive,
mixing incompatible fixed-basis and compounding-account models and turning valid candidates into
error rows.

## Goal

Implement Jan's ratified Option A: score every Stage-1 window strictly against the same fixed basis,
including after cumulative fixed-size losses exceed that basis, so severe losses remain negative
evidence in the ranking instead of deleting the candidate.

## Non-goals

- Implementing Option B's ruin/disqualifier signal or Option C's existing error behavior.
- Changing constant-basis sizing, gross/swap/net attribution, window boundaries, trade ownership,
  drawdown calculation, Calmar ranking, WFE, DSR, PBO, SPA, Romano-Wolf, MCS, or Stage-2 rules.
- Changing Stage 3, Stage 4, full-history trades, the deployed variation, live execution, or any
  limit, threshold, or gate.
- Running the complete nine-hour Stage-1 matrix; the two affected XAGUSD tasks are rerun directly.
- Opening a pull request while the GitHub Actions quota is exhausted.

## Behavioural requirements

- `window_returns` attributes every close event once and divides both aggregate and per-trade
  returns by the unchanged constant `basis`.
- Cumulative outcomes before a window never change its denominator and never raise a ruin error.
- A window after cumulative fixed-basis loss at or below `-basis` is still returned and scored.
- Large negative windows remain large negative returns; they are never replaced with zero,
  truncated, dropped, or encoded as an error/disqualifier row.
- Both the chosen Stage-1 path and every inner parameter-combination path use the corrected
  `window_returns` function.
- The two real XAGUSD `36m` candidates, `no_wpr_rsi` and `no_confirms`, complete `_run_task` with
  numeric scores and no `error` field.
- Stage-1 cumulative curves remain only where required to measure return path and drawdown/Calmar;
  no cumulative balance is used to decide whether a candidate or later window exists.

## Acceptance criteria

- AC-01: A fixed-basis event stream whose cumulative PnL crosses `-basis` returns every window
  without raising, and the later window return remains its own PnL divided by the original basis.
- AC-02: Losses totaling exactly `-basis` and losses below `-basis` produce the same later-window
  score when the later-window events are identical.
- AC-03: Repository search finds no Stage-1 account-exhaustion/post-ruin branch or error message;
  chosen-path and candidate-matrix callers both use the sole basis-relative implementation.
- AC-04: Real XAGUSD `no_wpr_rsi@36m` and `no_confirms@36m` tasks produce complete numeric result
  rows, including all windows, instead of the baseline's two error rows.
- AC-05: The deployed `no_bb_wpr` portfolio metrics remain exact, regression has no unexpected
  changes at `0.0%` trade-count and `0.0pp` annual-return tolerances, and both trade CSVs are
  byte-identical.
- AC-06: Every locally executable cumulative R3 gate passes; Linux mutation is recorded as blocked
  by the Actions quota through 2026-08-01, never as pending or passed.

## Invariants

- INV-01: Every Stage-1 training and OOS trade remains sized from one Decimal
  `sizing_equity`; window scoring uses that same basis.
- INV-02: `r` remains gross, `swap_r` remains separate, and `net_r` remains the sole statistical
  return stream.
- INV-03: Window ownership stays half-open between windows and inclusive only at the final boundary.
- INV-04: Cumulative return curves used for max drawdown and Calmar remain statistical measurements,
  never account-existence gates.
- INV-05: No Stage-2 eligibility threshold, reported deployed number, trade stream, or live-money
  behavior changes.
- INV-06: No live runner is stopped, restarted, queried, or otherwise touched.

## Assumptions

- The fixed basis is positive and already supplied by the established scoring configuration; this
  task changes no denominator validation.
- Targeted execution of the two formerly failing real tasks is sufficient to prove their error-row
  removal without recomputing the other 430 unchanged Stage-1 tasks.

## Open questions

None. Jan ratified Option A on issue #58 on 2026-07-27; Options B and C are explicitly declined.

## Expected artifacts

- Simplified basis-relative `research/engine/continuous.py::window_returns`.
- Red-first behavioral guards in `tests/test_research_continuous_windows.py`.
- Generalized coupled-accounting finding in `.ai/quality/finding-patterns.toml`.
- Targeted real XAGUSD task evidence and ignored zero-tolerance regression evidence under
  `reports/research/`.
- Complete R3 task artifacts under `.ai/tasks/ISSUE-58/`.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because `continuous.py` owns Stage-1 constant-basis
sizing, candidate scoring, and window attribution; the finding registry is also R3 governance.

## Human decisions required

Jan has decided Option A, the two real-candidate acceptance set, exact regression thresholds,
build-only/no-PR delivery, and Jan-only merge authority. No methodology choice remains open.
