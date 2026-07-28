# Evidence

## HEAD

HEAD: 26a22d0b10c35f797887bb7e627a761e85dcf4d8

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Seven changed Python files were formatted; Ruff, strict mypy, impact analysis, and 418 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Post-#98 rebase Ruff, strict mypy over 180 files, Vulture, and 1,197 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | The critical dependency map selected and passed 418 Stage-1/3, swap, H4, scenario, path-risk, stage, and reporting tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Twenty-one properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_research_portfolio_trades.py tests/test_research_stage1_swap.py tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_risk.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_factsheet.py tests/test_research_stage_lineage.py tests/test_research_stages.py tests/test_research_regression.py` | 0 | 253 tests passed, including producer-to-H4 direction, swap, scenarios, path replay, and real stage entrypoints. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-99 --base origin/main` | 0 | Task schema, R3 declaration, criterion traceability, review, and evidence are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-99 --base origin/main` | 0 | Sixteen counterexample findings are recorded and resolved, including Claude's P2; the adverse numerical result remains visible. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 317 post-#98 rebase critical tests passed, including constant-basis windows, chronological H4 drawdown, gross/swap decomposition, and direction integration. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation` | 1 | **Blocked by infrastructure:** the Actions allowance for this organisation is exhausted until 2026-08-01. A $0 Actions budget is set, so this local run is the evidence; no Linux mutation result exists and none is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core/strategies` plus row-by-row gross-stream comparison | 0 | No live/signal code changed; both trade streams retain exact identity, prices, stop, gross PnL, and gross R. The declared #57 exception permits only direction, swap, and derived artifacts to move. |
| `live-money-review` | `.ai/tasks/ISSUE-99/review.md` plus `just check-invariants` | 0 | No live path was invoked or changed; risk limits and gates remain fixed, while the newly exposed worse risk is reported without mitigation. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-99 --base origin/main` | 0 | Jan's source-field, artifact-exception, Stage-1 deferral, draft-only, and merge decisions are explicit; no methodology choice remains delegated. |
| `no-autonomous-merge` | `git branch --show-current` and repository merge-policy review | 0 | Feature branch `codex/issue-99-entry-side-direction`; draft PR only, with no ready, merge, or auto-merge action. |

### Additional evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates. |
| `red-first` | three exact producer/H4 pytest node IDs before the production change | 1 | Three expected failures: closed BUY emitted short, invalid `HOLD` did not raise, and the H4 stream emitted `[False, False]` instead of `[True, False]`. |
| `focused-green` | the same three exact pytest node IDs after the production change | 0 | Three tests passed. |
| `review-red-first` | `uv run pytest -q tests/test_research_sizing.py::test_h4_reconstruction_fails_closed_without_explicit_direction tests/test_research_h4_path.py::test_explicit_short_direction_handles_small_positive_pnl tests/test_research_h4_path.py::test_explicit_short_direction_handles_equal_entry_and_exit` before the review fix | 1 | The missing-direction guard failed because the outcome fallback did not raise; the two converted explicit-direction tests passed. |
| `review-focused-green` | `uv run pytest -q tests/test_research_factsheet.py tests/test_research_sizing.py tests/test_research_h4_path.py` | 0 | 58 tests passed; all valid H4/fact-sheet fixtures now carry explicit direction. |
| `outcome-fallback-audit` | `rg` over `research/portfolio/sizing.py` for the removed outcome expressions | 0 | No `won = pnl`, `is_long = won`, or optional-`is_long` fallback remains. `swap_analysis.py` was not changed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Two production files, eleven direct and thirteen transitive test paths, critical escalation for direction and H4 diagnostics, and no unknown/dynamic edges. |
| `security` | `uvx --from rust-just just check-security` | 0 | Post-#98 rebase secret scan clean; pip-audit reports no known vulnerabilities; Ruff security checks pass. |
| `post-119-rebase` | `git rebase origin/main` plus baseline/scope audit | 0 | Rebased onto `main@1815baa`; branch carries #119's `4,568`-mutant, 417-survivor exact baseline unchanged. No survivor was classified and no baseline file is in the branch diff. |
| `rebase-semantic-integration` | `uv run pytest -q` with seven exact #96/#99 H4/direction node IDs | 0 | Seven cross-boundary tests passed: explicit BUY/SELL controls low/high marking, missing direction fails closed, and chronological peaks never use a later close or a pre-entry close. |
| `rebase-h4-sizing-suite` | `uv run pytest -q tests/test_research_h4_path.py tests/test_research_sizing.py` | 0 | All 57 combined H4/sizing tests passed on the rebased implementation. |
| `rebase-config-union` | TOML parse and identifier-set comparison against `origin/main` and pre-rebase `cb77cc87` | 0 | Mutation targets and critical-dependency edges contain both sides' complete sets; `git diff --exit-code origin/main...HEAD -- .ai/quality/mutation-baseline.toml` is clean. |
| `post-97-rebase-integrity` | `git range-diff 8263206..84246c2 8851b91..HEAD`; structural TOML union audit | 0 | Issue #99 patches remain equivalent; F-035/F-038 are unique and ordered; mutation targets and critical edges contain both sides; mutation baseline unchanged. |
| `post-97-caller-integration` | `uv run pytest -q tests/test_research_stats.py tests/test_research_portfolio_trades.py tests/test_research_stage1_swap.py` | 0 | 17 tests passed across #97's gross/swap/net helper and #99's authoritative direction producer. The combined behavioral boundary requires fresh independent review. |
| `post-98-rebase-integrity` | `git range-diff 8851b91..443f6f9 494eafc..HEAD`; structural TOML union audit | 0 | Issue #99 patches remain equivalent; F-035/F-036/F-038 are unique and ordered; mutation targets and critical edges contain both sides; mutation baseline unchanged. |
| `post-98-stage1-integration` | `uv run pytest -q tests/test_research_continuous_windows.py tests/test_research_stage1_swap.py tests/test_research_portfolio_trades.py` | 0 | 29 tests passed across #98 fixed-basis scoring and #99 direction-dependent swap/net returns. This behavioral composition remains unresolved pending fresh independent review. |
| `real-direction-reconciliation` | offline ten-market Nautilus report/extraction script | 0 | Every market's raw `entry=BUY/SELL` count equals extracted `is_long=True/False`; XAUUSD is `374/386`, full history is `4,522/4,181`. No MT5 connection was made. |
| `stage-3` | `uv run python -m research.stages.portfolio --run reports/research/run_20260728_issue99 --fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full --allow-legacy-unverified` | 0 | Replayed 1,348 holdout trades and 8,703 full-history trades on a copied baseline; corrected H4 path breaches the hard daily limit. |
| `stage-4` | `uv run python -m research.stages.verdict --run reports/research/run_20260728_issue99 --allow-legacy-unverified` | 0 | Production 10,000-path plug-in plus fixed sensitivities completed; verdict remains `FAIL`, now also on the hard account limits and a 64.38% internal-breach upper bound. |
| `gross-stream-reconciliation` | Decimal/string row-by-row comparison of baseline and candidate trade CSVs | 0 | Row counts and every declared direction-independent column are exact; both hashes change as required because `is_long` and `swap_r` are corrected. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-99 --base origin/main` | 1 | NOT READY solely because the required Linux mutation gate is truthfully blocked with exit 1. |

## Red-first proof

Before the production edit:

```text
uv run pytest -q \
  tests/test_research_portfolio_trades.py::test_closed_position_uses_entry_side_for_direction \
  tests/test_research_portfolio_trades.py::test_unrecognized_entry_side_fails_closed \
  tests/test_research_h4_path.py::test_extracted_entry_side_drives_long_low_and_short_high
```

Exit `1`, three failures. The old producer returned `False` for a closed BUY because `side=FLAT`,
did not raise for `entry=HOLD`, and delivered `[False, False]` to H4 replay. The identical command
after implementation exits `0` with three passing tests.

The focused producer/H4/swap suite then passed `65` tests. Fixtures now mirror the real Nautilus
closed-position schema instead of inventing `side=LONG/SHORT`.

Claude's P2 was separately proven RED before the review fix. A synchronized-H4 call without
`is_long` completed silently through the PnL/price-outcome fallback, so
`test_h4_reconstruction_fails_closed_without_explicit_direction` failed with `DID NOT RAISE
ValueError`. After removing the fallback, the same stream raises
`synchronized H4 reconstruction requires an explicit is_long column`. Every valid sizing, H4, and
fact-sheet fixture now supplies the categorical field explicitly. The final focused impact run
passes 418 tests; the post-#119 full suite passes 1,197 tests. No Stage-3/4 artifact was regenerated because
all valid producer streams already contain `is_long`, so the review hardening changes only malformed
input behavior and leaves the numerical comparison below unchanged.

## Real direction reconciliation

The offline ten-market full-history extraction ran the fixed deployed structure against the local
catalog and compared two independent fields: raw report `entry` and emitted `is_long`.

| Market | Raw BUY / extracted long | Raw SELL / extracted short |
|---|---:|---:|
| XAUUSD | 374 / 374 | 386 / 386 |
| XAGUSD | 516 / 516 | 462 / 462 |
| EURUSD | 633 / 633 | 581 / 581 |
| GBPUSD | 427 / 427 | 357 / 357 |
| AUDUSD | 481 / 481 | 415 / 415 |
| USDJPY | 399 / 399 | 344 / 344 |
| US30 | 466 / 466 | 420 / 420 |
| DE40 | 382 / 382 | 376 / 376 |
| US500 | 409 / 409 | 401 / 401 |
| USTEC | 435 / 435 | 439 / 439 |
| **Total** | **4,522 / 4,522** | **4,181 / 4,181** |

The holdout changes from `0 long / 1,348 short` to `689 long / 659 short`. The full deployed history
changes from `0 / 8,703` to `4,522 / 4,181`. This is an independent correctness reconciliation,
not a comparison with the known-wrong categorical baseline.

## Numerical comparison

Reference: `reports/research/run_20260727_p11_scaled`.

Candidate: `reports/research/run_20260728_issue99`, a copy of the reference rerun with the exact
fixed variation/config, flat `0.15%` risk, `1.5` stress multiplier, and full-history tail. Legacy
inspection mode is required because the copied run predates complete upstream lineage; it cannot
produce a deployable PASS. The reference directory was not modified.

Exact direction-independent invariants:

- trade counts: holdout `1,348 -> 1,348`, full history `8,703 -> 8,703`;
- every row's `market`, `ts_opened`, `ts_closed`, `entry` price, `exit`, `sl_pct`, `pnl_base`, and
  gross `r` is string-exact;
- tail cap `0.1816%`, worst day `-11.02R`, stress `1.5`, fixed config, variation, and train length
  are exact;
- holdout CSV SHA-256 changes from `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`
  to `bc4e0c716afa3f249748d52df6eb7328e80b35cb7f1d4ffdce54dbf1c878264c`;
- full-history CSV SHA-256 changes from
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`
  to `5e61c8ce9143ef523119003d84829fde4b2a0e5287b689614efeb3a2146c7ad9`.

The byte changes are required: both artifacts carry `is_long` and `swap_r`. Issue #57's
byte-identity invariant is suspended for this package only; it is replaced by exact gross-field
identity above.

Corrected net and risk movements:

- holdout total `swap_r`: `-24.79047082589613776826R -> -51.91321726147804905619R`
  (`-27.12274643558191128793R`);
- full-history total `swap_r`: `-206.909801924771341965250R ->
  -579.485996218373726731039R` (`-372.576194293602384765789R`);
- annual return `40.6% -> 37.9%`; total return `60.8% -> 56.7%`;
- holdout synchronized-H4 max drawdown `-3.30% -> -5.09%`;
- maximum synchronized daily loss `2.27% -> 4.21%`;
- observed hard daily breach days `0 -> 1`, so Stage 3 changes from `breached=false` to `true`;
- full-history/holdout Sharpe becomes `2.68 / 3.30`; the gross trade rows are exact, but net swap
  correctly changes these statistics.

P-11 selected-path results:

- internal daily/trailing/any breach probability:
  `0% / 1.12% / 1.12% -> 62.81% / 6.26% / 63.59%`;
- prop daily/trailing/any breach probability:
  `0% / 0.26% / 0.26% -> 62.81% / 2.10% / 63.12%`;
- internal-any one-sided 95% Clopper-Pearson upper bound:
  `1.3090985789842287% -> 64.3834673691741%`, still `FAIL` against `<=1%`;
- negative-return upper bound stays `0.0299528359776612%`, still `PASS` against `<=5%`;
- final-return P05/median/P95:
  `38.20% / 60.73% / 88.16% -> 34.53% / 56.68% / 83.78%`;
- ES05 `33.25% -> 29.68%`;
- drawdown P05/median/P95:
  `1.56% / 5.22% / 10.65% -> 1.95% / 5.97% / 11.41%`;
- time under water P05/median/P95:
  `64.23% / 72.26% / 80.29% -> 65.51% / 73.72% / 81.93%`;
- overall verdict remains `FAIL`, but now also fails the hard-account-limit check.

The risk result is materially worse, as pre-registered: real longs now take H4 lows rather than
favorable highs. No limit, bound, confidence level, threshold, or consumer was weakened or changed.

## Deferred Stage-1 validation

The nine-hour Stage-1 candidate matrix was not rerun. Correct direction changes Stage-1 swap and
therefore its net selection stream. The next frozen full research run must re-derive P-01's
DSR/train-length conclusion, issue #58's pending effect, candidate daily/window artifacts,
SPA/Romano-Wolf/MCS results, and auto-selection. Existing Stage-1 artifacts are not certified under
the corrected direction.

## Infrastructure blocker

GitHub Actions has a $0 budget and its quota is exhausted until 2026-08-01. The required Linux
Critical mutation workflow therefore cannot start. Windows cannot run Mutmut's fork-based critical
job; the full suite correctly skips that one Linux-only self-test. The branch inherits #119's
`4,568`-mutant, 417-survivor exact-name baseline unchanged. No branch-specific mutation score,
survivor classification, or baseline result is invented. On quota reset, push an empty commit, run the
Critical mutation workflow, reconcile the exact baseline if required, update this evidence, rerun
`pr-ready`, and only then consider marking the PR ready.

## Coverage and mutation

The rebased code HEAD has 1,197 passing tests, 418 focused impact tests, 253 explicit integration
tests, 317 critical invariant tests, and twenty-one properties passing twice. New behavioural coverage
spans the producer's BUY/SELL/fail-closed boundary, missing-direction failure, and the
producer-to-synchronized-H4 path. Critical mutation targets cover both trade extraction and
portfolio sizing, but no Linux result exists because of the infrastructure blocker above.

## Deferred checks

Linux Critical mutation is explicitly blocked by infrastructure, not pending or passed. The
rebases also change the reviewed code context by composing issue #99 with PR #96 in the same H4
replay, PR #97 at the downstream `_market_trades` boundary, and PR #98 in Stage-1 fixed-basis
scoring. Targeted semantic checks pass, but the earlier independent review does not cover these
combined implementations. A fresh independent review and Jan's merge decision remain external.
The PR is draft-only.
