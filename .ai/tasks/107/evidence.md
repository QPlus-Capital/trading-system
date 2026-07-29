# Evidence

## HEAD

HEAD: 6d7dcb76e86391425267e52dc326aa315e4a2d89

This is the implementation commit. The only later commit is this evidence file, which
`pr_ready` explicitly accepts as evidence-only freshness.

## Commands

All `just` commands use the repository's required Windows shell override:
`uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command`.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample` on pre-renderer HEAD `5166b22`, after adding the nine fourth-review cases | 1 | RED: the seven earlier cases stayed protected, while **9 failed / 7 passed** because all nine new semantic violations were accepted by the prose parsers |
| `red-first-totality` | fifth-review execution against `f689ee4`, using the supplied `tests/test_review_counterexamples_107.py` regression and three contract mutations | 1 | RED: the existing complete suite accepted a deleted `Reviewing` → `Implementing` row, the documentation suite accepted a deleted #110 activation, and the documentation suite accepted an invented `Backlog` → `Done` edge; the supplied regression was green on the real contract and red on all three mutations |
| `green-oracle` | `uv run pytest -q tests/test_workflow_contract.py` | 0 | GREEN: **27 passed** — the three new guards plus all 19 counterexamples; each new TOML mutation regenerates the document views before the totality assertion |
| `format` | `just check-fast` | 0 | GREEN: Ruff and strict mypy clean over 183 files |
| `impacted-tests` | `just check-fast` | 0 | GREEN: **133 focused tests passed** |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py tests/test_finding_registry.py tests/test_quality_validate_task.py tests/test_docs_architecture_map.py` | 0 | GREEN: **199 passed** |
| `workflow-render-drift` | `uv run python -m scripts.quality.workflow_contract` | 0 | GREEN: generated blocks and all four non-generated document skeleton digests match |
| `check` | `just check` on clean implementation HEAD `6d7dcb7` | 0 | GREEN: Ruff, strict mypy over 183 files, Vulture, and **1238 passed / 1 expected Windows Mutmut skip**; 98 existing warnings |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 1238 passed; no live terminal or account interaction |
| `invariants` | `just check-invariants` | 0 | GREEN: **325 passed**; 12 existing warnings |
| `security` | `just check-security` | 0 | GREEN: secret scan clean, pip-audit reports no known vulnerabilities, static security check clean |
| `impact` | `just impact` | 0 | GREEN: R3; only `scripts/quality/workflow_contract.py` is production code; seven focused suites selected; no critical-path escalation |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 0 | GREEN: task valid, **10 AC / 2 INV** |
| `parity-where-applicable` | `git diff --quiet origin/main...HEAD -- core research live monitoring .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: no trading, runner, hook, CI, recipe, or dependency path changed |
| `live-money-review` | `git diff --name-only origin/main...HEAD -- core research live monitoring` plus changed-path inspection | 0 | GREEN: zero trading production paths changed; no runner or terminal was contacted |
| `human-decision-escalation` | issue #107 fourth- and fifth-review instructions and task spec | 0 | GREEN: Jan's accepted TOML renderer remains intact; the fifth-review decision pins authorized records in the test rather than inside the guarded TOML; no contract fact changed |
| `no-autonomous-merge` | constitution/role-document guards and repository state | 0 | GREEN: no merge, auto-merge, PR creation, or ready transition occurred |
| `mutation-on-touched-critical` | `just mutation-critical` | 1 | **BLOCKED BY INFRASTRUCTURE:** Mutmut 3.5.0 requires fork/WSL and refuses native Windows. The dedicated Linux Actions job cannot start because the organisation allowance is exhausted until 2026-08-01. No trading critical function or configured critical mutation target changed. |
| `adversarial-review` | `.ai/tasks/107/review.md` after the fifth-review totality fix | 1 | **BLOCKED BY REQUIRED HANDOVER:** Claude has not independently reviewed the fix to its fifth-review finding. The builder disposition is recorded but is not review coverage. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 107 --base origin/main` | 1 | NOT READY as required: only the fresh adversarial review and Linux critical mutation gate remain blocking |

## Coverage and mutation

The renderer-owned contract facts remain in TOML. The authorized transition graph, required
semantic transition identities, and required activation identities are independently pinned in the
test module so a TOML edit cannot authorize itself. TOML contains:

- seven statuses and meanings;
- 16 complete source/target/actor/trigger transitions;
- the disjoint Start and Resume condition/action records;
- four ordered approval actions with `approved` last;
- five activation owner/fallback records;
- the explicit gate lower bound, ready ordering, and #124 transitional review procedure.

`tests/test_workflow_contract.py` regenerates every contract-owned block and verifies that every TOML
record is emitted. Exact skeleton digests cover prose outside the generated blocks. Nineteen
semantic oracle cases execute the original seven, the nine fourth-review document mutations, and
the three fifth-review contract mutations. The latter remove the review-loop return edge, remove
the #110 activation, and add an unauthorized `Backlog` → `Done` shortcut. Their document views are
regenerated before assertion, so renderer drift cannot hide a missing totality guard.

The first uncommitted `just check` for this fifth-review fix reproduced the repository's known
Windows lineage-decoding defect: 54 research-lineage tests received `None` while Python decoded a
Unicode-bearing `git diff` through cp1252; 1184 tests passed. The identical clean implementation
commit passed 1238/1. No production workaround or test relaxation was made.

The security gate initially rejected ordinary SHA-256 hex snapshots as high-entropy strings. The
contract now stores each digest as 32 integer bytes and reconstructs it with strict range/length
validation. The secret scanner was not allowlisted or weakened.

The Linux mutation gate cannot be substituted locally. It must run after the Actions allowance
resets. No mutation baseline, target, threshold, or survivor classification changed in this work.

## Deferred checks

- **Fresh independent review — blocking.** Claude must independently verify the fix to the
  fifth-review totality finding. The builder has not reviewed its own change. The branch remains in
  `Reviewing`; no pull request is opened or marked ready under the #124 transitional rule.
- **Linux critical mutation — infrastructure blocked.** On or after 2026-08-01, retrigger the
  dedicated Linux job and record its real outcome. Native Windows cannot run Mutmut because it lacks
  `fork`.
- **Branch protection — external.** GitHub's repository plan still prevents the intended branch
  protection. This change neither claims nor activates it.
