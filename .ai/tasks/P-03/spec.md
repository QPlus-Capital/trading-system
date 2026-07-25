# P-03: Persist canonical candidate return streams

## Problem

Stage 1 discards the aligned net return streams needed to reproduce and calibrate selection-bias
statistics, leaving downstream methodology packages to reconstruct evidence from incomplete
aggregates.

## Goal

Persist four deterministic, lineage-bound artifacts for each complete top-level
`(variation, train_months)` candidate without changing any existing result:
`candidate_daily_returns.csv`, `candidate_window_returns.csv`,
`candidate_market_window_returns.csv`, and `candidate_metadata.json`.

## Non-goals

- Changing Stage-1 scoring, DSR, PBO, Sharpe, WFE, ranking, selection, universe filters, holdout,
  Stage-3 extraction, sizing, or any live path.
- Promoting the 24 inner SL/TP combinations to top-level candidates.
- Recomputing spread, commission, slippage, swap, gross R, or net R.
- Making P-04 or any statistical decision consume the artifacts.
- Committing generated data under `reports/`.

## Behavioural requirements

- A formal candidate is exactly `(variation, train_months)`. The production robustness config
  therefore defines 12 x 3 = 36 formal candidates and records its five manual trials separately.
- The chosen Stage-1 path carries the exact P-01 `net_r` events produced by
  `stage1_trade_returns`; persistence never derives trade returns from PnL, price, or costs again.
- Daily portfolio return is the flat sum of trade `net_r` at
  `STAT_RISK_FRAC = Decimal("0.0018")`.
- Daily rows use the 16:15 America/Chicago loss-day axis and contain every day, including
  zero-trade days, over the common day intersection.
- Only window labels shared by every persisted candidate and every configured market are kept.
  Every candidate column has the same ordered dates and windows.
- A candidate missing any configured market is omitted from every stream artifact and recorded as
  excluded metadata; it is never represented by zero-filled market data.
- Candidate-window returns and market-window returns are sums of the same canonical trade events.
  Exact Decimal invariants bind daily totals, window totals, and market-window totals.
- Stage 1 copies the four immutable pre-filter artifacts into the research run. Selection and
  universe filtering only read other artifacts and cannot rewrite them.
- Metadata records candidate definitions, configured formal/manual trial counts, markets,
  common dates/windows, risk fraction, cost semantics, observation counts, source lineage, and
  lineage-format content hashes for the three CSV artifacts.

## Acceptance criteria

- AC-01: The production configuration yields 36 unique formal candidate IDs and metadata records
  36 formal plus 5 manual trials.
- AC-02: Daily output uses the 16:15 Chicago axis and explicitly fills every zero-trade day.
- AC-03: For every candidate, the exact Decimal sum of daily returns equals the exact Decimal sum
  of candidate-window returns.
- AC-04: For every candidate and window, the exact Decimal sum across market-window rows equals
  the candidate-window cell, including net R, return, and trade counts.
- AC-05: Every candidate column shares one ordered date grid and one ordered window grid.
- AC-06: A candidate missing one configured market is absent from all three streams and is named
  in metadata; no cell is silently zero-filled for the missing market.
- AC-07: The daily CSV converts directly to `candidate -> daily float array` input accepted by
  P-04 `select_block_length`.
- AC-08: Metadata hashes use the lineage SHA-256 convention and change when an artifact changes.
- AC-09: Stage 1 copies the four artifacts byte-for-byte into the run directory, and a subsequent
  universe-selection pass cannot rewrite them.
- AC-10: Persistence leaves `study.csv`, `ranking.csv`, and `overfitting.json` byte-identical.
- AC-11: A zero-threshold regression of an unchanged run reports zero drift on every bounded
  metric and byte-identical `full_history_trades.csv`.
- AC-12: `just check` and every required R3 gate pass.

## Invariants

- INV-01: `r` stays gross, `swap_r` stays separate, and `net_r = r + swap_r` remains the sole
  statistical return stream.
- INV-02: No cost, trade return, existing metric, ranking, selection, or portfolio number changes.
- INV-03: Formal candidate identity is `(variation, train_months)`; inner grid combinations remain
  an internal training procedure.
- INV-04: Incomplete candidates fail closed by absence across all stream artifacts.
- INV-05: All aggregation is exact over one canonical event set; no aggregate reads a rounded
  sibling artifact as its source.
- INV-06: Pre-filter evidence is immutable after Stage 1 and independent of market selection.
- INV-07: Generated reports remain gitignored; only code, tests, docs, and task evidence are
  committed.
- INV-08: No live runner, live trade, holdout decision, or account/risk path is touched.

## Risk class

R3. The classifier assigns R3 because the change touches Stage-1 selection output, continuous
walk-forward attribution, lineage, and result integrity.

## Scope

- Add one research-engine module for deterministic candidate-stream construction and persistence.
- Carry canonical chosen-path net-R events through the existing walk-forward result.
- Wire study creation, study provenance, and Stage-1 run publication to the four artifacts.
- Update architecture documentation and focused tests.

## Assumptions

- A daily portfolio return is the additive flat-risk return across all trades and configured
  markets; no cross-market averaging or compounding is applied.
- Exact equality is evaluated by parsing the canonical decimal strings written to CSV.
- Existing studies without the new optional artifacts remain inspectable; newly computed studies
  always produce and bind all four artifacts.

## Open questions

None. Candidate identity, risk fraction, trial counts, common-intersection policy, loss-day axis,
and the requirement of no numerical movement are fixed by issue #45.

## Human decisions required

Jan retains merge authority. Claude performs the independent doubly rigorous review. No
methodology, go-live, architecture, or risk decision remains open for implementation.
