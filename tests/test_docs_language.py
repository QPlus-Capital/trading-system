"""Keep source English while allowing the constitution's German operator output.

The dashboard exception is syntax-aware: only literals passed directly to the scoped Streamlit
rendering calls are excluded from the marker scan. Identifiers, comments, docstrings, logs, and
indirect strings remain protected. The legacy file-level list remains a shrinking ratchet.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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
_DASHBOARD_OPERATOR_CALLS = {"caption", "error", "info", "warning"}

#: Markers that are unambiguously German and occur in this codebase's operator strings. Short
#: words that also appear in English or inside identifiers are deliberately absent: a check that
#: cries wolf gets disabled, and then it protects nothing.
_MARKERS = (
    "aenderung", "änderung", "abbruch", "bericht", "rendite", "gewaehlt", "gewählt",
    "naechster", "nächster", "maerkte", "märkte", "auswahl", "handelbar", "urteil",
    "unbestimmt", "nicht bestimmbar", "herkunft", "laesst", "lässt", "klaeren", "klären",
    "angekuendigt", "angekündigt", "staerker", "stärker", "zahlen bewegen",
)


def _char_column(line: str, byte_column: int) -> int:
    """Translate an AST UTF-8 byte column to a Python string index."""
    return len(line.encode("utf-8")[:byte_column].decode("utf-8"))


def _without_dashboard_operator_literals(source: str) -> str:
    """Blank only direct Streamlit rendering literals while retaining line structure."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    starts: list[int] = []
    position = 0
    for line in lines:
        starts.append(position)
        position += len(line)
    mask = [False] * len(source)

    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Attribute):
            continue
        direct_streamlit = (
            isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
            and call.func.attr in _DASHBOARD_OPERATOR_CALLS
        )
        if not direct_streamlit and call.func.attr != "metric":
            continue
        values = [*call.args, *(keyword.value for keyword in call.keywords)]
        for value in values:
            for literal in ast.walk(value):
                if not isinstance(literal, (ast.Constant, ast.JoinedStr)):
                    continue
                if isinstance(literal, ast.Constant) and not isinstance(literal.value, str):
                    continue
                if literal.end_lineno is None or literal.end_col_offset is None:
                    continue
                start_line = literal.lineno - 1
                end_line = literal.end_lineno - 1
                start = starts[start_line] + _char_column(lines[start_line], literal.col_offset)
                end = starts[end_line] + _char_column(lines[end_line], literal.end_col_offset)
                mask[start:end] = [True] * (end - start)

    return "".join(
        " " if hidden and char not in "\r\n" else char
        for char, hidden in zip(source, mask, strict=True)
    )


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
    assert not hits, (
        f"{rel} contains German outside approved operator literals: {', '.join(hits)}."
    )


def test_dashboard_exception_is_limited_to_direct_operator_literals() -> None:
    operator_only = 'st.caption("nicht bestimmbar; Märkte")\n'
    rendered = _without_dashboard_operator_literals(operator_only).lower()
    assert not any(marker in rendered for marker in _MARKERS)

    unscoped = (
        operator_only
        + '# Märkte remain English in source comments\n'
        + 'log.warning("nicht bestimmbar")\n'
    )
    hits = {
        marker
        for marker in _MARKERS
        if marker in _without_dashboard_operator_literals(unscoped).lower()
    }
    assert {"märkte", "nicht bestimmbar"} <= hits


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
