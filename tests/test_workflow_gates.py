"""Repository setup preconditions for the risk-class gates."""

from __future__ import annotations

import subprocess
from pathlib import Path

from workflow import gates
from workflow.hooks.install import install


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def test_gates_refuse_when_the_push_hook_is_not_installed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "extensions.worktreeConfig", "true")
    hook = root / "workflow" / "git-hooks" / "pre-push"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test Operator",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "test: add tracked hook",
    )

    missing = gates.push_hook_setup_gate(root=root)
    assert not missing.passed
    assert missing.command == "just install-hooks"
    assert "just install-hooks" in missing.detail

    install(root)
    assert gates.push_hook_setup_gate(root=root).passed

    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "-b", "ticket", str(linked))
    assert _git(linked, "config", "--get", "core.hooksPath") == "workflow/git-hooks"
    assert gates.push_hook_setup_gate(root=linked).passed
    _git(linked, "hook", "run", "pre-push")
