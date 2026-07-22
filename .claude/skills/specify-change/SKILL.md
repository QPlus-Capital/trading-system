---
name: specify-change
description: Invoke before implementing any non-trivial repository change to create its executable task contract.
---

This skill is mandatory before implementation begins for every non-trivial change.

## Required inputs

- The issue or operator request, `docs/engineering/constitution.md`, and `AGENTS.md` or `CLAUDE.md`.
- The repository state and the task identifier.

## Procedure

1. Run `uv run python -m scripts.quality.classify --base origin/main` when a branch diff exists;
   otherwise classify the expected paths explicitly. Treat the result as a minimum and upgrade it
   when semantic impact is broader.
2. Create the five files under `.ai/tasks/<id>/` from the repository task-artifact structure.
3. Convert the request into numbered acceptance criteria and invariants, with explicit non-goals,
   assumptions, human decisions, and expected artifacts.
4. Run `uv run python -m scripts.quality.validate_task <id>`.

## Outputs

- A valid task specification and companion impact, test-plan, review, and evidence files.
- A declared risk class and explicit unresolved decisions.

## Stop conditions

- Stop before implementation if a business, trading, methodology, architecture, or live-money
  decision is unresolved.
- Stop if the declared risk would understate the classifier result.

## Prohibited shortcuts

- Do not replace acceptance criteria with narrative intent.
- Do not copy the classifier or validator policy into the skill or task prose.
- Do not implement code while the task artifact is invalid.
