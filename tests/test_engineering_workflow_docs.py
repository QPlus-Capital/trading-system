"""The external repository settings and review/session policies are explicit and auditable."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_FUTURE_SETTINGS_ACTION = re.compile(
    r"\b(will|shall|plans to|going to|must still|has not yet|later|"
    r"after this workflow lands|are to be|todo)\b",
    re.IGNORECASE,
)


def _required_status_section(text: str) -> str:
    start = "## Required status checks"
    end = "## Review and merge policy"
    assert text.count(start) == 1, f"expected exactly one {start!r} heading"
    remainder = text.split(start, 1)[1]
    assert remainder.count(end) == 1, f"expected exactly one {end!r} heading"
    return remainder.split(end, 1)[0]


def _effective_contexts(workflow: dict[str, object]) -> set[str]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    contexts: set[str] = set()
    for key, raw_job in jobs.items():
        assert isinstance(key, str)
        assert isinstance(raw_job, dict)
        strategy = raw_job.get("strategy")
        if strategy is not None:
            assert isinstance(strategy, dict)
            assert "matrix" not in strategy, f"{key}: a matrix suffixes the status context"
        assert "uses" not in raw_job, f"{key}: a reusable workflow changes the status context"
        name = raw_job.get("name", key)
        assert isinstance(name, str)
        contexts.add(name)
    return contexts


def _assert_no_future_settings_claim(text: str) -> None:
    sentences = re.split(r"(?<=[.!?])(?:\s+|$)|\n+", text)
    for sentence in sentences:
        if "these settings" in sentence.casefold():
            assert _FUTURE_SETTINGS_ACTION.search(sentence) is None, (
                f"future application claim is forbidden: {sentence.strip()}"
            )


def test_branch_protection_names_every_required_check_and_setting() -> None:
    text = (_ROOT / "docs/engineering/branch-protection.md").read_text(encoding="utf-8")
    normalized = " ".join(text.replace("**", "").split())
    ci = yaml.safe_load((_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    mutation = yaml.safe_load(
        (_ROOT / ".github/workflows/mutation.yml").read_text(encoding="utf-8")
    )
    status_section = _required_status_section(text)
    assert "Require these exact contexts, without a workflow-name prefix:" in status_section
    required_checks = {
        line.removeprefix("- `").removesuffix("`")
        for line in status_section.splitlines()
        if line.startswith("- `")
    }
    assert required_checks == {
        "platform-quality",
        "full-quality",
        "critical-change-filter",
        "mutation-critical",
    }
    assert required_checks == _effective_contexts(ci) | _effective_contexts(mutation)
    for phrase in (
        "active branch ruleset named `main`",
        "Set enforcement to `Active`",
        "no bypass actors",
        "Require a pull request before merging",
        "Require conversation resolution before merging",
        "Block force pushes",
        "Restrict deletions",
        "zero required approvals",
        "same account",
        "Do not dismiss stale approvals after new commits",
        "Do not require approval of the most recent reviewable push",
        "do not require a code-owner review",
        "Set allowed merge methods to `squash` only",
        "Do not enable Require linear history",
        "squash-only",
        "do not require branches to be up to date before merging",
        "rebase and re-run",
        "applied on 2026-07-30",
        "no autonomous merge",
        "Codex, and hooks never merge",
        "renamed required check must be",
        "same rollout window",
    ):
        assert phrase.casefold() in normalized.casefold()
    _assert_no_future_settings_claim(text)


@pytest.mark.parametrize(
    "claim",
    [
        "Jan will configure these settings.",
        "Jan will enable these settings.",
        "These settings will be applied by Jan.",
        "Jan has not yet applied these settings.",
        "Jan must still configure these settings.",
        "Jan shall apply these settings.",
        "Jan is going to configure these settings.",
        "Jan plans to configure these settings.",
        "These settings are to be applied by Jan.",
        "TODO configure these settings in GitHub.",
    ],
)
def test_branch_protection_rejects_future_application_claims(claim: str) -> None:
    with pytest.raises(AssertionError):
        _assert_no_future_settings_claim(claim)


def test_effective_contexts_allow_non_matrix_strategy() -> None:
    workflow: dict[str, object] = {
        "jobs": {"quality": {"strategy": {"fail-fast": False}, "name": "quality"}}
    }
    assert _effective_contexts(workflow) == {"quality"}


def test_effective_contexts_refuse_reusable_workflow_jobs() -> None:
    workflow: dict[str, object] = {
        "jobs": {"quality": {"uses": "./.github/workflows/reusable.yml"}}
    }
    with pytest.raises(AssertionError, match="reusable workflow"):
        _effective_contexts(workflow)


def test_required_status_section_requires_its_closing_heading() -> None:
    text = """## Required status checks

- `quality`

## Review and merge rules
"""
    with pytest.raises(AssertionError, match="Review and merge policy"):
        _required_status_section(text)


def test_reviewer_findings_policy_closes_the_feedback_loop() -> None:
    text = (_ROOT / "docs/engineering/reviewer-findings.md").read_text(encoding="utf-8")
    for phrase in (
        ".ai/quality/finding-patterns/",
        "failing test",
        "permanent",
        "repeated defect class",
        "workflow failure",
    ):
        assert phrase.casefold() in text.casefold()


def test_session_policy_uses_artifacts_and_restarts_review_after_material_fixes() -> None:
    text = (_ROOT / "docs/engineering/sessions.md").read_text(encoding="utf-8")
    for phrase in (
        "fresh session",
        "artifacts",
        "isolated subagent",
        "full adversarial review",
        "material fix",
        "stop",
    ):
        assert phrase.casefold() in text.casefold()
