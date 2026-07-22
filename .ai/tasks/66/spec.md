# Issue 66: Claude workflow skills, reviewers, and hooks

## Problem

The repository has no Claude Code-native skills, isolated review agents, or deterministic command
hooks enforcing its existing R3 quality workflow.

## Goal

Add correctly formatted Claude Code runtime files that orchestrate the existing quality tooling and
block unsafe commit, push, PR, live-command, secret, bypass, baseline, and review states.

## Non-goals

- CI restructuring, templates, a security-scanner CI job, or session documentation.
- Changes to trading, research, monitoring, live account state, or reported research numbers.
- Reimplementing risk classification, task validation, impact analysis, or PR readiness.

## Behavioural requirements

- Store hook logic in importable, strictly typed Python under `scripts/quality/hooks/`.
- Keep `.claude/settings.json` to documented Claude Code event wiring only.
- Invoke the hook as `uv run python -m scripts.quality.hooks.pre_bash` on Windows and POSIX shells.
- Emit only generic actionable denial reasons; never include command, diff, credential, or file
  contents in hook output.
- Use `classify.py`, `pr_ready.py`, and `validate_task.py` as the authoritative implementations.
- Never invoke a live runner, order operation, or account interaction from code or tests.

## Acceptance criteria

- AC-01: All eight skills and three agents exist, parse with the documented frontmatter keys, and
  state their required invocation or reviewer role.
- AC-02: Every one of the eight hook decisions has an unsafe blocking test and a safe allowing test.
- AC-03: A synthetic fake credential is blocked while clean staged content is allowed, and no hook
  result contains either input.
- AC-04: The Claude settings handler uses the documented `PreToolUse`/`Bash` schema, invokes the
  importable module through `uv run python -m`, and the complete repository gate remains green.

## Invariants

- INV-01: `scripts/quality/classify.py` remains the only path-to-risk matcher.
- INV-02: PR readiness and R3 review validity are delegated to `pr_ready.py` and
  `validate_task.py`, not approximated by hook-local policy.
- INV-03: Hook tests and runtime code never execute or interact with live trading.
- INV-04: Denial output never leaks a command, staged diff, secret value, or file content.

## Assumptions

- Claude Code command hooks receive JSON on stdin with `tool_name` and `tool_input.command`.
- A project settings handler uses the canonical single `command` string supported by the installed
  Claude Code version.
- `uv`, Git, and the repository checkout are available to Claude Code in Git Bash on Windows.

## Open questions

None.

## Expected artifacts

- Eight `.claude/skills/*/SKILL.md` files and three `.claude/agents/*.md` files.
- Thin `.claude/settings.json` event wiring and importable Python hook logic with unit tests.
- Claude workflow documentation, architecture-map updates, and this five-file task record.

## Risk class

R3 — project hooks and `scripts/quality/**` can block commits, pushes, and pull-request creation.

## Human decisions required

- Claude performs the independent post-open review.
- Jan retains scope, go-live, and merge authority; this change must not merge itself.
