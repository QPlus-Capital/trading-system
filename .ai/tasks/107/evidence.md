# Evidence

## HEAD

HEAD: 43b1239cfcaa07b6ca901e744e9bc69ead5f6dbc

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast` | 0 | GREEN: format check, Ruff and mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py` | 0 | GREEN: 147 governance, runtime-schema, template and language tests passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, mypy, vulture and 1183 pytest tests passed; 1 skipped (mutmut needs fork/WSL on Windows) |
| `impacted-tests` | `uvx --from rust-just just check-fast` | 0 | GREEN: impact selected the engineering-doc suite; 57 tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: 20 properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 1183 passed with no live terminal or account interaction |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: 306 critical live-risk, parity, sizing, research-integrity and workflow tests passed |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring scripts .claude .github justfile pyproject.toml uv.lock` | 0 | GREEN: no trading, quality-tool, hook, CI, recipe or dependency behaviour changed |
| `mutation-on-touched-critical` | `git diff --name-only origin/main -- core research live monitoring` | 0 | GREEN: zero production files changed, so no critical function was touched and the ratchet is vacuous here. See Deferred checks. |
| `live-money-review` | changed-path audit against `live/**`, sizing, risk and broker paths | 0 | GREEN: no live, risk, order or account code changed and no runner was contacted; the immutable constraints remain stated inline in both role contracts |
| `human-decision-escalation` | issue #107 and `tests/test_engineering_docs.py::test_role_contracts_preserve_exception_and_human_authority` | 0 | GREEN: Jan retains every business, trading, methodology, live-money, architecture, risk and merge decision; the change adds an explicit approval gate rather than removing one |
| `no-autonomous-merge` | `tests/test_engineering_docs.py::test_direct_to_main_exception_is_R0_only_everywhere` plus the constitution and `workflow.md` | 0 | GREEN: R3 autonomous merge remains prohibited; `workflow.md` states that no agent merges and auto-merge is never enabled |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: tracked-secret scan, dependency audit and static security checks passed |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 107` | 1 | RED: blocked on the outstanding independent review — see Deferred checks |
| `adversarial-review` | `.ai/tasks/107/review.md` | 1 | RED: not performed. Claude authored this change and must not review it. |

## Coverage and mutation

No production critical function changed: `git diff --name-only origin/main -- core research live
monitoring` returns zero paths. The mutation ratchet has nothing to bite on for this change, so the
absence of a mutation run leaves no production path unprotected.

One test file changed (`tests/test_engineering_docs.py`): the builder-contract marker was updated
from `Do not open a pull request until` to `Do not mark a pull request ready for review until`,
because the rule it guards changed in the same commit. This is the case the test's own docstring
anticipates. No assertion was removed, weakened or made conditional; the marker still binds, it
binds to the new wording.

## Deferred checks

- **Independent adversarial review — outstanding and blocking.** Claude authored this change, so the
  review belongs to Codex in fresh context. Until it is recorded in `review.md`, both
  `adversarial-review` and `artifact-schema` stay red and `pr_ready` correctly reports NOT READY.
- **Bootstrap ordering.** This change introduces the rule that the draft pull request carries the
  review, but the readiness gate that would permit a draft to be created before the review exists
  lands with issue #109. Until then this one change is reviewed on the branch rather than on a draft.
  Every later change follows the documented order.
- **Linux critical-mutation workflow — not run.** The organisation's GitHub Actions allowance is
  exhausted; since 2026-07-27 every job fails within seconds with a billing error, and the allowance
  resets on 2026-08-01. This is an infrastructure failure, not a code failure. The gate is vacuous
  for this change, as recorded above; that will not be true for any later change touching production
  code.
- **Branch protection on `main` — not active.** The repository is private on a plan that rejects
  protection rules, so the merge discipline described in `workflow.md` is enforced by convention and
  by the Claude pre-Bash hook only. A plan upgrade is planned separately.
