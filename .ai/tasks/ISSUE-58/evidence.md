# Evidence

## HEAD

HEAD: 81ada9235ce257bb920e5667407760657d9bebd3

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Both changed Python files were already formatted; Ruff, strict mypy, impact analysis, and 352 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Post-#97 rebase: Ruff, strict mypy over 180 files, Vulture, and 1,194 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | The conservative impact graph selected and passed 352 tests, including continuous-window, real-engine integration, candidate-matrix, Stage-1 swap, edge, factsheet, regression, and stage tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Post-#97 rebase: 21 properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uvx --from rust-just just check-fast origin/main` plus the two targeted real `_run_task` executions below | 0 | Static/dynamic impact tests passed, and both formerly failing XAGUSD candidates traversed the real characterize/continuous engine path without an error row. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-58 --base origin/main` | 0 | The task schema, traceability, R3 declaration, evidence, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-58 --base origin/main` | 0 | Four findings remain resolved; range-diff proves the rebase changed no Stage-1 implementation or test behaviour. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | Post-#97 rebase: 316 critical invariant tests passed, including continuous windows, Stage-1 sizing, regression, risk, and readiness. |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | 1 | **BLOCKED BY INFRASTRUCTURE:** The Actions allowance for this organisation is exhausted until 2026-08-01. Mutmut requires fork/WSL and the repository's mutation self-test is skipped on Windows; this local gate run is the evidence. No mutation result is claimed and no baseline or gate was weakened. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies research/portfolio research/stages research/engine/walkforward_runner.py research/engine/characterize.py` plus exact regression/hash comparison | 0 | No live, signal, deployed portfolio, Stage-3, or Stage-4 path changed; both trade CSVs are byte-identical. |
| `live-money-review` | `.ai/tasks/ISSUE-58/review.md` plus `uvx --from rust-just just check-invariants` | 0 | Research scoring only: no runner interaction, order path, risk limit, sizing limit, account identity, or deployed variation changed. The two already-running live processes were observed only as OS processes and never touched. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-58 --base origin/main` | 0 | Jan's pinned Option A, exact regression thresholds, build-only delivery, and merge authority are explicit; Options B/C are excluded and no methodology decision remains delegated. |
| `no-autonomous-merge` | `gh pr view 98 --json isDraft,state` | 0 | PR #98 remains open and draft; no merge, ready transition, or auto-merge action was taken. |

### Additional package evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 because `research/engine/continuous.py` owns Stage-1 constant-basis scoring and the finding registry is R3 governance; all 14 cumulative gates apply. |
| `red-first` | `uv run pytest -q tests/test_research_continuous_windows.py::test_fixed_basis_scores_after_cumulative_losses_exceed_the_basis tests/test_research_continuous_windows.py::test_prior_loss_depth_never_changes_a_later_fixed_basis_score` before the production edit | 1 | RED: three failures and one pass. The `-110%`, exact `-100%`, and `-150%` histories raised `RuntimeError: account exhausted`; only the `-99.5%` case scored. |
| `red-first-green` | the same focused command after the production edit | 0 | Four tests passed: the first window retains `-110%`, the later window retains `-20%`, and a later `+10%` is invariant to prior losses of `-99.5%`, `-100%`, and `-150%`. |
| `focused-behavior` | `uv run pytest -q tests/test_research_continuous_windows.py tests/test_research_candidate_matrix.py tests/test_research_continuous_integration.py tests/test_research_stage1_swap.py tests/test_research_candidate_artifacts.py tests/test_research_edge_ranking.py tests/test_research_selection_protocol.py` | 0 | 113 tests passed; the fixed-basis scorer, both candidate paths, canonical net stream, persisted evidence, and selection consumers remain coherent. |
| `source-audit` | `rg -n -i "account exhausted\|post-ruin\|running.?equity\|equity = basis" research/engine research/stages` with no-match required | 0 | No Stage-1 running-equity viability branch or ruin message remains. Statistical cumulative curves still exist only for return/drawdown calculations. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | One changed production file; no unknown/dynamic edges; `continuous.py` escalates as a critical Stage-1 scoring dependency. |
| `security` | `uvx --from rust-just just check-security` | 0 | Post-#97 rebase: secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `rebase-integrity` | `git range-diff 8263206..8a96098 8851b91..HEAD`; registry parse; mutation-baseline diff | 0 | Issue #58 production/test patches remain equivalent; F-035 and F-036 are retained in ID order with no duplicate; `.ai/quality/mutation-baseline.toml` is unchanged. No behavior changed. |
| `regression` | `uv run python -m research.regression --issue 58 --pair reports/research/run_20260727_p11_scaled=reports/research/run_20260727_issue58 --out reports/research/regression/58-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN at exact thresholds: no unexpected changes. The candidate is a read-only byte-copy because the changed scorer is unreachable from Stage 3/4. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-58 --base origin/main` | 1 | NOT READY on `mutation-on-touched-critical` alone, as required in build-only mode. All other task/schema/evidence/readiness checks pass. |

## Red-first proof

The production edit was not present when the two new guards first ran. Pytest collected four cases:
the synthetic `-110%` history and the parametrized exact/below-basis cases failed inside
`window_returns` with the obsolete account-exhaustion exception, while the `-99.5%` control passed.
After removing only that branch, the identical command passed all four cases. The final full suite
and focused impact suite include these guards.

## Real XAGUSD acceptance

The frozen `research/config/robustness.py` recipe, `standard_broker()` snapshot, local XAGUSD catalog
data, `train_months=36`, `test_months=6`, `step_months=6`, `holdout_months=24`, and
`embargo_days=7` were passed through the production `characterize._run_task` path for each affected
candidate:

- `XAGUSD/no_wpr_rsi@36m`: normal numeric result with 21 windows, 742 trades, all 24 inner
  combinations, `mean_oos_pct=5.59`, `oos_maxdd_pct=6.69`, `return_per_dd=0.836`,
  `pct_profitable=76`, and `wfe_norm=0.454`;
- `XAGUSD/no_confirms@36m`: normal numeric result with 21 windows, 745 trades, all 24 inner
  combinations, `mean_oos_pct=5.21`, `oos_maxdd_pct=7.08`, `return_per_dd=0.735`,
  `pct_profitable=71`, and `wfe_norm=0.427`.

Both result dictionaries omitted the `error` field and retained negative windows down to about
`-16.71%`; neither candidate was zero-filled or dropped. The reference
`reports/research/study_20260724_1146/study.csv` contains exactly the two corresponding
`account exhausted` error rows. The full 432-task, nine-hour Stage-1 matrix was not rerun and no
future ranking/selection result is claimed.

## Numerical regression

Reference: `reports/research/run_20260727_p11_scaled`.

Candidate: `reports/research/run_20260727_issue58`.

The candidate is an ignored byte-copy of the current deployed baseline. This is the correct
Stage-3/4 regression fixture because `window_returns` is a Stage-1 scorer and the diff audit proves
that no deployed portfolio or verdict path changed.

Exact results:

- trades `1,348 -> 1,348`;
- annual return `40.6% -> 40.6%`;
- total return `60.8% -> 60.8%`;
- max drawdown `-3.30% -> -3.30%`;
- `unexpected_changes = []`;
- `portfolio_trades.csv` SHA-256 on both sides:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv` SHA-256 on both sides:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

No reported deployed number moved. A future full Stage-1 rerun is expected to change the candidate
matrix and selection diagnostics because the two XAGUSD observations will finally be present; this
build does not fabricate those values.

## Coverage and mutation

The rebased complete deterministic suite passes 1,192 tests, invariants pass 314, and properties
pass 21 twice. Range-diff shows the Stage-1 implementation and test patches are unchanged, so the
prior 352-test focused impact and real XAGUSD execution evidence remains applicable.

Linux Critical mutation is **blocked by infrastructure — Actions quota exhausted until
2026-08-01**. It cannot run in the repository's supported mutation environment, and the local
Windows suite explicitly skips Mutmut because it requires fork/WSL. The gate is recorded with exit
status 1, the mutation baseline is unchanged, and readiness must remain NOT READY on this gate
alone.

## Deferred checks

Only the Linux Critical mutation gate and subsequent independent Claude review/Jan decision remain.
No implementation, local deterministic gate, targeted real acceptance run, or deployed regression
check is pending. PR #98 remains draft and must not be marked ready while mutation is blocked.
