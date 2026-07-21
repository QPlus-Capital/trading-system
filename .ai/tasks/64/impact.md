# Impact analysis

## Direct impact

- `.ai/quality/`: task schema and explicit critical dependency edges.
- `.ai/tasks/`: reusable templates and the issue 64 task record.
- `scripts/quality/`: task validation, impact analysis, and readiness orchestration.
- `justfile`: adds `impact`, `check-fast`, `check-security`, `check-critical`, and `pr-ready`; the
  existing `check` commands are unchanged.
- `tests/`: behavioural guards for all three tools.

## Transitive impact

- Every future change may consume the task schema and readiness summary.
- Focused-test execution calls pytest on statically and explicitly related test modules.
- Architecture documentation and the versioned impact JSON describe the new tooling and latest map.

## Critical dependencies

- `pr_ready.py` delegates path matching and changed-range discovery to `classify.py`.
- `pr_ready.py` delegates artifact, traceability, and review checks to `validate_task.py`.
- Critical-map entries escalate the continuous research engine, live risk controller, and shared
  signal engine to their known cross-boundary tests.

## Unknown or dynamic edges

- Static AST analysis cannot prove runtime imports, plugin registration, or external invocation
  completeness; it reports uncertain edges and keeps full pytest mandatory.
- `just` and git subprocess behaviour is covered locally but remains environment-dependent.
