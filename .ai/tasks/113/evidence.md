# Evidence

## HEAD

HEAD: f0058650d1ccc2e12571237bbb3cfb4a500a7f63

This is the tested HEAD after rebasing onto `origin/main`
`76103809c753fb1d990ad5d0b8bd626e738db3be`, retaining main's F-055 and renumbering this
branch's independent-review pattern to F-056. A later evidence-only commit is permitted by the
readiness freshness rule.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | PowerShell `just check-fast origin/main` | 0 | Five changed Python files were formatted; Ruff and strict mypy passed. |
| `docs-consistency` | PowerShell `just check` | 0 | Engineering-document, finding-registry, and workflow consistency guards passed in the complete suite. |
| `check` | PowerShell `just check` | 0 | Ruff, strict mypy over 184 files, Vulture, and pytest passed: 1,578 passed and one expected Windows Mutmut skip. |
| `impacted-tests` | `uv run pytest -q tests/test_ci_cost_workflows.py tests/test_quality_impact.py`; `just check-fast origin/main` | 0 | The review-focused set passed 32/32; the impact-selected workflow set passed 45/45. |
| `property-tests-where-applicable` | PowerShell `just check-properties` | 0 | 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | PowerShell `just check`; embedded-filter execution against concrete repository paths | 0 | The full 1,578-test suite passed and the exact filter returned true for production, direct-test, transitive-test, and unknown-dynamic cases while retaining the intended false cases. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 113 --base origin/main` | 0 | Task 113 is valid with seven acceptance criteria and three invariants; review F1 has a resolved disposition and executable traceability. |
| `adversarial-review` | PR #130 independent re-review `4810464072`, 2026-07-29 | 0 | No finding. The reviewer verified a nine-shape matrix against the production predicate, including the transitive case; three real-file fail-closed probes; surviving coverage under the renamed test; and that the remediation did not touch `ci.yml`. |
| `invariants` | PowerShell `just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | Filter regression set and concrete predicate matrix | 0 | Direct and transitive critical test changes now select the unchanged ratchet; unrelated workflow, documentation, `.ai/`, and test changes still skip. No configured mutation target changed in this package. |
| `parity-where-applicable` | Windows collection and native Linux comparison | 1 | Current Windows collection has 1,579 node IDs, but native Linux collection remains unobserved while the PR is draft and is not claimed green. |
| `live-money-review` | PR #130 independent R3 re-review `4810464072`, 2026-07-29 | 0 | No finding; the reviewer verified the platform and gate structure plus the bounded remediation against executable counterexamples. |
| `human-decision-escalation` | spec, actual CI runs, and active ruleset audit | 0 | The platform limitation, external required-check transition, and deferred ready-state observations are explicit; no result was guessed. |
| `no-autonomous-merge` | Draft PR #130 and project-state audit | 0 | PR #130 is draft and the card is in `Reviewing`; no merge, ready transition, or auto-merge occurred. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerability, and Ruff security checks passed. |
| `impact` | PowerShell `just check-fast origin/main` | 0 | R3; `scripts/quality/impact.py` is the changed production quality module and 45 focused workflow/impact tests were selected and passed. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because the finding registry, workflow enforcement, and classifier/impact logic govern live-money gates. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 113 --base origin/main` | 1 | Correctly NOT READY because native Linux parity and ready-state observations remain deferred. |

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

Independent-review remediation is separately red-first. Commit `dc2ca16` changes only the workflow
contract. Against the unchanged production-only filter,
`uv run pytest -q tests/test_ci_cost_workflows.py` exited 1 with **3 failed and 13 passed**:

- `tests/test_live_risk_control.py` returned false instead of true.
- Named transitive case `tests/test_strategy_sizing_basis.py` returned false instead of true.
- Unknown-dynamic-import fixture `tests/test_research_stages.py` returned false instead of true.

Implementation commit `fe2a27e` reuses `scripts/quality/impact.py` and the loaded mutation policy.
The review-focused workflow/impact set now passes **32/32** and the impact-selected set passes
**45/45**. Concrete predicate execution returns:

- true: `live/risk_control.py`, `tests/test_live_risk_control.py`,
  `tests/test_strategy_sizing_basis.py`, `tests/test_research_stages.py`;
- false: `tests/test_gate_consistency.py`, `README.md`, `.ai/tasks/113/evidence.md`,
  `.github/workflows/ci.yml`.

PR #130's body was edited at `2026-07-29T15:12:51Z`. After 55 seconds, the branch run list still
ended at synchronize-triggered runs `30464626811` and `30464627044`, both created at
`2026-07-29T15:11:16Z`; no workflow run was created for the `edited` event. This is the external
AC-04 observation, not an inference from the local expression evaluator.

### Independent re-review

Claude's independent re-review `4810464072` completed on 2026-07-29 with no finding. It exercised
the production predicate over nine changed-path shapes: critical production, direct critical test,
transitive critical test, direct monitoring test, unrelated documentation, methodology plus task
artifacts, `ci.yml`, a genuinely unrelated test, and the empty set. All nine decisions were correct,
including the transitive case.

The reviewer also wrote three real probe files: an unparseable test, an unresolvable dynamic import,
and a non-existent path. All three selected the mutation run, proving fail-closed behavior. The
review confirmed that the renamed mutation-filter test retains the earlier coverage and adds direct,
transitive, and unresolved cases. The review remediation left `.github/workflows/ci.yml`
byte-identical.

### Test inventory and platform boundary

- Pre-change Windows collection: 1,286 node IDs, SHA-256
  `c1c907cdea66a2c66d88eb07a55e27f4544e9555a1b90b9fa53ecacf2a0f6ee0`.
- Pre-review-remediation Windows collection: 1,300 node IDs, SHA-256
  `02c08ec7066cabc88844cfccef43f11efdbe7ae55a98aff55404fd0f40f100e5`.
- Current rebased Windows collection: 1,579 node IDs, SHA-256
  `21011613e1c4590d96bb9d4c053343eb78e9f32f50108635ff132d18ee74c2d4`.
- The earlier collection-safe optional MT5 proof remains recorded at its tested commit. On the
  rebased tree, 1,578 tests execute and only the expected Windows mutation self-test skips; no
  existing test is filtered out.
- Exact Windows MT5 boundary:
  `tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries` passed.

No mutation target, pattern, threshold, baseline, survivor, gate content, or job platform changed.
The workflow combines the existing
`select_fast_targets(changed_paths(...), load_policy(), load_model())` predicate with
`changed_tests_exercise_targets` over the same loaded policy. The helper uses `_facts` for direct
imports and unresolved-test failure, then `analyze_impact` for transitive tests and unknown dynamic
production edges. It does not consume the critical dependency map's copied test lists as proof that
a test executes a target.

## Deferred checks

- **AC-01 native Linux node-ID diff — ready transition.** `wsl.exe --status` reports that WSL is
  not installed; Docker, Podman, Nerdctl, Lima, Multipass, and local Hyper-V VMs are absent. The
  package-less Windows execution proves dependency separation but is not a Linux observation.
  With independent review complete, the ready-only `full-quality` Linux job must collect its node
  IDs and diff them against the recorded Windows 1,579-ID set. A non-empty diff blocks readiness.
- **AC-05 Actions critical path.** Local execution now proves production, direct-test, transitive-
  test, and fail-closed selection. A real non-draft Actions change must still prove that the same
  policy-driven filter starts `mutation-critical`; this draft is not transitioned merely to create
  that observation.
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
