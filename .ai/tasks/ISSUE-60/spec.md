# ISSUE-60: Preserve gross and net returns in market trades

## Problem

`research/portfolio/stats.py::_market_trades` overwrites gross `r` with swap-adjusted return when a
broker supplies a swap specification, destroying the canonical gross/net decomposition required by
constitution section 4.

## Goal

Keep gross price `r` recoverable, attach realized close-time `swap_r` separately, and derive
`net_r = r + swap_r` without changing any deployed Stage-1 through Stage-4 result.

## Non-goals

- Changing swap rates, rollover calendars, trade extraction, signals, sizing, selection, risk
  limits, stages, factsheets, or live execution.
- Correcting `swap_analysis.market_swaps` direction inference; that separate metric-moving defect is
  tracked in issue #95.
- Changing `research/portfolio/trades.py` or the already-canonical Stage-1 return path.
- Running or interacting with either live runner.
- Opening a pull request while the GitHub Actions quota is exhausted.

## Behavioural requirements

- `_market_trades` always computes `r` from the engine's realized PnL before swap.
- When a broker is supplied, `_market_trades` adds `swap_r`; a missing market swap specification
  produces an explicit zero column rather than changing gross `r`.
- When a broker is supplied, `_market_trades` derives `net_r` exactly as `r + swap_r`.
- Swap is attached once to the closed trade and is never marked through the holding period.
- `swap_analysis.main` continues to request and consume gross `r`, then computes its independently
  refreshed live-snapshot swap leg exactly once.
- The deployed portfolio path remains `research/portfolio/trades.py` and does not call
  `_market_trades`.

## Acceptance criteria

- AC-01: A swap-bearing broker fixture returns unchanged gross `r`, non-zero separate `swap_r`, and
  exact `net_r = r + swap_r`.
- AC-02: A broker without a market swap specification returns `swap_r == 0` and `net_r == r`.
- AC-03: Every repository caller of `_market_trades` is classified as gross or net in `impact.md`
  and reads the intended column without double-counting swap.
- AC-04: The Stage-1/2/3/4 and deployed portfolio call graph contains no `_market_trades` edge; no
  reported trading number changes.
- AC-05: A zero-tolerance regression reports no unexpected changes, and both portfolio trade CSV
  files are byte-identical.
- AC-06: Every locally executable cumulative R3 gate passes; Linux mutation is recorded as blocked
  by the GitHub Actions quota through 2026-08-01, never as passed or pending.

## Invariants

- INV-01: `r` is gross price R, `swap_r` is separate realized carry, and `net_r = r + swap_r`.
- INV-02: Swap is signed, direction-aware, and realized once at close.
- INV-03: No deployed research number, trade stream, live path, limit, threshold, or gate changes.
- INV-04: Money, prices, and quantities retain their existing Decimal/Nautilus boundaries; this
  column-attribution fix introduces no new float money arithmetic.
- INV-05: No live runner is stopped, restarted, queried, or otherwise touched.

## Assumptions

- `_market_trades` remains the full-history helper for the operator-only swap analysis surface.
- The caller audit is complete because repository-wide static search finds one direct call in
  `research/portfolio/swap_analysis.py::main` and no dynamic dispatch.

## Open questions

None.

## Expected artifacts

- Corrected `research/portfolio/stats.py`.
- Corrected canonical-return wording in `core/broker.py` and a generalized permanent guard entry
  in `.ai/quality/finding-patterns.toml`.
- Focused behavioural guards in `tests/test_research_stats.py`.
- R3 task specification, impact analysis, test plan, adversarial review, and truthful local
  evidence under `.ai/tasks/ISSUE-60/`.
- Ignored zero-tolerance regression evidence under `reports/research/regression/`.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 to `research/portfolio/stats.py` because it owns
per-trade R and swap attribution and therefore result-stream integrity.

## Human decisions required

Jan fixed the canonical gross/separate-swap/net convention, exact regression thresholds, build-only
delivery, and no-PR boundary while Actions are unavailable. Jan alone decides review and merge
after infrastructure recovers.
