"""Repo-root resolution, independent of a module's nesting depth.

Every module that needs to reach data/, reports/ or a config file asks here instead of
counting ``Path(__file__).parents[N]`` -- that count breaks the moment a file moves. We
walk up to the directory that contains ``pyproject.toml`` and cache it.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path


@cache
def repo_root() -> Path:
    """The repository root: the nearest ancestor holding ``pyproject.toml``."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("repo root not found (no pyproject.toml in any parent)")


REPO_ROOT = repo_root()
