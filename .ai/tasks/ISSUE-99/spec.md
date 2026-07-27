# ISSUE-99: Extract direction from the position entry side

## Problem

`research/portfolio/trades.py::timed_trades_from_report` reads a closed Nautilus position's
current `side`, which is always `FLAT`, instead of its opening `entry` side (`BUY`/`SELL`), so every
Stage-1/3/full-history trade is persisted as short.

## Goal

Extract one authoritative Boolean direction at the producer boundary (`BUY -> True`,
`SELL -> False`), fail closed on every other value, and let every existing swap, H4 path, scenario,
risk, and reporting consumer inherit the correction without local patches.

## Non-goals

- Adding outcome-based direction inference anywhere in the extraction path.
- Changing signals, trade identity, timestamps, entry/exit prices, gross PnL, gross `r`, stops,
  parameters, risk limits, thresholds, or live execution.
- Retuning or rerunning the nine-hour Stage-1 candidate matrix in this package.
- Forcing Stage-3/4 net/path metrics to match the known-wrong baseline.
- Implementing operator-only issue #95; it remains blocked until this producer is corrected.
- Connecting to MT5, refreshing the swap snapshot, or interacting with either live runner.

## Behavioural requirements

- Read the report's `entry` side before emitting the extracted row whose `entry` key means entry
  price.
- Accept `BUY` as long and `SELL` as short after whitespace/case normalization.
- Raise `ValueError` for `FLAT`, empty, missing/NaN, or any unrecognized entry side.
- Never infer direction from price movement, realized PnL, `r`, or any other outcome.
- Preserve every non-direction extraction field exactly.
- All downstream consumers continue reading the single emitted `is_long` field; none reconstructs
  a replacement in this package.

## Acceptance criteria

- AC-01: A closed position with `side=FLAT` and `entry=BUY` extracts `is_long=True`; an
  `entry=SELL` position extracts `False`.
- AC-02: An unrecognized entry side fails closed with a diagnostic naming the value; it never
  defaults to short.
- AC-03: Real XAUUSD extraction matches the raw report exactly: 374 BUY/386 SELL becomes
  374 longs/386 shorts.
- AC-04: The corrected full deployed history contains both directions; record its exact split and
  reconcile each market against raw BUY/SELL counts.
- AC-05: An integration guard sends producer-extracted BUY/SELL trades through synchronized H4
  replay and proves the long consumes the interval low while the short consumes the high.
- AC-06: Holdout and full-history trade counts, identity fields, `pnl_base`, and gross `r` remain
  exact row-for-row; `is_long` and `swap_r` are allowed and expected to change.
- AC-07: Record before/after total `swap_r`, holdout max drawdown, maximum synchronized daily loss,
  all four P-11 breach probabilities, and internal trailing/any upper-bound gate outcome.
- AC-08: Every locally executable cumulative R3 gate passes; Linux Critical mutation is recorded
  as blocked by the Actions quota through 2026-08-01, never pending or passed.

## Invariants

- INV-01: The opening-side field is the sole authoritative direction producer for extracted
  Nautilus positions.
- INV-02: `r` remains gross price R, `swap_r` remains separate realized carry, and
  `net_r = r + swap_r` remains the statistical stream.
- INV-03: Swap is booked once at close; direction changes its signed broker term, not realization
  timing.
- INV-04: Synchronized H4 replay marks longs at interval lows and shorts at interval highs, then
  P-10/P-11 consume the resulting shared diagnostics.
- INV-05: Trade count, ordering, timestamps, prices, gross PnL, gross R, stops, and selection
  configuration do not change.
- INV-06: Internal limits remain 2.5%/5%, prop limits remain 3%/6%, and no gate or confidence bound
  is weakened.
- INV-07: No live code or running process is invoked, restarted, queried, or changed.

## Artifact-integrity exception

The #57 byte-identity invariant is suspended for this package only. Both trade CSVs contain
`is_long` and `swap_r`, so a correct fix must change their bytes. Acceptance instead requires exact
row identity and exact direction-independent columns (`market`, timestamps, prices, stop,
`pnl_base`, and gross `r`) while explicitly measuring the corrected categorical and swap columns.
No later package inherits this exception automatically.

## Stage-1 consequence

The complete nine-hour Stage-1 matrix is deliberately not rerun here. Its net return stream changes
where BUY and SELL swap terms differ, so the P-01 DSR/train-length conclusion, #58's restored
candidate effect, candidate daily/window streams, SPA/Romano-Wolf/MCS evidence, and auto-selection
must be re-derived in the next frozen full research run. Cached Stage-1 selection evidence is not
certified by this package.

## Assumptions

- Nautilus closed-position reports retain opening direction in `entry` as `BUY`/`SELL`; this was
  directly measured on current full-history runs and confirmed by Claude against deployed
  artifacts.
- Stage 3/4 may be rerun on a copied legacy baseline solely to measure the already-contaminated
  deployed configuration; the result is diagnostic and cannot restore clean holdout status.

## Open questions

None. Jan ratified the source field, fail-closed behavior, temporary artifact exception, expected
metric movement, Stage-1 deferral, and draft-only delivery.

## Expected artifacts

- Corrected `research/portfolio/trades.py::timed_trades_from_report`.
- Red-first producer and synchronized-H4 integration guards.
- Focused mutation/impact registration for the direction producer.
- Generalized stable-wrong-category finding in `.ai/quality/finding-patterns.toml`.
- Complete R3 task artifacts under `.ai/tasks/ISSUE-99/`.
- Ignored Stage-3/4 candidate and before/after measurement evidence under `reports/research/`.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because `research/portfolio/trades.py` owns the
out-of-sample trade stream, swap attribution, H4 path direction, selection/execution parity, and
reported-result integrity.

## Human decisions required

Jan has decided the source field, exception boundary, required numerical disclosures, deferred full
Stage-1 rerun, draft-only PR, and merge authority. No methodology choice remains delegated.
