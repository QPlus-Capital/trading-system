# Evidence

## HEAD

HEAD: a91eed6535677a8ec7570647dd168f8ad6754112

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py` | 1 | RED: 24 failed, 9 passed; stale permits survived moves, `withdraw` was absent, and refusal diagnostics were generic |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3: `scripts/quality/board.py` and the finding registry govern every later change |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: changed Python files formatted; Ruff and strict mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_workflow_contract.py` | 0 | GREEN: 88 passed; the unchanged workflow contract still renders without drift |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy, Vulture, and pytest; 1660 passed, 1 skipped because Mutmut is unavailable on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py` | 0 | GREEN: 39 passed |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` (twice) | 0 | GREEN: 21 passed on each deterministic replay |
| `integration-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py` | 0 | GREEN: 39 passed, including CLI dispatch and content-addressed registry integration |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 136 --base origin/main` | 0 | GREEN: task 136 valid with 13 AC and 4 INV |
| `adversarial-review` | Claude independent review | 1 | BLOCKED: the draft has not yet received its independent review; Codex did not review its own work |
| `invariants` | `uv run pytest -q tests/test_live_risk_control.py tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_signal_adapter_parity.py tests/test_strategy_sizing_basis.py tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_portfolio_dd.py tests/test_research_risk.py tests/test_research_stats.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_continuous_windows.py tests/test_research_regression.py tests/test_research_forward_test_registry.py tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py tests/test_quality_classify.py tests/test_quality_pr_ready.py` | 0 | GREEN: 529 passed |
| `mutation-on-touched-critical` | `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | GREEN (vacuous): selector returned `[]`; no configured mutation target is touched directly or through the import graph |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: only board tooling and its tests changed; no signal, research, portfolio, or live adapter path changed |
| `live-money-review` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: no `core/**`, `research/**`, `live/**`, or `monitoring/**` path changed and no terminal or runner was contacted |
| `human-decision-escalation` | issue #136 specification and open-decision audit | 0 | GREEN: issue #136 resolves the permit semantics completely; no unresolved human decision was guessed |
| `no-autonomous-merge` | draft pull request inspection | 1 | BLOCKED until the draft pull request exists; merge and auto-merge remain prohibited |
| `security` | `uv run python -m scripts.quality.security`; `uv run pip-audit --skip-editable`; `uv run ruff check core research live monitoring scripts --select S --ignore S101,S110,S603,S607` | 0 | GREEN: no secret findings, no known dependency vulnerabilities, and security lint passed |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | R3; one production file, two directly related test files, no critical-path escalation or discovered dynamic edge |

## Coverage and mutation

- Red-first Board suite: 24 failed and 9 passed on the unmodified implementation.
- Green Board suite: 35 passed; the two-file Board/registry integration suite: 39 passed.
- Full deterministic suite: 1660 passed and 1 skipped; the skip is the pre-existing Mutmut
  console-script availability guard on Windows.
- The fast mutation selector returned no target. This package does not alter
  `.ai/quality/mutation.toml`, `.ai/quality/mutation-baseline.toml`, a configured mutation target,
  or a test that reaches one through the import graph. The critical ratchet is therefore vacuous,
  not deferred.
- The finding-pattern migration guard still proves all 58 pre-migration findings have identical
  content, while permitting the separately validated 59th content-addressed finding added here.

## Deferred checks

- Claude's independent R3 adversarial review has not run. The pull request must remain draft and
  `pr-ready` must remain NOT READY until `review.md` and this evidence record the completed review.
- Required GitHub checks will run on the draft/current head after push. They are not represented as
  local successes here.
