# Impact analysis

## Direct impact

- Claude Code discovers eight workflow skills and three read-only review agents from `.claude/`.
- Every Bash tool call passes through one fast Python pre-tool hook.
- Commit, push, and PR boundaries gain deterministic safety and readiness enforcement.

## Transitive impact

- Future R1–R3 changes must leave `main`, provide current successful evidence, and resolve review
  findings before they can be pushed or opened as a PR through Claude Code.
- Changes to mutation or quality baselines require explicit successful mutation evidence.
- Claude workflows gain reusable procedures without duplicating the existing Python policy.

## Critical dependencies

- Risk and changed-path decisions remain in `scripts/quality/classify.py`.
- Current-HEAD evidence and required gates remain in `scripts/quality/pr_ready.py`.
- Task and review structure remain in `scripts/quality/validate_task.py`.
- The hook payload and settings schema follow current official Claude Code documentation.

## Unknown or dynamic edges

- Claude Code is not installed in the local Windows environment, so schema tests and official
  documentation validation cover discovery format; runtime dogfooding occurs when Claude reviews.
- Git Bash inherits Windows executable lookup for `uv`; the handler avoids shell-specific syntax.
