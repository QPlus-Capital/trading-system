# Evidence

## HEAD

HEAD: 364062d1f03f8e5ae7faf45c228c413d613604dd

The later evidence-only commit changes no document, guard, or test behaviour.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` against the unchanged page | 1 | The assertion received the seven retired contexts instead of the four active contexts. |
| `review-red-first` | Strengthened existing documentation test against the pre-remediation document | 1 | The test failed because `Set allowed merge methods to squash only` was not an explicit configured setting; review `4825906480` separately demonstrated that deleting the closing warning, adding `name`/`strategy`, and moving context bullets left the old guard green. |
| `focused` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` | 0 | The page names the exact four effective non-matrix workflow contexts and binds all applied parameters, reasons, and warning clauses. |
| `format` | `just check-standard` | 0 | Ruff, strict mypy over 193 source files, and Vulture passed. |
| `docs-consistency` | `just check` | 0 | The complete suite includes the engineering-document consistency guards; all passed. |
| `check` | `just check` | 0 | Ruff, strict mypy, Vulture, and pytest passed: 1,635 passed and one expected unavailable-Mutmut skip. |
| `impacted-tests` | `uv run pytest -q tests/test_engineering_workflow_docs.py tests/test_gate_consistency.py` | 0 | All 12 directly related documentation and workflow-consistency tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | All 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | `just check` | 0 | The full Windows repository integration suite passed with 1,635 tests and one capability skip. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 135 --base origin/main` | 0 | Task 135 is valid with five acceptance criteria and three invariants. |
| `adversarial-review` | Claude review `4825906480` on PR #145 | 1 | Every finding is dispositioned, but the complete independent re-review of the material fix has not run. |
| `invariants` | `just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | Python evaluation of `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | The production selector found zero mutation targets because no production or configured critical function changed. |
| `parity-where-applicable` | `just check` on Windows plus impact classification | 0 | The documentation and parsed YAML behavior is platform-independent and the Windows suite passed; no Linux run is claimed. |
| `live-money-review` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: no live, research, strategy, sizing, risk-limit, or trading path changed. |
| `human-decision-escalation` | Approved issue #135 and live-ruleset API comparison | 0 | Jan approved the exact R3 scope with no open business, trading, architecture, or risk decision. |
| `no-autonomous-merge` | `gh pr view 145 --json isDraft,autoMergeRequest,headRefName,url` | 0 | PR #145 remains draft on its feature branch with auto-merge disabled. |
| `security` | `just check-security` | 0 | Secret scan and Ruff security checks passed; pip-audit found no known vulnerability. |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Only the existing engineering-workflow documentation test is directly related; no production, critical-path, or unknown dynamic edge was found. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3, because `docs/engineering/**` is governance that protects live-money and result-integrity changes. |

## Coverage and mutation

The behavioral guard scopes context parsing to the required-status section, resolves each
workflow's effective context from `job.name` or its key, refuses matrix jobs, and requires exact
set equality with the four documented contexts. It also checks Active enforcement, no bypass
actors, code-owner policy, squash-only merging, the applied date, ruleset name, pull-request
parameters, deliberate zero-approval and non-strict-check reasons, generalized future-action
wording, and both closing-warning clauses. The live ruleset was read before and after the
repository edit; its rules, parameters, bypass actors, and required contexts were unchanged. No
production or configured mutation target changed.

The Linux-only mutation command was probed on Windows and correctly refused because Mutmut 3.5.0
requires `fork`. That refusal is not presented as a passing ratchet. The executable production
selector returned an empty target set, which is the applicable mutation result for this
documentation-only implementation.

## Deferred checks

- Claude's complete independent re-review of `364062d` is pending.
- `pr-ready` remains correctly blocked on that review alone.
- Linux parity has not been observed for this branch and is not claimed green while the pull
  request remains draft.
