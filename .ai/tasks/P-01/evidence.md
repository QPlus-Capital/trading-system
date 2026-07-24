# Evidence

## HEAD

HEAD: f04ab09af2464575f7af509e32d9bf7900353ca0

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
| `adversarial-review` | `.ai/tasks/P-01/review.md` | 0 | GREEN: 12 counterexamples attempted; no unresolved builder-preflight finding |
| `invariants` | exact `check-invariants` pytest recipe | 0 | GREEN: all 178 critical live, parity, sizing, research-integrity, and workflow tests passed |
| `mutation-on-touched-critical` | exact `stage1_account_returns` mutation `net_r -> r`; focused test must fail; restore; rerun | 0 | GREEN: 3 behavioral tests failed under the gross-stream mutant; all 7 passed after exact restoration |
| `parity-where-applicable` | fixed Stage-3 bypass test plus full continuous/portfolio suites | 0 | GREEN: fixed Stage-3 extraction remains gross and attaches swap only in its existing portfolio layer |
| `live-money-review` | `git diff --quiet origin/main -- core live monitoring` | 0 | GREEN: no live/order/account/signal/monitoring path changed and no live system was invoked |
| `human-decision-escalation` | task-spec open-question audit | 0 | GREEN: validation thresholds are explicitly deferred to Claude and Jan; no value was guessed |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: draft PR only; validation remains deferred and Jan retains merge authority |
| `security` | exact `check-security` commands | 0 | GREEN: secret scan, dependency audit, and high-signal Ruff security checks passed |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | GREEN: seven production files, fifteen direct tests, continuous-OOS critical escalation, and no unknown/dynamic edge |
| `forbidden-artifacts` | `git diff --quiet origin/main -- research/regression.py reports` | 0 | GREEN: no validation report or regression artifact changed |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready P-01 --base origin/main` | 0 | GREEN for a code-review draft: valid R3 task, all 14 required gates recorded, current evidence |

## Coverage and mutation

The seven focused P-01 tests cover the common trade frame, duration-sensitive ranking, positive
carry, close-only realization, the real Stage-1 CLI, snapshot lineage, and fixed Stage-3 bypass.
The full repository suite passed 855 tests. The exact gross-stream mutation killed three focused
tests; restoration passed all seven. No numerical validation result is asserted here.

## Deferred checks

The approximately nine-hour Stage-1 validation and regression comparison against
`run_20260723_1540` are deliberately deferred until Claude and Jan agree thresholds before the
run. This code-only pull request must remain draft and must not merge before that later step.
