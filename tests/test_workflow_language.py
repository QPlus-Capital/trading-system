"""Keep source English while allowing the constitution's German operator output.

The dashboard exception is syntax-aware: only literals resolved by the shared operator-copy scope
are excluded from the marker scan. Identifiers, comments, docstrings, and logs remain protected.
The legacy file-level list remains a shrinking ratchet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from workflow.operator_copy import without_operator_literals

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGES = ("core", "research", "live", "monitoring")

#: Legacy file-level exemptions. This is a ratchet, not a licence: the test below fails both when a
#: file outside it carries unscoped German and when a file inside it no longer does.
_KNOWN_VIOLATIONS = {
    "research/stages/edge.py",
    "research/stages/select.py",
    "research/stages/portfolio.py",
    "research/stages/verdict.py",
    "research/stages/_runbook.py",
    "research/stages/open_report.py",
    "research/portfolio/factsheet.py",
    "research/portfolio/html_report.py",
}

_DASHBOARD = "monitoring/dashboard.py"

#: Markers that are unambiguously German and occur in this codebase's operator strings. Short
#: words that also appear in English or inside identifiers are deliberately absent: a check that
#: cries wolf gets disabled, and then it protects nothing.
_MARKERS = (
    "aenderung",
    "änderung",
    "abbruch",
    "bericht",
    "rendite",
    "gewaehlt",
    "gewählt",
    "naechster",
    "nächster",
    "maerkte",
    "märkte",
    "auswahl",
    "handelbar",
    "urteil",
    "unbestimmt",
    "nicht bestimmbar",
    "herkunft",
    "laesst",
    "lässt",
    "klaeren",
    "klären",
    "angekuendigt",
    "angekündigt",
    "staerker",
    "stärker",
    "zahlen bewegen",
)


def _without_dashboard_operator_literals(source: str) -> str:
    """Blank the same operator literals that the dashboard copy review collects."""
    return without_operator_literals(source, filename=_DASHBOARD)


def _carries_german(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    if path.relative_to(_ROOT).as_posix() == _DASHBOARD:
        source = _without_dashboard_operator_literals(source)
    lowered = source.lower()
    return sorted({marker for marker in _MARKERS if marker in lowered})


def _python_files() -> list[Path]:
    return sorted(f for pkg in _PACKAGES for f in (_ROOT / pkg).rglob("*.py"))


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_no_new_file_carries_german(path: Path) -> None:
    rel = path.relative_to(_ROOT).as_posix()
    if rel in _KNOWN_VIOLATIONS:
        return  # covered by the ratchet test below, not skipped
    hits = _carries_german(path)
    assert not hits, f"{rel} contains German outside approved operator literals: {', '.join(hits)}."


def test_dashboard_exception_is_limited_to_direct_operator_literals() -> None:
    operator_only = 'st.caption("nicht bestimmbar; Märkte")\n'
    rendered = _without_dashboard_operator_literals(operator_only).lower()
    assert not any(marker in rendered for marker in _MARKERS)

    unscoped = (
        operator_only
        + "# Märkte remain English in source comments\n"
        + 'log.warning("nicht bestimmbar")\n'
        + 'raise RuntimeError("Märkte nicht bestimmbar")\n'
    )
    hits = {
        marker
        for marker in _MARKERS
        if marker in _without_dashboard_operator_literals(unscoped).lower()
    }
    assert {"märkte", "nicht bestimmbar"} <= hits


@pytest.mark.parametrize(
    ("unscoped", "marker"),
    [
        ("# Märkte remain English in source comments\n", "märkte"),
        ('log.warning("nicht bestimmbar")\n', "nicht bestimmbar"),
        ('raise RuntimeError("Märkte nicht bestimmbar")\n', "märkte"),
        ('st.warning(f"{maerkte_count}")\n', "maerkte"),
    ],
)
def test_dashboard_exception_is_limited_to_resolved_operator_copy(
    unscoped: str, marker: str
) -> None:
    operator_only = """def render():
    message = "Märkte nicht bestimmbar"
    st.warning(message)
"""
    rendered = _without_dashboard_operator_literals(operator_only).lower()
    assert not any(marker in rendered for marker in _MARKERS)

    rendered = _without_dashboard_operator_literals(operator_only + unscoped).lower()
    assert marker in rendered


def test_the_known_violations_are_exactly_those_that_remain() -> None:
    """The list may only shrink.

    Asserting equality rather than membership is what makes it a ratchet: a file that has been
    translated must leave the list, so it cannot quietly become a permanent exemption.
    """
    still_german = {
        rel for rel in _KNOWN_VIOLATIONS if (_ROOT / rel).is_file() and _carries_german(_ROOT / rel)
    }
    gone = _KNOWN_VIOLATIONS - still_german
    assert not gone, (
        f"no longer German (or no longer present): {', '.join(sorted(gone))}. "
        "Remove them from _KNOWN_VIOLATIONS so the list keeps shrinking."
    )
