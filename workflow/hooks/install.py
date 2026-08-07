"""Install the tracked Git hook directory for the whole repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

from workflow.classify import REPO_ROOT

TRACKED_HOOKS_PATH = Path("workflow/git-hooks")
PUSH_HOOK_PATH = TRACKED_HOOKS_PATH / "pre-push"
INSTALL_COMMAND = "just install-hooks"


def install(root: Path = REPO_ROOT) -> None:
    """Point the repository-wide Git config at the tracked hooks.

    ``--local`` writes the shared repository config. In a repository with
    ``extensions.worktreeConfig`` enabled, ``--worktree`` would affect only the current worktree
    and leave future ticket worktrees unprotected.
    """

    if not (root / PUSH_HOOK_PATH).is_file():
        raise FileNotFoundError(f"tracked push hook is missing: {PUSH_HOOK_PATH.as_posix()}")
    subprocess.run(
        ["git", "config", "--local", "core.hooksPath", TRACKED_HOOKS_PATH.as_posix()],
        cwd=root,
        check=True,
    )


def main() -> int:
    install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
