"""CI must enforce the same gates as ``just check`` -- neither may silently drift from the other.

A check that runs locally but not in CI (or over a smaller surface) is a gate that does not bind on
a pull request. This asserts the two definitions cover the same packages for the tools where the
surface matters.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_JUSTFILE = (_ROOT / "justfile").read_text(encoding="utf-8")
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _vulture_packages(text: str) -> set[str]:
    """The package list passed to vulture in a file (the tokens between ``vulture`` and a flag)."""
    match = re.search(r"vulture\s+([\w\s/]+?)\s+--", text)
    assert match, "no vulture invocation found"
    return set(match.group(1).split())


def test_vulture_scans_the_same_packages_locally_and_in_ci() -> None:
    local = _vulture_packages(_JUSTFILE)
    ci = _vulture_packages(_CI)
    assert local == ci, (
        f"just check scans {sorted(local)} but CI scans {sorted(ci)}; a dead-code regression in a "
        "package only one of them covers would not be caught on a PR."
    )
    assert "scripts" in ci, "the dev tooling must be dead-code scanned in CI too"


def test_ci_runs_the_core_gates() -> None:
    """CI must run the same four gates as ``just check`` (ruff, mypy, pytest, vulture)."""
    for tool in ("ruff check", "mypy", "pytest", "vulture"):
        assert tool in _CI, f"CI must run {tool}"
        assert tool in _JUSTFILE, f"just check must run {tool}"
