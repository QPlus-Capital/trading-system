"""Contribution templates must demand evidence rather than accept narrative claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import scripts.quality.pr_body as pr_body
from scripts.quality.classify import load_model
from scripts.quality.pr_body import (
    PRBodyPolicy,
    PRBodyValidation,
    load_pr_body_policy,
    validate_pr_body,
)
from scripts.quality.review_observation import ReviewObservation, ReviewStatus

from tests.test_quality_validate_task import _task

_ROOT = Path(__file__).resolve().parents[1]
_ISSUES = _ROOT / ".github" / "ISSUE_TEMPLATE"
_PR_TEMPLATE = _ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _policy(*sections: str) -> PRBodyPolicy:
    return PRBodyPolicy(
        {risk: tuple(sections) for risk in ("R0", "R1", "R2", "R3")},
        "No live runner was touched.",
    )


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
    policy = _policy("Summary")
    body = (
        "## Summary\n<!-- nothing supplied -->\n\n"
        "## Risk class and reason\nR1 — tooling.\n\n"
        "## Live-runner attestation\nNo live runner was touched."
    )
    result = validate_pr_body(body, task_root=tmp_path, policy=policy)
    assert not result.ok
    assert any("empty required PR section: Summary" in issue for issue in result.issues)


def test_pr_body_validator_accepts_a_complete_body_with_ready_evidence(tmp_path: Path) -> None:
    task = _task(tmp_path)
    policy = load_pr_body_policy()
    bodies = []
    for heading in policy.sections_for("R1"):
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
    policy = _policy("Acceptance criteria")
    body = (
        "## Risk class and reason\n\nR1 — tooling.\n\n"
        "## Acceptance criteria\n\n- [ ] AC-01 is proven.\n\n"
        "## Task artifact\n\n`.ai/tasks/67/`\n\n"
        "## Live-runner attestation\n\n- [ ] No live runner was touched."
    )
    result = validate_pr_body(body, task_root=tmp_path, policy=policy)
    assert not result.ok
    assert any("unchecked checklist item" in issue for issue in result.issues)
    assert any("checked live-runner attestation" in issue for issue in result.issues)


def test_pr_body_validator_requires_a_linked_issue_matching_a_numeric_task(tmp_path: Path) -> None:
    policy = _policy("Linked issue", "Task artifact", "Risk class and reason")
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


def test_real_pr_body_validation_forwards_strict_review_observation(
    tmp_path: Path,
) -> None:
    task = _task(tmp_path)
    gates = load_model().required_gates("R3")
    rows = "\n".join(f"| `{gate}` | `verify {gate}` | 0 | passed |" for gate in gates)
    (task / "evidence.md").write_text(
        "# Evidence\n\n## HEAD\nHEAD: abc123\n\n## Commands\n"
        "| Gate | Command | Exit status | Result |\n"
        "|---|---|---:|---|\n"
        f"{rows}\n\n"
        "## Coverage and mutation\nComplete.\n\n## Deferred checks\nNone.\n",
        encoding="utf-8",
    )
    policy = load_pr_body_policy()
    sections = []
    for heading in policy.sections_for("R3"):
        value = "Completed."
        if heading == "Linked issue":
            value = "Closes #134"
        elif heading == "Task artifact":
            value = f"`.ai/tasks/{task.name}/`"
        elif heading == "Risk class and reason":
            value = "R3 — required quality-gate enforcement."
        elif heading == "Live-runner attestation":
            value = f"- [x] {policy.required_attestation}"
        sections.append(f"## {heading}\n\n{value}")
    body = "\n\n".join(sections)
    observation = ReviewObservation("unverifiable", "GitHub review API unavailable", None)

    permissive = validate_pr_body(
        body,
        task_root=tmp_path,
        changed=["scripts/tool.py"],
        head_sha="abc123",
        review_observation=observation,
        require_verifiable_review=False,
    )
    strict = validate_pr_body(
        body,
        task_root=tmp_path,
        changed=["scripts/tool.py"],
        head_sha="abc123",
        review_observation=observation,
        require_verifiable_review=True,
    )

    assert permissive.ok, permissive.issues
    assert not strict.ok
    assert any("GitHub review API unavailable" in issue for issue in strict.issues)


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    (("verified", 0), ("rejected", 1), ("unverifiable", 1)),
)
def test_ci_pr_body_entrypoint_strictly_binds_the_observed_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected_exit: int,
) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"body": "Task artifact: `.ai/tasks/134/`"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setattr(pr_body, "_head_sha", lambda root: "head")
    monkeypatch.setattr(pr_body, "changed_paths", lambda base: ["scripts/quality/pr_body.py"])
    observation = ReviewObservation(
        cast(ReviewStatus, status),
        f"review {status}",
        "https://review/1" if status == "verified" else None,
    )
    observed_task_ids: list[str] = []

    def observe(gateway: object, head_sha: str, task_id: str) -> ReviewObservation:
        observed_task_ids.append(task_id)
        return observation

    monkeypatch.setattr(pr_body, "observe_independent_review", observe)

    def validate(
        body: str,
        **kwargs: object,
    ) -> PRBodyValidation:
        assert kwargs["review_observation"] is observation
        assert kwargs["require_verifiable_review"] is True
        return PRBodyValidation(()) if status == "verified" else PRBodyValidation(("blocked",))

    monkeypatch.setattr(pr_body, "validate_pr_body", validate)

    assert pr_body.main([]) == expected_exit
    assert observed_task_ids == ["134"]
