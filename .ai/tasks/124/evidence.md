# Evidence

## HEAD

HEAD: 9cf42d098904cd86e3b8f24c9c8e2f79d6fcaaca

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python scripts/quality/classify.py .ai/quality/task-artifacts.toml scripts/quality/pr_ready.py AGENTS.md tests/test_workflow_contract.py` | 0 | R3 from quality policy, readiness tooling, and the builder contract. |
| `red-first` | `uv run pytest -q tests/test_quality_process_scaling.py tests/test_finding_registry_split.py` | 1 | RED during collection: missing `pr_transition_decision` and missing `scripts.quality.finding_registry`; 2 collection errors. |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | 17 changed Python files formatted; Ruff and mypy passed. |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract` and `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_workflow_contract.py` | 0 | Generated contract matched its TOML facts; 92 documentation/contract tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, mypy, vulture, and full pytest passed: 1572 passed, 1 Windows mutation skip. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Conservative focused set passed: 177 tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Deterministic property replay passed twice: 21 + 21. |
| `integration-tests` | `uv run pytest -q tests/test_workflow_system_validation.py tests/test_quality_process_scaling.py tests/test_finding_registry_split.py` | 0 | 19 end-to-end workflow, scaling, and real-Git merge cases passed. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 124 --base origin/main` | 1 | Expected at draft handover: schema files are present, but independent review has not run. |
| `adversarial-review` | `Claude fresh-session review on draft PR` | 1 | Not run; builder must not review its own work. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | `uvx --from rust-just just mutation-critical` | 1 | Local platform refusal: mutmut 3.5 requires fork and WSL is not installed; the dedicated Linux required check must supply this result. |
| `parity-where-applicable` | `git diff --name-only origin/main...HEAD` | 0 | No `core/**`, `research/**`, `live/**`, or `monitoring/**` path changed; trading parity is not applicable. |
| `live-money-review` | `git diff --name-only origin/main...HEAD` | 0 | No live-money or trading path changed; the R3 review is workflow-focused. |
| `human-decision-escalation` | `gh issue view 124 --comments --json body,comments,labels,projectItems` | 0 | No open Jan decision; the approved 5/8/14/20 workflow contract controls the stale AC-02 class name. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found 0 known vulnerabilities, Ruff security checks passed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; 7 quality-tool production files and 11 directly related tests; no dynamic or critical-path edge discovered. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 124 --base origin/main` | 1 | Correctly NOT READY because independent review and Linux mutation evidence are not complete. |

## Coverage and mutation

The focused red/green suite passed 110 tests and the complete focused workflow set
passed 177. The full suite passed 1572 with only the repository's intentional
Windows mutmut skip. No mutation target, pattern, threshold, baseline, or survivor
classification changed. The production mutation tree is therefore unchanged; the
required Linux job remains the authoritative ratchet observation.

## Deferred checks

Independent adversarial review is intentionally deferred to Claude on the draft pull
request. The Linux mutation gate is deferred to the required GitHub Actions Linux job
because native Windows lacks `fork` and this machine has no WSL installation. After
both complete, replace the non-zero rows, rerun `pr_ready` on the then-current HEAD,
and only then mark the pull request ready for review. The no-autonomous-merge check is
confirmed after draft creation.
