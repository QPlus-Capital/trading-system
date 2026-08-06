"""The test suite may spawn only explicitly allowed local programs."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.parametrize("entrypoint", ["run", "Popen", "check_output"])
def test_an_unlisted_program_is_refused_before_it_starts(entrypoint: str) -> None:
    command = ["qplus-unlisted-test-program", "--must-not-start"]
    spawn: Any = getattr(subprocess, entrypoint)

    with pytest.raises(AssertionError, match=re.escape("qplus-unlisted-test-program")):
        spawn(command)


@pytest.mark.parametrize(
    "command",
    [["gh"], ["gh.exe"], [r"C:\untrusted\bin\gh.exe"], ["codex"], ["claude"]],
)
def test_the_program_is_matched_by_name_not_by_the_path_it_arrived_as(
    command: list[str],
) -> None:
    with pytest.raises(AssertionError, match=re.escape(command[0])):
        subprocess.run(command, check=False)


def test_git_may_not_reach_a_remote_from_the_suite() -> None:
    for subcommand in ("push", "fetch", "pull", "clone", "ls-remote", "remote"):
        command = ["git", subcommand]
        with pytest.raises(AssertionError, match=re.escape(" ".join(command))):
            subprocess.run(command, check=False)

    subprocess.run(["git", "--version"], check=True, capture_output=True)


def test_the_spawns_the_suite_actually_makes_are_allowed(
    assert_test_spawn_allowed: Callable[[list[str]], None],
) -> None:
    mutmut_name = "mutmut.exe" if os.name == "nt" else "mutmut"
    mutmut = Path(sys.executable).with_name(mutmut_name)
    commands = (
        ["git", "ls-files", "-z"],
        ["git", "check-ignore", "workflow/impact/test-map.json"],
        ["uv", "run", "python", "-c", "pass"],
        [sys.executable, "-c", "pass"],
        [str(mutmut), "run", "sample.*"],
    )

    for command in commands:
        assert_test_spawn_allowed(command)
