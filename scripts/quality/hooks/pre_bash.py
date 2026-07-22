"""Claude Code ``PreToolUse:Bash`` hook for repository safety boundaries.

Claude Code sends a tool payload as JSON on stdin. Safe commands exit zero without output. A denial
uses Claude Code's documented structured permission response and never echoes the command, diff,
file contents, or a detected credential.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.quality.classify import REPO_ROOT, changed_paths, classify_paths, load_model
from scripts.quality.hooks.decisions import (
    Decision,
    baseline_evidence_decision,
    bypass_decision,
    dangerous_command_decision,
    main_branch_decision,
    pr_readiness_decision,
    push_readiness_decision,
    review_artifact_decision,
    secret_decision,
)
from scripts.quality.pr_ready import main as pr_ready_main
from scripts.quality.validate_task import (
    EvidenceRecord,
    ValidationIssue,
    evidence_records,
    validate_task_dir,
)

_BOUNDARY = re.compile(r"\b(?:git\s+(?:commit|push)|gh\s+pr\s+create)\b", re.IGNORECASE)
_COMMIT = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)
_PUSH = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
_PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b", re.IGNORECASE)
_TASK_FILES = ("spec.md", "impact.md", "test-plan.md", "review.md", "evidence.md")


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
    )
    return completed.stdout.strip()


def _staged_paths(root: Path = REPO_ROOT) -> list[str]:
    output = _git(["diff", "--cached", "--no-renames", "--name-only"], root=root)
    return [line for line in output.splitlines() if line]


def _branch_diff(base: str, root: Path = REPO_ROOT) -> str:
    return _git(["diff", "--no-renames", "--unified=1", f"{base}...HEAD"], root=root)


def _staged_diff(root: Path = REPO_ROOT) -> str:
    return _git(["diff", "--cached", "--no-renames", "--unified=1"], root=root)


def _task_id(paths: Sequence[str]) -> str | None:
    ids = {
        parts[2]
        for path in paths
        if len(parts := path.replace("\\", "/").split("/")) >= 4
        and parts[:2] == [".ai", "tasks"]
        and parts[2] != "_templates"
    }
    return next(iter(ids)) if len(ids) == 1 else None


def _readiness(task_id: str | None, base: str) -> bool:
    if task_id is None:
        return False
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return pr_ready_main([task_id, "--base", base]) == 0


def _task_state(
    task_id: str, *, index: bool, root: Path = REPO_ROOT
) -> tuple[tuple[ValidationIssue, ...], tuple[EvidenceRecord, ...]]:
    """Validate and parse the task snapshot that the commit or push actually carries."""

    with tempfile.TemporaryDirectory(prefix="qplus-task-hook-") as raw_temp:
        task_dir = Path(raw_temp) / task_id
        task_dir.mkdir()
        for name in _TASK_FILES:
            path = f".ai/tasks/{task_id}/{name}"
            revision = f":{path}" if index else f"HEAD:{path}"
            try:
                content = _git(["show", revision], root=root)
            except subprocess.CalledProcessError:
                continue
            (task_dir / name).write_text(f"{content}\n", encoding="utf-8")
        validation = validate_task_dir(task_dir)
        evidence_path = task_dir / "evidence.md"
        evidence = (
            evidence_records(evidence_path.read_text(encoding="utf-8"))
            if evidence_path.is_file()
            else ()
        )
        return validation.issues, evidence


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
    """Evaluate one Bash command, collecting Git/task metadata only at change boundaries."""

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
    task_id = _task_id(paths)
    validation_issues: tuple[ValidationIssue, ...]
    evidence: tuple[EvidenceRecord, ...]
    if task_id is None:
        validation_issues = (ValidationIssue("missing-file", "missing review.md task artifact"),)
        evidence = ()
    else:
        validation_issues, evidence = _task_state(task_id, index=committing, root=root)

    checks = [
        secret_decision(staged_diff) if committing else Decision(True),
        main_branch_decision(command, branch, classification.risk_class),
        bypass_decision(command, diff),
        baseline_evidence_decision(command, paths, evidence),
        review_artifact_decision(command, classification.risk_class, validation_issues),
    ]
    readiness = (
        _readiness(task_id, base) if _PUSH.search(command) or _PR_CREATE.search(command) else True
    )
    checks.extend(
        (
            push_readiness_decision(command, readiness, task_id),
            pr_readiness_decision(command, readiness, task_id),
        )
    )
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
