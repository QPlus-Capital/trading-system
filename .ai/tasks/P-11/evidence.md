# Evidence

## HEAD

HEAD: c3c10fda6857a2d542e4f357df778ecf85ad06fb

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Six changed Python files formatted; Ruff, strict mypy, impact analysis, and 177 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 180 files, Vulture, and 1,175 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative impact map selected and passed 177 tests, including stage lineage and real stage entrypoints. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Twenty properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_research_path_risk.py tests/test_research_scenarios.py tests/test_research_regression.py tests/test_research_stage_lineage.py tests/test_research_stages.py` | 0 | 157 tests passed, including the real Stage-4 verdict path with diagnostic `P(profit)=0`. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | P-11 task schema, traceability, risk declaration, evidence, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | Five findings were recorded and fixed or explicitly dispositioned; 22 counterexamples were attempted. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 298 critical invariant tests passed, including live limits, H4 path, scenarios, P-11, regression, and readiness. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation`, run `30244535955` | 0 | Linux/Python 3.13, Mutmut 3.5.0: 3,966/4,358 killed, 392 exact classified survivors, score `0.9101`; the self-test and exact ratchet passed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies` plus SHA-256 comparison of both trade CSVs | 0 | No live/signal changes; `portfolio_trades.csv` and `full_history_trades.csv` are byte-identical to P-10. |
| `live-money-review` | adversarial review in `.ai/tasks/P-11/review.md` plus `just check-invariants` | 0 | Replay limits remain 2.5%/5% versus 3%/6%, inclusive boundaries match live flattening, and no live execution path changed. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | Jan's four limits, confidence, gate thresholds, and merge authority are explicit; no methodology decision remains delegated. |
| `no-autonomous-merge` | `git branch --show-current` and repository merge policy review | 0 | Feature branch `codex/p-11-breach-probability-gates`; PR is review-only, with no merge or auto-merge action. |

### Additional required package evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates. |
| `red-first` | `uv run pytest -q tests/test_research_path_risk.py` before `path_risk.py` existed | 2 | RED during collection: `ModuleNotFoundError: research.portfolio.path_risk`. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Three production files; no unknown/dynamic edges; path risk and joint scenarios escalated as critical. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerability, and Ruff security checks passed. |
| `exact-binomial-cross-check` | `uv run --with scipy python` comparison against SciPy beta quantiles | 0 | Six independent fixtures matched; maximum absolute difference was `3.3e-16`. |
| `stage-4` | `uv run python -m research.stages.verdict --run reports/research/run_20260727_p11 --allow-legacy-unverified` | 0 | Production 10,000-replication plug-in plus 5/10/20/60 sensitivity completed; verdict FAIL. |
| `regression` | `uv run python -m research.regression --issue 52 --pair reports/research/run_20260726_p10=reports/research/run_20260727_p11 --out reports/research/regression/52-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN: no unexpected changes at exact thresholds. |

## Coverage and mutation

The first focused run failed during collection because the P-11 module did not exist. The first
Linux mutation measurement then exposed real gaps in cumulative time under water, persistent
breaches, exact count types, nearest-rank/ES boundaries, and count/probability consistency. Focused
tests killed every mutant that changed a statistic, breach flag, bound, gate, or serialized value.

The final 30 new survivors are exact-name classified: 29 alter only exception text after the same
fail-closed condition, and one changes exact CDF equality to the adjacent higher 60-digit Decimal
probability. The latter is strictly more conservative and cannot understate either gate. The global
score improved from `0.9077` to `0.9101`; no prior survivor changed status.

An initial format check identified only the new `path_risk.py`; Ruff formatted that file, all tests
remained green, and the Critical mutation workflow was rerun successfully on the formatted commit.

## Numerical regression

Reference: `reports/research/run_20260726_p10`.

Candidate: `reports/research/run_20260727_p11`.

The candidate is a read-only copy of the P-10 artifacts. Existing Stage-1 lineage names an older
`robustness.py`, so its copied manifests correctly refused reuse. For regression only, the copied
run was inspected through the framework's explicit legacy mode after removing manifests from the
copy. The original baseline was not changed, and the candidate remains non-deployable for missing
upstream lineage.

Exact invariants:

- trades `1348 -> 1348`;
- annual return `40.6% -> 40.6%`;
- total return `60.8% -> 60.8%`;
- deterministic flat max drawdown `-3.3% -> -3.3%`;
- hit rate `0.4621661721068249`, profit factor `1.5736035501130958`, payoff
  `1.8312400864076954`, expectancy `45.09430628791957`, Sharpe
  `3.5340898931550346`, tail cap `0.1816%`, worst day `-11.02R`, and stress multiplier `1.5`
  are exactly unchanged;
- `portfolio_trades.csv` SHA-256
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv` SHA-256
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

Gate/path comparison:

- overall verdict: `FAIL -> FAIL`;
- old gate: `P(profit)=100% >= 60%`, PASS;
- new internal gate: raw any-breach probability `74.95%`, one-sided 95% upper bound
  `75.6622834199968% <= 1%`, **FAIL**;
- new negative-return gate: raw probability `0%`, one-sided 95% upper bound
  `0.0299528359776612% <= 5%`, PASS;
- final return P05/median/P95: `42.07% / 60.75% / 80.48%`;
- expected shortfall 5%: `37.45%`;
- maximum-drawdown P05/median/P95: `1.62% / 5.30% / 10.78%`;
- internal daily/trailing breach probabilities: `74.76% / 3.78%`;
- prop daily/trailing breach probabilities: `33.63% / 1.36%`;
- time-under-water P05/median/P95: `64.05% / 71.90% / 79.74%`.

The gate failure is the result, not a defect. No limit, confidence bound, threshold, or test was
relaxed to obtain a favourable verdict.

## Deferred checks

No implementation, regression, or required R3 check is deferred. Independent Claude review and
Jan's merge decision intentionally occur after the ready PR and remain outside builder authority.
