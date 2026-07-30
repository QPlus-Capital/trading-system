# Impact analysis

## Direct impact

- `scripts/quality/board.py` adds the only supported command surface for reading and moving board
  status, adding an issue to the project, arming an approved issue, and consuming the build permit.
  It reads statuses, transitions, approval steps, and builder guards from
  `.ai/quality/workflow-contract.toml`.
- `scripts/quality/issue_body.py` validates R2/R3 issue bodies from a new TOML policy and scaffolds
  exactly the task files selected by `.ai/quality/task-artifacts.toml`.
- `justfile` adds `new-task`, delegating to the production scaffolder rather than copying templates
  itself.
- `.ai/quality/workflow-contract.toml` removes only issue #110's delivered activation. The generated
  activation table in `docs/engineering/workflow.md` and the independent exact activation oracle
  change in the same commit.
- `docs/architecture.md` gains the two quality-tool module-map entries.

## Transitive impact

- Claude's approval path can call `board arm`; Codex's permit path can call `board start`; both use
  the same ordered service and GitHub adapter.
- The project can be rebuilt without code changes because project, field, item, and option IDs are
  resolved at runtime. Every contract status must exist by name before a mutation is attempted.
- Issue validation uses its own issue-body policy. It does not reuse PR-body sections, which have a
  different purpose and risk-class shape.
- Task scaffolding imports `load_schema()` from `validate_task.py`; changes to artifact scaling
  therefore flow into `just new-task` without a second file list.
- No existing task directory is rewritten. Scaffolding refuses an existing destination.

## Critical dependencies

- `scripts/quality/workflow_contract.py::load_contract` remains the sole workflow-fact loader.
- `scripts/quality/validate_task.py::load_schema` remains the sole task-artifact schema loader.
- GitHub mutations are ordered by the production service and tested through a fake adapter: failed
  status writes cannot consume or create the permit.
- The command surface excludes `Done`, pull-request creation, review approval, auto-merge, and merge.
- `.ai/quality/risk-classes.toml` classifies the quality modules, quality policies, workflow
  contract, and `justfile` as R3. No risk rule or gate list changes.

## Unknown or dynamic edges

- GitHub ProjectV2 IDs and option IDs are external runtime data. The adapter resolves them by name
  on every process invocation and fails if any contract status is absent.
- The `gh` token must carry `project`; the adapter checks this before project access and emits one
  actionable sentence rather than forwarding a raw GraphQL/404 response.
- Project item enumeration and GitHub labels are eventually consistent. The service re-reads the
  issue before writing `approved`, so a status mutation that did not take effect fails closed.
- Adding issue #101 to the real project is an explicitly requested operational verification. It
  changes only project metadata and does not edit the issue, repository, or any runtime system.
- No live runner, MT5 terminal, order, research artifact, or trading configuration is reachable
  from this package.
