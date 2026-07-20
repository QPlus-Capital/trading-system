"""Enforces AGENTS.md's rule that everything in the repo is English.

Scans the four packages for German markers. AGENTS.md grants no exception, and this test grants
none either: the files below are a RATCHET of violations that already exist, asserted to be
exactly the current set. A new German file fails, and a cleaned-up file fails until it is removed
from the list -- so the count can only fall. Issue #40 decides whether the operator-facing wording
of the research stages is translated or the rule is amended; either way this list empties.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGES = ("core", "research", "live", "monitoring")

#: Files that still contain German, pending #40. This is a ratchet, not a licence: the test below
#: fails both when a file outside it carries German AND when a file inside it no longer does.
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

#: Markers that are unambiguously German and occur in this codebase's operator strings. Short
#: words that also appear in English or inside identifiers are deliberately absent: a check that
#: cries wolf gets disabled, and then it protects nothing.
_MARKERS = (
    "aenderung", "änderung", "abbruch", "bericht", "rendite", "gewaehlt", "gewählt",
    "naechster", "nächster", "maerkte", "märkte", "auswahl", "handelbar", "urteil",
    "unbestimmt", "nicht bestimmbar", "herkunft", "laesst", "lässt", "klaeren", "klären",
    "angekuendigt", "angekündigt", "staerker", "stärker", "zahlen bewegen",
)


def _carries_german(path: Path) -> list[str]:
    lowered = path.read_text(encoding="utf-8").lower()
    return sorted({marker for marker in _MARKERS if marker in lowered})


def _python_files() -> list[Path]:
    return sorted(f for pkg in _PACKAGES for f in (_ROOT / pkg).rglob("*.py"))


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_no_new_file_carries_german(path: Path) -> None:
    rel = path.relative_to(_ROOT).as_posix()
    if rel in _KNOWN_VIOLATIONS:
        return  # covered by the ratchet test below, not skipped
    hits = _carries_german(path)
    assert not hits, (
        f"{rel} contains German: {', '.join(hits)}. AGENTS.md requires English throughout."
    )


def test_the_known_violations_are_exactly_those_that_remain() -> None:
    """The list may only shrink.

    Asserting equality rather than membership is what makes it a ratchet: a file that has been
    translated must leave the list, so it cannot quietly become a permanent exemption.
    """
    still_german = {
        rel for rel in _KNOWN_VIOLATIONS
        if (_ROOT / rel).is_file() and _carries_german(_ROOT / rel)
    }
    gone = _KNOWN_VIOLATIONS - still_german
    assert not gone, (
        f"no longer German (or no longer present): {', '.join(sorted(gone))}. "
        "Remove them from _KNOWN_VIOLATIONS so the list keeps shrinking."
    )
