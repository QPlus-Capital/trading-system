"""Behavioural guards for issue-body validation and risk-scaled scaffolding."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.quality.issue_body import scaffold_task, validate_issue_body

_VALID_R2 = """## Problem
Problem.

## Goal
Goal.

## Scope
Tooling.

## Non-goals
No workflow automation.

## Acceptance criteria
- [ ] AC-01 First result.
- [ ] AC-02 Second result.

## Invariants
- [ ] INV-01 No merge path.

## Affected modules
scripts/quality/issue_body.py

## Risk class
R2 — issue completeness controls whether work may be approved.

## Verification plan
Behavioural tests.

## Open decisions (Jan)
None.
"""


@pytest.mark.parametrize(
    ("body", "message"),
    (
        (_VALID_R2.replace("## Goal\nGoal.\n\n", ""), "Goal"),
        (
            _VALID_R2.replace(
                "- [ ] AC-01 First result.\n- [ ] AC-02 Second result.",
                "No criterion.",
            ),
            "acceptance criterion",
        ),
        (_VALID_R2.replace("AC-02", "Second criterion"), "numbered AC-nn"),
        (_VALID_R2.replace("AC-02", "AC-03"), "contiguous"),
        (
            _VALID_R2.replace("## Goal\nGoal.", "## Goal\nGoal.\n\n## Goal\nDifferent."),
            "exactly once",
        ),
        (
            _VALID_R2.replace(
                "R2 — issue completeness controls whether work may be approved.",
                "R2",
            ),
            "reason",
        ),
        (_VALID_R2.replace("None.\n", "Choose project 1 or 2.\n", 1), "open decision"),
    ),
)
def test_r2_issue_body_rejects_each_invalid_shape(body: str, message: str) -> None:
    result = validate_issue_body(body, "R2")
    assert not result.ok
    assert message.casefold() in " ".join(result.issues).casefold()


def test_issue_body_accepts_valid_r2_and_skips_r0_r1() -> None:
    assert validate_issue_body(_VALID_R2, "R2").ok
    assert validate_issue_body("", "R0").ok
    assert validate_issue_body("not a specification", "R1").ok


@pytest.mark.parametrize(
    ("risk_class", "expected"),
    (
        ("R0", ()),
        ("R1", ()),
        ("R2", ("review.md", "evidence.md")),
        ("R3", ("impact.md", "test-plan.md", "review.md", "evidence.md")),
    ),
)
def test_scaffold_task_copies_only_files_required_by_issue_risk(
    tmp_path: Path,
    risk_class: str,
    expected: tuple[str, ...],
) -> None:
    template_root = tmp_path / "templates"
    template_root.mkdir()
    for name in ("impact.md", "test-plan.md", "review.md", "evidence.md"):
        (template_root / name).write_text(f"template:{name}\n", encoding="utf-8")
    task_root = tmp_path / "tasks"
    created = scaffold_task(
        101,
        labels=(f"risk:{risk_class}",),
        task_root=task_root,
        template_root=template_root,
    )
    assert tuple(path.name for path in created) == expected
    assert (task_root / "101").is_dir() is bool(expected)
    for path in created:
        assert path.read_text(encoding="utf-8") == f"template:{path.name}\n"


def test_just_new_task_delegates_to_the_production_scaling_scaffolder() -> None:
    completed = subprocess.run(
        ["just", "--dry-run", "new-task", "101"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}".replace("\r\n", "\n")
    assert "uv run python -m scripts.quality.issue_body scaffold --issue 101" in output
