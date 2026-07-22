---
name: prepare-pr
description: Invoke before every pull request to require current evidence and assemble the reviewable handoff.
---

This skill is mandatory immediately before a pull request is created.

## Required inputs

- Final committed HEAD, valid task artifacts, resolved review, and completed required gates.

## Procedure

1. Run `uv run python -m scripts.quality.validate_task <id>`.
2. Run `uv run python -m scripts.quality.pr_ready <id> --base origin/main`.
3. If readiness passes, generate a concise PR body from the task artifacts: scope, risk, AC mapping,
   red-first proof, exact commands/results, review dispositions, and deferred work.
4. Verify author identity, conventional commits, branch target, no AI co-author, and the operator's
   requested draft/ready state.

## Outputs

- A readiness-approved PR body and a current, auditable evidence record.

## Stop conditions

- Stop immediately on any non-zero readiness result and report the missing command or evidence.
- Stop if evidence does not cover current HEAD.

## Prohibited shortcuts

- Do not infer readiness from file presence or narrative claims.
- Do not open a PR before all mandatory gates report exit zero.
- Do not merge or enable autonomous merge for R3.
