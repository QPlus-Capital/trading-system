"""Validate Claude Code runtime files against the documented project schemas."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path

from scripts.quality.classify import REPO_ROOT, classify_path, load_model

_SKILLS = {
    "adversarial-review",
    "create-issues",
    "design-tests",
    "impact-analysis",
    "implement-change",
    "prepare-pr",
    "resolve-review",
    "specify-change",
}
_AGENTS = {
    "adversarial-code-reviewer",
    "live-money-reviewer",
    "test-quality-reviewer",
}


def _frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0] == "---", f"{path} has no opening frontmatter delimiter"
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise AssertionError(f"{path} has no closing frontmatter delimiter") from error
    values: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        assert separator and key.strip() and value.strip(), f"invalid frontmatter line: {line!r}"
        values[key.strip()] = value.strip()
    return values, "\n".join(lines[end + 1 :]).strip()


def test_expected_skill_files_have_documented_frontmatter_and_contract() -> None:
    skills_root = REPO_ROOT / ".claude" / "skills"
    discovered = {path.parent.name for path in skills_root.glob("*/SKILL.md")}
    assert discovered == _SKILLS

    for name in sorted(_SKILLS):
        frontmatter, body = _frontmatter(skills_root / name / "SKILL.md")
        assert frontmatter.keys() == {"name", "description"}
        assert frontmatter["name"] == name
        assert "invoke" in frontmatter["description"].casefold()
        for heading in (
            "## Required inputs",
            "## Procedure",
            "## Outputs",
            "## Stop conditions",
            "## Prohibited shortcuts",
        ):
            assert heading in body, f"{name} is missing {heading}"


def test_expected_agents_are_read_only_and_name_their_role() -> None:
    agents_root = REPO_ROOT / ".claude" / "agents"
    discovered = {path.stem for path in agents_root.glob("*.md")}
    assert discovered == _AGENTS

    for name in sorted(_AGENTS):
        frontmatter, body = _frontmatter(agents_root / f"{name}.md")
        assert frontmatter.keys() == {"name", "description", "tools"}
        assert frontmatter["name"] == name
        assert frontmatter["description"]
        assert frontmatter["tools"] == "Read, Grep, Glob, Bash"
        assert "do not edit" in re.sub(r"\s+", " ", body.casefold())


def test_settings_use_thin_documented_pre_tool_hook_schema() -> None:
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings.keys() == {"hooks"}
    assert settings["hooks"].keys() == {"PreToolUse"}
    groups = settings["hooks"]["PreToolUse"]
    assert len(groups) == 1
    assert groups[0].keys() == {"matcher", "hooks"}
    assert groups[0]["matcher"] == "Bash"
    handlers = groups[0]["hooks"]
    assert handlers == [
        {
            "type": "command",
            "command": "uv run python -m scripts.quality.hooks.pre_bash",
            "timeout": 30,
        }
    ]


def test_claude_hook_settings_are_classified_r3() -> None:
    assert classify_path(".claude/settings.json", load_model()).risk_class == "R3"


def test_configured_hook_module_executes_a_safe_payload_without_output() -> None:
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    invocation = shlex.split(command, posix=True)
    assert invocation == ["uv", "run", "python", "-m", "scripts.quality.hooks.pre_bash"]
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git status --short"},
    }
    completed = subprocess.run(
        invocation,
        cwd=REPO_ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
