"""Smoke test: the four top-level packages import cleanly and the repo root resolves."""

import importlib


def test_worlds_import() -> None:
    for pkg in ("core", "research", "live", "monitoring"):
        assert importlib.import_module(pkg) is not None


def test_repo_root_resolves() -> None:
    from core.paths import REPO_ROOT

    assert (REPO_ROOT / "pyproject.toml").is_file()
