"""Behavioural tests for the engineering-task artifact validator."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.quality.finding_registry as finding_registry
import scripts.quality.validate_task as task_validator
from scripts.quality.classify import REPO_ROOT
from scripts.quality.review_observation import ReviewObservation
from scripts.quality.validate_task import ValidationResult, discover_task_id, validate_task_dir

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

_LEGACY_UNRESOLVED_TEST_PLAN_REFERENCES = frozenset(
    {
        (
            ".ai/tasks/_templates/test-plan.md",
            "test_invariant",
        ),
        (
            ".ai/tasks/_templates/test-plan.md",
            "test_name",
        ),
        (
            ".ai/tasks/ISSUE-62/test-plan.md",
            "test_gate_consistency",
        ),
        (
            ".ai/tasks/ISSUE-91/test-plan.md",
            "test_drawdown_uses_an_observable_h4_high_before_a_later_minimum",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_artifact_hashes_use_lineage_convention_and_detect_drift",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_candidate_missing_one_market_is_absent_everywhere",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_continuous_payload_reuses_stage1_net_trade_rows",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_daily_artifact_feeds_p04_block_selector_directly",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_daily_artifact_uses_prop_day_and_includes_zero_trade_days",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_exact_daily_window_and_market_window_invariants",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_generated_candidate_artifacts_remain_gitignored",
        ),
        (
            ".ai/tasks/P-03/test-plan.md",
            "test_production_candidate_definitions_are_formal_trials_only",
        ),
        (
            ".ai/tasks/P-05/test-plan.md",
            "test_edge_publishes_lineage_bound_spa_evidence",
        ),
        (
            ".ai/tasks/P-05/test-plan.md",
            "test_spa_loader_reads_the_persisted_daily_matrix_without_recomputation",
        ),
    }
)


def _task(tmp_path: Path, *, spec: str = _SPEC, test_plan: str = _TEST_PLAN) -> Path:
    task = tmp_path / "task"
    task.mkdir()
    files = {
        "spec.md": spec,
        "impact.md": "# Impact\n\n## Direct impact\nNone.\n\n## Transitive impact\nNone.\n\n"
        "## Critical dependencies\nNone.\n\n## Unknown or dynamic edges\nNone.\n",
        "test-plan.md": test_plan,
        "review.md": "# Review\n\n## Findings\nNo findings; 1 counterexamples attempted\n\n"
        "## Dispositions\nNone.\n",
        "evidence.md": "# Evidence\n\n## HEAD\nHEAD: abc123\n\n## Commands\n"
        f"{_R1_EVIDENCE_ROWS}\n"
        "## Coverage and mutation\nDeferred.\n\n## Deferred checks\nNone.\n",
    }
    for name, content in files.items():
        (task / name).write_text(content, encoding="utf-8")
    return task


def test_every_task_plan_test_reference_collects() -> None:
    """Full and bare acceptance-map references resolve, except an exact shrinking legacy set."""
    references: list[str] = []
    shorthand: list[str] = []
    bare_references: list[tuple[str, str]] = []
    for plan in sorted((REPO_ROOT / ".ai" / "tasks").glob("*/test-plan.md")):
        text = plan.read_text(encoding="utf-8")
        references.extend(re.findall(r"`(tests/[A-Za-z0-9_./-]+\.py::[A-Za-z0-9_:\[\].-]+)`", text))
        shorthand.extend(re.findall(r"`(::test_[^`]+)`", text))
        without_full_ids = re.sub(
            r"`tests/[A-Za-z0-9_./-]+\.py::[A-Za-z0-9_:\[\].-]+`",
            "",
            text,
        )
        bare_references.extend(
            (plan.relative_to(REPO_ROOT).as_posix(), name)
            for name in re.findall(r"`(test_[A-Za-z0-9_]+)`", without_full_ids)
        )
    assert not shorthand, (
        "task test plans must use complete pytest node ids, not path-relative shorthand: "
        f"{shorthand}"
    )

    collected_names: set[str] = set()
    for path in (REPO_ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        collected_names.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    unresolved = {(path, name) for path, name in bare_references if name not in collected_names}
    assert unresolved == _LEGACY_UNRESOLVED_TEST_PLAN_REFERENCES, (
        "bare task-plan references must resolve; only the explicit shrinking legacy set is "
        "temporarily allowed:\n"
        f"new={sorted(unresolved - _LEGACY_UNRESOLVED_TEST_PLAN_REFERENCES)!r}\n"
        f"now-resolved={sorted(_LEGACY_UNRESOLVED_TEST_PLAN_REFERENCES - unresolved)!r}"
    )

    assert references, "at least one task test plan must cite an executable pytest node id"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *sorted(set(references))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "a task test plan cites a pytest node id that does not collect:\n"
        f"{result.stdout}\n{result.stderr}"
    )


def _messages(task: Path) -> str:
    return "\n".join(issue.message for issue in validate_task_dir(task).issues)


def test_a_clean_task_passes(tmp_path: Path) -> None:
    assert validate_task_dir(_task(tmp_path)).ok


def test_changed_task_discovery_requires_exactly_one_artifact() -> None:
    assert discover_task_id([".ai/tasks/67/spec.md", "scripts/quality/pr_body.py"]) == "67"
    assert discover_task_id([".ai/tasks/66/spec.md", ".ai/tasks/67/spec.md"]) is None
    assert discover_task_id(["scripts/quality/pr_body.py"]) is None


def test_cli_reports_the_discovered_task_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        task_validator,
        "changed_paths",
        lambda _base: [".ai/tasks/67/evidence.md", "scripts/quality/pr_ready.py"],
    )
    monkeypatch.setattr(
        task_validator,
        "validate_task",
        lambda task_id, risk_class, require_completed_review: ValidationResult(
            Path(task_id), (), ("AC-01",), ("INV-01",)
        ),
    )
    assert task_validator.main(["--base", "origin/main"]) == 0
    assert "Task 67: valid" in capsys.readouterr().out


def test_the_versioned_templates_satisfy_the_schema() -> None:
    assert validate_task_dir(REPO_ROOT / ".ai" / "tasks" / "_templates").ok


def test_a_missing_required_section_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    impact = task / "impact.md"
    impact.write_text(
        impact.read_text(encoding="utf-8").replace("## Direct impact\nNone.\n\n", ""),
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "Direct impact" in _messages(task)


def test_an_empty_required_section_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    impact = task / "impact.md"
    impact.write_text(
        impact.read_text(encoding="utf-8").replace(
            "## Direct impact\nNone.",
            "## Direct impact\n",
        ),
        encoding="utf-8",
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "Direct impact" in _messages(task)


def test_a_test_plan_without_an_acceptance_id_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, test_plan=_TEST_PLAN.replace("AC-01", "criterion"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-*" in _messages(task)


def test_an_incomplete_acceptance_trace_fails(tmp_path: Path) -> None:
    task = _task(
        tmp_path,
        test_plan=_TEST_PLAN.replace(
            "| AC-01 | `test_guard` | RED: guard absent | GREEN: guard rejects |",
            "| AC-01 | `test_guard` | | |",
        ),
    )
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-01" in _messages(task)


def test_an_id_outside_the_requirement_column_does_not_count_as_mapped(tmp_path: Path) -> None:
    misplaced = _TEST_PLAN.replace("| AC-01 | `test_guard`", "| criterion | `test-AC-01-guard`")
    task = _task(tmp_path, test_plan=misplaced)
    result = validate_task_dir(task)
    assert not result.ok
    assert "AC-*" in _messages(task)


def test_an_unmapped_invariant_fails(tmp_path: Path) -> None:
    task = _task(tmp_path, test_plan=_TEST_PLAN.replace("INV-01", "criterion"))
    result = validate_task_dir(task)
    assert not result.ok
    assert "INV-*" in _messages(task)


def test_draft_schema_validation_does_not_require_a_pr_review(tmp_path: Path) -> None:
    task = _task(tmp_path)
    assert validate_task_dir(task, require_completed_review=False).ok


def test_task_validator_accepts_new_severities_and_rejects_old_codes() -> None:
    """The historic migration guard now binds at the finding-registry boundary."""

    assert (
        frozenset({"Blocker", "Defect", "Suspected defect", "Note"}) == finding_registry._SEVERITIES
    )
    assert not finding_registry._SEVERITIES & {"P0", "P1", "P2", "P3"}


def test_blocking_severity_set_is_unchanged_by_the_migration() -> None:
    assert frozenset({"blocker", "defect", "suspected defect"}) == task_validator._CRITICAL
    assert set(task_validator._SEVERITIES.values()) == {
        "Blocker",
        "Defect",
        "Suspected defect",
        "Note",
    }


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


@pytest.mark.parametrize(
    "review_text",
    (
        "# Review\n\nOld exact phrase with no PR review.\n",
        "# Different shape\n\n**No findings; 3 counterexamples attempted**\n",
        "# Review\n\n| arbitrary | markdown |\n|---|---|\n| is | irrelevant |\n",
    ),
)
def test_review_markdown_shape_is_not_a_gate_input(tmp_path: Path, review_text: str) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        f"# Review\n\n## Findings\n\n{review_text}\n\n## Dispositions\n\nNone.\n",
        encoding="utf-8",
    )
    observation = ReviewObservation("verified", "review verified", "https://review/1")

    assert validate_task_dir(task, review_observation=observation).ok


def test_old_review_phrase_without_an_observed_pr_review_fails(tmp_path: Path) -> None:
    task = _task(tmp_path)
    observation = ReviewObservation("rejected", "no submitted PR review", None)

    result = validate_task_dir(task, review_observation=observation)

    assert not result.ok
    assert "no submitted PR review" in " ".join(issue.message for issue in result.issues)


@pytest.mark.parametrize("risk_class", ("R2", "R3"))
@pytest.mark.parametrize("severity", ("Blocker", "Defect", "Suspected defect"))
def test_observed_review_does_not_clear_an_unresolved_blocking_finding(
    tmp_path: Path,
    risk_class: str,
    severity: str,
) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        f"| R-01 | {severity} | Broken guard | Pending | unresolved |\n\n"
        "## Dispositions\n\nPending.\n",
        encoding="utf-8",
    )
    observation = ReviewObservation("verified", "review verified", "https://review/1")

    result = validate_task_dir(
        task,
        risk_class=risk_class,
        review_observation=observation,
        require_verifiable_review=True,
    )

    assert not result.ok
    assert any(issue.code == "unresolved-review" for issue in result.issues)


@pytest.mark.parametrize("risk_class", ("R2", "R3"))
def test_review_sections_bind_independently_of_the_observed_review(
    tmp_path: Path,
    risk_class: str,
) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text("", encoding="utf-8")
    observation = ReviewObservation("verified", "review verified", "https://review/1")

    result = validate_task_dir(
        task,
        risk_class=risk_class,
        review_observation=observation,
        require_verifiable_review=True,
    )

    assert not result.ok
    assert {issue.code for issue in result.issues} >= {"missing-section"}
    assert any("Findings" in issue.message for issue in result.issues)
    assert any("Dispositions" in issue.message for issue in result.issues)


@pytest.mark.parametrize("risk_class", ("R2", "R3"))
def test_completed_review_strict_mode_refuses_an_unobserved_review(
    tmp_path: Path,
    risk_class: str,
) -> None:
    task = _task(tmp_path)

    result = validate_task_dir(
        task,
        risk_class=risk_class,
        require_completed_review=True,
        require_verifiable_review=True,
    )

    assert not result.ok
    assert any(issue.code == "unverifiable-adversarial-review" for issue in result.issues)


def test_task_validator_enforces_the_review_severity_vocabulary(tmp_path: Path) -> None:
    observation = ReviewObservation("verified", "review verified", "https://review/1")
    for severity in ("Blocker", "Defect", "Suspected defect", "Note"):
        case_root = tmp_path / severity.replace(" ", "-")
        case_root.mkdir()
        task = _task(case_root)
        (task / "review.md").write_text(
            "# Review\n\n## Findings\n\n"
            "| ID | Severity | Finding | Disposition | Status |\n"
            "|---|---|---|---|---|\n"
            f"| R-01 | {severity} | Checked path | Verified | resolved |\n\n"
            "## Dispositions\n\nVerified.\n",
            encoding="utf-8",
        )
        assert validate_task_dir(task, review_observation=observation).ok

    for severity in ("P0", "P1", "P2", "P3"):
        case_root = tmp_path / severity
        case_root.mkdir()
        task = _task(case_root)
        (task / "review.md").write_text(
            "# Review\n\n## Findings\n\n"
            "| ID | Severity | Finding | Disposition | Status |\n"
            "|---|---|---|---|---|\n"
            f"| R-01 | {severity} | Old vocabulary | None | resolved |\n\n"
            "## Dispositions\n\nRejected.\n",
            encoding="utf-8",
        )
        result = validate_task_dir(task, review_observation=observation)
        assert not result.ok
        assert any(issue.code == "invalid-review-severity" for issue in result.issues)
