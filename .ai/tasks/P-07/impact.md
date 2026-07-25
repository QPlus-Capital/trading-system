# Impact analysis

## Classification

Planned-path classification is R3. `research/engine/mcs.py` defines statistical selection
evidence, `research/stages/edge.py` publishes it, and `docs/methodology.md` defines its meaning.

## Direct impact

- Add a pure Hansen-Lunde-Nason MCS implementation consuming the P-03 daily candidate matrix.
- Expose the existing P-05 paired-bootstrap index and long-run-variance helpers for direct reuse.
- Add one lineage-bound edge-stage artifact, `mcs.json`.
- Add statistical calibration, stage-path tests, and focused mutation scope.

## Input and evidence path

1. P-01 produces the canonical Stage-1 close-time `net_r` stream.
2. P-03 persists the aligned 36-column flat-risk daily matrix in
   `candidate_daily_returns.csv` and binds its content hash in `candidate_metadata.json`.
3. P-05 strictly loads those bytes and confirms all 36 formal candidates.
4. P-05 selects P-04's block length and draws paired stationary-bootstrap day indices.
5. P-07 receives the same matrix, selected length, replications, and seed; it reuses the same
   index and stationary-bootstrap variance kernels.
6. P-07 negates daily returns into losses, computes the full range-elimination path, and writes
   `mcs.json` atomically with the edge stage.
7. P-08, not P-07, will consume verified membership.

## Coupled quantities and every consumer

- **Candidate daily return bytes:** produced only by P-03; read by P-05/P-07 through
  `load_candidate_family`. P-07 never reconstructs trades or returns.
- **Candidate identity:** P-03 metadata/header, P-05 expected-family validation, P-07 artifact
  counts/identities, future P-08 membership consumer. All remain the same 36 formal candidates.
- **Block length:** P-04 selector -> P-05 selected SPA result -> edge passes that exact length to
  P-07 -> MCS artifact. P-07 does not select a second length.
- **Bootstrap draw:** P-04 `stationary_bootstrap` -> P-05 shared index helper -> SPA and MCS use the
  same `(T, L, B, seed)` draw.
- **Long-run variance:** P-05 helper -> SPA candidate scores and P-07 pair-difference scores. The
  helper's existing `Var(sqrt(n) mean)` unit is preserved.
- **MCS membership:** produced and lineage-bound by edge; no current stage consumes it. P-08 is the
  first authorized consumer.

## Existing consumers that must not move

- P-01/P-03 Stage-1 net-return scoring, persisted bytes, hashes, grids, and metadata.
- P-04 block-length selection and stationary-bootstrap behavior.
- P-05 SPA statistics, sensitivities, p-values, and fail-closed Stage-2 gate.
- Existing DSR, PBO, eligibility, consistency, ranking, and forced-selection semantics.
- Stage-3 trade extraction, costs, sizing, limits, factsheet, and full-history metrics.
- Every live, monitoring, signal, account, order, and risk-control path.

## Transitive impact

P-07 adds evidence only. Generated edge manifests gain `mcs.json`; no selection, portfolio, verdict,
monitoring, or live caller reads it in this package.

## Files and lifecycle

- `research/engine/mcs.py` — new strict MCS computation and serialization.
- `research/engine/spa.py` — public wrappers over the existing P-04 index and P-05 variance kernels;
  SPA behavior must remain bit-identical.
- `research/stages/edge.py` — compute and atomically publish `mcs.json`.
- `docs/architecture.md` / `docs/methodology.md` — module map and exact evidence definition.
- Focused tests, mutation configuration/baseline, critical dependency map, and task artifacts.

## Artifact and lineage impact

`mcs.json` is derived evidence, not a new return stream. The edge-stage manifest hashes it through
`ResearchRun.stage`; stale, missing, or modified bytes fail provenance verification. No generated
report is committed.

## Failure and boundary cases

- Missing or malformed P-03 artifacts fail in the reused P-05 loader.
- Empty, unequal-length, non-finite, or fewer-than-three-observation families fail closed.
- A singleton is valid and returns p-value 1.
- Exact-identical pair streams have zero score; unequal effectively deterministic pairs fail closed.
- Invalid `L`, replications, seed, alpha, confidence, probabilities, ranks, identities, or flags
  cannot deserialize as valid evidence.
- Exact statistic/elimination ties are resolved by candidate identifier.

## Critical dependencies

- `research.engine.candidate_returns` owns serialized return semantics.
- `research.engine.spa` owns strict loading, shared P-04 index draws, variance, and Monte Carlo.
- `research.portfolio.resample` remains the only block selector and stationary bootstrap.
- `research.stages.lineage.ResearchRun` remains the only publication/verification path.

## Unknown or dynamic edges

- Generated `reports/research/run_*` data are gitignored and not statically enumerable.
- The observed MCS size is data-dependent and may legitimately be all 36 candidates.
- P-06 may later expose overlapping P-05 helper APIs; if it lands first, the branches must be
  reconciled by preserving one shared implementation rather than duplicating helpers.

## Numerical impact

Expected effect on every existing trading and research number: exactly none. New values are MCS
statistics, set p-values, model p-values, elimination order, and membership flags. Any movement in
existing study, SPA, ranking, selection, trade, return, drawdown, or portfolio values is blocking.

## Initial impact command

The explicit planned-path classifier reports R3. `just impact origin/main` is recorded after this
specification exists and rerun over the final diff.
