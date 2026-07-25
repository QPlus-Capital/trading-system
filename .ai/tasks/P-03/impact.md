# Impact analysis

## Classification

Planned-path classification is R3 because `research/engine/characterize.py`,
`research/engine/continuous.py`, `research/engine/walkforward.py`, and
`research/stages/lineage.py` govern Stage-1 selection evidence and result integrity.

## Canonical quantity path

The persisted values must follow this existing P-01 path without a second calculation:

1. `research.engine.continuous.run_continuous_oos` returns the chosen path's closed positions.
2. `stage1_trade_returns` calls Stage 3's authoritative trade extraction, retains gross `r`,
   attaches realized close-time `swap_r`, and creates `net_r`.
3. `stage1_account_returns` scales those same `net_r` rows for existing Stage-1 scoring.
4. `stage1_close_events` supplies `window_returns`, which feeds OOS return, drawdown, WFE,
   Sharpe, DSR/PBO, `study.csv`, `ranking.csv`, and selection.
5. P-03 carries the same chosen rows' close timestamps and `net_r` into a payload; it does not
   read PnL, entry/exit, swap inputs, or rounded Stage-1 aggregates.
6. The new writer scales each event once by the fixed statistical risk fraction and derives all
   three CSV views from that event set.

## Existing consumers that must not move

- Training Calmar and in-sample return in `research/engine/walkforward_runner.py`.
- Chosen OOS window return, trade count, and drawdown in `continuous_walk_forward`.
- Inner-grid `oos_by_combo`, current candidate matrix, Sharpe variance, DSR, and PBO in
  `research/engine/characterize.py`.
- `study.csv`, `ranking.csv`, `ranking_by_train.csv`, `overfitting.json`, and heatmaps.
- Stage-1 edge ranking and Stage-2 structure/universe selection.
- Stage-3 fixed and re-optimized extraction, portfolio metrics, and full-history trades.

## Files and lifecycle

- `research/engine/candidate_returns.py` — new pure aggregation/writer module.
- `research/engine/continuous.py` — expose the already-built chosen-path net-R events without
  changing their scored account-return path.
- `research/engine/walkforward.py` — additive result payload fields with compatibility defaults.
- `research/engine/characterize.py` — retain the payload in memory, write new artifacts only after
  existing reports, and include source lineage in metadata.
- `research/stages/lineage.py` — optionally bind and verify the new study sidecars while preserving
  compatibility with older provenance records.
- `research/stages/edge.py` — byte-copy the pre-filter sidecars into the run's atomic Stage-1
  publication.
- `docs/architecture.md` — module map and artifact-flow update.
- `tests/test_research_candidate_artifacts.py` plus focused lineage/continuous tests.

## Artifact and caller graph

`characterize` writes all four sidecars into its study directory. `edge` copies them into the
`run_*` directory inside its atomic stage writer. Later stages do not receive a writer for these
paths; they remain pre-filter evidence. Study provenance records them when present, metadata hashes
the three CSVs with `lineage.hash_paths`, and the edge manifest hashes the copied outputs.

## Failure and boundary cases

- Duplicate candidate IDs, markets, or window labels raise.
- Non-finite net R, invalid timestamps, empty common candidates/windows/dates, and non-positive
  observation spans raise.
- Missing market rows exclude the whole candidate before any common intersection is computed.
- A market with zero trades remains present and contributes explicit zero returns; it is not the
  same as a missing market row.
- Day conversion is DST-aware through the existing public prop-loss-day function.
- Old studies lacking optional P-03 artifacts remain readable; a new metadata record with a
  missing or changed hashed CSV fails provenance verification.

## Numerical impact

Expected effect on every existing number: exactly none. New files are the only expected output
delta. Any changed existing study, selection, portfolio, or full-history value is a blocking
finding.

## Initial impact command

`just impact origin/main` is recorded before implementation. Static impact is conservative and the
full R3 suite remains mandatory.
