# Evidence

## HEAD

HEAD: 414e1ab307c0b41a1c6bcc51a091958f797d6b5d

This is the task-document HEAD after implementation HEAD
`6f5dfe9acfe69b2ce3f3ef7ccf9dc8346c966fab`. A later evidence-only commit is permitted by the
readiness freshness rule. The branch is based on the actual `origin/main` at build start,
`14f0cdb45224a3982ca5476b45cb78ba9c447411`; the user-supplied parenthetical `8b75ff0` had already
been superseded by merged PR #105.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Changed Python files were formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `uvx --from rust-just just check` | 0 | Engineering-document and workflow consistency guards passed in the complete suite. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 182 files, Vulture, and pytest passed: 1,299 passed and one Windows-only mutation test skipped. |
| `impacted-tests` | `uv run pytest -q tests/test_ci_cost_workflows.py tests/test_gate_consistency.py tests/test_workflow_system_validation.py` | 0 | All 27 focused workflow guards passed on the final architecture. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | package-less full pytest plus exact Windows MT5 boundary | 0 | With the optional `MetaTrader5` package unavailable, 1,298 passed and two expected platform skips remained; the exact Windows boundary node separately passed 1/1. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 113 --base origin/main` | 1 | Correctly refuses completion because independent R3 review has not run; this draft is a review handoff, not ready evidence. |
| `adversarial-review` | independent Claude review | 1 | Not run. The builder does not review its own R3 workflow change. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | All 433 critical invariant tests passed. |
| `mutation-on-touched-critical` | GitHub Actions run `30463967228` (`Critical mutation`) | 0 | `critical-change-filter` passed and selected no configured production target; `mutation-critical` was skipped. The ratchet is vacuous for this workflow/test-only diff, and no baseline or survivor changed. |
| `parity-where-applicable` | Windows and no-MT5 node collection; native Linux comparison | 1 | Both local dependency conditions collect the same 1,300 node IDs, but native Linux collection remains unobserved while the PR is draft and is not claimed green. |
| `live-money-review` | independent R3 review | 1 | Not run. No trading production file changed, but the workflow enforcement boundary still requires independent review. |
| `human-decision-escalation` | spec, actual CI runs, and active ruleset audit | 0 | The platform limitation, external required-check transition, and deferred ready-state observations are explicit; no result was guessed. |
| `no-autonomous-merge` | Draft PR #130 and project-state audit | 0 | PR #130 is draft and the card is in `Reviewing`; no merge, ready transition, or auto-merge occurred. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerability, and Ruff security checks passed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; no production file or configured mutation target changed, and the direct workflow tests were selected. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because both changed workflow files execute repository-wide gates. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 113 --base origin/main` | 1 | Correctly NOT READY: independent review, native Linux parity, task validation, and their evidence are absent. |

## Coverage and mutation

### Red-first proof

Commit `d0aa5d2` contains the desired tests while retaining the old workflows. In a detached
worktree at that exact commit:

`python -m pytest -q tests/test_ci_cost_workflows.py tests/test_gate_consistency.py`

exited 1 with **14 failed and 7 passed**. The failures independently named the old `edited`
trigger, six Windows jobs, absent draft/ready split, absent configuration-driven mutation filter,
missing Linux/Windows partition, missing cache, and retired job split.

The first implementation architecture then exposed two genuine platform defects through real
GitHub execution:

- Run `30462492983` failed because nested `uv run` commands resynchronized the excluded
  `MetaTrader5` dependency on Linux. The new no-resync guard was red 1/1 before `UV_NO_SYNC=1`.
- Run `30463365617` reached strict mypy and failed because `live/notify.py` uses the Windows-only
  `winsound.Beep` API. The desired final architecture was then proven red with **11 failed and
  12 passed** before moving standard quality to the single Windows platform job.

On implementation HEAD, the three focused files pass **27/27**. Run `30463967296` confirms the
final draft path: `platform-quality` passed on Windows and `full-quality` was skipped because the
pull request is draft. Run `30463967228` confirms that a non-critical change executes the
configuration-driven filter and does not start the mutation job.

### Test inventory and platform boundary

- Pre-change Windows collection: 1,286 node IDs, SHA-256
  `c1c907cdea66a2c66d88eb07a55e27f4544e9555a1b90b9fa53ecacf2a0f6ee0`.
- Final Windows collection: 1,300 node IDs, SHA-256
  `02c08ec7066cabc88844cfccef43f11efdbe7ae55a98aff55404fd0f40f100e5`.
- The collection-safe optional MT5 boundary produces the same 1,300 node IDs when the package is
  unavailable. The 14 additional IDs are workflow guards; no existing test is filtered out.
- Full execution with `MetaTrader5` unavailable: 1,298 passed; only the existing Windows mutation
  self-test and the separately executed MT5 boundary node skipped.
- Exact Windows MT5 boundary:
  `tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries` passed.

No mutation target, pattern, threshold, baseline, survivor, or production module changes. The
workflow executes the production
`select_fast_targets(changed_paths(...), load_policy(), load_model())` predicate. Both local
execution and Actions run `30463967228` selected no target for this package.

## Deferred checks

- **AC-01 native Linux node-ID diff — ready transition.** `wsl.exe --status` reports that WSL is
  not installed; Docker, Podman, Nerdctl, Lima, Multipass, and local Hyper-V VMs are absent. The
  package-less Windows execution proves dependency separation but is not a Linux observation.
  After independent review, the ready-only `full-quality` Linux job must collect its node IDs and
  diff them against the recorded Windows 1,300-ID set. A non-empty diff blocks readiness.
- **AC-04 edited event.** The parsed-workflow test proves an `edited` payload selects no job, but
  an actual body-edit observation must be recorded on PR #130 without claiming the parser as the
  external observation.
- **AC-05 critical path.** Run `30463967228` proves the non-critical half: the filter passed and
  mutation was skipped. A later critical-path change must prove that the same policy-driven filter
  starts `mutation-critical`.
- **AC-06 ready and synchronize events.** Run `30463967296` proves the draft half:
  `platform-quality` passed and `full-quality` skipped. After independent review, the
  `ready_for_review` transition and a subsequent non-draft `synchronize` event must each run the
  complete platform and Linux gate set on their current HEAD.
- **AC-07 billed minutes.** Compare the first complete ready run with the last comparable six-job
  Windows run. Record both run IDs, outcomes, runner operating systems, and billed minutes; do not
  substitute wall time.
- **Required-check context transition.** The active `main` ruleset still requires
  `standard-quality`, `tests`, `task-artifact-validation`, `security`, `critical-invariants`,
  `pr-evidence-validation`, and `mutation-critical`. After the first observed green ready run, Jan
  must atomically replace the six retired CI contexts with `platform-quality` and `full-quality`
  while retaining `mutation-critical`. Until then the PR remains draft and unmergeable.
- **Independent review.** Claude must review the complete R3 workflow change before task validation
  or readiness can pass.
