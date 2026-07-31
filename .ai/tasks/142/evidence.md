# Evidence

## HEAD

HEAD: e14c6ed0683b1b7bc2d82e4099c5665f6bcc1e53

The later evidence-only commit changes no policy, baseline, test, production code, or workflow.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | Six named issue-142 policy/workflow tests against unchanged `origin/main` | 1 | RED: all 6 failed because the Board target, selector result, Mutmut path/test selection, baseline target, target-specific ratchet case, and workflow selection were absent |
| `red-first` | Focused mutation tests after adding the target but before updating the baseline | 1 | RED: the prior fingerprint `8de068…` differed from `5783b1…`, and the baseline contained neither the target nor its survivors |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3: the mutation policy and baseline govern the result-integrity gate; 11 changed paths classified cumulatively |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | GREEN: all 3 changed Python files are formatted |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_workflow_contract.py` | 0 | GREEN: 88 passed |
| `check` | `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check` | 0 | GREEN: Ruff, strict mypy over 193 source files, Vulture, and pytest; 1,720 passed and one expected Windows Mutmut-availability test skipped |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_quality_mutation.py tests/test_ci_cost_workflows.py` | 0 | GREEN: 271 passed and one expected Windows Mutmut-availability test skipped |
| `property-tests-where-applicable` | `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-properties` | 0 | GREEN: the fixed seed replay passed twice, 21 tests on each execution |
| `integration-tests` | `uv run pytest -q tests/test_quality_board.py tests/test_quality_mutation.py tests/test_ci_cost_workflows.py` | 0 | GREEN: 271 passed across Board behavior, production policy/config/baseline integration, and unchanged workflow selection |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 142 --base origin/main` | 0 | GREEN: task 142 valid with 7 AC and 3 INV |
| `invariants` | `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-invariants` | 0 | GREEN: 529 critical invariant tests passed |
| `mutation-on-touched-critical` | [Linux Critical mutation run `30618204290`](https://github.com/QPlus-Capital/trading-system/actions/runs/30618204290) on `d1ee42b` | 0 | GREEN: exact ratchet passed with fingerprint `5783b1…`; 5,485 total, 5,072 killed, 413 survived, and every unhealthy status zero |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main` plus `git diff --exit-code origin/main -- scripts/quality/board.py` | 0 | Not applicable: no signal, adapter, research, portfolio, live, or production Board behavior changed; the Board module is byte-identical |
| `live-money-review` | Changed-path and production-diff inspection | 0 | Not applicable: no `core/**`, `research/**`, `live/**`, or `monitoring/**` path changed, and no runner, account, order, threshold, or risk limit was touched |
| `human-decision-escalation` | Issue #142 contract and approved scope inspection | 0 | GREEN: Jan selected the exact-target variant after #136 merged; no open business, methodology, architecture, live-money, or risk decision was inferred |
| `security` | `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-security` | 0 | GREEN: secret scan, locked dependency audit, and security lint all passed with no findings |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | R3; no changed production file, unknown/dynamic edge, or critical escalation; exactly 3 directly related tests |

## Coverage and mutation

- Commit `5169c5d` records the red contract. Native run `30616591967` then measured the unchanged
  Board behavior against the new target: 314 Board mutants, 272 killed, and 42 survived.
- Commit `44d5d4a` adds only new behavioral tests. Native run `30617552213` measured the same 314
  Board mutants: 311 killed and exactly 3 survived. Thus the new tests kill all 39 observable
  survivors, including issue propagation, validation, guard selection, write verification, and
  exact fail-closed diagnostics.
- Generated-source inspection shows the three survivors are equivalent variants of
  `transition.target != "Done"` inside `BoardService.move`. The exact `"Done"` input is rejected by
  an earlier guard; every other input makes the original and all three mutated comparisons true.
- Commit `d1ee42b` appends those three exact names with that observability proof, updates the
  fingerprint, and preserves all 27 prior targets and 410 prior exact survivors in their original
  order. Native run `30618204290` passes the committed ratchet.
- The final report contains 5,485 total mutants, 5,072 killed, 413 survived, and zero `no_tests`,
  `skipped`, `suspicious`, `timeout`, `not_checked`, `interrupted`, `segfault`, or
  `caught_by_type_check` outcomes.
- The full deterministic suite ran on Windows. Linux executed the complete critical mutation
  scope; a separate Linux full pytest suite was not run and is not claimed.

## Deferred checks

- A fresh independent Claude review on the draft pull request is pending. Until it is complete,
  `adversarial-review`, `no-autonomous-merge`, `check-pr-evidence`, and `pr-ready` are deliberately
  not recorded as passing.
- No validation is deferred from the implementation or exact mutation baseline.
