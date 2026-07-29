# Evidence

## HEAD

HEAD: 0e56193677a966c80e6c352e8c4ae2f48d376fad

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 from the finding registry, workflow contracts, role contracts, constitution, and quality tooling; 107 changed paths classified. |
| `red-first` | `uv run pytest -q tests/test_review_selection.py tests/test_claude_runtime_files.py tests/test_finding_registry_split.py tests/test_finding_registry.py tests/test_quality_validate_task.py tests/test_engineering_docs.py tests/test_workflow_contract.py` | 1 | Collection stopped on `ModuleNotFoundError: scripts.quality.review_selection`; the executable selection source did not exist before implementation. |
| `format` | `uvx --from rust-just just check-standard` | 0 | Ruff, strict mypy over 189 files, and Vulture passed. |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract` | 0 | Generated blocks and all four skeleton digests match the machine contract. |
| `check` | `uvx --from rust-just just check-standard` and `uvx --from rust-just just check-tests` | 0 | The two CI recipes passed: static quality green; 1,615 tests passed with the one intentional Windows Mutmut-unavailable skip. |
| `impacted-tests` | `uv run pytest -q tests/test_claude_runtime_files.py tests/test_engineering_docs.py tests/test_finding_registry.py tests/test_finding_registry_split.py tests/test_github_templates.py tests/test_quality_hooks.py tests/test_quality_pr_ready.py tests/test_quality_process_scaling.py tests/test_quality_validate_task.py tests/test_review_selection.py tests/test_workflow_contract.py tests/test_workflow_system_validation.py` | 0 | All 202 tests recommended by the production impact engine passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Fixed seed `20260721` passed twice: 21 plus 21 properties. |
| `integration-tests` | same 202-test impacted command | 0 | Skill discovery, review selection, registry loading, task validation, workflow rendering, templates, hooks, and readiness integrate cleanly. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-111-112 --base origin/main` | 0 | Valid R3 task: 11 acceptance criteria and 4 invariants mapped. |
| `adversarial-review` | independent Claude review on the draft pull request | 1 | Pending by design; the builder has not reviewed its own work. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | production `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | Exact result `[]`: none of the four changed quality modules is a configured mutation target. Native Mutmut remains Linux-only; no mutation claim or baseline change is made. |
| `parity-where-applicable` | `git diff --name-only origin/main...HEAD` | 0 | No `core/**`, `research/**`, `live/**`, or `monitoring/**` production path changed; trading parity is not applicable. |
| `live-money-review` | `git diff --name-only origin/main...HEAD` | 0 | No live-money, runner, bridge, order, sizing, risk-limit, or account path changed or ran; the executable selection matrix does not select the live-money reviewer for these paths. |
| `human-decision-escalation` | approved issue bodies for #111 and #112 | 0 | Both issues have no open Jan decision; both permits were valid and consumed before work began. |
| `no-autonomous-merge` | draft pull-request state and auto-merge inspection | 0 | The pull request will remain draft, auto-merge disabled, and Jan retains ready/merge authority. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean after encoding migration digests as byte arrays; pip-audit found no known vulnerabilities; security Ruff passed. |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Four changed quality modules, twelve directly related test modules, no transitive or dynamic unknowns, and no critical mutation target. |

## Coverage and mutation

The red-first collection failure proves the matrix was absent. After implementation, 148 initial
focused tests and the final 202-test impact set passed. The complete suite passed 1,615 tests; the
property replay passed 21 tests twice; and 529 critical invariants passed.

All 58 pattern records match the committed pre-migration witness on every non-severity field and
the exact four-value mapping. All legacy numeric IDs load under refreshed digests, all three
content-addressed records have filenames derived from their migrated content, and every regression
reference resolves.

The production mutation selector returned an empty target tuple. `mutation-fast` also confirmed the
platform boundary by refusing on Windows before mutation execution; the authoritative selector,
not that refusal, is the applicability evidence. No mutation policy, target, baseline, threshold,
or survivor classification changed.

## Deferred checks

Independent Claude review is intentionally deferred until the draft pull request exists. The
`adversarial-review` gate remains non-zero, so readiness must remain blocked. Jan alone makes the
pull request ready and merges it.
