# Evidence

## HEAD

HEAD: da99894416fcfedfc29c82d4cdcd79518e482efc

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` against the unchanged page | 1 | The assertion received the seven retired contexts instead of the four active contexts. |
| `focused` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` | 0 | The corrected page names the exact four workflow jobs and all applied parameters and reasons. |
| `format` | `just check-standard` | 0 | Ruff, strict mypy over 193 source files, and Vulture passed. |
| `docs-consistency` | `just check` | 0 | The complete suite includes the engineering-document consistency guards; all passed. |
| `check` | `just check` | 0 | Ruff, strict mypy, Vulture, and pytest passed: 1,635 passed and one expected unavailable-Mutmut skip. |
| `impacted-tests` | `uv run pytest -q tests/test_engineering_workflow_docs.py tests/test_gate_consistency.py` | 0 | All 12 directly related documentation and workflow-consistency tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | All 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | `just check` | 0 | The full Windows repository integration suite passed with 1,635 tests and one capability skip. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 135 --base origin/main` | 0 | Task 135 is valid with five acceptance criteria and three invariants. |
| `invariants` | `just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | Python evaluation of `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | The production selector found zero mutation targets because no production or configured critical function changed. |
| `parity-where-applicable` | `just check` on Windows plus impact classification | 0 | The documentation and parsed YAML behavior is platform-independent and the Windows suite passed; no Linux run is claimed. |
| `human-decision-escalation` | Approved issue #135 and live-ruleset API comparison | 0 | Jan approved the exact R3 scope with no open business, trading, architecture, or risk decision. |
| `security` | `just check-security` | 0 | Secret scan and Ruff security checks passed; pip-audit found no known vulnerability. |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Only the existing engineering-workflow documentation test is directly related; no production, critical-path, or unknown dynamic edge was found. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3, because `docs/engineering/**` is governance that protects live-money and result-integrity changes. |

## Coverage and mutation

The behavioral guard parses the two workflow files and compares their job keys with the four
contexts documented on the page. It also checks the applied date, ruleset name, pull-request
parameters, deliberate zero-approval and non-strict-check reasons, and removal of the future-action
sentence. The live ruleset was read before and after the repository edit; its rules, parameters,
bypass actors, and required contexts were unchanged. No production or configured mutation target
changed.

The Linux-only mutation command was probed on Windows and correctly refused because Mutmut 3.5.0
requires `fork`. That refusal is not presented as a passing ratchet. The executable production
selector returned an empty target set, which is the applicable mutation result for this
documentation-only implementation.

## Deferred checks

- Independent Claude review and live-money review are pending.
- `pr-ready` and final evidence freshness are pending that review.
- Linux parity has not been observed for this branch and is not claimed green while the pull
  request remains draft.
