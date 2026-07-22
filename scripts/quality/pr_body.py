"""Validate a pull-request body against current task artifacts and readiness evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.quality.classify import REPO_ROOT, changed_paths
from scripts.quality.pr_ready import assess_readiness

POLICY_PATH = REPO_ROOT / ".ai" / "quality" / "pr-body.toml"
_SECTION = re.compile(
    r"^##\s+(?P<heading>.+?)\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_TASK = re.compile(r"\.ai/tasks/(?P<task_id>[A-Za-z0-9._-]+)/")


@dataclass(frozen=True)
class PRBodyPolicy:
    required_sections: tuple[str, ...]
    required_attestation: str


@dataclass(frozen=True)
class PRBodyValidation:
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def load_pr_body_policy(path: Path = POLICY_PATH) -> PRBodyPolicy:
    """Load the PR-body contract from TOML."""

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("PR body policy version must be 1")
    required = tuple(str(value) for value in data.get("required_sections", ()))
    attestation = str(data.get("required_attestation", "")).strip()
    if not required or not attestation:
        raise ValueError("PR body policy requires sections and an attestation")
    return PRBodyPolicy(required, attestation)


def _sections(body: str) -> dict[str, str]:
    return {
        match.group("heading").strip().casefold(): match.group("body").strip()
        for match in _SECTION.finditer(body)
    }


def _has_meaningful_content(value: str) -> bool:
    without_comments = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    without_boxes = re.sub(r"[-*]?\s*\[[ xX]\]", "", without_comments)
    return bool(re.search(r"[A-Za-z0-9]", without_boxes))


def validate_pr_body(
    body: str,
    *,
    task_root: Path = REPO_ROOT / ".ai" / "tasks",
    changed: Sequence[str] | None = None,
    head_sha: str | None = None,
    root: Path = REPO_ROOT,
    policy: PRBodyPolicy | None = None,
) -> PRBodyValidation:
    """Validate structure and bind the body to executable readiness evidence when available."""

    active_policy = policy or load_pr_body_policy()
    sections = _sections(body)
    issues: list[str] = []
    for heading in active_policy.required_sections:
        section = sections.get(heading.casefold())
        if section is None:
            issues.append(f"missing required PR section: {heading}")
        elif not _has_meaningful_content(section):
            issues.append(f"empty required PR section: {heading}")
    unchecked = re.findall(r"^\s*[-*]\s+\[\s\]", body, flags=re.MULTILINE)
    if unchecked:
        issues.append(f"PR body has {len(unchecked)} unchecked checklist item(s)")
    checked_attestation = re.search(
        rf"^\s*[-*]\s+\[[xX]\]\s+{re.escape(active_policy.required_attestation)}\s*$",
        body,
        flags=re.MULTILINE,
    )
    if checked_attestation is None:
        issues.append(
            f"missing checked live-runner attestation: {active_policy.required_attestation}"
        )

    required_names = {heading.casefold() for heading in active_policy.required_sections}
    linked_issue: str | None = None
    if "linked issue" in required_names:
        linked_match = re.search(r"#(?P<number>\d+)\b", sections.get("linked issue", ""))
        if linked_match is None:
            issues.append("Linked issue must contain a GitHub issue number such as #67")
        else:
            linked_issue = linked_match.group("number")
    if (
        "risk class and reason" in required_names
        and re.search(r"\bR[0-3]\b", sections.get("risk class and reason", "")) is None
    ):
        issues.append("Risk class and reason must name R0, R1, R2, or R3")

    task_matches = tuple(dict.fromkeys(match.group("task_id") for match in _TASK.finditer(body)))
    if len(task_matches) != 1:
        issues.append("PR body must name exactly one task artifact path under .ai/tasks/<id>/")
        return PRBodyValidation(tuple(issues))

    if task_matches[0].isdigit() and linked_issue is not None and task_matches[0] != linked_issue:
        issues.append(
            f"linked issue #{linked_issue} does not match task artifact {task_matches[0]}"
        )

    task_dir = task_root / task_matches[0]
    if not task_dir.is_dir():
        issues.append(f"task artifact does not exist: .ai/tasks/{task_matches[0]}/")
        return PRBodyValidation(tuple(issues))
    if changed is None or head_sha is None:
        issues.append("task artifact readiness was not evaluated against changed paths and HEAD")
        return PRBodyValidation(tuple(issues))

    readiness = assess_readiness(task_dir, changed, head_sha, root=root)
    if not readiness.ready:
        failed = "; ".join(check.detail for check in readiness.checks if not check.ok)
        issues.append(f"task artifact is not PR-ready: {failed}")
    return PRBodyValidation(tuple(issues))


def _event_body(path: Path) -> str:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub event payload must be an object")
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict) or not isinstance(pull_request.get("body"), str):
        raise ValueError("GitHub event payload has no pull_request.body")
    return str(pull_request["body"])


def _head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a local body file or the current GitHub pull-request event."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", default="")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)
    body_file = str(args.body_file).strip()
    event_file = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    try:
        if body_file:
            body = Path(body_file).read_text(encoding="utf-8")
        elif event_file:
            body = _event_body(Path(event_file))
        else:
            raise ValueError("provide --body-file or GITHUB_EVENT_PATH")
        result = validate_pr_body(
            body,
            changed=changed_paths(args.base),
            head_sha=_head_sha(REPO_ROOT),
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"PR body validation failed closed: {type(exc).__name__}")
        return 2
    if result.ok:
        print("PR body: valid and backed by current task evidence.")
        return 0
    print("PR body: NOT VALID")
    for issue in result.issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
