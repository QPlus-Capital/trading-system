---
name: impact-analysis
description: Invoke after specifying a change and before test design to trace its direct and transitive effects.
---

This skill is mandatory after `specify-change` for every non-trivial change.

## Required inputs

- The task spec, repository architecture, current code, and proposed changed paths.

## Procedure

1. Run `uv run python -m scripts.quality.impact --base origin/main` for the current branch, or pass
   the proposed paths when implementation has not started.
2. Inspect each recommended dependency, caller, configuration consumer, test, and documented module
   edge; add dynamic or reflection-based edges that static analysis cannot see.
3. Record direct impact, transitive impact, critical dependencies, and unknown/dynamic edges in
   `.ai/tasks/<id>/impact.md`.
4. Re-run the impact command when the final path set differs from the proposal.

## Outputs

- A current impact artifact and the authoritative focused-test recommendation.

## Stop conditions

- Stop if a live-money, result-integrity, or methodology edge is unknown and cannot be verified.

## Prohibited shortcuts

- Do not invent a second path matcher or dependency map.
- Do not omit dynamic consumers merely because static analysis cannot resolve them.
- Do not treat recommended focused tests as a substitute for the risk class's required gates.
