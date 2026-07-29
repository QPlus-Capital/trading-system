---
name: specify-change
description: Invoke as Claude's primary design path to turn Jan's intent into an executable contract.
---

This is Claude's primary conceptual-design skill. It produces the issue that carries the
specification and controls Claude's board transitions. It never arms work without Jan's explicit
approval.

## Required inputs

- The issue or operator request, `docs/engineering/constitution.md`, and `AGENTS.md` or `CLAUDE.md`.
- The repository state, issue number, project item, and current board status.

## Procedure

1. Move the project card to `Specifying`.
2. Check that the problem still exists, is not a duplicate, and does not violate the constitution.
3. Classify the expected paths with `scripts.quality.classify`; treat the result as a minimum.
4. Write the complete specification into the issue body: problem, goal, scope, non-goals, numbered
   acceptance criteria and invariants, affected modules, justified risk class, verification plan,
   and open decisions.
5. If a decision only Jan can make remains open, move the card to `Blocked` and stop.
6. Present the complete issue body and risk to Jan. **Stop before** moving to
   `Ready to Implement` or adding `approved` until Jan's explicit approval.
7. After that approval only, write the final issue body, add `risk:Rn`, move the card to
   `Ready to Implement`, and add `approved` last.

## Outputs

- A complete issue body, declared risk class, and explicit unresolved decisions.
- A board card left unarmed while Jan's approval is absent, or armed in the required order after it.

## Stop conditions

- Stop before arming when Jan has not explicitly approved the complete issue body.
- Stop if a business, trading, methodology, architecture, live-money, or risk decision is open.
- Stop if the declared risk would understate the classifier result.

## Prohibited shortcuts

- Do not create a second specification under `.ai/tasks/`; the issue body is authoritative.
- Do not copy the classifier or validator policy into the skill or task prose.
- Do not add `approved` before every earlier approval action succeeds.
