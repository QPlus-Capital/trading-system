"""The external repository settings and review/session policies are explicit and auditable."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_branch_protection_names_every_required_check_and_setting() -> None:
    text = (_ROOT / "docs/engineering/branch-protection.md").read_text(encoding="utf-8")
    for check in (
        "CI / standard-quality",
        "CI / tests",
        "CI / task-artifact-validation",
        "CI / security",
        "CI / critical-invariants",
        "CI / pr-evidence-validation",
        "Critical mutation / mutation-critical",
    ):
        assert check in text
    for phrase in (
        "Require a pull request before merging",
        "Require conversation resolution before merging",
        "Block force pushes",
        "Restrict deletions",
        "no autonomous merge",
        "Codex",
    ):
        assert phrase.casefold() in text.casefold()


def test_reviewer_findings_policy_closes_the_feedback_loop() -> None:
    text = (_ROOT / "docs/engineering/reviewer-findings.md").read_text(encoding="utf-8")
    for phrase in (
        ".ai/quality/finding-patterns.toml",
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
