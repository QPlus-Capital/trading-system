# Evidence

## HEAD

HEAD: 884d190b0716af744e86e9e48f25b8edf0a2da78

The later evidence-only commit changes no production code, guard, or test behaviour.

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py` from `a91eed6` against production `origin/main` | 1 | RED: 27 failed, 8 passed; stale permits survived moves, `withdraw` was absent, and refusal diagnostics were generic |
| `review-red-first` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py` from the first remediation against `1c0b10b` | 1 | RED: 7 failed, 49 passed; seven behavioral defects reproduced the generic build-start bypass, partial-failure diagnostic, move absence message, raw-stderr leak, and undocumented command surface |
| `review-coverage-ratchet` | independent mutation probes in reviews `4818275329`, `4819183725`, `4823058968`, and `4823428302`; combined local hand-mutant against the four round-four guards | 0 | GREEN: prefix recognition in `arm` and `_write_approved`, an R3 constant in the conflict branch, and stale-state removal in `start` produced exactly 4 targeted failures and 4 unaffected passes |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3: `scripts/quality/board.py` and the finding registry govern every later change |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | GREEN: all three changed Python files formatted and impact analysis completed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_workflow_contract.py` | 0 | GREEN: 88 passed; the documented command surface and updated non-generated hash match without contract-fact drift |
| `check` | PowerShell: `$env:PYTHONUTF8='1'; just --shell "C:\Program Files\Git\bin\sh.exe" check` | 0 | GREEN: Ruff, strict mypy over 193 source files, Vulture, and pytest; 1698 passed, 1 skipped because Mutmut is unavailable on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py tests/test_finding_registry.py` | 0 | GREEN: 82 passed |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` (twice) | 0 | GREEN: 21 passed on each deterministic replay |
| `integration-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py tests/test_finding_registry.py` | 0 | GREEN: 82 passed, including CLI refusal, concurrent and lost writes, every arm conflict class, exact lookalike handling, reference resolution, and content-addressed registry integration |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 136 --base origin/main` | 0 | GREEN: task 136 valid with 13 AC and 4 INV |
| `adversarial-review` | Claude reviews `4818275329`, `4819183725`, `4823058968`, and `4823428302` on PR #140 | 1 | BLOCKED: every actionable finding through round four is resolved and recorded, but the required complete re-review of current head has not run |
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
- Review-remediation counterexamples against `1c0b10b`: 7 failed and 49 passed. Nine other tests
  closed coverage gaps on unchanged behavior and independently killed at least one mutant each.
- Round-three review found the wrong regex lookalike, masked Start refusals, one unreachable
  approval interleaving, and two unpinned operational outcomes. The discriminating `risk:R4`
  Start matrix, exact refusal prefix, production `arm` interleaving, CLI exit assertion, and
  zero-write assertion each kill their named mutants.
- Round-four review correctly identified that the Start matrix could not reach `arm` or
  `_write_approved`. Dedicated production-`arm` tests now bind both exact-risk sites; the conflict
  branch runs at R0, R1, R2, and R3; withdrawal is composed with a refused Start; and Start's
  removal short-circuit is pinned to the post-move state. No production behavior changed.
- Green Board/registry integration suite: 82 passed.
- Full deterministic suite: 1698 passed and 1 skipped; the skip is the pre-existing Mutmut
  console-script availability guard on Windows.
- The first Windows `just check` probe omitted `PYTHONUTF8`; Git-diff subprocess output was decoded
  as CP1252, reader threads returned `None`, and 54 lineage tests failed secondarily. The identical
  code passed after forcing Python UTF-8. No test, production file, or gate was changed for this
  environment-only failure.
- The fast mutation selector returned no target. This package does not alter
  `.ai/quality/mutation.toml`, `.ai/quality/mutation-baseline.toml`, a configured mutation target,
  or a test that reaches one through the import graph. The critical ratchet is therefore vacuous,
  not deferred.
- The finding-pattern migration guard proves all 58 pre-migration findings have identical content,
  names every changed or missing digest explicitly, and proves every loaded finding has unique
  severity-independent content. Three review patterns were strengthened and rehashed without
  changing the 64-finding total.

## Deferred checks

- Claude's complete independent R3 re-review of `884d190` has not run. The pull request must remain
  draft and `pr-ready` must remain NOT READY until the reviewer records it.
- Per Jan's explicit scope, this remediation does not decide R-04/decision 2 (`withdraw` plus
  `arm` without a board trace), decision 1 (constitutional versus contract wording), decision 3
  (`board.py` as a mutation target), or N4 (tracked by #134).
- Required GitHub checks run on the pushed draft head. Their results are not represented as local
  successes here; independent review remains the only intentionally incomplete readiness step.
