# Impact analysis

## Direct impact

- `.ai/quality/risk-classes.toml` is the authoritative model read by
  `scripts.quality.classify.load_model`.
- `scripts.quality.classify.classify_path` applies the unchanged max-wins matcher to the changed
  rules.
- `docs/engineering/risk-classes.md` documents the affected categories without duplicating the
  exhaustive glob list.
- `tests/test_quality_classify.py` binds all five acceptance criteria and the complete tracked-tree
  comparison.
- `tests/test_engineering_docs.py` adds only three R3 guard paths and changes the architecture-map
  representative expectation from R0 to R2. This keeps the edit local to the classification region
  also touched by unmerged issue #107 elsewhere in the file.

## Transitive impact

- `scripts.quality.pr_ready` uses the classifier result to select cumulative mandatory gates.
- `scripts.quality.impact` uses changed paths and risk classification when recommending checks.
- `scripts.quality.hooks.decisions` and the Claude Bash hooks consume readiness/classification at
  commit, push, and PR boundaries.
- CI task-artifact and PR-evidence jobs execute those quality tools.
- Every future `.claude/**` change receives R3 gates; future architecture-map changes receive at
  least R2 gates.
- No caller receives a changed Python API or classifier algorithm.

## Critical dependencies

- `.ai/quality/risk-classes.toml` is itself R3 and is the only changed policy input.
- `scripts/quality/classify.py` remains the single matcher; no second matcher is introduced.
- The tracked-tree invariant calls the production `classify_path` for both reconstructed pre-change
  and committed post-change models.
- `tests/test_engineering_docs.py` remains the concrete R3 guard list.

## Classification inventory

The pre/post comparison enumerates every path returned by `git ls-files -z`. It rejects:

- any class decrease;
- any increase outside `.claude/**` and `docs/architecture.md`;
- an empty or implausibly small tracked inventory;
- loss of either the exact settings rule or the new `.claude/**` catch-all;
- any remaining duplicate R2 workflow rule.

The duplicate `.github/workflows/**` R2 rule is also added back in isolation and compared across the
complete tracked inventory. A non-empty delta blocks the change.

## Documentation audit

Repository search found the old concrete `docs/architecture.md -> R0` statement only in classifier
tests. The prose risk-class document describes categories rather than an exhaustive glob list and
needs the `.claude/**` and architecture-map categories added. README, AGENTS, CLAUDE, and the
constitution link to the architecture and risk documents but do not state the old class.

## Unknown or dynamic edges

- Git-tracked paths are dynamic by design and therefore read from Git rather than copied into a
  fixture.
- Semantic upgrades remain a human obligation above the path-derived minimum; this issue does not
  change that rule.
- No runtime reflection, plugin loading, MT5 terminal, runner, market data, or generated research
  artifact is involved.
