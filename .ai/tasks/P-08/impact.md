# Impact analysis

## Classification

The explicit planned-path classifier reports R3. Stage-1 diagnostics, Stage-2 selection,
methodology config, lineage-bound evidence, and Stage-4 deployability are result-integrity paths.

## Dependency status

P-05, P-06, and P-07 are merged to `main`. Their artifacts and strict APIs exist:

- `spa.json` -> `SpaAnalysis.from_dict`;
- `romano_wolf.json` -> `RomanoWolfAnalysis.from_dict`;
- `mcs.json` -> `McsResult.from_dict`.

P-08 consumes these APIs and must not recompute their statistics.

## Direct impact

- Rebuild Stage-1 DSR and PBO as synchronized, labelled diagnostics.
- Replace automatic Stage-2 selection with the SPA gate, Romano-Wolf/MCS intersection, existing
  structure constraints, and the configured complexity-first ordering.
- Update Stage-4's deployability re-check to match the new Stage-2 evidence contract.
- Preserve the forced-selection path and every downstream trade/portfolio calculation.

## Coupled quantity: synchronized candidate-window returns

Every producer and consumer that must move together:

1. `research/engine/continuous.py::window_returns` attributes net Stage-1 returns to labelled
   walk-forward windows.
2. `research/engine/characterize.py::_run_task` records per-market `window_oos` and
   `candidate_windows`.
3. `research/engine/candidate_returns.py::write_candidate_artifacts` intersects candidates,
   markets, and labels and writes `candidate_window_returns.csv`.
4. `research/engine/characterize.py::_write_reports` currently pools unsynchronized streams for
   DSR and uses obsolete candidate/variation PBO paths; it must instead use the same synchronized
   36-column window matrix semantics.
5. `ranking.csv` receives candidate diagnostic fields; `overfitting.json` receives study-level
   DSR/PBO inputs and labels.
6. `research/stages/edge.py` copies and displays those diagnostics.
7. `research/stages/select.py` records but does not gate on them.
8. `research/stages/verdict.py` displays but does not gate on them.

Daily SPA/Romano-Wolf/MCS inputs remain untouched.

## Coupled quantity: eligibility and selection

Every selection consumer that must move together:

- `research/stages/edge.py::ranking` owns completeness, positive-market fraction, and
  return/drawdown columns. `dsr_ok` must become a diagnostic label, never eligibility.
- `research/stages/select.py::main` is the authoritative automatic and forced Stage-2 entrypoint.
- `research/stages/universe.py` owns per-config aggregation and per-market universe filtering; its
  return-first structure helper must not remain an alternate automatic path with different order.
- `selection.json` and the select-stage manifest carry the chosen candidate and cumulative evidence.
- `research/stages/verdict.py::selection_is_gated` re-checks deployability and must require
  SPA/Romano-Wolf/MCS/structure evidence while excluding DSR/PBO from the boolean gate.
- `research/stages/portfolio.py` consumes only the selected variation, training length, and markets;
  its trade extraction and outputs must not change.
- Tests in `test_research_stage_lineage.py`, `test_research_stages.py`,
  `test_research_universe_select.py`, and verdict tests encode the old DSR/PBO semantics and need
  synchronized replacement.

## Artifact completeness and lineage

Automatic selection must require verified `edge_ranking.csv`, `spa.json`, `romano_wolf.json`,
`mcs.json`, `ranking.csv`, `overfitting.json`, and the run's anchored config. Artifact candidate
identities must agree exactly. Missing or modified bytes fail through `RunDir.require` and stage
manifest verification before any choice.

Forced selection still reads the anchored study/config and computes its universe, but deliberately
bypasses SPA/Romano-Wolf/MCS/structure/complexity eligibility. Its manifest remains `forced=true`,
which Stage 4 rejects for deployment.

## DSR diagnostic inputs and outputs

- Input shape: common six-month labels by all 36 complete candidates.
- Candidate Sharpe sample: 36 synchronized per-window Sharpes.
- Correlation: mean finite upper-triangle Pearson coefficient, clipped to `[0,1]`.
- Effective trials: real-valued `min(41, 5 + rho_bar + (1-rho_bar)*36)`.
- Variance: sample variance across the 36 synchronized Sharpes.
- Per-candidate evidence: effective DSR, nominal DSR, benchmark(s), observations, skew,
  non-excess kurtosis, threshold label.
- Study evidence: `N_eff`, `rho_bar`, variance, family/candidate counts, manual count, window labels
  or count, and explicit `diagnostic` role.

`research/engine/overfitting.py` currently types trial count as `int`; supporting the specified
real-valued `N_eff` must preserve existing integer callers and add finite/domain guards.

## PBO diagnostic inputs and outputs

Use the same common-window by 36-candidate matrix. The split count is
`min(10, n_windows)` rounded down to even, with existing minimum-validity behavior. Remove the old
per-training-length grid-candidate and variation fallbacks from the reported decision diagnostic;
no silent alternative matrix is permitted.

## Configuration route

`research/config/robustness.py::VARIATIONS` is the only formal variation registry. No complexity
mapping exists. The config is loaded by edge/select through `load_config_module` and is lineage
hashed. Adding the Jan-approved mapping there makes any later edit a new content identity.

## Numerical and live impact

- Expected unchanged: `study.csv`, candidate return streams, trades, full-history/holdout returns,
  costs, drawdowns, sizing, factsheets, signals, orders, and live behavior.
- Expected changed: DSR/PBO diagnostic values and schemas, diagnostic labels, automatic selection,
  selection/verdict gate manifests, and possibly whether automatic selection succeeds.
- `full_history_trades.csv` must remain byte-identical for an unchanged forced validation run.
- No `live/**`, broker, instrument, signal, order, sizing, or risk-control file is in scope.

## Transitive impact

Automatic Stage-2 output may choose a different `(variation, train_months)` candidate or fail
closed, and Stage 4 will enforce that exact evidence. Historical trades, return streams, portfolio
metrics, live configuration, and execution behavior remain unchanged.

## Critical dependencies

- `research.engine.candidate_returns` owns the synchronized 36-candidate evidence.
- `research.engine.spa`, `research.engine.romano_wolf`, and `research.engine.mcs` own strict
  parsing and statistical results; P-08 consumes rather than recomputes them.
- `research.stages.lineage.RunDir` and stage manifests must verify every consumed artifact.
- `research.config.robustness` must own the Jan-approved pre-registered complexity mapping.

## Failure modes

- Joining Romano-Wolf/MCS by variation while dropping training length.
- Accepting partial or disagreeing evidence families.
- Applying return before complexity or using pandas' incidental row order.
- Leaving an alternate return-first selector callable from the real entrypoint.
- Demoting DSR/PBO in Stage 2 but leaving them deployability gates in Stage 4.
- Letting forced selection become deployable because it bypassed the new fields.
- Computing DSR/PBO from daily rows, pooled instruments, or separate training-length matrices.
- Treating NaN correlation or zero-variance streams as zero evidence instead of failing closed.

## Unknown or dynamic edges

- Generated research runs are gitignored and cannot be statically enumerated.
- A clean historical regression run is outside this code package unless Jan separately requests
  it; executable fixtures must prove no trade-return path changes.
- The observed SPA/Romano-Wolf/MCS intersection and resulting automatic choice are data-dependent.

## Initial impact command

The planned-path classifier reports R3. The final committed branch diff is rerun through
`just impact` because the repository impact tool intentionally considers committed branch paths.
