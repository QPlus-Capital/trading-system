---
name: specify-change
description: Invoke as Claude's primary design path to turn the operator's intent into an executable contract.
---

This is Claude's primary conceptual-design skill. It produces the issue that carries the
specification and moves the card. It never releases work without the operator's explicit word.

## Required inputs

- The issue or operator request, `workflow/workflow.md`, and the repository state.
- The issue number and its current board status.

## Procedure

1. Move the project card to `Specifying`.
2. Reality check: does the problem still exist, is it a duplicate, would the fix violate a safety
   or methodology rule? If so, cite the evidence and propose closing.
3. Classify the expected paths with `workflow.classify`; treat the result as a minimum and
   raise it out loud when the semantic impact is broader.
4. Read the code to the depth the class sets, and search for existing functions to reuse.
5. Write the complete specification into the issue body: problem, goal, non-goals, numbered
   acceptance criteria and invariants, affected modules, justified risk class, open decisions.
   Every `AC-nn` maps to exactly one named test.
6. If a decision only the operator can make remains open, move the card to `Blocked` and stop.
7. Present the complete issue body and, at R3, the risk itself. **Stop before** moving the card.
8. Only after the operator's explicit release: add `risk:Rn` and move the card to
   `Ready to Implement`. Report only that the issue is released — no prompt, no call to action.

## Outputs

- A complete issue body, a declared risk class, and explicit unresolved decisions.
- A card left in `Specifying` or `Blocked` while the release is absent, or moved to
  `Ready to Implement` after it.

## Stop conditions

- Stop before releasing when the operator has not explicitly released the complete issue body.
- Stop if a business, trading, methodology, architecture, live-money, or risk decision is open.
- Stop if the declared risk would understate the classifier result.

## Prohibited shortcuts

- Do not create a second specification as a file; the issue body is authoritative.
- Do not copy the classifier or the contract into the skill or the issue prose.
- Do not implement, edit a branch, or merge. You never build.
