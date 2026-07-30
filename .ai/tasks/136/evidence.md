# Evidence

## HEAD

HEAD: eca4f1e0af7bef5be65c6ff8c330a6d667fe795d

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py` against `origin/main` | 1 | RED: 27 failed, 8 passed; stale permits survived moves, `withdraw` was absent, and refusal diagnostics were generic |
| `review-red-first` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py` against `1c0b10b` | 1 | RED: 7 failed, 49 passed; the generic build-start bypass, partial-failure diagnostic, move absence message, raw-stderr leak, and undocumented command surface were reproduced |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3: `scripts/quality/board.py` and the finding registry govern every later change |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: changed Python files formatted; Ruff and strict mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_workflow_contract.py` | 0 | GREEN: 88 passed; the documented command surface and updated non-generated hash match without contract-fact drift |
| `check` | `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check` | 0 | GREEN: Ruff, strict mypy, Vulture, and pytest; 1677 passed, 1 skipped because Mutmut is unavailable on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py tests/test_finding_registry.py` | 0 | GREEN: 61 passed |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` (twice) | 0 | GREEN: 21 passed on each deterministic replay |
| `integration-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py tests/test_finding_registry.py` | 0 | GREEN: 61 passed, including CLI dispatch, concurrent writes, reference resolution, and content-addressed registry integration |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 136 --base origin/main` | 0 | GREEN: task 136 valid with 13 AC and 4 INV |
| `adversarial-review` | Claude review 4818275329 on PR #140 | 1 | BLOCKED: the first complete review found R-01/R-02, S1-S8, R-03, and Notes; fixes are built, but the required complete re-review has not run |
| `invariants` | `uv run pytest -q tests/test_live_risk_control.py tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_signal_adapter_parity.py tests/test_strategy_sizing_basis.py tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_portfolio_dd.py tests/test_research_risk.py tests/test_research_stats.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_continuous_windows.py tests/test_research_regression.py tests/test_research_forward_test_registry.py tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py tests/test_quality_classify.py tests/test_quality_pr_ready.py` | 0 | GREEN: 529 passed |
| `mutation-on-touched-critical` | `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | GREEN (vacuous): selector returned `[]`; no configured mutation target is touched directly or through the import graph |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: only board tooling and its tests changed; no signal, research, portfolio, or live adapter path changed |
| `live-money-review` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: no `core/**`, `research/**`, `live/**`, or `monitoring/**` path changed and no terminal or runner was contacted |
| `human-decision-escalation` | review 4818275329 decision audit plus Jan's remediation scope | 0 | GREEN: R-04/decision 2, the constitution-versus-contract ordering scope, and adding `board.py` as a mutation target remain explicit Jan decisions; N4 stays with #134; none was guessed or changed |
| `no-autonomous-merge` | `gh pr view 140 --json isDraft,state,autoMergeRequest,headRefName,url` | 0 | GREEN: PR #140 remains OPEN and draft with `autoMergeRequest` null; the card is temporarily `Implementing` for remediation |
| `security` | `uv run python -m scripts.quality.security`; `uv run pip-audit --skip-editable`; `uv run ruff check core research live monitoring scripts --select S --ignore S101,S110,S603,S607` | 0 | GREEN: no secret findings, no known dependency vulnerabilities, and security lint passed |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | R3; one production file, two directly related test files, no critical-path escalation or discovered dynamic edge |

## Coverage and mutation

- Original final Board suite against `origin/main`: 27 failed and 8 passed.
- Review-remediation counterexamples against `1c0b10b`: 7 failed and 49 passed.
- Green Board/registry integration suite: 61 passed.
- Full deterministic suite: 1677 passed and 1 skipped; the skip is the pre-existing Mutmut
  console-script availability guard on Windows.
- The fast mutation selector returned no target. This package does not alter
  `.ai/quality/mutation.toml`, `.ai/quality/mutation-baseline.toml`, a configured mutation target,
  or a test that reaches one through the import graph. The critical ratchet is therefore vacuous,
  not deferred.
- The finding-pattern migration guard proves all 58 pre-migration findings have identical content
  and also proves every loaded finding has unique severity-independent content. Six
  content-addressed review patterns replace the original branch-local pattern, for 64 total.

## Deferred checks

- Claude's complete independent R3 re-review has not run. The pull request must remain draft and
  `pr-ready` must remain NOT READY until the reviewer records it.
- Per Jan's explicit scope, this remediation does not decide R-04/decision 2 (`withdraw` plus
  `arm` without a board trace), decision 1 (constitutional versus contract wording), decision 3
  (`board.py` as a mutation target), or N4 (tracked by #134).
- Required GitHub checks run on the pushed draft head. Their results are not represented as local
  successes here; independent review remains the only intentionally incomplete readiness step.
