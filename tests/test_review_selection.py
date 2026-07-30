"""The review agent set is selected by one executable risk/path matrix."""

from __future__ import annotations

import pytest
from scripts.quality.review_selection import select_reviewers


@pytest.mark.parametrize(
    ("risk_class", "paths", "expected"),
    (
        ("R0", ("live/runner.py",), ()),
        ("R1", ("research/stages/edge.py",), ()),
        (
            "R2",
            ("README.md",),
            ("adversarial-code-reviewer", "test-quality-reviewer"),
        ),
        (
            "R3",
            ("README.md",),
            ("adversarial-code-reviewer", "test-quality-reviewer"),
        ),
        (
            "R3",
            ("live/runner.py",),
            (
                "adversarial-code-reviewer",
                "test-quality-reviewer",
                "live-money-reviewer",
            ),
        ),
        (
            "R3",
            ("research/stages/edge.py",),
            (
                "adversarial-code-reviewer",
                "test-quality-reviewer",
                "methodology-reviewer",
            ),
        ),
        (
            "R3",
            ("docs/methodology.md",),
            (
                "adversarial-code-reviewer",
                "test-quality-reviewer",
                "methodology-reviewer",
            ),
        ),
        (
            "R3",
            ("docs/strategies/rsi_wpr_bb.md",),
            (
                "adversarial-code-reviewer",
                "test-quality-reviewer",
                "methodology-reviewer",
            ),
        ),
        (
            "R3",
            ("live/runner.py", "research/stages/edge.py"),
            (
                "adversarial-code-reviewer",
                "test-quality-reviewer",
                "live-money-reviewer",
                "methodology-reviewer",
            ),
        ),
    ),
)
def test_reviewer_selection_matrix(
    risk_class: str,
    paths: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    assert select_reviewers(risk_class, paths) == expected


def test_reviewer_selection_rejects_an_unknown_risk_class() -> None:
    with pytest.raises(ValueError, match="unknown risk class"):
        select_reviewers("Note", ("README.md",))
