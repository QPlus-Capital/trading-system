# Evidence

## HEAD

HEAD: 9242d703cb55885875a2f9f60fabb1c679cfc1d3

`origin/main` was merged into the branch first, so this evidence binds a tree that already contains
every pull request merged up to `8b75ff0` (#96, #97, #98, #100, #116, #119). Comparisons below use the merge base (`origin/main...HEAD`), not the two-dot form,
which would otherwise report PR #96's files as changes of this task.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_workflow_contract.py` against the pre-fix documents (`git stash`) | 1 | RED: **6 failed** — no transition table, the resume rule named no status and did not exempt the permit, both role summaries still opened a ready pull request, the Gates step read "no more, no less", the review loop had no way back to `Reviewing`, and no activation register existed |
| `format` | `uvx --from rust-just just check-fast` | 0 | GREEN: format, Ruff and mypy passed; 63 focused tests |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py` | 0 | GREEN: **153 passed**, including the six new contract guards |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, mypy, vulture and **1215 passed**, 1 skipped (mutmut needs fork/WSL on Windows); re-run at this HEAD after the F-039 renumber |
| `impacted-tests` | `uvx --from rust-just just check-fast` | 0 | GREEN: impact selected the engineering-doc and contract suites; 63 passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 1215 passed with no live terminal or account interaction |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: **325** critical live-risk, parity, sizing, research-integrity and workflow tests passed |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 0 | GREEN: valid, 10 acceptance criteria and 2 invariants; all seven review findings resolved |
| `adversarial-review` | `.ai/tasks/107/review.md` | 0 | GREEN: independent Codex review in fresh context; **7 findings (4 P1, 3 P2), all confirmed and resolved**, 12 counterexamples attempted. See Deferred checks — a re-review is owed. |
| `parity-where-applicable` | `git diff --quiet origin/main...HEAD -- core research live monitoring scripts .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: this change touches no trading, quality-tool, hook, CI, recipe or dependency path |
| `mutation-on-touched-critical` | `git diff --name-only origin/main...HEAD -- core research live monitoring` | 0 | GREEN: zero production files changed, so no critical function was touched and the ratchet is vacuous. See Deferred checks. |
| `live-money-review` | changed-path audit against `live/**`, sizing, risk and broker paths | 0 | GREEN: no live, risk, order or account code changed and no runner was contacted; the immutable constraints remain stated inline in both role contracts |
| `human-decision-escalation` | issue #107, and `tests/test_engineering_docs.py::test_role_contracts_preserve_exception_and_human_authority` | 0 | GREEN: finding F4 was escalated rather than fixed — the label rename had reached the contracts without passing back through approval, Jan was shown the discrepancy and reapproved explicitly, and issue #107 now carries the corrected AC-04/AC-05 plus AC-07 to AC-10 |
| `no-autonomous-merge` | `tests/test_engineering_docs.py::test_direct_to_main_exception_is_R0_only_everywhere`, plus the constitution and `workflow.md` | 0 | GREEN: R3 autonomous merge remains prohibited; no agent merges and auto-merge is never enabled |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: tracked-secret scan, dependency audit and static security checks passed |

## Coverage and mutation

No production critical function changed: `git diff --name-only origin/main...HEAD -- core research
live monitoring` returns zero paths.

Two test files changed. `tests/test_workflow_contract.py` is new and is the substance of this
change's verification: six guards, all six red against the pre-fix documents. In
`tests/test_engineering_docs.py` a single builder-contract marker moved from `Do not open a pull
request until` to `Do not mark a pull request ready for review until`, because the rule it guards
changed in the same commit — the case that test's own docstring anticipates. No assertion was
removed, weakened or made conditional.

One defect found during verification was **not** fixed here, because it is out of scope: on Windows
`research/stages/lineage.py` decodes git output with the platform codec, so any uncommitted file
containing a character outside cp1252 crashes lineage computation — 54 tests failed from a single
curly quote in an uncommitted Markdown file. Filed as
[#115](https://github.com/QPlus-Capital/trading-system/issues/115) with a reproduction, and it is a
result-integrity path (constitution §4).

The generalised pattern for this change's own findings is registered as `F-039` in
`.ai/quality/finding-patterns.toml`.

## Deferred checks

- **Re-review after a material fix — owed, and blocking.** Constitution §11 and §14 require the
  complete independent review to run again after a material fix, and all seven findings were
  material. `pr_ready` cannot see this: it checks that `review.md` records resolved findings, not
  that the review post-dates the fix. The readiness tool is therefore weaker than the rule here, and
  the pull request must not be marked ready for review until Codex has reviewed this HEAD.
- **Linux critical-mutation workflow — not run.** The organisation's GitHub Actions allowance is
  exhausted; every job has failed within seconds with a billing error since 2026-07-27, and the
  allowance resets on 2026-08-01. This is an infrastructure failure, not a code failure. The gate is
  vacuous for this change, as recorded above.
- **Branch protection on `main` — not active.** The repository is private on a plan that rejects
  protection rules, so the merge discipline is enforced by convention and by the Claude pre-Bash hook
  only. A plan upgrade is planned separately.
