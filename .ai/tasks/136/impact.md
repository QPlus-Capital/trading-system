# Impact analysis

## Direct impact

- `scripts/quality/board.py`
  - `PUBLIC_COMMANDS`, `_parser`, and `main` gain the non-transitioning `withdraw` operation.
  - `BoardService.move` refuses the actor-specific build-start edge, then invalidates and verifies
    any existing permit before every permitted demotion.
  - `BoardService.withdraw`, `start`, `arm`, and `_write_approved` report only observed state and
    share verified permit removal.
  - `GhBoardGateway._run` no longer copies untrusted `gh` stderr into an operator-visible error.
- `tests/test_quality_board.py`
  - The fake gateway gains sticky-removal, sticky-status, sticky-label-addition, and one-shot
    write-interleaving faults.
  - The suite covers the issue criteria, every accepted review counterexample, all `arm` status
    and risk-class boundaries, exact risk-label recognition, and all three lost-write read-backs.
- `.ai/quality/finding-patterns/`
  - Three of the six review patterns are strengthened and renamed from their newly derived content
    hashes so their permanent-protection claims name every executable guard.
- `docs/engineering/workflow.md` and `.ai/quality/workflow-contract.toml`
  - The public board command surface and every permit-removal path are documented without
    pretending the manually maintained table is generated; the contract's non-generated-document
    hash is updated without changing a contract fact.

Withdrawal remains a board maintenance operation, not a new workflow transition or approval step.
The existing `Ready to Implement -> Specifying` demotion requires removal first, while
`Ready to Implement -> Implementing` is refused by `move` and remains exclusively owned by
`start`, which moves first and removes afterwards.

## Transitive impact

- The command-line surface `uv run python -m scripts.quality.board` is the only production caller.
  `status`, `add`, `move`, `arm`, and `start` retain their existing accepted-input behaviour; the
  new operation is additive. Exhaustive status and risk-class tests now bind `arm`'s accepted-input
  surface.
- `AGENTS.md`, `CLAUDE.md`, `docs/engineering/workflow.md`, and
  `docs/engineering/constitution.md` define the permit lifecycle consumed by the service. Their
  contract facts and generated blocks do not change.
- Build start still moves to `Implementing` before removing `approved`; generic `move` cannot invoke
  that edge. Permitted demotions remove and verify the permit before their status write.
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
  atomic by GitHub's APIs. One-shot interleaving hooks and operation-specific sticky writes prove
  every concurrent-modification and lost-write re-read fails closed.
- The CLI's `gh` subprocess and project-scope authentication remain unchanged and are covered by
  existing tests.
