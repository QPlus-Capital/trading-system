# Evidence

## HEAD

HEAD: c9ae366497b1e90b18ee4cae69d0f952200facff

This is the implementation commit. The only later commit is this evidence file, which
`pr_ready` explicitly accepts as evidence-only freshness.

## Commands

All `just` commands use the repository's required Windows shell override:
`uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command`.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample` on pre-renderer HEAD `5166b22`, after adding the nine fourth-review cases | 1 | RED: the seven earlier cases stayed protected, while **9 failed / 7 passed** because all nine new semantic violations were accepted by the prose parsers |
| `green-oracle` | `uv run pytest -q tests/test_workflow_contract.py` | 0 | GREEN: **21 passed** — loader/render/drift guards plus all 16 counterexamples |
| `format` | `just check-fast` | 0 | GREEN: five changed Python files formatted; Ruff and strict mypy clean over 183 files |
| `impacted-tests` | `just check-fast` | 0 | GREEN: **127 focused tests passed** |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py tests/test_finding_registry.py tests/test_quality_validate_task.py tests/test_docs_architecture_map.py` | 0 | GREEN: **193 passed** |
| `workflow-render-drift` | `uv run python -m scripts.quality.workflow_contract` | 0 | GREEN: generated blocks and all four non-generated document skeleton digests match |
| `check` | `just check` | 0 | GREEN: Ruff, strict mypy over 183 files, Vulture, and **1232 passed / 1 expected Windows Mutmut skip**; 98 existing warnings |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 1232 passed; no live terminal or account interaction |
| `invariants` | `just check-invariants` | 0 | GREEN: **325 passed**; 12 existing warnings |
| `security` | `just check-security` | 0 | GREEN: secret scan clean, pip-audit reports no known vulnerabilities, static security check clean |
| `impact` | `just impact` | 0 | GREEN: R3; only `scripts/quality/workflow_contract.py` is production code; seven focused suites selected; no critical-path escalation |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 0 | GREEN: task valid, **10 AC / 2 INV** |
| `parity-where-applicable` | `git diff --quiet origin/main...HEAD -- core research live monitoring .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: no trading, runner, hook, CI, recipe, or dependency path changed |
| `live-money-review` | `git diff --name-only origin/main...HEAD -- core research live monitoring` plus changed-path inspection | 0 | GREEN: zero trading production paths changed; no runner or terminal was contacted |
| `human-decision-escalation` | issue #107 fourth-review instruction and task spec | 0 | GREEN: Jan's decision to replace prose parsing with TOML data/rendering is recorded; no contract fact was changed |
| `no-autonomous-merge` | constitution/role-document guards and repository state | 0 | GREEN: no merge, auto-merge, PR creation, or ready transition occurred |
| `mutation-on-touched-critical` | `just mutation-critical` | 1 | **BLOCKED BY INFRASTRUCTURE:** Mutmut 3.5.0 requires fork/WSL and refuses native Windows. The dedicated Linux Actions job cannot start because the organisation allowance is exhausted until 2026-08-01. No trading critical function or configured critical mutation target changed. |
| `adversarial-review` | `.ai/tasks/107/review.md` after the material fourth-review remediation | 1 | **BLOCKED BY REQUIRED HANDOVER:** Claude's fresh complete independent review has not yet run. Builder dispositions are recorded but are not review coverage. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 107 --base origin/main` | 1 | NOT READY as required: only the fresh adversarial review and Linux critical mutation gate remain blocking |

## Coverage and mutation

The contract facts are no longer duplicated in Python expectations. TOML contains:

- seven statuses and meanings;
- 16 complete source/target/actor/trigger transitions;
- the disjoint Start and Resume condition/action records;
- four ordered approval actions with `approved` last;
- five activation owner/fallback records;
- the explicit gate lower bound, ready ordering, and #124 transitional review procedure.

`tests/test_workflow_contract.py` regenerates every contract-owned block and verifies that every TOML
record is emitted. Exact skeleton digests cover prose outside the generated blocks. All 16 semantic
oracle cases mutate temporary document copies: the original seven, plus Force, an extra AGENTS start
rule, duplicate Start, duplicate activation, a second transition table, non-terminal Done, a
neighbouring gate ceiling, and both ready-PR role regressions.

The first uncommitted `just check` reproduced the repository's known Windows lineage-decoding defect:
54 research-lineage tests received `None` while Python decoded a Unicode-bearing `git diff` through
cp1252. The identical committed tree passed 1232/1. No production workaround or test relaxation was
made.

The security gate initially rejected ordinary SHA-256 hex snapshots as high-entropy strings. The
contract now stores each digest as 32 integer bytes and reconstructs it with strict range/length
validation. The secret scanner was not allowlisted or weakened.

The Linux mutation gate cannot be substituted locally. It must run after the Actions allowance
resets. No mutation baseline, target, threshold, or survivor classification changed in this work.

## Deferred checks

- **Fresh independent review — blocking.** This remediation replaces the load-bearing guard
  architecture and changes AGENTS' handover procedure. Claude must review the complete diff in fresh
  context. The branch remains in `Reviewing`; no pull request is opened under the #124 transitional
  rule.
- **Linux critical mutation — infrastructure blocked.** On or after 2026-08-01, retrigger the
  dedicated Linux job and record its real outcome. Native Windows cannot run Mutmut because it lacks
  `fork`.
- **Branch protection — external.** GitHub's repository plan still prevents the intended branch
  protection. This change neither claims nor activates it.
