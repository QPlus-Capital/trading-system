"""Block/allow proofs for Claude Code command-hook decisions."""

from __future__ import annotations

import io
import json
import sys

import pytest
from workflow.classify import Classification
from workflow.hooks import pre_bash
from workflow.hooks.decisions import (
    bypass_decision,
    dangerous_command_decision,
    main_branch_decision,
    secret_decision,
)
from workflow.hooks.pre_bash import denied_payload


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


def test_text_that_mentions_a_live_command_is_not_an_invocation() -> None:
    """Regression: the hook matched its patterns against the whole command line, so a commit
    message *describing* a live command read exactly like running one and was refused. Data the
    user wrote is not something the shell executes."""

    described = 'git commit -m "docs: stop documenting just live-ttp-execute, it never existed"'
    assert dangerous_command_decision(described).allowed
    assert main_branch_decision(described, "codex/139-readme", "R0").allowed

    heredoc = "git commit -F - <<'EOF'\nfix: refuse just live-ttp-execute from a stale runbook\nEOF"
    assert dangerous_command_decision(heredoc).allowed

    long_form = 'gh pr create --body "adds a guard around uv run python -m live.run"'
    assert dangerous_command_decision(long_form).allowed

    joined = 'git commit --message="note: systemctl restart qplus-runner is operator-only"'
    assert dangerous_command_decision(joined).allowed


def test_the_real_invocation_still_refuses_however_it_is_written() -> None:
    """The narrowing must not create a way through: an actual invocation still matches, including
    after a shell operator and with its arguments quoted."""

    assert not dangerous_command_decision("just live-ttp-execute").allowed
    assert not dangerous_command_decision("uv run pytest -q && just live-ttp-execute").allowed
    after_operator = "cd live; uv run python -m live.run --mode execute"
    assert not dangerous_command_decision(after_operator).allowed
    assert not dangerous_command_decision('uv run python -m live.run --account "ttp"').allowed
    assert not dangerous_command_decision("systemctl restart qplus-runner").allowed
    assert not dangerous_command_decision("git push --force origin HEAD:main").allowed


def test_a_bypass_flag_inside_written_text_is_not_a_bypass() -> None:
    """Regression: the same over-broad match refused a commit whose message named the flag."""

    verify_bypass = "--no-" + "verify"
    described = f'git commit -m "chore: document why {verify_bypass} is prohibited"'
    assert bypass_decision(described, "").allowed
    assert not bypass_decision(f"git commit {verify_bypass}", "").allowed


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


def test_bypass_decision_blocks_bypass_and_allows_narrow_suppression() -> None:
    verify_bypass = "git commit --no-" + "verify"
    assert not bypass_decision(verify_bypass, "").allowed
    assert not bypass_decision("git commit", "+value = parse(raw)  # type: ignore\n").allowed
    assert not bypass_decision("git commit", '+@pytest.mark.skip(reason="force green")\n').allowed
    assert not bypass_decision("git commit", "+value = call()  # noqa: ALL\n").allowed
    assert not bypass_decision("git commit", "+value = parse(raw)  # type: ignore[]\n").allowed
    assert bypass_decision("git commit", "+value = parse(raw)  # type: ignore[arg-type]\n").allowed
    assert bypass_decision("git commit", "+value = call()  # noqa: S603\n").allowed
    fixture_source = '+assert not bypass_decision("git commit", "+x = 1  # type: ignore\\n")\n'
    assert bypass_decision("git commit", fixture_source).allowed
    docs_diff = "+++ b/docs/example.md\n+Example: # type: ignore\n"
    assert bypass_decision("git commit", docs_diff).allowed


def test_bypass_decision_blocks_widened_toml_per_file_ignores() -> None:
    diff = '+++ b/pyproject.toml\n [tool.ruff.lint.per-file-ignores]\n+"scripts/**" = ["S603"]\n'
    assert not bypass_decision("git commit", diff).allowed


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


def test_evaluate_classifies_the_paths_the_commit_actually_carries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = ["workflow/hooks/pre_bash.py"]
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

    assert pre_bash.evaluate("git commit -m test").allowed
    assert observed == {"paths": paths, "model": model}


def test_evaluate_blocks_an_r3_commit_that_targets_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pre_bash, "_staged_paths", lambda root: ["workflow/hooks/pre_bash.py"]
    )
    monkeypatch.setattr(pre_bash, "changed_paths", lambda base, root: [])
    monkeypatch.setattr(pre_bash, "_staged_diff", lambda root: "+safe = True\n")
    monkeypatch.setattr(pre_bash, "_branch_diff", lambda base, root: "")
    monkeypatch.setattr(pre_bash, "_git", lambda args, root: "main")
    monkeypatch.setattr(pre_bash, "classify_paths", lambda paths, model: Classification("R3", ()))

    decision = pre_bash.evaluate("git commit -m test")

    assert not decision.allowed
    assert "feature branch" in decision.reason


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
