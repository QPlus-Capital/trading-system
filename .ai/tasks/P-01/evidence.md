# Evidence

## HEAD

HEAD: eb5c5b17b49d74892c8d279f4822930f925d7a9d

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | planned-path `uv run python -m scripts.quality.classify ...` | 0 | R3: Stage-1 selection, parameter search, continuous OOS attribution, and trade-return paths |
| `impact-pre-code` | `just impact origin/main` | 0 | R0 for task-document-only diff; no production file existed yet, so the explicit coupled-quantity inventory governs implementation |
| `red-first` | `uv run pytest -q tests/test_research_stage1_swap.py` before implementation | 1 | RED: 5 failed, 1 passed; missing net APIs, unchanged real CLI output under -0.50R swap, and absent direct-study provenance |
| `format` | Ruff formatting audit within `just check` | 0 | GREEN: all changed Python files are correctly formatted |
| `docs-consistency` | full pytest within `just check` | 0 | GREEN: architecture and engineering-document guards passed |
| `check` | `uvx --from rust-just just check` with bundled Git Bash on `PATH` | 0 | GREEN: Ruff, strict mypy over 163 files, Vulture, and 855 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | full pytest plus the impact-selected superset | 0 | GREEN: all affected tests are contained in the 855-test repository suite |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` | 0 | GREEN: 13 deterministic property tests passed |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 855 passed without a Stage-1 validation run or live-system interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-01 --base origin/main` | 0 | GREEN: valid task with 8 acceptance criteria and 7 invariants |
| `adversarial-review` | Claude full review of PR #84 | 0 | GREEN: independent review passed with no findings |
| `invariants` | exact `check-invariants` pytest recipe | 0 | GREEN: all 178 critical live, parity, sizing, research-integrity, and workflow tests passed |
| `mutation-on-touched-critical` | exact `stage1_account_returns` mutation `net_r -> r`; focused test must fail; restore; rerun | 0 | GREEN: 3 behavioral tests failed under the gross-stream mutant; all 7 passed after exact restoration |
| `parity-where-applicable` | fixed Stage-3 bypass test plus full continuous/portfolio suites | 0 | GREEN: fixed Stage-3 extraction remains gross and attaches swap only in its existing portfolio layer |
| `live-money-review` | `git diff --quiet origin/main -- core live monitoring` | 0 | GREEN: no live/order/account/signal/monitoring path changed and no live system was invoked |
| `human-decision-escalation` | issue #44 pre-run decision audit | 0 | GREEN: Claude and Jan agreed `--trade-count-pct 3.0 --annual-return-pp 2.5` before the validation run |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: ready-for-review PR only; Jan retains merge authority and merge/auto-merge remain prohibited |
| `security` | `uvx --from rust-just just check-security` after GitPython 3.1.54 -> 3.1.56 | 0 | GREEN: secret scan clean, pip-audit reports no known vulnerabilities, and high-signal Ruff security checks passed |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | GREEN: seven production files, fifteen direct tests, continuous-OOS critical escalation, and no unknown/dynamic edge |
| `forbidden-artifacts` | `git diff --quiet origin/main -- research/regression.py reports` | 0 | GREEN: no validation report or regression artifact changed |
| `methodology-validation` | regression of `run_20260724_1146` against `run_20260723_1540` with `--trade-count-pct 3.0 --annual-return-pp 2.5` | 0 | GREEN: every change is inside the pre-announced range; 1,348->1,348 deployed trades, 40.6%->40.6% annual return, and byte-identical full-history trades |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready P-01 --base origin/main` | 0 | READY for review: valid R3 task, all 14 required gates exit 0, current evidence, independent review and methodology validation complete |

## Coverage and mutation

The seven focused P-01 tests cover the common trade frame, duration-sensitive ranking, positive
carry, close-only realization, the real Stage-1 CLI, snapshot lineage, and fixed Stage-3 bypass.
The full repository suite passed 855 tests. The exact gross-stream mutation killed three focused
tests; restoration passed all seven.

## Completed validation

Validation run `run_20260724_1146` completed on this branch. Its lineage inputs are byte-identical
by content hash to baseline `run_20260723_1540`.

The downstream protocol matched the baseline:

- Stage 2 forced `--variation no_bb_wpr`.
- Stage 3 used `--fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5
  --tail full`.
- Regression used the thresholds agreed on issue #44 before the run:
  `--trade-count-pct 3.0 --annual-return-pp 2.5`.

The regression was GREEN: deployed trades remained 1,348 -> 1,348, annual return remained
40.6% -> 40.6%, and `full_history_trades.csv` is byte-identical. P-01 took effect on Stage-1
selection: selected training length moved 36m -> 18m, DSR moved 0.3694 -> 0.1866, and
`mean_rpd` moved 2.413 -> 2.220.

## Deferred checks

None. Independent review and the pre-announced methodology validation are complete. Merge
authority remains with Jan.
