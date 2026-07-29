# Evidence

## HEAD

HEAD: 71d1b15318d5c35cd4097975e5d9623a0562d3cd

This is the tested HEAD after rebasing onto `origin/main`
`98b47ec3b9414cd7ea6ff24dadea05777267c143`. The three confirmed PR #130 findings are
content-addressed under the registry contract introduced by #124, and the 55-file legacy registry
remains byte-faithful. A later evidence-only commit is permitted by the readiness freshness rule.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | PowerShell `just check-fast origin/main` | 0 | Seven changed Python files were already formatted; Ruff and strict mypy passed. |
| `docs-consistency` | PowerShell `just check` | 0 | Engineering-document, finding-registry, and workflow consistency guards passed in the complete suite. |
| `check` | PowerShell `just check` | 0 | Ruff, strict mypy over 187 files, Vulture, and pytest passed: 1,593 passed and one expected unavailable-Mutmut skip. |
| `impacted-tests` | `just check-fast origin/main` | 0 | The impact-selected workflow, account-environment, mutation, and quality set passed 287/287 with one expected unavailable-Mutmut skip. |
| `property-tests-where-applicable` | PowerShell `just check-properties` | 0 | 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | PowerShell `just check`; Actions run `30478429911` | 0 | Windows passed 1,593 tests with one tool-availability skip; Linux passed 1,592 with the expected Mutmut and MT5-boundary skips. The same 1,594-node inventory was collected on both platforms. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 113 --base origin/main` | 0 | Task 113 is valid with seven acceptance criteria and three invariants; review F1 has a resolved disposition and executable traceability. |
| `adversarial-review` | PR #130 reviews `4810464072` and `4811220729`, 2026-07-29 | 0 | The nine-shape predicate review remained sound. The first Linux run found two environment-precondition defects; both are reproduced, resolved, and permanently registered with executable proof. |
| `invariants` | PowerShell `just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | Actions run `30478424981` | 0 | The real weakened-test probe passed with Mutmut supplied, then the unchanged critical ratchet passed at 4,761/5,171 killed and 410 exact survivors. |
| `parity-where-applicable` | Actions run `30478429911`; local Windows collection | 0 | The ready-state Linux suite collected the same 1,594-node inventory and passed 1,592 with only the expected unavailable-Mutmut and unavailable-MT5 skips; Windows passed 1,593 with only the unavailable-Mutmut skip. |
| `live-money-review` | PR #130 independent R3 re-review `4810464072`, 2026-07-29 | 0 | No finding; the reviewer verified the platform and gate structure plus the bounded remediation against executable counterexamples. |
| `human-decision-escalation` | spec, actual CI runs, and active ruleset audit | 0 | The platform limitation, external required-check transition, and deferred ready-state observations are explicit; no result was guessed. |
| `no-autonomous-merge` | Ready PR #130 and project-state audit | 0 | Jan performed the ready transition; the card remains in `Reviewing`, and no merge or auto-merge occurred. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerability, and Ruff security checks passed. |
| `impact` | PowerShell `just check-fast origin/main` | 0 | R3; `scripts/quality/impact.py` is the changed production quality module and 45 focused workflow/impact tests were selected and passed. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because the finding registry, workflow enforcement, and classifier/impact logic govern live-money gates. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready 113 --base origin/main` | 0 | All R3 artifacts and gates cover the tested HEAD; the later evidence-only commit is accepted by the freshness rule. |

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

### First Linux run and remediation

Ready-state run `30475661794` was the red proof for the two platform defects: Linux reported
1,576 passing tests plus the inherited-`UV_NO_SYNC` dotenv warning failure and the unavailable
Mutmut failure. With `UV_NO_SYNC=1` exported locally, the dotenv node reproduced the warning failure
before the fix and passed after it while retaining the broad `warning:` assertion.

Post-fix synchronize run `30478429911` passed its Linux Tests, deterministic Properties,
Task-Artifact Validation, Security, and Critical Invariants steps. The Tests step reported 1,592
passed and only the two intended capability skips: Mutmut is absent from full-quality and the real
MT5 package is confined to the Windows boundary. The job's first pass stopped only at stale
PR-evidence, which this evidence-only commit resolves. Mutation run `30478424981` separately proved
that the same Mutmut node executes and passes when `mutmut==3.5.0` is supplied.

### Test inventory and platform boundary

- Pre-change Windows collection: 1,286 node IDs, SHA-256
  `c1c907cdea66a2c66d88eb07a55e27f4544e9555a1b90b9fa53ecacf2a0f6ee0`.
- Pre-review-remediation Windows collection: 1,300 node IDs, SHA-256
  `02c08ec7066cabc88844cfccef43f11efdbe7ae55a98aff55404fd0f40f100e5`.
- Current rebased Windows collection: 1,594 node IDs, SHA-256
  `00b403a3a32f8c03a10a4f82731a2dcba67f9c2b9459f7a14d18acb0aa5a18e4`.
- The ready Linux run collected the same 1,594 tests: 1,592 passed and the unavailable Mutmut and
  MT5 boundary nodes skipped. Windows executed 1,593 and skipped only unavailable Mutmut. No
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

### Cost comparison

GitHub's timing API reports zero billable milliseconds for both runs because this repository is
public. Using the actual per-job durations, per-job minute rounding, and the standard
Windows-to-Linux minute weighting, the last comparable six-Windows-job run `30476116476` consumed
20 Linux-equivalent minutes; post-change run `30478429911` consumed four, an 80% reduction. The
measured exposure is materially lower even though the current public repository incurs zero charge.

## Deferred checks

- **Required-check context transition.** The active `main` ruleset still requires
  `standard-quality`, `tests`, `task-artifact-validation`, `security`, `critical-invariants`,
  `pr-evidence-validation`, and `mutation-critical`. After the first observed green ready run, Jan
  must atomically replace the six retired CI contexts with `platform-quality` and `full-quality`
  while retaining `mutation-critical`. Until then the PR remains draft and unmergeable.
