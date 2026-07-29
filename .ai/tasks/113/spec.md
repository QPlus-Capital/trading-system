# Issue 113: Cut GitHub Actions cost without losing a check

## Problem

The pull-request workflows pay for six duplicated Windows environments, run on non-code PR-body
edits and non-critical changes, and do not distinguish draft feedback from final-HEAD validation.

## Goal

Run the same binding ready-PR gates and test set with one cached Linux full-validation environment,
one cached Windows platform environment for the standard gate plus the genuinely MT5-dependent
boundary test, and critical mutation only for configured critical production paths.

## Non-goals

- Do not remove, weaken, merge away, or allow failure of any existing gate.
- Do not change a `just` recipe, timeout ceiling, permission, concurrency rule, mutation target,
  threshold, baseline, trading path, or reported result.
- Do not claim workflow behaviour from a simulation; record only executable local tests or actual
  GitHub run IDs.
- Do not change the active GitHub ruleset from repository code.

## Behavioural requirements

- Pull-request actions `opened`, `reopened`, `synchronize`, and `ready_for_review` trigger CI;
  `edited` and `push` do not.
- Drafts run only the fast standard-quality recipe in the single Windows platform job. Every
  non-draft event, including `opened` directly ready and `synchronize` after readiness, also runs
  the six remaining recipes on Linux and the MT5 boundary on the event HEAD.
- Full Linux quality runs once after a locked sync excluding the Windows-only `metatrader5`
  package. `UV_NO_SYNC=1` prevents nested `uv run` calls in unchanged `just` recipes from trying to
  reinstall the excluded package. Each recipe remains a separate, clearly named step.
- The standard recipe and the single real-MT5 pytest boundary share the only Windows job.
  Execution proved that strict mypy evaluates `winsound.Beep` differently on Linux, so moving that
  unchanged recipe would require an out-of-scope live-file or gate change.
- The mutation filter imports `changed_paths`, `load_policy`, `load_model`, and
  `select_fast_targets`; it never restates mutation target paths in workflow YAML.
- A draft or a non-critical change skips `mutation-critical`. A critical non-draft change and a
  manual dispatch run the unchanged mutation recipes.
- Dependency caching is enabled and every action remains pinned to a full commit SHA.

## Acceptance criteria

- AC-01: The union of test node IDs executed for a ready pull request is identical before and
  after on Windows and Linux.
- AC-02: Every job that does not require MetaTrader 5 runs on `ubuntu-latest`.
- AC-03: The one MT5-dependent boundary test runs on Windows and passes.
- AC-04: A `pull_request` event with action `edited` triggers neither CI nor mutation.
- AC-05: A non-critical changed-path set skips `mutation-critical`, while a path selected from the
  production mutation policy runs it.
- AC-06: Draft events select only fast gates; a ready event selects the full set.
- AC-07: After the first reviewed ready transition, a complete run records materially fewer billed
  minutes than the last comparable six-job Windows run.

## Invariants

- INV-01: Every gate binding on a ready pull request before the change still binds on its final
  HEAD after the change.
- INV-02: CI invokes the existing local `just` recipes verbatim; recipe bodies remain unchanged.
- INV-03: `synchronize` on an already-ready pull request selects the full gate set.

## Assumptions

- `MetaTrader5` is the only Windows-only installed dependency. Repository import and collection
  audits found one test with an unconditional package import; all production imports are already
  isolated behind fake-safe test seams. Actual Linux CI additionally proved that the unchanged
  standard recipe is platform-specific at static-analysis time because mypy rejects
  `winsound.Beep` on Linux.
- A GitHub skipped job is not used as proof of a required gate. Only the consolidated full-quality,
  Windows MT5 boundary, and conditional mutation contexts should bind after the ruleset transition.

## Open questions

- The task states WSL is available, but `wsl.exe --status` reports that WSL is not installed and no
  local Linux VM/container runtime exists. The Linux half of AC-01 must therefore execute in the
  ready-only Linux GitHub job after independent review; it cannot honestly be green while the PR
  remains draft.
- The active `main` ruleset still requires the six old CI job names plus `mutation-critical`.
  Before this PR can merge, Jan must atomically replace those six CI contexts with
  `platform-quality` and `full-quality` after their first observed ready run. Keeping the old names
  would require the six runner starts this issue exists to remove.

## Expected artifacts

- Consolidated `.github/workflows/ci.yml`.
- Configuration-driven `.github/workflows/mutation.yml`.
- Executable parsed-workflow and platform-boundary guards under `tests/`.
- Complete `.ai/tasks/113/` specification, impact, test plan, review handoff, and evidence.
- A draft pull request and a project card in `Reviewing`.

## Risk class

R3. `scripts/quality/classify.py` assigns `.github/workflows/**` to R3 because CI executes the
guards that protect every live-money and result-integrity change.

## Human decisions required

Jan already approved the issue's trigger, platform, consolidation, and draft/full policy. Jan must
perform the external required-check context transition described under Open questions; Codex does
not mutate branch protection in this package.
