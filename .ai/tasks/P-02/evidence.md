# Evidence

## HEAD

HEAD: cf54dbf2ccf6626b13ea9c475ecebe4254d92631

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify` | 0 | GREEN: R3 for both training selectors; all 14 required gates listed |
| `red-first` | `uv run pytest -q tests/test_research_training_boundary.py` before implementation | 1 | RED: both call paths raised `KeyError: 'flatten_on_stop'` after capturing two configs |
| `format` | `just check-fast origin/main` | 0 | GREEN: all three changed Python files Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` with Git Bash on `PATH` | 0 | GREEN: Ruff, strict mypy over 162 files, vulture, and 848 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `just check-fast origin/main` | 0 | GREEN: all 160 impact-selected tests passed after format, lint, and strict types |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: 13 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 848 passed without a Stage-1 run or live-system interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-02 --base origin/main` | 0 | GREEN: valid task with 4 acceptance criteria and 5 invariants |
| `adversarial-review` | `.ai/tasks/P-02/review.md` | 0 | GREEN: 10 counterexamples attempted; no unresolved finding |
| `invariants` | `just check-invariants` | 0 | GREEN: all 178 critical live, parity, sizing, research-integrity, and workflow tests passed |
| `mutation-on-touched-critical` | temporary exact `False -> True` mutation on both selectors; wrapper requires focused pytest exit 1; restore; rerun focused pytest | 0 | GREEN: both guards failed under the inverse mutant and both passed after exact restoration |
| `parity-where-applicable` | unchanged-path audit plus continuous/portfolio/strategy focused suites | 0 | GREEN: continuous OOS already remains non-flattening; global defaults and realized-trade extraction are unchanged |
| `live-money-review` | `git diff --quiet origin/main -- core live monitoring` | 0 | GREEN: no live/risk/order/account/broker/signal/monitoring path changed and no live system was invoked |
| `human-decision-escalation` | issue #43 pre-run decision audit | 0 | GREEN: Claude and Jan agreed `--trade-count-pct 3.0 --annual-return-pp 2.5` on issue #43 before the validation run |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: ready-for-review PR only; Jan retains merge authority and merge/auto-merge are prohibited |
| `security` | `just check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and high-signal static security checks passed |
| `impact` | `just impact origin/main` | 0 | GREEN: two production selectors, four direct tests, twelve transitive tests, and no unknown/dynamic edge |
| `forbidden-artifacts` | `git diff --quiet origin/main -- research/regression.py reports research/engine/continuous.py research/engine/grid.py research/engine/recipe.py` | 0 | GREEN: no generated report, Stage-1 output, regression implementation, shared extractor, recipe default, or continuous-OOS change is committed |
| `methodology-validation` | `uv run python -m research.regression --issue 43 --pair run_20260721_0722=run_20260723_1540 --out reports/research/regression/43-comparison.json --trade-count-pct 3.0 --annual-return-pp 2.5` | 0 | GREEN: every change is inside the pre-announced range; 1,348->1,348 trades, 40.6%->40.6% annual return, and byte-identical full-history trades |
| `pr-ready` | `just pr-ready P-02 origin/main` | 0 | READY for code review: valid task, declared/classified R3, all 14 required gates exit 0, and evidence covers the tested code HEAD |

## Coverage

Both red-first behavioral tests now pass, as do 37 focused boundary tests, all 160 impact-selected
tests, 178 critical invariants, and the 848-test repository suite.

## Coverage and mutation

The two behavioral tests capture every training config built by the Stage-1 and Stage-3
optimizers. Focused existing suites cover continuous OOS configuration, real strategy stop
behavior, portfolio trade extraction, walk-forward window attribution, and parameter scheduling.
An exact inverse mutation of both changed values made both focused guards fail; restoration made
them pass. The repository's broad Linux mutation baseline does not target these selector mappings,
so no unrelated mutation score is presented as evidence for this change.

## Completed validation

The validation run `run_20260723_1540` completed on this branch's clean code at
`cf54dbf2ccf6626b13ea9c475ecebe4254d92631`. Its lineage inputs are byte-identical by content hash
to baseline `run_20260721_0722`.

The downstream protocol matched the baseline:

- Stage 2 forced `--variation no_bb_wpr`.
- Stage 3 used `--fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5
  --tail full`.
- The regression used the thresholds agreed on issue #43 before the run:
  `--trade-count-pct 3.0 --annual-return-pp 2.5`.

The regression was GREEN: "Every change is inside the announced range." Trades remained
1,348 -> 1,348, annual return remained 40.6% -> 40.6%, and `full_history_trades.csv` is
byte-identical. P-02 nevertheless took effect on the selection path: selected DSR moved
0.3541 -> 0.3694, and `study.csv`, `edge_ranking.csv`, and `ranking.csv` differ from the baseline.
The package's methodology validation is complete; merge authority remains with Jan after
independent review.

## Deferred checks

None. The Stage-1 validation and pre-announced regression comparison are complete.
