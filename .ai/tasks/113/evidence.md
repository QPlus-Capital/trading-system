# Evidence

## HEAD

HEAD: 269d97fc2068fccfb69e48bfd38d80ed1b5a0031

This is the implementation HEAD. A later evidence-only commit is permitted by the readiness
freshness rule. The branch is based on the actual `origin/main` at build start,
`14f0cdb45224a3982ca5476b45cb78ba9c447411`; the user-supplied parenthetical `8b75ff0` had already
been superseded by merged PR #105.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Three changed test files were already formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `uvx --from rust-just just check` | 0 | Engineering-document and workflow consistency guards passed in the complete suite. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 182 files, Vulture, and pytest passed: 1,298 passed and one Windows-only mutation test skipped. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Impact selected the three changed workflow test files; all 26 focused tests passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | package-less full pytest plus exact Windows MT5 boundary | 0 | With `MetaTrader5` import blocked, 1,297 passed and two expected platform skips remained; the exact Windows boundary node separately passed 1/1. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 113 --base origin/main` | 1 | Correctly refuses completion because independent R3 review has not run; the draft is a review handoff, not ready evidence. |
| `adversarial-review` | independent Claude review | 1 | Not run. The builder does not review its own R3 workflow change. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | All 433 critical invariant tests passed. |
| `mutation-on-touched-critical` | production policy selection over `changed_paths("origin/main")` | 0 | Ten changed paths selected zero configured production mutation targets. The critical mutation job is therefore vacuous for this workflow/test-only change; no baseline or survivor changed. |
| `parity-where-applicable` | Windows and no-MT5 node collection; native Linux comparison | 1 | Both local collections contain the same 1,299 IDs and hash, but the required real Linux collection cannot run locally and is not claimed green. |
| `live-money-review` | independent R3 review | 1 | Not run. No live/research/monitoring production file changed, but the workflow enforcement boundary still requires independent review. |
| `human-decision-escalation` | spec and active ruleset audit | 0 | The external required-check context transition and unavailable Linux proof are explicit; no rule or observation was guessed. |
| `no-autonomous-merge` | local branch and project-state audit | 0 | No merge or auto-merge occurred; the requested handoff remains draft. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerability, and Ruff security checks passed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; no production file or configured mutation target changed, and all three direct workflow test files were selected. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because both changed workflow files execute repository-wide gates. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 113 --base origin/main` | 1 | Correctly NOT READY: independent review, real Linux parity, task validation, and their evidence are absent. |

## Coverage and mutation

### Red-first proof

Commit `d0aa5d2` contains the desired tests while retaining the old workflows. In a detached
worktree at that exact commit:

`python -m pytest -q tests/test_ci_cost_workflows.py tests/test_gate_consistency.py`

exited 1 with **14 failed and 7 passed**. The failures independently named the old `edited`
trigger, six Windows jobs, absent draft/ready split, absent configuration-driven mutation filter,
missing Linux/Windows partition, missing cache, and retired job split. On implementation HEAD, the
same files plus the MT5 boundary file pass **26/26**.

### Test inventory and platform boundary

- Pre-change Windows collection: 1,286 node IDs, SHA-256
  `c1c907cdea66a2c66d88eb07a55e27f4544e9555a1b90b9fa53ecacf2a0f6ee0`.
- Final Windows collection: 1,299 node IDs, SHA-256
  `4d026e9a7a495549f471b3ad3b5b137eb01da1ea52fcd49eb5645f303dcb30c3`.
- Final collection with the `MetaTrader5` import made unavailable: the same 1,299 node IDs and the
  same hash. The 13 additional IDs are the new workflow guards; no production test is filtered.
- Final full execution with `MetaTrader5` unavailable: 1,297 passed; only the existing Windows
  mutation self-test and the separately executed MT5 boundary node skipped.
- Exact Windows MT5 boundary:
  `tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries` passed.

No mutation target, pattern, threshold, baseline, survivor, or production module changes. Executing
the production `select_fast_targets(changed_paths(...), load_policy(), load_model())` predicate
selected `[]`, so the Linux critical ratchet has no mutant to measure for this package.

## Deferred checks

- **AC-01 native Linux node-ID diff — 2026-08-01.** `wsl.exe --status` reports that WSL is not
  installed; Docker, Podman, Nerdctl, Lima, Multipass, and local Hyper-V VMs are absent. The
  package-less Windows execution is useful dependency evidence but is not a Linux observation.
  After the Actions allowance resets, collect the ready-PR Linux IDs and diff them against the
  recorded Windows 1,299-ID set. A non-empty diff blocks readiness.
- **AC-04 through AC-06 observation — 2026-08-01.** The parsed-workflow tests are green for
  `edited`, docs-only/critical paths, draft, `ready_for_review`, direct-ready, and ready
  `synchronize` payloads. They are executable guards, not a claim that GitHub ran the events.
  Observe the first actual draft, ready transition, later synchronize, and non-critical/critical
  mutation cases after reset and record their run IDs.
- **AC-07 billed minutes — 2026-08-01.** Compare the first complete ready run with the last
  comparable six-job Windows run. Record both run IDs, outcomes, runner operating systems, and
  billed minutes; do not substitute wall time.
- **Required-check context transition.** The active `main` ruleset still requires
  `standard-quality`, `tests`, `task-artifact-validation`, `security`, `critical-invariants`,
  `pr-evidence-validation`, and `mutation-critical`. After the first observed green ready run, Jan
  must atomically replace the six retired CI contexts with `full-quality` and `mt5-boundary` while
  retaining `mutation-critical`. Until then the PR must remain draft and unmergeable.
- **Independent review.** Claude must review the complete R3 workflow change before task validation
  or readiness can pass.
