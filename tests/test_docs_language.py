"""Enforces AGENTS.md's rule that everything in the repo is English.

Scans the four packages for German markers in source. One set of files is exempt: the research
stages and the fact-sheet renderers, whose operator-facing terminal and report output is German.
Issue #40 decides whether that becomes the documented rule or is translated away; until then the
exemption is listed explicitly, so it stays visible and shrinks rather than spreading.

The rule is enforced here rather than left to review because a convention that depends on
remembering it is not enforced at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGES = ("core", "research", "live", "monitoring")

#: Files whose operator-facing output is German pending the decision in #40.
_EXEMPT = {
    "research/stages/edge.py",
    "research/stages/select.py",
    "research/stages/portfolio.py",
    "research/stages/verdict.py",
    "research/stages/_runbook.py",
    "research/stages/open_report.py",
    # The fact sheet and its HTML report are the same operator surface as the stages that print
    # them. This check found them; I did not know they were German until it ran.
    "research/portfolio/factsheet.py",
    "research/portfolio/html_report.py",
}

#: Words that are unambiguously German and common in this codebase's operator strings. Short
#: words that also occur in English or in identifiers ("die", "der", "ist") are deliberately
#: absent: a check that cries wolf gets disabled, and then it protects nothing.
_MARKERS = (
    "aenderung", "änderung", "abbruch", "bericht", "rendite", "gewaehlt", "gewählt",
    "naechster", "nächster", "maerkte", "märkte", "auswahl", "handelbar", "urteil",
    "unbestimmt", "nicht bestimmbar", "herkunft", "laesst", "lässt", "klaeren", "klären",
    "angekuendigt", "angekündigt", "staerker", "stärker", "zahlen bewegen",
)


def _python_files() -> list[Path]:
    return [f for pkg in _PACKAGES for f in (_ROOT / pkg).rglob("*.py")]


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_source_carries_no_german(path: Path) -> None:
    rel = path.relative_to(_ROOT).as_posix()
    if rel in _EXEMPT:
        pytest.skip(f"{rel} is a documented exception pending #40")
    lowered = path.read_text(encoding="utf-8").lower()
    hits = sorted({marker for marker in _MARKERS if marker in lowered})
    assert not hits, (
        f"{rel} contains German: {', '.join(hits)}. AGENTS.md requires English throughout; "
        "operator-facing wording for the research stages is the exception tracked in #40."
    )


def test_the_exemption_list_only_names_files_that_exist() -> None:
    """An exemption for a file that has moved would silently start covering nothing."""
    missing = [rel for rel in _EXEMPT if not (_ROOT / rel).is_file()]
    assert not missing, f"exempted files no longer exist: {', '.join(missing)}"
