"""Claude Code ``PreToolUse:Bash`` hook for repository safety boundaries.

Claude Code sends a tool payload as JSON on stdin. Safe commands exit zero without output. A denial
uses Claude Code's documented structured permission response and never echoes the command, diff,
file contents, or a detected credential.

The hook guards what must hold whatever the process state: live trading is never touched, a
credential never reaches a commit, an R1+ change never lands directly on ``main``, and a gate is
never weakened to make a branch pass. Everything that depends on where a ticket stands is the
board's and the orchestrator's business, not this hook's.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from workflow.classify import REPO_ROOT, changed_paths, classify_paths, load_model
from workflow.hooks.decisions import (
    Decision,
    bypass_decision,
    dangerous_command_decision,
    main_branch_decision,
    secret_decision,
)

_BOUNDARY = re.compile(r"\bgit\s+(?:commit|push)\b", re.IGNORECASE)
_COMMIT = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)


def denied_payload(reason: str) -> dict[str, object]:
    """Build the documented structured denial response."""

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _git(args: Sequence[str], *, root: Path = REPO_ROOT) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _staged_paths(root: Path = REPO_ROOT) -> list[str]:
    output = _git(["diff", "--cached", "--no-renames", "--name-only"], root=root)
    return [line for line in output.splitlines() if line]


def _branch_diff(base: str, root: Path = REPO_ROOT) -> str:
    return _git(["diff", "--no-renames", "--unified=1", f"{base}...HEAD"], root=root)


def _staged_diff(root: Path = REPO_ROOT) -> str:
    return _git(["diff", "--cached", "--no-renames", "--unified=1"], root=root)


def _command(payload: Mapping[str, Any]) -> str | None:
    if payload.get("hook_event_name") != "PreToolUse" or payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        raise ValueError("Bash hook payload has no tool_input object")
    command = tool_input.get("command")
    if not isinstance(command, str):
        raise ValueError("Bash hook payload has no command string")
    return command


def evaluate(command: str, *, base: str = "origin/main", root: Path = REPO_ROOT) -> Decision:
    """Evaluate one Bash command, collecting Git metadata only at a commit or push boundary."""

    decision = dangerous_command_decision(command)
    if not decision.allowed:
        return decision
    decision = bypass_decision(command, "")
    if not decision.allowed:
        return decision
    if _BOUNDARY.search(command) is None:
        return Decision(True)

    committing = bool(_COMMIT.search(command))
    branch_paths = changed_paths(base, root)
    staged_paths = _staged_paths(root) if committing else []
    staged_diff = _staged_diff(root) if committing else ""
    paths = list(dict.fromkeys([*branch_paths, *staged_paths]))
    diff = f"{_branch_diff(base, root)}\n{staged_diff}" if committing else _branch_diff(base, root)
    classification = classify_paths(paths, load_model())
    branch = _git(["branch", "--show-current"], root=root)

    checks = [
        dangerous_command_decision(command, branch),
        secret_decision(staged_diff) if committing else Decision(True),
        main_branch_decision(command, branch, classification.risk_class),
        bypass_decision(command, diff),
    ]
    return next((check for check in checks if not check.allowed), Decision(True))


def main() -> int:
    """Read one Claude payload and emit only a structured denial when policy blocks it."""

    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, Mapping):
            raise ValueError("hook payload is not an object")
        command = _command(payload)
        if command is None:
            return 0
        decision = evaluate(command, base=os.environ.get("CLAUDE_HOOK_BASE", "origin/main"))
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
        decision = Decision(
            False,
            "Blocked: the repository safety hook could not verify this command; inspect the hook "
            "and retry.",
        )
    if decision.allowed:
        return 0
    print(json.dumps(denied_payload(decision.reason), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
