# Evidence

## HEAD

HEAD: 93e9a8bddf731351cdcebb502ada531752dad3d6

`origin/main` was merged into the branch first, so this evidence binds a tree that already contains
every pull request merged up to `8b75ff0` (#96, #97, #98, #100, #116, #119). Comparisons below use
the merge base (`origin/main...HEAD`), not the two-dot form, which would otherwise report PR #96's
files as changes of this task.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample tests/test_quality_validate_task.py::test_every_task_plan_test_reference_collects` before the parser and task-map fixes | 1 | RED: **8 failed** — all seven committed semantic counterexamples failed because the old guard did not raise, and the node-id collector rejected the stale shorthand/deleted test names |
| `format` | `uvx --from rust-just just check-fast` | 0 | GREEN: format, Ruff and mypy passed; **116 focused tests** |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py` | 0 | GREEN: **161 passed**, including seven primary contract guards and all seven committed counterexamples |
| `check` | `uvx --from rust-just just check` | 0 | GREEN at committed code HEAD: Ruff, mypy, vulture and **1224 passed**, 1 skipped (mutmut needs fork/WSL on Windows) |
| `impacted-tests` | `uvx --from rust-just just check-fast` | 0 | GREEN: impact selected six engineering workflow/validator suites; **116 passed** |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 1224 passed with no live terminal or account interaction |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: **325** critical live-risk, parity, sizing, research-integrity and workflow tests passed |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 0 | GREEN: valid, 10 acceptance criteria and 2 invariants; the third-review P1/P2 are resolved with executable proof |
| `adversarial-review` | `.ai/tasks/107/review.md` | 0 | GREEN for completed rounds: round 1 found 7, round 2 found 4, and round 3 found 2; all are resolved. The structural guard fix is material, so a fresh complete Claude review is now owed before readiness. |
| `parity-where-applicable` | `git diff --quiet origin/main...HEAD -- core research live monitoring scripts .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: this change touches no trading, quality-tool, hook, CI, recipe or dependency path |
| `mutation-on-touched-critical` | `git diff --name-only origin/main...HEAD -- core research live monitoring` | 0 | GREEN: zero production files changed, so no critical function was touched and the ratchet is vacuous. See Deferred checks. |
| `live-money-review` | changed-path audit against `live/**`, sizing, risk and broker paths | 0 | GREEN: no live, risk, order or account code changed and no runner was contacted; the immutable constraints remain stated inline in both role contracts |
| `human-decision-escalation` | issue #107, and `tests/test_engineering_docs.py::test_role_contracts_preserve_exception_and_human_authority` | 0 | GREEN: finding F4 was escalated rather than fixed — the label rename had reached the contracts without passing back through approval, Jan was shown the discrepancy and reapproved explicitly, and issue #107 carries the corrected AC-04/AC-05 plus AC-07 to AC-10 |
| `no-autonomous-merge` | `tests/test_engineering_docs.py::test_direct_to_main_exception_is_R0_only_everywhere`, plus the constitution and `workflow.md` | 0 | GREEN: R3 autonomous merge remains prohibited; no agent merges and auto-merge is never enabled |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: tracked-secret scan, dependency audit and static security checks passed |

## Coverage and mutation

No production critical function changed: `git diff --name-only origin/main...HEAD -- core research
live monitoring` returns zero paths.

Three test files changed across issue #107. `tests/test_workflow_contract.py` now contains seven
primary fact guards plus seven parametrized counterexample cases. Before the third-review fix, every
counterexample failed because its guard did not reject the mutation; afterward all fourteen cases
pass. `tests/test_quality_validate_task.py` now collects every complete pytest node id cited by a
versioned task test plan and rejects shorthand, so a renamed or deleted guard cannot remain green in
the audit trail. In `tests/test_engineering_docs.py` a single builder-contract marker moved from
`Do not open a pull request until` to `Do not mark a pull request ready for review until`, because
the rule it guards changed in the same commit — the case that test's own docstring anticipates. No
assertion was removed, weakened or made conditional.

The first full `just check` attempt with these files uncommitted reproduced issue #115: Windows
lineage decoding read the Unicode-bearing `git diff` through cp1252, returned `None`, and caused 54
research-lineage failures. After committing the exact same code/test tree, the canonical command
passed 1224/1; no production workaround or test relaxation was made here.

The generalised pattern for this change's own findings is registered as `F-039` in
`.ai/quality/finding-patterns.toml`.

## Deferred checks

- **Re-review after a material fix — owed, and blocking.** The third independent Codex review found
  R3-F1 and R3-F2; Codex then switched to the builder role and fixed them. Claude must now run the
  complete review in fresh context. `pr_ready` cannot see that temporal ordering: it checks resolved
  finding syntax, not that review post-dates the fix. The branch must not be marked ready until that
  review is clean.
- **Linux critical-mutation workflow — not run.** The organisation's GitHub Actions allowance is
  exhausted; every job has failed within seconds with a billing error since 2026-07-27, and the
  allowance resets on 2026-08-01. This is an infrastructure failure, not a code failure. The gate is
  vacuous for this change, as recorded above.
- **Branch protection on `main` — not active.** The repository is private on a plan that rejects
  protection rules, so the merge discipline is enforced by convention and by the Claude pre-Bash
  hook only. A plan upgrade is planned separately.
