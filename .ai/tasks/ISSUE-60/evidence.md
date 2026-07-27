# Evidence

## HEAD

HEAD: 196730c1adc02bcbb8c5ca8784e5c2eee795e08f

The only later commit permitted in build-only mode is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Four changed Python files were formatted; Ruff, strict mypy, impact analysis, and 465 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Rebase HEAD: Ruff, strict mypy over 180 files, Vulture, and 1,193 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative impact mapping selected and passed 465 direct/transitive tests with no unknown or dynamic edge. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Rebase HEAD: 21 properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_research_stats.py tests/test_research_swap_analysis.py tests/test_research_stage1_swap.py tests/test_research_continuous_integration.py tests/test_research_portfolio_trades.py tests/test_research_risk.py tests/test_research_factsheet.py tests/test_research_stages.py` | 0 | 59 tests passed, covering both corrected helper branches and the independent Stage-1/3/4 paths. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-60 --base origin/main` | 0 | Task schema, AC/INV traceability, R3 declaration, evidence, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-60 --base origin/main` | 0 | Three findings and ten counterexamples remain resolved; range-diff proves the rebase changed no implementation behaviour. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | Rebase HEAD: 315 critical tests passed, including live limits, signal parity, return attribution, risk, scenarios, regression, and readiness. |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | 1 | **Blocked by infrastructure — Actions quota exhausted until 2026-08-01.** Windows skips Mutmut because it requires fork/WSL; no Linux result exists and none is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies research/engine research/stages research/portfolio/trades.py research/portfolio/risk.py research/portfolio/factsheet.py` plus SHA-256 comparison | 0 | No live, signal, stage, canonical Stage-1/3, risk, or fact-sheet path changed; both trade CSVs are byte-identical. |
| `live-money-review` | `.ai/tasks/ISSUE-60/review.md` plus `just check-invariants` | 0 | No live runner was invoked or changed; limits, sizing, signals, orders, accounts, and deployed result paths remain untouched. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-60 --base origin/main` | 0 | Jan's canonical column convention, exact regression thresholds, build-only/no-PR boundary, and merge authority are explicit; no methodology question remains delegated. |
| `no-autonomous-merge` | `gh pr view 97 --json isDraft,state` | 0 | PR #97 remains open and draft; no merge, ready transition, or auto-merge action was taken. |

### Additional evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates; stats return attribution, broker semantics, and the finding registry all classify R3. |
| `red-first` | `uv run pytest -q tests/test_research_stats.py::test_market_trades_preserves_gross_and_separate_swap tests/test_research_stats.py::test_market_trades_records_zero_swap_when_broker_has_no_market_spec` | 1 | Two expected failures: the swap-bearing case returned net `r=0.75` instead of gross `1.0`, and the no-spec broker raised `KeyError: 'swap_r'`. |
| `focused-tests` | `uv run pytest -q tests/test_research_stats.py tests/test_research_swap_analysis.py` | 0 | Eleven tests passed after the fix, including the caller's explicit gross-column guard. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Two production files, five direct and 29 transitive tests, no unknown/dynamic edges; R3 assigned. |
| `security` | `uvx --from rust-just just check-security` | 0 | Rebase HEAD: secret scan clean; pip-audit reports no known vulnerabilities; Ruff security checks pass. |
| `caller-audit` | `rg --pcre2 -n "(?<![A-Za-z0-9])_market_trades\\(" research tests` | 0 | One definition, one production caller in `swap_analysis.main`, and the new test helper; Stage 1-4 have no call edge. |
| `regression` | `uv run python -m research.regression --issue 60 --pair reports/research/run_20260727_p11_scaled=reports/research/run_20260727_issue60 --out reports/research/regression/60-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN: 1,348→1,348 trades, 40.6%→40.6% annual return, no unexpected changes. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-60 --base origin/main` | 1 | Expected NOT READY solely because the required Linux mutation gate is truthfully non-zero; build-only delivery forbids opening a PR. |

## Numerical regression

Reference: `reports/research/run_20260727_p11_scaled`.

Candidate: `reports/research/run_20260727_issue60`, a read-only copy because the changed helper is
not reachable from Stage 1, Stage 2, Stage 3, Stage 4, the fact sheet, or the deployed live path.
Rerunning those stages would exercise unrelated code and cannot provide additional evidence for a
dormant analysis-helper branch.

- Regression thresholds: trade-count drift `0.0%`; annual-return drift `0.0` percentage points.
- Trades: `1348 -> 1348`.
- Annual return: `40.6% -> 40.6%`.
- Total return: `60.8% -> 60.8%`.
- Max drawdown: `-3.30% -> -3.30%`.
- `unexpected_changes`: empty.
- `portfolio_trades.csv` SHA-256 on both sides:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`.
- `full_history_trades.csv` SHA-256 on both sides:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

## Coverage and mutation

The behavioural test crosses the real `_market_trades` orchestration boundary: only the expensive
Nautilus node and deterministic position-report extraction are faked. The actual `r_multiples`,
`BrokerProfile.swap_spec`, and `swap_r_per_trade` implementations run. This prevents a helper-only
test from passing while the defective branch remains wired.

The rebased local suite passes 1,193 tests, invariants pass 315, and properties pass 21 twice.
The prior focused impact and 59-test integration evidence remains applicable because range-diff
shows no implementation/test patch change. The Linux Critical mutation gate cannot run locally on
Windows and GitHub Actions is quota-blocked. No mutation baseline, survivor allowance, timeout,
score, or threshold was changed or guessed.

## Deferred checks

- Linux Critical mutation: **blocked by infrastructure — Actions quota exhausted until
  2026-08-01**.
- Independent Claude review and Jan's merge decision occur after infrastructure recovers.
- PR #97 remains draft and must not be marked ready while the mutation gate is blocked.
