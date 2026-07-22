"""Contribution templates must demand evidence rather than accept narrative claims."""

from __future__ import annotations

from pathlib import Path

from scripts.quality.pr_body import PRBodyPolicy, load_pr_body_policy, validate_pr_body

from tests.test_quality_validate_task import _task

_ROOT = Path(__file__).resolve().parents[1]
_ISSUES = _ROOT / ".github" / "ISSUE_TEMPLATE"
_PR_TEMPLATE = _ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def test_all_issue_templates_are_renderable_markdown() -> None:
    expected = {"bug.md", "feature.md", "refactor.md", "methodology-decision.md"}
    assert {path.name for path in _ISSUES.glob("*.md")} == expected
    for path in _ISSUES.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        frontmatter = text.split("---", 2)[1]
        assert "name:" in frontmatter
        assert "about:" in frontmatter
        assert "\n# " in text
        assert "<!--" in text


def test_bug_template_requests_safety_and_time_boundary_context() -> None:
    text = (_ISSUES / "bug.md").read_text(encoding="utf-8").casefold()
    for phrase in (
        "observed behaviour",
        "expected behaviour",
        "reproducibility",
        "affected data",
        "time boundary",
        "invariant violation",
        "safety impact",
        "scope",
    ):
        assert phrase in text


def test_pr_template_contains_every_evidence_field() -> None:
    text = _PR_TEMPLATE.read_text(encoding="utf-8").casefold()
    for phrase in (
        "linked issue",
        "task artifact",
        "risk class",
        "acceptance criteria",
        "invariant checklist",
        "impact-analysis summary",
        "proof of red-first regression",
        "property-test summary",
        "mutation summary",
        "security summary",
        "live-money impact",
        "deferred validations",
        "adversarial-review summary",
        "codex status",
        "human decisions required",
        "no live runner was touched",
    ):
        assert phrase in text


def test_pr_body_validator_rejects_a_missing_required_section(tmp_path: Path) -> None:
    body = _PR_TEMPLATE.read_text(encoding="utf-8").replace("## Security summary", "")
    result = validate_pr_body(body, task_root=tmp_path)
    assert not result.ok
    assert any("Security summary" in issue for issue in result.issues)


def test_pr_body_validator_rejects_a_missing_task_artifact(tmp_path: Path) -> None:
    result = validate_pr_body(_PR_TEMPLATE.read_text(encoding="utf-8"), task_root=tmp_path)
    assert not result.ok
    assert any("task artifact" in issue.casefold() for issue in result.issues)


def test_pr_body_validator_rejects_an_empty_required_section(tmp_path: Path) -> None:
    policy = PRBodyPolicy(("Summary",), "No live runner was touched.")
    body = (
        "## Summary\n<!-- nothing supplied -->\n\n"
        "## Live-runner attestation\nNo live runner was touched."
    )
    result = validate_pr_body(body, task_root=tmp_path, policy=policy)
    assert not result.ok
    assert any("empty required PR section: Summary" in issue for issue in result.issues)


def test_pr_body_validator_accepts_a_complete_body_with_ready_evidence(tmp_path: Path) -> None:
    task = _task(tmp_path)
    policy = load_pr_body_policy()
    bodies = []
    for heading in policy.required_sections:
        value = "Completed."
        if heading == "Linked issue":
            value = "Closes #67"
        elif heading == "Task artifact":
            value = f"`.ai/tasks/{task.name}/`"
        elif heading == "Risk class and reason":
            value = "R1 — local tooling."
        elif heading == "Live-runner attestation":
            value = f"- [x] {policy.required_attestation}"
        bodies.append(f"## {heading}\n\n{value}")
    result = validate_pr_body(
        "\n\n".join(bodies),
        task_root=tmp_path,
        changed=["scripts/tool.py"],
        head_sha="abc123",
    )
    assert result.ok, result.issues


def test_pr_body_validator_requires_checked_attestations_and_checklists(tmp_path: Path) -> None:
    policy = PRBodyPolicy(("Acceptance criteria",), "No live runner was touched.")
    body = (
        "## Acceptance criteria\n\n- [ ] AC-01 is proven.\n\n"
        "## Task artifact\n\n`.ai/tasks/67/`\n\n"
        "## Live-runner attestation\n\n- [ ] No live runner was touched."
    )
    result = validate_pr_body(body, task_root=tmp_path, policy=policy)
    assert not result.ok
    assert any("unchecked checklist item" in issue for issue in result.issues)
    assert any("checked live-runner attestation" in issue for issue in result.issues)


def test_pr_body_validator_requires_a_linked_issue_matching_a_numeric_task(tmp_path: Path) -> None:
    policy = PRBodyPolicy(
        ("Linked issue", "Task artifact", "Risk class and reason"),
        "No live runner was touched.",
    )
    body = (
        "## Linked issue\n\nCloses #66\n\n"
        "## Task artifact\n\n`.ai/tasks/67/`\n\n"
        "## Risk class and reason\n\nR3 — CI gate change.\n\n"
        "## Live-runner attestation\n\n- [x] No live runner was touched."
    )
    result = validate_pr_body(body, task_root=tmp_path, policy=policy)
    assert not result.ok
    assert any(
        "linked issue #66 does not match task artifact 67" in issue for issue in result.issues
    )
