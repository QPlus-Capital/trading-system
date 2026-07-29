"""Risk-scaled process cost must preserve every high-risk enforcement boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.quality.classify import load_model
from scripts.quality.hooks.decisions import pr_transition_decision
from scripts.quality.pr_body import load_pr_body_policy, validate_pr_body
from scripts.quality.pr_ready import assess_readiness
from scripts.quality.validate_task import load_schema, validate_task_dir

_R3_GATES = (
    "format",
    "docs-consistency",
    "check",
    "impacted-tests",
    "property-tests-where-applicable",
    "integration-tests",
    "artifact-schema",
    "adversarial-review",
    "invariants",
    "mutation-on-touched-critical",
    "parity-where-applicable",
    "live-money-review",
    "human-decision-escalation",
    "no-autonomous-merge",
)


def _write_task(task: Path, risk_class: str, *, missing: str | None = None) -> None:
    task.mkdir()
    files = {
        "impact.md": (
            "# Impact\n\n## Direct impact\nDirect.\n\n## Transitive impact\nTransitive.\n\n"
            "## Critical dependencies\nCritical.\n\n## Unknown or dynamic edges\nNone.\n"
        ),
        "test-plan.md": (
            "# Test plan\n\n"
            "| Requirement | Test | Before-fix result | After-fix result |\n"
            "|---|---|---|---|\n"
            "| AC-01 | `tests/test_quality_process_scaling.py::"
            "test_validate_task_schema_has_no_spec_and_scales_files` | RED | GREEN |\n"
            "| INV-01 | `tests/test_quality_process_scaling.py::"
            "test_r3_gate_list_is_unchanged` | RED | GREEN |\n"
        ),
        "review.md": (
            "# Review\n\n## Findings\nNo findings; 3 counterexamples attempted\n\n"
            "## Dispositions\nNone required.\n"
        ),
        "evidence.md": "",
    }
    rows = "\n".join(
        f"| `{gate}` | `verify {gate}` | 0 | passed |"
        for gate in load_model().required_gates(risk_class)
    )
    files["evidence.md"] = (
        "# Evidence\n\n## HEAD\nHEAD: abc123\n\n## Commands\n"
        "| Gate | Command | Exit status | Result |\n"
        "|---|---|---:|---|\n"
        f"{rows}\n\n## Coverage and mutation\nComplete.\n\n## Deferred checks\nNone.\n"
    )
    for name in load_schema().required_files_for(risk_class):
        if name != missing:
            (task / name).write_text(files[name], encoding="utf-8")


def _body(risk_class: str, *, omit: str | None = None, task_id: str = "124") -> str:
    policy = load_pr_body_policy()
    parts: list[str] = []
    for heading in policy.sections_for(risk_class):
        if heading == omit:
            continue
        value = "Completed."
        if heading == "Linked issue":
            value = f"Closes #{task_id}"
        elif heading == "Task artifact":
            value = f"`.ai/tasks/{task_id}/`"
        elif heading == "Risk class and reason":
            value = f"{risk_class} — classified by production paths."
        elif heading in {"Acceptance criteria", "Invariant checklist"}:
            value = "- [x] Executable proof recorded."
        elif heading == "Live-runner attestation":
            value = f"- [x] {policy.required_attestation}"
        parts.append(f"## {heading}\n\n{value}")
    return "\n\n".join(parts)


def test_pr_ready_scales_task_artifacts_by_risk(tmp_path: Path) -> None:
    r1 = assess_readiness(None, ["scripts/tool.py"], "abc123")
    assert r1.ready
    assert r1.risk_class == "R1"

    r3_task = tmp_path / "124"
    _write_task(r3_task, "R3", missing="impact.md")
    r3 = assess_readiness(r3_task, ["scripts/quality/pr_ready.py"], "abc123")
    assert not r3.ready
    assert "impact.md" in " ".join(check.detail for check in r3.checks if not check.ok)


@pytest.mark.parametrize(
    ("risk_class", "count"),
    [("R0", 5), ("R1", 8), ("R2", 14), ("R3", 20)],
)
def test_pr_body_requires_exact_risk_class_sections(
    tmp_path: Path,
    risk_class: str,
    count: int,
) -> None:
    policy = load_pr_body_policy()
    assert len(policy.sections_for(risk_class)) == count

    task_root = tmp_path / ".ai" / "tasks"
    task_root.mkdir(parents=True)
    task = task_root / "124"
    if risk_class in {"R2", "R3"}:
        _write_task(task, risk_class)
    complete = validate_pr_body(
        _body(risk_class),
        task_root=task_root,
        changed=["README.md"] if risk_class == "R0" else ["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    if risk_class in {"R0", "R1"}:
        assert complete.ok, complete.issues

    missing_heading = policy.sections_for(risk_class)[-1]
    incomplete = validate_pr_body(
        _body(risk_class, omit=missing_heading),
        task_root=task_root,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    assert not incomplete.ok
    assert any(missing_heading in issue for issue in incomplete.issues)


def test_validate_task_schema_has_no_spec_and_scales_files(tmp_path: Path) -> None:
    schema = load_schema()
    assert "spec.md" not in schema.all_required_files
    assert schema.required_files_for("R1") == ()
    assert schema.required_files_for("R2") == ("review.md", "evidence.md")
    assert schema.required_files_for("R3") == (
        "impact.md",
        "test-plan.md",
        "review.md",
        "evidence.md",
    )

    task = tmp_path / "124"
    _write_task(task, "R3")
    assert not (task / "spec.md").exists()
    assert validate_task_dir(task, risk_class="R3").ok


def test_hook_allows_draft_creation_and_blocks_unready_transition() -> None:
    assert pr_transition_decision("gh pr create --draft --fill", False).allowed
    assert not pr_transition_decision("gh pr create --fill", True).allowed
    assert not pr_transition_decision("gh pr ready 124", False).allowed
    assert pr_transition_decision("gh pr ready 124", True).allowed
    assert pr_transition_decision("git push origin HEAD", False).allowed


def test_r3_gate_list_is_unchanged() -> None:
    assert load_model().required_gates("R3") == _R3_GATES


@pytest.mark.parametrize(
    ("path", "risk_class"),
    [
        ("README.md", "R0"),
        ("scripts/tool.py", "R1"),
        ("core/paths.py", "R2"),
        ("scripts/quality/pr_ready.py", "R3"),
    ],
)
def test_readiness_never_uses_less_than_classifier_gate_set(
    tmp_path: Path,
    path: str,
    risk_class: str,
) -> None:
    task: Path | None = None
    if risk_class in {"R2", "R3"}:
        task = tmp_path / risk_class
        _write_task(task, risk_class)
    result = assess_readiness(task, [path], "abc123")
    assert set(result.required_gates) == set(load_model().required_gates(risk_class))
