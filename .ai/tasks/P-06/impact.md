# Impact analysis

## Classification

Planned-path `scripts.quality.classify` assigns R3 to
`research/engine/romano_wolf.py`, `research/engine/spa.py`,
`research/stages/edge.py`, methodology documentation, and critical quality configuration.

## Direct impact

- Expose existing P-05 validation, paired-index, long-run-variance, and studentized-score kernels
  as the shared statistical resampling boundary.
- Add pure Romano-Wolf computation and validated serialization.
- Add `romano_wolf.json` to the atomic edge-stage publication.
- Add critical mutation and dependency-map coverage.

## Input and artifact path

1. P-03 persists the 36 aligned daily net-R candidate streams.
2. `edge._spa_family` validates the complete formal family once.
3. P-05 selects P-04's production block length and analyzes the family.
4. P-06 receives the same family, selected length, replication count, and seed.
5. Both call the same P-04-backed bootstrap-index and long-run-variance kernels.
6. P-06 performs the ordered remaining-family stepdown and writes `romano_wolf.json`.
7. The edge manifest content-hashes the new artifact. P-08 will be its first consumer.

## Existing consumers that must not move

- P-03 candidate daily/window/market-window streams and metadata.
- P-04 block-length selection and stationary-bootstrap implementation.
- P-05 SPA selected and sensitivity results, serialization, and Stage-2 family gate.
- Existing edge ranking, DSR, PBO, structure gates, and auto-pick display.
- Stage-2 selection, Stage-3 portfolio, Stage-4 verdict, all reported metrics, and all live paths.

## Coupled quantities

- Matrix: SPA and Romano-Wolf receive the same ordered candidate mapping.
- Sample size: both derive it from that matrix; no independent date or count source.
- Block length: Romano-Wolf receives `spa_analysis.selected_block_length`.
- Replications and seed: both receive `SPA_REPLICATIONS` and P-04's default seed.
- Variance and studentization: both call the same P-05 helpers.
- Gate boundary: adjusted p-value is converted through `Decimal(str(value))` before comparison.

## Transitive impact

The edge manifest gains one output and downstream lineage verification sees that output hash. No
downstream logic reads its contents in P-06, so selection and every numerical result remain
unchanged. A later P-08 change will make candidate eligibility load-bearing.

## Failure and boundary cases

- Empty, unequal-length, non-finite, too-short, zero-long-run-variance, or incomplete formal
  families raise before publication.
- Invalid block length, replications, or seed fail before resampling.
- Exact statistic ties resolve lexically and remain deterministic.
- Finite Monte Carlo p-values cannot be zero.
- Deserialization rejects duplicate/missing candidates, non-monotone adjusted p-values,
  adjusted p-values below unadjusted values, inconsistent flags, or count/order disagreement.
- Failure after stage entry publishes neither the artifact nor a completion manifest.

## Files and lifecycle

- `research/engine/romano_wolf.py`: new stepdown engine and artifact schema.
- `research/engine/spa.py`: shared P-05 statistical kernels; SPA output must remain unchanged.
- `research/stages/edge.py`: compute and atomically publish additive evidence.
- `docs/architecture.md`, `docs/methodology.md`: module map and method.
- Tests, mutation TOML, critical dependencies, mutmut selection, and P-06 task evidence.

## Numerical impact

Expected effect on every existing historical, selection, portfolio, and live number: exactly none.
Only new observed statistics, p-values, and eligibility flags appear. Any existing-number drift is
a blocking finding.

## Unknown or dynamic edges

Generated `reports/research/run_*` directories are gitignored and cannot be statically enumerated.
No code-level dynamic edge is expected; final `just impact origin/main` must confirm the complete
diff and full pytest remains mandatory.

## Initial impact command

The explicit planned-path classifier reports R3 and all 14 cumulative gates. Final impact analysis
is rerun after the implementation exists.
