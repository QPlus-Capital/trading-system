# Impact analysis

## Direct impact

- `scripts/quality/board.py`
  - `PUBLIC_COMMANDS`, `_parser`, and `main` gain the non-transitioning `withdraw` operation.
  - `BoardService.move` invalidates and verifies any existing permit before changing status, so no
    generic board transition can carry `approved` into another state.
  - `BoardService.withdraw`, `start`, `arm`, and `_write_approved` report only observed state and
    share verified permit removal.
- `tests/test_quality_board.py`
  - The existing fake gateway gains a sticky-removal fault and the issue's thirteen behavioural
    acceptance guards plus four invariant guards.
- `.ai/quality/finding-patterns/`
  - One content-addressed regression pattern records the confirmed stale-permit/fail-closed defect.

The workflow contract is not changed. Withdrawal is a board maintenance operation, not a new
workflow transition or approval step; the existing `Ready to Implement -> Specifying` transition
already requires removal first, and the existing approval order remains authoritative.

## Transitive impact

- The command-line surface `uv run python -m scripts.quality.board` is the only production caller.
  `status`, `add`, `move`, `arm`, and `start` retain their existing accepted-input behaviour; the
  new operation is additive.
- `AGENTS.md`, `CLAUDE.md`, `docs/engineering/workflow.md`, and
  `docs/engineering/constitution.md` define the permit lifecycle consumed by the service. Their
  contract facts and generated blocks do not change.
- Build start still moves to `Implementing` before removing `approved`; generic `move` removes a
  permit before any status transition, matching the already-registered approval-demotion rule.
- GitHub issue labels and Project status are the external state. All writes are followed by a
  read-back before success is returned.

## Critical dependencies

- `scripts/quality/board.py` classifies R3 because it enforces the build permit governing every
  later change.
- No current mutation target names `scripts/quality/board.py`; the R3 mutation selector must be run
  and its exact applicability result recorded rather than inventing a target in this package.
- `tests/test_quality_board.py`, `tests/test_quality_hooks.py`,
  `tests/test_workflow_contract.py`, and `tests/test_workflow_system_validation.py` are the primary
  integration surfaces.
- No `core/**`, `research/**`, `live/**`, or `monitoring/**` path is touched; trading and live-money
  parity are vacuous, and no live runner or terminal is contacted.

## Unknown or dynamic edges

- The GitHub Project option ids and issue state are resolved dynamically by `GhBoardGateway`; tests
  use fakes and never mutate a real card except through the explicitly requested workflow handovers.
- Concurrent human or automation changes between a write and its verification cannot be made
  atomic by GitHub's APIs. The implementation fails closed on any mismatching re-read.
- The CLI's `gh` subprocess and project-scope authentication remain unchanged and are covered by
  existing tests.
