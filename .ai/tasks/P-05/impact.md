# Impact analysis

## Classification

Planned-path classification is R3. `research/stages/edge.py` publishes Stage-1 selection evidence,
`research/stages/select.py` controls automatic structure selection, and `docs/methodology.md`
defines the decision protocol.

## Direct impact

- Add a pure Hansen SPA implementation consuming the P-03 daily candidate matrix.
- Add one lineage-bound edge-stage artifact, `spa.json`.
- Add one cumulative fail-closed family gate to automatic Stage-2 selection.
- Add statistical calibration and stage-path tests plus mutation scope for the new critical code.

## Input and decision path

1. P-01 produces the canonical Stage-1 close-time `net_r` stream.
2. P-03 persists the aligned 36-column flat-risk daily matrix in
   `candidate_daily_returns.csv` and binds its content hash in `candidate_metadata.json`.
3. P-05 strictly loads those bytes and confirms metadata declares and persists all 36 formal
   candidates.
4. P-04 `select_block_length` receives the same candidate-to-daily-array mapping.
5. P-04 `stationary_bootstrap` generates shared circular stationary-bootstrap row indices; P-05
   applies those identical indices to every candidate.
6. P-05 computes the selected-length and 5/10/20/60 sensitivity SPA results and writes `spa.json`
   atomically in the edge stage.
7. Stage 2 requires the edge manifest's verified `spa.json`. Auto-selection continues only when
   every reported SPA p-value is at most 0.05.

## Existing consumers that must not move

- P-01 Stage-1 net-return scoring, market summaries, window returns, Sharpe, WFE, DSR, PBO,
  ranking, and return/drawdown inputs.
- P-03 construction, bytes, hashes, grids, candidate identity, and metadata.
- P-04 block-length selection and stationary-bootstrap behavior.
- Existing eligibility, DSR, PBO, consistency, risk, and forced-selection semantics except for the
  additive recorded SPA gate.
- Stage-3 trade extraction, costs, portfolio sizing, limits, factsheet, and full-history metrics.
- Every live, monitoring, signal, account, order, and risk-control path.

## Transitive impact

Stage 2's auto-selection outcome may change from selectable to fail-closed because of the new
family gate. A forced exploratory run records the result but retains its existing explicit-override
path. Later universe, portfolio, verdict, and reporting stages may observe that no automatic
selection artifact exists after a failed gate, but no numerical calculation inside those stages is
changed.

## Files and lifecycle

- `research/engine/spa.py` — new strict loader, paired bootstrap, studentized SPA, recentering,
  sensitivity, serialization, and validation.
- `research/stages/edge.py` — compute SPA from the source P-03 artifacts and publish `spa.json`
  atomically with existing edge evidence.
- `research/stages/select.py` — require and validate `spa.json`, record it in selection evidence,
  and fail closed for auto-selection.
- `docs/architecture.md` and `docs/methodology.md` — module map and exact gate definition.
- Focused tests and critical mutation configuration.

## Artifact and lineage impact

`spa.json` is derived evidence, not a new return stream. The edge-stage manifest hashes it with the
existing lineage convention. Stage 2 obtains it only through `ResearchRun.require`, so stale,
missing, or modified bytes fail provenance verification. No generated report is committed.

## Failure and boundary cases

- Missing CSV or metadata, invalid UTF-8/CSV/JSON, duplicate or empty candidate names, invalid or
  non-consecutive dates, unequal column lengths, non-finite values, and candidate-count mismatch
  raise before a gate can pass.
- Fewer than three observations, fewer than two bootstrap replications, invalid block lengths, or
  invalid seed/replication metadata raise.
- Zero-variance non-positive candidates cannot create positive evidence; a deterministic positive
  candidate represents certain superiority and yields an infinite observed score with bootstrap
  p-value zero.
- Selected and sensitivity p-values are each independently decisive; one failure makes the family
  gate false.
- A forced variation can expose a failed test as exploratory evidence but cannot label it passed.

## Critical dependencies

- `research.engine.candidate_returns` owns P-03 serialization semantics.
- `research.portfolio.resample.select_block_length` and `stationary_bootstrap` remain the only
  dependence-selection and bootstrap conventions.
- `research.stages.lineage.ResearchRun` remains the only stage publication and verification path.
- `research.stages.select` remains the sole structure-selection command.

## Unknown or dynamic edges

- Generated `reports/research/run_*` data are gitignored and not statically enumerable.
- The selected P-04 block length depends on the observed daily family. The deterministic procedure,
  not a guessed length, is fixed.
- The current run may fail SPA. That changes deployability, not any measured trading number, and is
  explicitly an expected possible outcome.

## Numerical impact

Expected effect on all existing trading and research numbers: exactly none. New outputs are SPA
statistics, p-values, block lengths, and a boolean gate. Any movement in existing study, ranking,
trade, return, drawdown, or portfolio values is a blocking finding.

## Initial impact command

The planned-path classifier reports R3 for the selection, methodology, lineage, and quality paths.
`just impact origin/main` is recorded after the specification exists; the final command is rerun
over the complete diff.
