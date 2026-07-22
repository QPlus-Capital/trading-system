---
name: adversarial-review
description: Invoke as Claude's primary path after Codex verifies a change and before Jan approves it.
---

This is Claude's primary workflow skill. It is mandatory after Codex completes implementation and
deterministic gates, and it remains read-only and independent of the builder.

## Required inputs

- Constitution, contributor instructions, all task artifacts, final diff, and relevant source/tests.

## Procedure

1. Invoke `adversarial-code-reviewer` in fresh context with the required inputs.
2. Invoke `test-quality-reviewer` on the test diff and test evidence.
3. For R3 changes, invoke `live-money-reviewer`; never give it authority to interact with live trading.
4. Record every P0-P3 finding, executable counterexample, disposition, and status in `review.md`.
5. If there are no findings, record `No findings; N counterexamples attempted` with the actual
   positive count.
6. Run `uv run python -m scripts.quality.validate_task <id>`.

## Outputs

- An executed review artifact with file/line evidence and explicit dispositions.

## Stop conditions

- Stop before PR preparation while any P0-P2 finding is unresolved.
- Stop if required reviewer inputs are missing or stale.

## Prohibited shortcuts

- Do not review from the implementer's working context alone.
- Do not invent findings or accept narrative reassurance instead of an executable counterexample.
- Do not mark a finding resolved until its targeted execution path is proven.
