# Evidence

## HEAD

HEAD: 6a6c1d0aa10f891c485759282b29798cc4243e57

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Six changed Python files were already formatted; Ruff, strict mypy, impact analysis, and 185 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 180 files, Vulture, and 1,183 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative impact map selected and passed 185 tests, including scenario schema, path-risk, stage lineage, regression, and real stage entrypoints. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Twenty properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_research_path_risk.py tests/test_research_scenarios.py tests/test_research_regression.py tests/test_research_stage_lineage.py tests/test_research_stages.py` | 0 | 165 tests passed, including version-2 artifact rejection, scale invariance, compounded returns, and the real Stage-4 verdict path. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | P-11 task schema, traceability, risk declaration, evidence, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | Six findings were recorded and resolved; 26 counterexamples include varied source/path scales and legacy schemas. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 306 critical invariant tests passed, including live limits, H4 path, scenarios, relative replay, regression, and readiness. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation`, run `30248239284` | 0 | Linux/Python 3.13, Mutmut 3.5.0: 4,013/4,406 killed, 393 exact classified survivors, score `0.9108`; the self-test, health checks, and exact ratchet passed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies` plus SHA-256 comparison of both trade CSVs | 0 | No live/signal changes; both trade CSVs are byte-identical to P-10 at hashes `b5a0a9bb...` and `27592d20...`. |
| `live-money-review` | adversarial review in `.ai/tasks/P-11/review.md` plus `just check-invariants` | 0 | Replay limits remain 2.5%/5% versus 3%/6%, source-relative boundaries match live percentages, and no live execution path changed. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id P-11 --base origin/main` | 0 | Jan's four limits, confidence, gate thresholds, and merge authority are explicit; no methodology decision remains delegated. |
| `no-autonomous-merge` | `git branch --show-current` and repository merge policy review | 0 | Feature branch `codex/p-11-breach-probability-gates`; PR is review-only, with no merge or auto-merge action. |

### Additional required package evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates. |
| `red-first` | `uv run pytest -q tests/test_research_path_risk.py` before `path_risk.py` existed | 2 | RED during collection: `ModuleNotFoundError: research.portfolio.path_risk`. |
| `review-red-first` | `uv run pytest -q tests/test_research_path_risk.py -k "scale or zero_observed" tests/test_research_scenarios.py -k "scale or zero_observed or unversioned_scenario_schema"` before the review fix | 1 | Three RED guards: both scale tests rejected the absent source-opening field, and the unversioned artifact loaded instead of failing closed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Three production files; no unknown/dynamic edges; path risk and joint scenarios escalated as critical. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerability, and Ruff security checks passed. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready P-11 --base origin/main` | 0 | READY: task schema, R3 classification, all 14 required gates, and HEAD-bound evidence passed. |
| `exact-binomial-cross-check` | `uv run --with scipy python` comparison against SciPy beta quantiles | 0 | Six independent fixtures matched; maximum absolute difference was `3.3e-16`. |
| `stage-3` | `uv run python -m research.stages.portfolio --run reports/research/run_20260727_p11_scaled --fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full --allow-legacy-unverified` | 0 | Regenerated 548 schema-version-2 scenario days with source opening balances; portfolio metrics and both trade CSVs remained exact. |
| `stage-4` | `uv run python -m research.stages.verdict --run reports/research/run_20260727_p11_scaled --allow-legacy-unverified` | 0 | Production 10,000-replication plug-in plus 5/10/20/60 sensitivity completed; corrected verdict remains FAIL on internal trailing risk. |
| `regression` | `uv run python -m research.regression --issue 52 --pair reports/research/run_20260726_p10=reports/research/run_20260727_p11_scaled --out reports/research/regression/52-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN: no unexpected changes at exact thresholds. |

## Coverage and mutation

The original focused run failed during collection because the P-11 module did not exist. For this
review fix, the three new guards were RED against the pre-fix schema/replay: no source denominator
could be constructed and an unversioned artifact loaded successfully.

Linux run `30247216106` then measured the changed mutation surface: total `4,406`, killed `4,012`,
survived `394`, with no timeout/unchecked/no-test status. It correctly failed the exact ratchet:
six old exception-text names had disappeared, seven replacement survivors needed classification,
and `scenario_path_probability_of_profit mutmut_16` exposed that profitable paths were not counted
across multiple simulations. A three-path compounded-return test kills that real defect. The six
renumbered exception-text mutations retain the prior irrelevant classification; replay
`mutmut_69` is exactly equivalent because a zero opening balance breaches both inclusive zero
floors through either branch, while negative balances still fail closed.

Final Linux run `30248239284` passed independently: `4,013/4,406` killed, `393` exact classified
survivors, score `0.9108`, and zero unhealthy results. Every observed mutation that changes a source
scale, compounded return, breach flag, statistic, bound, gate, or serialized value is killed.

## Numerical regression

Reference: `reports/research/run_20260726_p10`.

Candidate: `reports/research/run_20260727_p11_scaled`.

The candidate began as a read-only copy of the P-10 artifacts. Stage 3 was rerun with the exact
P-10 fixed config/risk/stress/tail arguments to regenerate only the version-2 scenario schema from
the same P-09 diagnostics, then Stage 4 consumed it. Existing Stage-1 lineage names an older
`robustness.py`, so the copied run used the explicit legacy inspection mode after removing copied
stage manifests. The original baseline was not changed, and the candidate remains non-deployable
for missing upstream lineage.

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
- all 548 observed source days are below the daily limits: maximum adverse fraction
  `2.2714093388987694%`, internal daily breach days `0`, prop daily breach days `0`;
- pre-fix P-11 internal/prop daily breach probabilities `74.76% / 33.63%` fall to the
  scale-correct `0% / 0%`;
- corrected internal daily/trailing/any breach probabilities: `0% / 1.12% / 1.12%`;
- corrected prop daily/trailing/any breach probabilities: `0% / 0.26% / 0.26%`;
- corrected internal gate: raw any-breach probability `1.12%`, one-sided 95% upper bound
  `1.3090985789842287% <= 1%`, **FAIL**;
- corrected negative-return gate: raw probability `0%`, one-sided 95% upper bound
  `0.0299528359776612% <= 5%`, PASS;
- final return P05/median/P95: `38.20% / 60.73% / 88.16%`;
- expected shortfall 5%: `33.25%`;
- maximum-drawdown P05/median/P95: `1.56% / 5.22% / 10.65%`;
- time-under-water P05/median/P95: `64.23% / 72.26% / 80.29%`;
- diagnostic `P(profit)`: `100%`.

The return distribution widened in the expected direction from the pre-fix
`42.07% / 60.75% / 80.48%`. The corrected gate still fails, now because of sampled internal
trailing-limit risk rather than an absolute-scale daily-loss artifact. No limit, confidence bound,
threshold, or test was relaxed to obtain a favourable verdict.

## Deferred checks

No implementation, regression, or required R3 check is deferred. Independent Claude review and
Jan's merge decision intentionally occur after the ready PR and remain outside builder authority.
