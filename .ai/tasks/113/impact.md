# Impact analysis

## Direct impact

- `.github/workflows/ci.yml`: removes `push: main` and `pull_request: edited`, adds
  `ready_for_review`, replaces six duplicated Windows jobs with draft-fast and ready-full Linux
  jobs plus one narrow Windows MT5-boundary job, enables the existing setup-uv cache, and keeps all
  seven `just` recipe invocations as distinct blocking steps.
- `.github/workflows/mutation.yml`: retains the Linux mutation commands and timeout, adds a cheap
  configuration-driven changed-path detector, and gates the expensive job on both critical path
  selection and non-draft state.
- `tests/test_ci_cost_workflows.py`: parses YAML, evaluates the actual job expressions against
  concrete event payloads, executes the embedded mutation-path predicate from the workflow, and
  guards cache/platform/recipe/failure-label behaviour.
- `tests/test_gate_consistency.py`: updates the existing workflow contract from six duplicated jobs
  and an `edited` trigger to the consolidated exact gate set.
- `tests/test_workflow_system_validation.py`: makes the installed-MT5 boundary test collect on
  Linux and skip only when the Windows-only package is absent.

## Transitive impact

- Pull requests: drafts receive standard-quality feedback; direct-ready, `ready_for_review`, and every later
  non-draft `synchronize` event validate the complete event HEAD.
- Branch protection: the external required contexts must move from six legacy CI job names to the
  consolidated ready contexts. Until Jan performs that transition, this draft is intentionally not
  mergeable.
- Mutation: the detector uses all `MutationPolicy.targets` selected by the production risk model.
  Adding or removing a target in `.ai/quality/mutation.toml` changes workflow selection without a
  YAML edit.
- Test collection: the complete Linux suite retains the Windows-only boundary node as a skip, and
  the narrow Windows job executes that exact node. No other test remains on Windows.
- Billing: ready CI pays one Linux setup plus one narrow Windows setup instead of six full Windows
  setups; docs/non-critical drafts do not pay for mutation.

## Critical dependencies

- `justfile` remains the sole definition of `check-standard`, `check-tests`, `check-properties`,
  `check-task-artifact`, `check-security`, `check-invariants`, `check-pr-evidence`,
  `mutation-self-test`, and `mutation-critical`.
- `scripts/quality/classify.py::changed_paths`, `load_model`, and
  `scripts/quality/mutation.py::{load_policy,select_fast_targets}` are the authoritative mutation
  filter. No matcher or path list is duplicated.
- `.ai/quality/mutation.toml` is the authoritative critical target set.
- `tests/conftest.py::_load_mt5_module` is the existing optional MT5 seam and fail-closed fake
  boundary.
- The active GitHub ruleset currently requires seven legacy contexts and cannot be changed by this
  repository-only package.

## Unknown or dynamic edges

- GitHub event-condition semantics and billing are external. Local tests parse and evaluate the
  bounded expressions fail-closed, but AC-04 through AC-07 still require real observations after
  2026-08-01.
- Native Linux collection is unavailable locally because WSL, Docker, Podman, Hyper-V VMs, and
  other container runtimes are absent. Windows baseline collection is executable now; Linux
  collection and the cross-platform diff remain deferred rather than inferred.
- The last comparable billed Windows run must be selected after the allowance resets. Evidence
  will name both Actions run IDs and compare billed minutes, not wall-clock guesses.
