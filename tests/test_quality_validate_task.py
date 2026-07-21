"""Behavioural tests for the engineering-task artifact validator."""

from __future__ import annotations

from pathlib import Path

from scripts.quality.classify import REPO_ROOT
from scripts.quality.validate_task import validate_task_dir

_SPEC = """# Task

## Problem
Problem.

## Goal
Goal.

## Non-goals
None.

## Behavioural requirements
- Requirement.

## Acceptance criteria
- AC-01: The guard binds.

## Invariants
- INV-01: The invariant holds.

## Assumptions
None.

## Open questions
None.

## Expected artifacts
- Artifact.

## Risk class
R1 — local tooling.

## Human decisions required
None.
"""

_TEST_PLAN = """# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_guard` | RED: guard absent | GREEN: guard rejects |
| INV-01 | `test_invariant` | RED: invariant absent | GREEN: invariant holds |
"""

_R1_EVIDENCE_ROWS = """| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `verify format` | 0 | pass |
| `docs-consistency` | `verify docs-consistency` | 0 | pass |
| `check` | `verify check` | 0 | pass |
| `impacted-tests` | `verify impacted-tests` | 0 | pass |
"""


def _task(tmp_path: Path, *, spec: str = _SPEC, test_plan: str = _TEST_PLAN) -> Path:
    task = tmp_path / "task"
    task.mkdir()
    files = {
        "spec.md": spec,
        "impact.md": "# Impact\n\n## Direct impact\nNone.\n\n## Transitive impact\nNone.\n\n"
        "## Critical dependencies\nNone.\n\n## Unknown or dynamic edges\nNone.\n",
        "test-plan.md": test_plan,
        "review.md": "# Review\n\n## Findings\nNo findings.\n\n## Dispositions\nNone.\n",
        "evidence.md": "# Evidence\n\n## HEAD\nHEAD: abc123\n\n## Commands\n"
        f"{_R1_EVIDENCE_ROWS}\n"
        "## Coverage and mutation\nDeferred.\n\n## Deferred checks\nNone.\n",
    }
    for name, content in files.items():
        (task / name).write_text(content, encoding="utf-8")
    return task


def _messages(task: Path) -> str:
    return "\n".join(issue.message for issue in validate_task_dir(task).issues)


def test_a_clean_task_passes(tmp_path: Path) -> None:
    assert validate_task_dir(_task(tmp_path)).ok


def test_the_versioned_templates_satisfy_the_schema() -> None:
    assert validate_task_dir(REPO_ROOT / ".ai" / "tasks" / "_templates").ok


def test_a_missing_required_section_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("## Goal\nGoal.\n\n", ""))
    result = validate_task_dir(task)
    assert not result.ok
    assert "Goal" in _messages(task)


def test_an_empty_required_section_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("## Goal\nGoal.", "## Goal\n"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "Goal" in _messages(task)


def test_a_spec_without_an_acceptance_id_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("AC-01", "criterion"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-*" in _messages(task)


def test_an_unmapped_acceptance_criterion_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, test_plan=_TEST_PLAN.replace("AC-01", "AC-99"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-01" in _messages(task)


def test_an_id_outside_the_requirement_column_does_not_count_as_mapped(tmp_path: Path) -> None:
    misplaced = _TEST_PLAN.replace("| AC-01 | `test_guard`", "| AC-99 | `test-AC-01-guard`")
    task = _task(tmp_path, test_plan=misplaced)
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-01" in _messages(task)


def test_an_unmapped_invariant_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, test_plan=_TEST_PLAN.replace("INV-01", "INV-99"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "INV-01" in _messages(task)


def test_an_unresolved_p1_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        "| R-01 | P1 | Broken path | Investigate | unresolved |\n\n"
        "## Dispositions\nPending.\n",
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "P1" in _messages(task)


def test_an_empty_r3_review_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("R1", "R3", 1))
    result = validate_task_dir(task)
    assert not result.ok
    assert "counterexamples" in _messages(task).lower()


def test_an_r3_no_findings_review_records_counterexamples(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("R1", "R3", 1))
    (task / "review.md").write_text(
        "# Review\n\n## Findings\nNo findings; 3 counterexamples attempted\n\n"
        "## Dispositions\nNone required.\n",
        encoding="utf-8",
    )
    assert validate_task_dir(task).ok


def test_an_r3_no_findings_review_requires_a_counterexample(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("R1", "R3", 1))
    (task / "review.md").write_text(
        "# Review\n\n## Findings\nNo findings; 0 counterexamples attempted\n\n"
        "## Dispositions\nNone required.\n",
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "N >= 1" in _messages(task)


def test_an_r3_review_rejects_a_malformed_finding_row(tmp_path: Path) -> None:
    task = _task(tmp_path, spec=_SPEC.replace("R1", "R3", 1))
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n| P3 |\n\n## Dispositions\nNone.\n",
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "counterexamples" in _messages(task).lower()


def test_an_unresolved_p0_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        "| R-00 | P0 | Catastrophic path | Investigate | unresolved |\n\n"
        "## Dispositions\nPending.\n",
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "P0" in _messages(task)


def test_evidence_without_command_results_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    evidence = task / "evidence.md"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            _R1_EVIDENCE_ROWS,
            "No commands recorded.\n",
        ),
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "command" in _messages(task).lower()


def test_an_unresolved_p2_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        "| R-02 | P2 | Probable risk | None | open |\n\n"
        "## Dispositions\nPending.\n",
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "P2" in _messages(task)


def test_a_resolved_critical_finding_passes(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        "| R-01 | P1 | Broken path | Fixed by test_guard | resolved |\n\n"
        "## Dispositions\nVerified.\n",
        encoding="utf-8",
    )
    assert validate_task_dir(task).ok
