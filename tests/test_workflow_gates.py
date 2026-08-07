"""Repository setup preconditions for the risk-class gates."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from workflow import gates
from workflow.hooks.install import INSTALL_COMMAND, PUSH_HOOK_PATH, install

_ROOT = Path(__file__).resolve().parents[1]


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
    assert missing.command == INSTALL_COMMAND
    assert INSTALL_COMMAND in missing.detail

    install(root)
    assert gates.push_hook_setup_gate(root=root).passed

    _git(root, "config", "--local", "core.hooksPath", "wrong/hooks")
    assert not gates.push_hook_setup_gate(root=root).passed
    install(root)

    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "-b", "ticket", str(linked))
    assert _git(linked, "config", "--get", "core.hooksPath") == "workflow/git-hooks"
    assert gates.push_hook_setup_gate(root=linked).passed
    _git(linked, "hook", "run", "pre-push")


def test_gates_name_the_missing_tracked_hook_instead_of_the_installer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "--local", "core.hooksPath", "workflow/git-hooks")

    result = gates.push_hook_setup_gate(root=root)

    assert not result.passed
    assert result.command != INSTALL_COMMAND
    assert PUSH_HOOK_PATH.as_posix() in result.command
    assert INSTALL_COMMAND not in result.detail
    assert "update this checkout" in result.detail
    with pytest.raises(FileNotFoundError, match="update this checkout"):
        install(root)


def test_gates_refuse_a_non_executable_push_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    hook = root / PUSH_HOOK_PATH
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _git(root, "init", "-b", "main")
    _git(root, "config", "--local", "core.hooksPath", "workflow/git-hooks")
    monkeypatch.setattr(os, "access", lambda path, mode: False)

    result = gates.push_hook_setup_gate(root=root)

    assert not result.passed
    assert "executable" in result.detail


def test_gates_run_stops_before_policy_gates_when_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = gates.GateResult("push-hook", INSTALL_COMMAND, 1, 0.0, "missing")
    monkeypatch.setattr(gates, "required_gates", lambda paths, declared: ("R3", ("check",)))
    monkeypatch.setattr(gates, "push_hook_setup_gate", lambda root: setup)

    def unexpected_gate(*args: object, **kwargs: object) -> gates.GateResult:
        raise AssertionError("policy gates must not run after the setup gate fails")

    monkeypatch.setattr(gates, "run_gate", unexpected_gate)

    risk, results = gates.run(["workflow/gates.py"])

    assert risk == "R3"
    assert results == [setup]


def test_the_real_push_hook_shim_executes() -> None:
    shim = _ROOT / PUSH_HOOK_PATH
    assert shim.read_text(encoding="utf-8") == (
        '#!/bin/sh\nexec uv run python -m workflow.hooks.pre_push "$@"\n'
    )

    result = subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={(_ROOT / PUSH_HOOK_PATH.parent).as_posix()}",
            "hook",
            "run",
            "pre-push",
            "--",
            "origin",
            "unused-location",
        ],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
