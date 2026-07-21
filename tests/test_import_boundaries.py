"""The package dependency direction from the constitution (section 2), enforced.

`research/` and `live/` do not import each other's domain logic. The single documented exception is
`live/` importing the generic config-module loader `research.engine.config` to read its own config.
This walks each package's real imports (via the AST, so a string that merely mentions a module does
not count) and fails on any crossing that is not the allowed loader.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: The one live -> research crossing the constitution and docs/architecture.md permit: the generic
#: config-module loader.
_ALLOWED_LIVE_TO_RESEARCH = {"research.engine.config"}

#: research -> live crossings that exist today, as a RATCHET. Each is architecture debt tracked for
#: removal; the test allows exactly this set, so a NEW crossing fails and a removed one must leave
#: the list. The list may only shrink. swap_analysis refreshes the broker swap snapshot by pulling
#: it from the live MT5 bridge (cleanup tracked in issue #61).
_KNOWN_RESEARCH_TO_LIVE: dict[str, set[str]] = {
    "research/portfolio/swap_analysis.py": {"live.accounts", "live.mt5_bridge"},
}


def _rid(path: Path) -> str:
    """Repo-relative path with forward slashes, so allowlist keys are platform-independent."""
    return path.relative_to(_ROOT).as_posix()


def _imports_from(path: Path, prefix: str) -> list[str]:
    """Every module under ``prefix`` that ``path`` imports, from the parsed source."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == prefix or node.module.startswith(prefix + "."):
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == prefix or alias.name.startswith(prefix + "."):
                    found.append(alias.name)
    return found


def _package_files(package: str) -> list[Path]:
    return sorted((_ROOT / package).rglob("*.py"))


@pytest.mark.parametrize("path", _package_files("live"), ids=_rid)
def test_live_imports_only_the_allowed_research_loader(path: Path) -> None:
    crossings = _imports_from(path, "research")
    disallowed = [m for m in crossings if m not in _ALLOWED_LIVE_TO_RESEARCH]
    assert not disallowed, (
        f"{_rid(path)} imports {disallowed} from research; only "
        f"{sorted(_ALLOWED_LIVE_TO_RESEARCH)} is allowed (constitution section 2). Move shared "
        "code into core/, or change the documented exception in the constitution and here together."
    )


@pytest.mark.parametrize("path", _package_files("research"), ids=_rid)
def test_research_imports_live_only_where_already_allowlisted(path: Path) -> None:
    crossings = set(_imports_from(path, "live"))
    allowed = _KNOWN_RESEARCH_TO_LIVE.get(_rid(path), set())
    new = crossings - allowed
    assert not new, (
        f"{_rid(path)} newly imports {sorted(new)} from live. research must not depend on the live "
        "trading path (constitution section 2); this ratchet only shrinks."
    )


def test_research_to_live_ratchet_has_no_stale_entries() -> None:
    """A crossing removed from the code must leave the allowlist, so the list keeps shrinking."""
    stale: dict[str, set[str]] = {}
    for rel, allowed in _KNOWN_RESEARCH_TO_LIVE.items():
        actual = set(_imports_from(_ROOT / rel, "live"))
        gone = allowed - actual
        if gone:
            stale[rel] = gone
    assert not stale, f"remove these resolved crossings from _KNOWN_RESEARCH_TO_LIVE: {stale}"


def test_core_depends_on_no_sibling_package() -> None:
    """core/ is the shared base; it must not reach up into research, live, or monitoring."""
    offenders: dict[str, list[str]] = {}
    for path in _package_files("core"):
        crossings = [
            m
            for sibling in ("research", "live", "monitoring")
            for m in _imports_from(path, sibling)
        ]
        if crossings:
            offenders[str(path.relative_to(_ROOT))] = crossings
    assert not offenders, f"core/ must depend on no sibling package, but: {offenders}"
