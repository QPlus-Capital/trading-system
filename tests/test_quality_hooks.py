"""Block/allow proofs for Claude Code command-hook decisions."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from scripts.quality.classify import Classification
from scripts.quality.hooks import pre_bash
from scripts.quality.hooks.decisions import (
    baseline_evidence_decision,
    bypass_decision,
    dangerous_command_decision,
    main_branch_decision,
    pr_readiness_decision,
    push_readiness_decision,
    review_artifact_decision,
    secret_decision,
)
from scripts.quality.hooks.pre_bash import denied_payload
from scripts.quality.validate_task import EvidenceRecord, ValidationIssue, ValidationResult


@pytest.fixture
def synthetic_fake_secret() -> str:
    """Build a deliberately fake credential without storing a usable-looking value."""

    return "sk-" + "synthetic_" + ("x" * 32)


@pytest.mark.parametrize(
    ("unsafe", "safe"),
    [
        ("uv run python -m live.run --mode execute", "uv run pytest -q"),
        ("just live-ttp-execute", "just check-fast"),
        ("just live-ttp", "just check"),
        ("systemctl stop qplus-runner", "git status --short"),
        ("mt5 order place EURUSD", "Get-ChildItem live"),
        ("git push --force origin HEAD:main", "git push origin feature/safe"),
        ("git push --force-with-lease=main origin main", "git push --force origin feature/safe"),
    ],
)
def test_dangerous_command_decision_blocks_unsafe_and_allows_safe(unsafe: str, safe: str) -> None:
    assert not dangerous_command_decision(unsafe).allowed
    assert dangerous_command_decision(safe).allowed


def test_dangerous_command_decision_allows_offline_runner_tests_and_searches() -> None:
    assert dangerous_command_decision("uv run pytest tests/test_live_runner.py -k stop").allowed
    assert dangerous_command_decision('rg "place order" docs').allowed


def test_secret_decision_blocks_synthetic_secret_without_leaking_it(
    synthetic_fake_secret: str,
) -> None:
    diff = f"+API_KEY={synthetic_fake_secret}\n"
    decision = secret_decision(diff)
    assert not decision.allowed
    assert synthetic_fake_secret not in decision.reason
    assert diff not in decision.reason


def test_secret_decision_allows_clean_staged_content() -> None:
    assert secret_decision(
        '+risk_class = "R3"\n+token = placeholder\n+diff = f"API_KEY={fake_value}\\n"\n'
    ).allowed


def test_main_branch_decision_blocks_nontrivial_change_and_allows_safe_case() -> None:
    assert not main_branch_decision("git commit -m test", "main", "R1").allowed
    assert main_branch_decision("git commit -m docs", "main", "R0").allowed
    assert main_branch_decision("git commit -m test", "feature/66", "R3").allowed


def test_push_readiness_decision_blocks_failure_and_allows_success() -> None:
    assert not push_readiness_decision("git push origin HEAD", False).allowed
    assert push_readiness_decision("git push origin HEAD", True).allowed
    assert push_readiness_decision("git status", False).allowed


def test_pr_readiness_decision_blocks_failure_and_allows_success() -> None:
    assert not pr_readiness_decision("gh pr create --fill", False).allowed
    assert pr_readiness_decision("gh pr create --fill", True).allowed
    assert pr_readiness_decision("gh pr view 66", False).allowed


def test_baseline_evidence_decision_blocks_missing_and_allows_explicit_evidence() -> None:
    command = "git commit -m baseline"
    paths = (".ai/quality/mutation-baseline.toml",)
    assert not baseline_evidence_decision(command, paths, ()).allowed
    evidence = (EvidenceRecord("mutation-on-touched-critical", "just mutation-critical", 0, "ok"),)
    assert baseline_evidence_decision(command, paths, evidence).allowed
    assert baseline_evidence_decision(command, ("README.md",), ()).allowed


def test_bypass_decision_blocks_bypass_and_allows_narrow_suppression() -> None:
    assert not bypass_decision("git commit --no-verify", "").allowed
    assert not bypass_decision("git commit", "+value = parse(raw)  # type: ignore\n").allowed
    assert not bypass_decision("git commit", '+@pytest.mark.skip(reason="force green")\n').allowed
    assert bypass_decision("git commit", "+value = parse(raw)  # type: ignore[arg-type]\n").allowed
    assert bypass_decision("git commit", "+value = call()  # noqa: S603\n").allowed
    fixture_source = '+assert not bypass_decision("git commit", "+x = 1  # type: ignore\\n")\n'
    assert bypass_decision("git commit", fixture_source).allowed
    docs_diff = "+++ b/docs/example.md\n+Example: # type: ignore\n"
    assert bypass_decision("git commit", docs_diff).allowed


def test_bypass_decision_blocks_widened_toml_per_file_ignores() -> None:
    diff = '+++ b/pyproject.toml\n [tool.ruff.lint.per-file-ignores]\n+"scripts/**" = ["S603"]\n'
    assert not bypass_decision("git commit", diff).allowed


def test_review_artifact_decision_blocks_invalid_r3_and_allows_valid_review() -> None:
    issue = ValidationIssue("unresolved-review", "one unresolved P1 finding")
    assert not review_artifact_decision("git commit -m x", "R3", (issue,)).allowed
    assert review_artifact_decision("git commit -m x", "R3", ()).allowed
    assert review_artifact_decision("git commit -m x", "R2", (issue,)).allowed


def test_denied_payload_uses_documented_schema_and_never_echoes_input(
    synthetic_fake_secret: str,
) -> None:
    payload = denied_payload("A safe, fixed explanation.")
    encoded = json.dumps(payload)
    assert payload == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "A safe, fixed explanation.",
        }
    }
    assert synthetic_fake_secret not in encoded


def test_evaluate_reuses_classifier_and_task_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = ["scripts/quality/hooks/pre_bash.py", ".ai/tasks/66/review.md"]
    observed: dict[str, object] = {}

    monkeypatch.setattr(pre_bash, "_staged_paths", lambda root: paths)
    monkeypatch.setattr(pre_bash, "changed_paths", lambda base, root: [])
    monkeypatch.setattr(pre_bash, "_staged_diff", lambda root: "+safe = True\n")
    monkeypatch.setattr(pre_bash, "_branch_diff", lambda base, root: "")
    monkeypatch.setattr(pre_bash, "_git", lambda args, root: "feature/66")
    model = object()
    monkeypatch.setattr(pre_bash, "load_model", lambda: model)

    def classify(received: list[str], received_model: object) -> Classification:
        observed["paths"] = received
        observed["model"] = received_model
        return Classification("R3", ())

    monkeypatch.setattr(pre_bash, "classify_paths", classify)
    monkeypatch.setattr(pre_bash, "_task_state", lambda task_id, index, root: ((), ()))

    assert pre_bash.evaluate("git commit -m test").allowed
    assert observed == {"paths": paths, "model": model}


def test_evaluate_blocks_r3_boundary_without_task_review(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pre_bash, "_staged_paths", lambda root: ["scripts/quality/hooks/pre_bash.py"]
    )
    monkeypatch.setattr(pre_bash, "_staged_diff", lambda root: "+safe = True\n")
    monkeypatch.setattr(pre_bash, "_branch_diff", lambda base, root: "")
    monkeypatch.setattr(pre_bash, "changed_paths", lambda base, root: [])
    monkeypatch.setattr(pre_bash, "_git", lambda args, root: "feature/66")
    monkeypatch.setattr(pre_bash, "classify_paths", lambda paths, model: Classification("R3", ()))

    decision = pre_bash.evaluate("git commit -m test")

    assert not decision.allowed
    assert "review artifact" in decision.reason


def test_task_state_validates_the_staged_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_revisions: list[str] = []

    def git_show(args: list[str], root: Path) -> str:
        observed_revisions.append(args[-1])
        if args[-1].endswith("evidence.md"):
            return (
                "# Evidence\n\n## Commands\n\n"
                "| Gate | Command | Exit status | Result |\n"
                "|---|---|---:|---|\n| `check` | `just check` | 0 | green |"
            )
        return "# Task file"

    def validate(task_dir: Path) -> ValidationResult:
        assert sorted(path.name for path in task_dir.iterdir()) == sorted(pre_bash._TASK_FILES)
        return ValidationResult(task_dir, ())

    monkeypatch.setattr(pre_bash, "_git", git_show)
    monkeypatch.setattr(pre_bash, "validate_task_dir", validate)

    issues, evidence = pre_bash._task_state("66", index=True, root=tmp_path)

    assert issues == ()
    assert [record.gate for record in evidence] == ["check"]
    assert all(revision.startswith(":.ai/tasks/66/") for revision in observed_revisions)


def test_hook_main_fails_closed_on_malformed_bash_payload_without_echoing_it(
    synthetic_fake_secret: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"not_command": synthetic_fake_secret},
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    assert pre_bash.main() == 0

    output = capsys.readouterr().out
    assert json.loads(output)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert synthetic_fake_secret not in output
