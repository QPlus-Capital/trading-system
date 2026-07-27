# Evidence

## HEAD

HEAD: 53932b46a7603c2e3f403aee02ec5a7a55c32899

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Six changed Python files were already formatted; Ruff, strict mypy, impact analysis, and 388 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed on the final non-evidence HEAD. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 180 files, Vulture, and 1,190 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative impact mapping selected and passed 388 tests across H4 diagnostics, policy/fact-sheet, scenarios/path risk, stages, lineage, regression, and selection dependencies. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Twenty-one properties passed twice at fixed Hypothesis seed `20260721`, including future-close invariance and both limit-dominance conventions. |
| `integration-tests` | `uv run pytest -q tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_risk.py tests/test_research_factsheet.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_stage_lineage.py tests/test_research_stages.py tests/test_research_regression.py` | 0 | 246 tests passed, including real Stage-4 entrypoint and shared result-surface assertions. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-91 --base origin/main` | 0 | Task schema, criterion traceability, R3 declaration, review, and numeric evidence records are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-91 --base origin/main` | 0 | Five findings and eighteen counterexamples are recorded; every code finding is resolved and the gate decision is escalated to Jan. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 312 critical tests passed, including live limits, H4 event order, sizing, scenarios, sampled paths, regression, and readiness. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation`, run `30253721289` | 1 | **Blocked by infrastructure — quota.** GitHub did not start any workflow step: “recent account payments have failed or your spending limit needs to be increased.” No mutation result exists and none is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies` plus SHA-256 comparison | 0 | No live/signal changes; both trade CSVs and `loss_day_scenarios.csv` are byte-identical to the baseline. |
| `live-money-review` | `.ai/tasks/ISSUE-91/review.md` plus `just check-invariants` | 0 | Daily and trailing gate semantics, all four limits, confidence bounds, and thresholds remain unchanged; no live path was invoked. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-91 --base origin/main` | 0 | Strict chronological trailing HWM remains diagnostic-only and is an explicit open question for Jan. |
| `no-autonomous-merge` | `git branch --show-current` and repository merge-policy review | 0 | Feature branch `codex/issue-91-chronological-drawdown`; no merge or auto-merge action was taken. |

### Additional evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates. |
| `red-first` | four exact H4/path-risk pytest node IDs before production changes | 1 | Four expected failures: `-10% != -1%`, `-9.09% != -0.91%`, `10% != 1%`, and `9.09% != 1%`. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Three production files, nine direct and ten transitive test files, no unknown/dynamic edges, and critical escalation for sizing and path risk. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean; pip-audit reports no known vulnerabilities; Ruff security checks pass. |
| `stage-3` | `uv run python -m research.stages.portfolio --run reports/research/run_20260727_issue91 --fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full --allow-legacy-unverified` | 0 | Replayed 1,348 holdout trades and full-history tail; selected flat drawdown is `-3.35%`, daily loss `2.27%`, no account-limit breach. |
| `stage-4` | `uv run python -m research.stages.verdict --run reports/research/run_20260727_issue91 --allow-legacy-unverified` | 0 | Production 10,000-path plug-in plus fixed sensitivities completed; verdict remains FAIL on the unchanged internal breach gate. |
| `regression` | `uv run python -m research.regression --issue 91 --pair reports/research/run_20260727_p11_scaled=reports/research/run_20260727_issue91 --out reports/research/regression/91-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN: every change is inside the announced range and `unexpected_changes` is empty. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-91 --base origin/main` | 1 | NOT READY solely because the required Linux mutation gate is truthfully recorded with non-zero exit; no readiness result is misrepresented. |

## Red-first proof

Before production code changed:

```text
uv run pytest -q \
  tests/test_research_h4_path.py::test_drawdown_does_not_use_a_later_profitable_close_as_its_peak \
  tests/test_research_h4_path.py::test_drawdown_uses_an_observable_h4_high_before_a_later_minimum \
  tests/test_research_path_risk.py::test_path_drawdown_does_not_use_the_same_days_later_close_peak \
  tests/test_research_path_risk.py::test_path_drawdown_uses_a_prior_days_high_for_a_later_minimum
```

Exit `1`, four failures. Actual old results were `-10.0%`, `-9.09%`, `10%`, and
`9.090909...%`; the registered chronological results are `-1.0%`, `-0.91%`, `1%`, and `1%`.

The first implementation then exposed a boundary bug: a market close from before a position's
entry could be reused as its opening equity mark. `test_pre_entry_market_close_cannot_create_a_position_drawdown_peak`
guards the corrected timestamped-close rule.

## Numerical regression

Reference: `reports/research/run_20260727_p11_scaled`.

Candidate: `reports/research/run_20260727_issue91`.

The candidate is a read-only copy of the reference inputs. Stages 3 and 4 were rerun with the
reference's exact fixed config, flat `0.15%` risk, `1.5` stress multiplier, and full-history tail.
Legacy inspection mode is required because the copied baseline predates complete Stage-1/2 lineage;
it cannot produce a deployable PASS.

Exact invariants:

- trades `1348 -> 1348`;
- annual return `40.6% -> 40.6%`, total return `60.8% -> 60.8%`;
- hit rate `0.4621661721068249`, profit factor `1.5736035501130958`, payoff
  `1.8312400864076954`, expectancy `45.09430628791957`, Sharpe
  `3.5340898931550346`, tail cap `0.1816%`, worst day `-11.02R`, and stress `1.5` are unchanged;
- `portfolio_trades.csv` SHA-256
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv` SHA-256
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`;
- `loss_day_scenarios.csv` SHA-256
  `5e9d05b04d29633f2e16f6927b6b4e578cdf34af8c1e0220b45c0f0e2bed2deb`.

Drawdown surfaces:

- Stage-3 `portfolio.json`: `-3.30% -> -3.35%`;
- Stage-4 stats/path: `-3.30%/-3.30% -> -3.35%/-3.35%`;
- fact sheet full flat / full compound / holdout flat / holdout compound:
  `-2.27/-4.99/-3.30/-4.42% -> -2.44/-5.24/-3.35/-4.61%`;
- P-11 drawdown P05/median/P95:
  `1.5640/5.2166/10.6455% -> 1.4136/5.1222/10.5609%`.

The deterministic result worsens by `0.05` percentage points despite removing look-ahead. On the
worst day, a real observable H4 equity high precedes the later minimum and is slightly above the
prior daily close peak. AC-02 explicitly requires retaining that denominator; hiding it to force an
improvement would reintroduce a different bias.

Unchanged Stage-4 path outputs:

- internal daily/trailing/any `0% / 1.12% / 1.12%`;
- prop daily/trailing/any `0% / 0.26% / 0.26%`;
- internal exact one-sided 95% upper bound `1.3090985789842287%` (FAIL against `<=1%`);
- negative-return upper bound `0.0299528359776612%` (PASS against `<=5%`);
- final return P05/median/P95 `38.20% / 60.73% / 88.16%`;
- ES05 `33.25%`;
- time under water P05/median/P95 `64.23% / 72.26% / 80.29%`;
- overall verdict `FAIL -> FAIL`.

## Open decision measurement

Existing same-day-close trailing convention:

- raw internal trailing/any breach probability: `1.12% / 1.12%`;
- exact one-sided 95% upper bound on internal any breach: `1.3090985789842287%`.

Strictly chronological trailing-HWM diagnostic on the identical sampled paths:

- raw internal trailing/any breach probability: `1.12% / 1.12%`;
- exact one-sided 95% upper bound: `1.3090985789842287%`.

Measured inflation on this baseline is therefore **0.00 percentage points** in raw probability and
zero in the exact bound. This does not resolve the methodology choice generally; the gate convention
remains unchanged pending Jan's decision.

## Infrastructure blocker

Final-HEAD Linux workflow `30253721289` and earlier attempts `30252267168`/`30252491502` all failed
before checkout or any command. GitHub's annotation says the job was not started because account
payments failed or the spending limit must be increased. Windows cannot run Mutmut's fork-based
critical job and WSL is not installed. The required mutation gate is therefore honestly blocked,
not pending and not passed.

## Coverage and mutation

The deterministic suite has 1,190 passing tests and the focused impact set has 388. Twenty-one
properties pass twice; 246 explicit integration tests and 312 critical invariant tests pass. The
new tests cover later-close look-ahead, a real earlier H4 high, entry-boundary stale marks, sampled
day order, surface parity, trailing-convention separation, and exact regression hashes.

No mutation score or survivor disposition is available because GitHub did not start the Linux job.
The committed baseline is not guessed or regenerated from Windows. A future Linux run must measure
and reconcile the changed `portfolio-sizing` and `loss-day-path-risk` targets before readiness.

## Deferred checks

The Linux Critical mutation gate is blocked by infrastructure quota, with run `30253721289` as the
final-HEAD proof. It is the only incomplete required gate. Independent Claude review and Jan's
merge decision remain intentionally external; the branch is not ready and no PR is opened while
`pr-ready` reports NOT READY.
