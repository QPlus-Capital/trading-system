"""The external repository settings and review/session policies are explicit and auditable."""

from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]


def test_branch_protection_names_every_required_check_and_setting() -> None:
    text = (_ROOT / "docs/engineering/branch-protection.md").read_text(encoding="utf-8")
    normalized = " ".join(text.replace("**", "").split())
    ci = yaml.safe_load(
        (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    mutation = yaml.safe_load(
        (_ROOT / ".github/workflows/mutation.yml").read_text(encoding="utf-8")
    )
    required_checks = {
        line.removeprefix("- `").removesuffix("`")
        for line in text.splitlines()
        if line.startswith("- `")
    }
    assert required_checks == {
        "platform-quality",
        "full-quality",
        "critical-change-filter",
        "mutation-critical",
    }
    assert required_checks <= set(ci["jobs"]) | set(mutation["jobs"])
    for phrase in (
        "active branch ruleset named `main`",
        "Require a pull request before merging",
        "Require conversation resolution before merging",
        "Block force pushes",
        "Restrict deletions",
        "zero required approvals",
        "same account",
        "Do not dismiss stale approvals after new commits",
        "Do not require approval of the most recent reviewable push",
        "Do not enable Require linear history",
        "squash-only",
        "do not require branches to be up to date before merging",
        "rebase and re-run",
        "applied on 2026-07-30",
        "no autonomous merge",
        "Codex",
    ):
        assert phrase.casefold() in normalized.casefold()
    assert "Jan applies these settings" not in text


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
