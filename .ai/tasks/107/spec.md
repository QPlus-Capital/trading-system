# Task specification

## Problem

The development workflow was written down in fragments: role contracts in `CLAUDE.md` and
`AGENTS.md`, rules in `docs/engineering/constitution.md`, and nothing stating who acts, where, and in
which order. There was no board, the labels stopped being applied after issue #44, and the real
workflow state lived invisibly in `.ai/tasks/` on disk. Neither agent could be started from an issue
number alone, and the process cost the same for a typo as for a sizing change.

## Goal

One contract that states the end-to-end procedure with the project board as the state and the labels
as permits, so that `implement #101` is a complete instruction to the builder.

## Non-goals

- No file is moved; the folder consolidation is issue #108.
- No skill or subagent is renamed, merged, added or removed; that is #111 and #112.
- Finding severities keep the names `P0`–`P3`; renaming them is #112.
- No tooling is written; that is #110.
- No risk-model or gate configuration changes; that is #109.

## Behavioural requirements

- `docs/engineering/workflow.md` states, for each of the six phases, who acts, in which application,
  and which board status results.
- The constitution states that the risk class scales the process, not only whether a change merges.
- The constitution states the branch and worktree scheme, squash-on-merge, and the rule for merging
  when CI is red for an infrastructure reason.
- The constitution states the three fail-closed handover rules: the permit is written last, the card
  moves before the permit is removed, and the builder context never reaches the reviewer.
- `CLAUDE.md` states the three moments Claude owns and that arming requires explicit approval by Jan.
- `AGENTS.md` states the permit check as the first step of the build procedure.

## Acceptance criteria

- AC-01: `docs/engineering/workflow.md` states, for every one of the six phases, who acts, where, and
  the resulting board status.
- AC-02: The constitution states that the risk class scales the process, not only merge eligibility.
- AC-03: The constitution states the branch and worktree scheme and squash-on-merge.
- AC-04: `AGENTS.md` states the permit check and that the card moves before `arm:implement` is
  removed.
- AC-05: `CLAUDE.md` states that `arm:implement` is written last and that approval requires Jan
  explicitly.
- AC-06: The existing documentation consistency tests pass unchanged.

## Invariants

- INV-01: No load-bearing safety rule is removed from the constitution, `CLAUDE.md` or `AGENTS.md`.
- INV-02: The constitution remains the single source of truth; `workflow.md` never contradicts it.

## Assumptions

The GitHub project board exists with the seven status values named in `workflow.md`, and the five
labels exist. Both were established outside this change and verified against the live repository.

## Open questions

None.

## Expected artifacts

- `docs/engineering/workflow.md` (new)
- `docs/engineering/constitution.md` (§9, §16, new §19, header pointer)
- `CLAUDE.md` (new section on workflow duties)
- `AGENTS.md` (rewritten development protocol)

## Risk class

R3. The classifier already returns R3 for `docs/engineering/**`, `CLAUDE.md` and `AGENTS.md`. No
manual upgrade was needed; the class is not overstated either, because the change alters the rules
every later change is built and reviewed against.

## Human decisions required

None outstanding. Every design decision in this change was made by Jan during the workflow design
session: board columns, label set, specification location, process scaling, approval gate, branch
scheme, merge strategy, and the infrastructure-red merge rule.
