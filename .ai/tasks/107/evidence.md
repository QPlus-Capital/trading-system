# Evidence

## HEAD

HEAD: fd2efe4f26d862277f4e004732fffeaaede8c659

This is the implementation commit. The only later commit is this evidence file, which
`pr_ready` explicitly accepts as evidence-only freshness.

## Commands

All `just` commands use the repository's required Windows shell override:
`uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command`.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample` on pre-renderer HEAD `5166b22`, after adding the nine fourth-review cases | 1 | RED: the seven earlier cases stayed protected, while **9 failed / 7 passed** because all nine new semantic violations were accepted by the prose parsers |
| `red-first-totality` | fifth-review execution against `f689ee4`, using the supplied `tests/test_review_counterexamples_107.py` regression and three contract mutations | 1 | RED: the existing complete suite accepted a deleted `Reviewing` → `Implementing` row, the documentation suite accepted a deleted #110 activation, and the documentation suite accepted an invented `Backlog` → `Done` edge; the supplied regression was green on the real contract and red on all three mutations |
| `red-first-complete-records` | sixth-review execution against `1b146f1` | 1 | RED: rewriting the approval transition trigger to "the specification is complete" left **165 documentation tests passing**; the same partial guard had no required status set and accepted replacing the `Ready to Implement` approval actor with plain `Claude` |
| `red-first-branch-protection` | `uv run pytest -q tests/test_engineering_docs.py::test_direct_to_main_exception_is_R0_only_everywhere` after removing the obsolete exception from the documents and before updating the guard | 1 | RED: **1 failed** because the old guard still required the now-prohibited trivial-R0 direct-to-main exception |
| `green-oracle` | `uv run pytest -q tests/test_workflow_contract.py` | 0 | GREEN: **29 passed** — complete-record guards plus all 21 counterexamples; all five TOML mutations regenerate the document views before the totality assertion |
| `format` | `just check-fast origin/main` | 0 | GREEN: five changed files formatted; Ruff and strict mypy clean over 183 files |
| `impacted-tests` | `just check-fast origin/main` | 0 | GREEN: **135 focused tests passed** |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py tests/test_finding_registry.py tests/test_quality_validate_task.py tests/test_docs_architecture_map.py` | 0 | GREEN: **201 passed** |
| `workflow-render-drift` | `uv run python -m scripts.quality.workflow_contract` | 0 | GREEN: generated blocks and all four non-generated document skeleton digests match |
| `check` | `just check` on clean implementation HEAD `fd2efe4` | 0 | GREEN: Ruff, strict mypy over 183 files, Vulture, and **1240 passed / 1 expected Windows Mutmut skip**; 98 existing warnings |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 1240 passed; no live terminal or account interaction |
| `invariants` | `just check-invariants` | 0 | GREEN: **325 passed**; 12 existing warnings |
| `security` | `just check-security` | 0 | GREEN: secret scan clean, pip-audit reports no known vulnerabilities, static security check clean |
| `impact` | `just impact` | 0 | GREEN: R3; only `scripts/quality/workflow_contract.py` is production code; seven focused suites selected; no critical-path escalation |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 0 | GREEN: task valid, **10 AC / 2 INV** |
| `parity-where-applicable` | `git diff --quiet origin/main...HEAD -- core research live monitoring .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: no trading, runner, hook, CI, recipe, or dependency path changed |
| `live-money-review` | `git diff --name-only origin/main...HEAD -- core research live monitoring` plus changed-path inspection | 0 | GREEN: zero trading production paths changed; no runner or terminal was contacted |
| `human-decision-escalation` | issue #107 review instructions and task spec | 0 | GREEN: Jan's accepted TOML renderer and exact record guards remain intact; Jan explicitly removed the obsolete trivial-R0 direct-to-main exception after branch protection became active without bypass actors |
| `no-autonomous-merge` | constitution/role-document guards and repository state | 0 | GREEN: no merge, auto-merge, PR creation, or ready transition occurred |
| `mutation-on-touched-critical` | `git diff --quiet origin/main...HEAD -- core research live monitoring` | 0 | GREEN, vacuous: issue #107 touches no configured critical mutation target or trading production file, so there is no touched mutant set to measure and no deferred mutation blocker |
| `adversarial-review` | Claude's seventh complete independent review in `.ai/tasks/107/review.md` | 0 | GREEN on 2026-07-29: no findings; all seven independent mutations were caught — transition deleted, transition invented, transition actor changed, approval-edge trigger rewritten, status actor changed, status deleted, activation deleted |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 107 --base origin/main` | 0 | GREEN: READY on implementation HEAD `fd2efe4`; the later evidence-only commit is accepted by the freshness check |

## Coverage and mutation

The renderer-owned contract facts remain in TOML. All complete status and transition records, plus
required activation identities, are independently pinned in the test module so a TOML edit cannot
authorize itself. TOML contains:

- seven statuses and meanings;
- 16 complete source/target/actor/trigger transitions;
- the disjoint Start and Resume condition/action records;
- four ordered approval actions with `approved` last;
- five activation owner/fallback records;
- the explicit gate lower bound, ready ordering, and #124 transitional review procedure.

`tests/test_workflow_contract.py` regenerates every contract-owned block and verifies that every TOML
record is emitted. Exact skeleton digests cover prose outside the generated blocks. Twenty-one
semantic oracle cases execute the original seven, the nine fourth-review document mutations, the
three fifth-review contract mutations, and the two sixth-review complete-record mutations. The last
five remove the review-loop return edge, remove the #110 activation, add an unauthorized `Backlog`
→ `Done` shortcut, rewrite Jan's approval trigger, and rewrite the approval-bearing status actor.
Their document views are regenerated before assertion, so renderer drift cannot hide a missing
totality guard.

The first uncommitted `just check` for this fifth-review fix reproduced the repository's known
Windows lineage-decoding defect: 54 research-lineage tests received `None` while Python decoded a
Unicode-bearing `git diff` through cp1252; 1184 tests passed. The identical clean implementation
commit passed 1238/1. No production workaround or test relaxation was made.

The security gate initially rejected ordinary SHA-256 hex snapshots as high-entropy strings. The
contract now stores each digest as 32 integer bytes and reconstructs it with strict range/length
validation. The secret scanner was not allowlisted or weakened.

The seventh complete independent review ran on `85f8498` and found nothing. It confirmed that
`_AUTHORIZED_EDGES` and prefix matching are absent, the status, transition, and activation
comparisons are exact set equality in both directions, and the TOML was byte-identical to its
previous reviewed state. Its seven independent record mutations were all rejected.

The later Jan-directed branch-protection synchronization changes no status, transition, activation,
builder-guard, approval, gate, ready-order, or transitional-review record. It removes the obsolete
trivial-R0 direct-to-main exception from the four contributor-facing documents and updates only
their three stored skeleton hashes in the TOML. The revised guard requires the new rule positively
and rejects the old exception.

The critical mutation gate is vacuous, not deferred: the full branch diff contains no file under
`core`, `research`, `live`, or `monitoring`, and no mutation baseline, target, pattern, threshold, or
survivor classification changed.

## Deferred checks

None. Branch protection is active on `main` with no bypass actors. Its seven required checks still
run on the pull request; the local R3 evidence above is complete.
