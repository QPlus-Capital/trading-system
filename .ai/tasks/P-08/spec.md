# P-08: Make family evidence load-bearing in selection

## Problem

Stage 2 still blocks on methodologically unsuitable DSR/PBO diagnostics and does not consume the
lineage-bound SPA, Romano-Wolf, and MCS family evidence that now defines decision-grade eligibility.

## Goal

Replace automatic structure selection with the exact P-05/P-06/P-07 evidence intersection and
pre-registered complexity-first ordering, while rebuilding DSR/PBO as synchronized diagnostics and
preserving the forced-selection path.

## Non-goals

- Recomputing SPA, Romano-Wolf, MCS, candidate returns, trades, costs, or portfolio metrics.
- Changing any statistical threshold, holdout rule, market-universe threshold, signal, live config,
  order path, sizing rule, or risk limit.
- Inventing a complexity score from parameter counts, enabled filters, names, or observed results.
- Using DSR or PBO to block selection or a verdict.
- Changing the forced `--variation` behavior beyond diagnostic labels in its manifest.

## Behavioural requirements

- Recompute DSR and PBO only from the synchronized P-03 candidate-window artifact and expose them
  as labelled diagnostics without a selection or deployability veto.
- Require lineage-verified SPA, Romano-Wolf, and MCS evidence before automatic selection.
- Apply the fixed eligibility intersection and deterministic complexity-first tie-break exactly in
  the order specified below.
- Preserve forced selection as an explicit exploratory bypass that cannot become deployable.
- Fail closed on missing configuration, evidence, identity agreement, or threshold inputs.

## Statistical specification

- The formal family is exactly the 36 complete P-03 candidates, identified as
  `(variation, train_months)` and synchronized on the common six-month window labels persisted in
  `candidate_window_returns.csv`.
- Compute the upper-triangle mean Pearson correlation across the 36 synchronized candidate
  streams, rejecting missing, duplicate, non-finite, incomplete, unequal-length, or zero-variance
  inputs. Clip the mean to `[0, 1]` and call it `rho_bar`.
- Use five manual trials and
  `N_eff = min(41, 5 + rho_bar + (1 - rho_bar) * 36)`. `N_eff` is a real-valued effective count,
  is capped at 41, and is monotonically non-increasing in `rho_bar`.
- Compute all 36 candidate Sharpes on those same synchronized windows and use their sample
  variance (`ddof=1`). For every candidate report DSR at `N_eff` and nominal `N=41`, together with
  `N_eff`, `rho_bar`, variance, expected-max-Sharpe benchmark, observation count, sample skew, and
  non-excess kurtosis. `DSR >= Decimal("0.90")` remains a labelled diagnostic threshold only.
- Build PBO rows from the common six-month windows and columns from all 36 complete candidates in
  one matrix. Instruments are already aggregated in P-03 and all training lengths compete
  together. Use the largest even split count no greater than `min(10, n_windows)`. A missing or
  unusable diagnostic is labelled unavailable; it does not become a selection pass or gate.
- Automatic selection first requires complete, lineage-verified `spa.json`,
  `romano_wolf.json`, and `mcs.json` whose candidate identities agree exactly with each other and
  with the ranking rows. SPA must pass at `p <= Decimal("0.05")`.
- Candidate eligibility is the exact intersection, in this order: Romano-Wolf adjusted
  `p <= Decimal("0.05")`; MCS membership at 90%; complete market cells; positive mean result on at
  least 90% of markets; mean return/drawdown at least 85% of the best.
- When an intersection step empties the running set, fail closed and name that exact criterion.
  Never widen back to an earlier set.
- Order the non-empty final set by lowest pre-registered complexity, then higher mean net return,
  then training length preference `36, 24, 18`, then lexical variation name. Selection is
  deterministic.
- Forced `--variation` continues to choose that variation's highest-return training length and
  bypass every automatic eligibility/complexity rule. It remains exploratory and cannot support a
  deployable verdict.

## Acceptance criteria

- AC-01: A complete run whose SPA p-value exceeds 0.05 produces no automatic selection regardless
  of ranking returns.
- AC-02: Missing, malformed, stale, identity-inconsistent, or incomplete SPA/Romano-Wolf/MCS
  evidence fails closed.
- AC-03: Every eligibility step is applied in the specified order; when one empties the set, the
  error names that criterion.
- AC-04: An end-to-end tie fixture proves complexity, return, training preference, and lexical name
  are applied in exactly that order.
- AC-05: DSR below 0.90 and PBO above 0.20 do not block automatic selection and are labelled
  diagnostics in artifacts and operator output.
- AC-06: `N_eff` uses all 36 synchronized streams, is capped at 41, and is monotonically
  non-increasing in `rho_bar`.
- AC-07: DSR diagnostic evidence contains effective and nominal values plus every required input
  and shape statistic.
- AC-08: PBO uses one common-window by 36-candidate matrix and the largest permitted even split
  count.
- AC-09: Repeated selection from identical bytes is bit-for-bit deterministic.
- AC-10: The real Stage-2 entrypoint exercises SPA failure, evidence intersection, tie-breaking,
  manifest publication, and diagnostic labels.
- AC-11: Forced `--variation` still bypasses automatic eligibility and complexity and remains
  non-deployable.
- AC-12: Historical trade and return artifacts remain byte-identical; only diagnostic and
  auto-selected-structure outputs may change.
- AC-13: `just check` and every cumulative R3 gate pass.

## Invariants

- INV-01: P-03 candidate window returns remain the sole synchronized DSR/PBO input.
- INV-02: SPA, Romano-Wolf, and MCS artifacts are parsed by their existing strict APIs and agree on
  the exact candidate family.
- INV-03: DSR and PBO are diagnostics only in edge, select, selection manifests, verdicts, and
  reports.
- INV-04: Exact Decimal boundaries govern SPA, Romano-Wolf, MCS, and the diagnostic labels.
- INV-05: Eligibility is an intersection with no fallback, and failures identify the emptying
  criterion.
- INV-06: Complexity precedes return, training length, and name; observed performance never defines
  complexity.
- INV-07: Forced selection bypasses the automatic rule but cannot produce a deployable verdict.
- INV-08: No trade stream, historical metric, signal, order, sizing, risk, or live behavior changes.
- INV-09: Every consumed artifact is lineage-verified before selection.

## Risk class

R3. The planned-path classifier assigns R3 because this changes selection methodology,
result-integrity evidence, configuration promoted toward live, and the verdict's deployability
re-check.

## Scope

- Rebuild synchronized DSR/PBO diagnostics in `research/engine/characterize.py` using the canonical
  P-03 window artifact semantics.
- Make `research/stages/select.py` strictly consume P-05/P-06/P-07 evidence and the configured
  complexity score.
- Update edge diagnostic labels, selection/verdict manifest semantics, methodology/architecture
  documentation, focused tests, critical dependencies, mutation scope, and this task artifact.
- Add the approved pre-registered per-variation complexity configuration.

## Assumptions

- P-05, P-06, and P-07 are merged and their strict deserializers are authoritative.
- Candidate IDs use P-03's existing `<variation>__<train_months>m` convention.
- The separate training-length preference means complexity must not be inferred from observed
  training-window performance.

## Expected artifacts

- Rebuilt `ranking.csv` and `overfitting.json` diagnostic fields.
- A selection manifest containing SPA, Romano-Wolf, MCS, structure-gate, complexity, and diagnostic
  evidence without treating DSR/PBO as gates.
- Red-first statistical, ordering, lineage, verdict, forced-path, and real-entrypoint tests.

## Human decisions

Issue #50 fixes every statistical estimator, threshold, intersection step, and tie-break position.
Jan approved a per-variation complexity score on 2026-07-26, with lower values simpler:
`no_confirms=0`; `no_bb_wpr/no_bb_rsi/no_wpr_rsi=1`; `no_bb/no_wpr/no_rsi=2`; `baseline=3`;
`long_only/ema20/bb30/wpr21=4`. Training length remains the later independent tie-break. Jan
retains methodology, live-money, merge, and go-live authority.

## Open questions

None.

## Human decisions required

No implementation decision remains open. Jan must approve the merge and any later go-live use.
