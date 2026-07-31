# Impact analysis

## Direct impact

- `scripts/quality/board.py::GhBoardGateway` replaces whole-project item enumeration with one
  issue-scoped GraphQL snapshot that returns the issue, its project item, and project metadata when
  the process-local metadata cache is empty.
- `scripts/quality/board.py::BoardService` preserves every guard and verification read while
  recording only confirmed mutation steps for an interrupted command.
- `scripts/quality/board.py::main` distinguishes rate-limit exhaustion from an ordinary board-state
  refusal by exception type, message, and exit status.
- `tests/test_quality_board.py` gains a counting `gh` fake over small and large projects plus
  rate-limit, partial-progress, fresh-state, connection-boundary, real-write, and secret-redaction
  regressions.

## Transitive impact

- Every `status`, `add`, `move`, `arm`, and `start` invocation consumes the same gateway instance
  for one process, so immutable metadata may be reused within that command but never across CLI
  processes.
- Claude and Codex workflow guards call the CLI and therefore receive a bounded query cost and a
  distinct rate-limit refusal without any change to the workflow contract.
- `arm` still reads before approval, re-reads before writing `approved`, and verifies the final
  label. `start` still reads before the transition, verifies `Implementing`, removes `approved`,
  and verifies the removal.

## Critical dependencies

- `.ai/quality/workflow-contract.toml` remains the sole source for statuses, transitions, approval
  ordering, and builder guards.
- GitHub is the sole board-state source. Only project id, Status field id, option ids, and item ids
  already observed within the current command may be cached; labels and status are always re-read.
- Rate limits are classified from GraphQL error types and response headers before English text. If
  the failed response has no reset header, exactly one `gh api rate_limit` lookup obtains the reset
  without retrying the failed operation.
- Issue ownership is bound to `repository`; project membership is bound to the configured project
  id, not to the first project item returned for the issue. `--owner` intentionally names an
  organization because the project query is organization-bound.

## Unknown or dynamic edges

- GitHub's live GraphQL schema, response headers, and point accounting are external. Tests execute
  the exact query argument shape against a counting fake. The fake counts API calls, not billed
  GraphQL points; the bounded manual `status` observation is the separate point measurement.
- A transport failure after GitHub applied a mutation but before the CLI received success remains
  externally ambiguous. Progress reporting names only steps whose calls returned successfully and
  never claims the interrupted step.
- The account-wide GraphQL budget is shared with unrelated `gh` use. This change bounds this tool's
  query count but cannot attribute or reserve the shared budget.
