# Claude Code project workflow

The project-scoped Claude Code files under `.claude/` are versioned workflow configuration. Their
formats follow the current official documentation:

- [Skills](https://code.claude.com/docs/en/skills) are directories containing `SKILL.md`; YAML
  frontmatter declares `name` and the trigger-oriented `description`, and the Markdown body is the
  procedure Claude loads on invocation.
- [Subagents](https://code.claude.com/docs/en/sub-agents) are Markdown files under
  `.claude/agents/`; their YAML frontmatter declares `name`, `description`, and the least-privilege
  `tools` list, while the body is the reviewer system prompt.
- [Hooks](https://code.claude.com/docs/en/hooks) are declared in `.claude/settings.json`. The
  `PreToolUse` group matches `Bash` and invokes a command handler. Claude sends the tool payload as
  JSON on stdin; a block is returned as `hookSpecificOutput` with `hookEventName`,
  `permissionDecision`, and `permissionDecisionReason`.
- [Settings](https://code.claude.com/docs/en/settings) identifies `.claude/settings.json` as
  shareable project settings.

The JSON remains wiring only. Its handler uses the canonical single-command string supported by
the installed Claude Code version:

```text
uv run python -m scripts.quality.hooks.pre_bash
```

All decisions live in `scripts/quality/hooks/`. Safe commands produce no output. Denials use fixed,
actionable messages and never echo the command, staged diff, file contents, or a matched credential.
The hook reads the existing TOML-governed risk model and delegates task validity and current-HEAD
readiness to `validate_task.py` and `pr_ready.py`.

The repository's Python 3.13 environment and tests validate every runtime file and the exact hook
schema on Windows. Claude Code itself is not a project dependency, so discovery is additionally
dogfooded by the independent Claude review after the PR opens.

Claude's primary runtime path is conceptual design followed by independent, read-only review of the
completed Codex build. `review-change` and the four reviewer subagents implement that path.
The implementation and PR-preparation skills remain available only when Jan assigns Claude the
highest-stakes trading-work exception; a fresh independent reviewer must then review Claude's work.
