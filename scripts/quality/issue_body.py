"""Validate approved issue specifications and scaffold risk-scaled task artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts.quality.classify import CLASSES, REPO_ROOT
from scripts.quality.validate_task import SCHEMA_PATH, TASK_ROOT, load_schema

POLICY_PATH = REPO_ROOT / ".ai" / "quality" / "issue-body.toml"
TEMPLATE_ROOT = TASK_ROOT / "_templates"

_SECTION = re.compile(
    r"^##\s+(?P<heading>.+?)\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_CHECKLIST_ITEM = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?(?P<body>.+?)\s*$", re.MULTILINE)
_AC_ID = re.compile(r"\bAC-(?P<number>\d{2})\b", re.IGNORECASE)
_RISK_LABEL = re.compile(r"^risk:(R[0-3])$")
_RISK_REASON = re.compile(r"\b(?P<class>R[0-3])\b\s*(?:—|–|-|:)\s*(?P<reason>\S[\s\S]*)")


@dataclass(frozen=True)
class IssueBodyPolicy:
    """Risk-scaled section requirements for an issue specification."""

    required_sections: Mapping[str, tuple[str, ...]]

    def sections_for(self, risk_class: str) -> tuple[str, ...]:
        try:
            return self.required_sections[risk_class]
        except KeyError as exc:
            raise ValueError(f"unknown risk class: {risk_class}") from exc


@dataclass(frozen=True)
class IssueBodyValidation:
    """Every issue-body defect found in one validation pass."""

    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _normal_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _sections(body: str) -> dict[str, str]:
    return {
        _normal_heading(match.group("heading")): match.group("body").strip()
        for match in _SECTION.finditer(body)
    }


def load_issue_body_policy(path: Path = POLICY_PATH) -> IssueBodyPolicy:
    """Load the issue-body policy with stdlib TOML and fail closed on schema drift."""

    data = cast(dict[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    if data.get("version") != 1:
        raise ValueError("issue body policy version must be 1")
    raw = data.get("required_sections")
    if not isinstance(raw, dict):
        raise ValueError("issue body policy requires a required_sections table")
    sections = {
        risk: tuple(str(item) for item in cast(Sequence[object], raw.get(risk, ())))
        for risk in CLASSES
    }
    if sections["R0"] or sections["R1"]:
        raise ValueError("R0 and R1 issue bodies must be skipped")
    if not sections["R2"] or sections["R2"] != sections["R3"]:
        raise ValueError("R2 and R3 must share the complete issue specification")
    if len(sections["R2"]) != len(set(sections["R2"])):
        raise ValueError("issue body sections must be unique")
    return IssueBodyPolicy(sections)


def _open_decisions_resolved(value: str) -> bool:
    normalized = re.sub(r"^\s*[-*]\s*", "", value.strip()).strip().rstrip(".").casefold()
    return normalized == "none"


def validate_issue_body(
    body: str,
    risk_class: str,
    *,
    policy: IssueBodyPolicy | None = None,
) -> IssueBodyValidation:
    """Validate an R2/R3 issue specification; R0 and R1 deliberately carry no schema."""

    active = policy or load_issue_body_policy()
    required = active.sections_for(risk_class)
    if not required:
        return IssueBodyValidation(())

    matches = tuple(_SECTION.finditer(body))
    found = _sections(body)
    heading_counts: dict[str, int] = {}
    for match in matches:
        heading = _normal_heading(match.group("heading"))
        heading_counts[heading] = heading_counts.get(heading, 0) + 1
    issues: list[str] = []
    for heading in required:
        normalized = _normal_heading(heading)
        content = found.get(normalized)
        if content is None:
            issues.append(f"missing required issue section: {heading}")
        elif heading_counts[normalized] != 1:
            issues.append(f"issue section must appear exactly once: {heading}")
        elif not re.search(r"[A-Za-z0-9]", content):
            issues.append(f"empty required issue section: {heading}")

    acceptance = found.get("acceptance criteria", "")
    items = [match.group("body") for match in _CHECKLIST_ITEM.finditer(acceptance)]
    numbered: list[int] = []
    for item in items:
        ac_match = _AC_ID.search(item)
        if ac_match is None:
            issues.append("every acceptance criterion must be numbered AC-nn")
        else:
            numbered.append(int(ac_match.group("number")))
    if not numbered:
        issues.append("at least one acceptance criterion is required")
    elif numbered != list(range(1, len(numbered) + 1)):
        issues.append("acceptance criteria must be unique and contiguous from AC-01")

    risk_text = found.get("risk class", "")
    risk_match = _RISK_REASON.search(risk_text)
    if risk_match is None:
        issues.append("Risk class must carry a reason after Rn")
    elif risk_match.group("class") != risk_class:
        issues.append(
            f"body risk class {risk_match.group('class')} does not match requested {risk_class}"
        )

    decisions = found.get("open decisions (jan)", "")
    if decisions and not _open_decisions_resolved(decisions):
        issues.append("open decision remains unresolved")
    return IssueBodyValidation(tuple(dict.fromkeys(issues)))


def risk_class_from_labels(labels: Sequence[str]) -> str:
    """Return one and only one risk class carried by GitHub labels."""

    risks = [match.group(1) for label in labels if (match := _RISK_LABEL.fullmatch(label))]
    if len(risks) != 1:
        raise ValueError(f"issue must carry exactly one risk:Rn label, found {sorted(risks)!r}")
    return risks[0]


def scaffold_task(
    issue: int,
    *,
    labels: Sequence[str],
    task_root: Path = TASK_ROOT,
    template_root: Path = TEMPLATE_ROOT,
    schema_path: Path = SCHEMA_PATH,
) -> tuple[Path, ...]:
    """Copy exactly the artifact templates required by the issue's risk class."""

    if issue <= 0:
        raise ValueError("issue number must be positive")
    risk_class = risk_class_from_labels(labels)
    required = load_schema(schema_path).required_files_for(risk_class)
    if not required:
        return ()
    destination = task_root / str(issue)
    if destination.exists():
        raise FileExistsError(f"task artifact already exists: {destination}")
    for name in required:
        source = template_root / name
        if not source.is_file():
            raise FileNotFoundError(f"task template is missing: {source}")
    destination.mkdir(parents=True)
    created: list[Path] = []
    for name in required:
        target = destination / name
        target.write_bytes((template_root / name).read_bytes())
        created.append(target)
    return tuple(created)


def _issue_payload(issue: int, repository: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue),
            "--repo",
            repository,
            "--json",
            "body,labels",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("gh issue view returned a non-object")
    return cast(dict[str, object], payload)


def _payload_labels(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw = payload.get("labels")
    if not isinstance(raw, list):
        raise ValueError("issue labels are missing")
    labels: list[str] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("issue labels have an unexpected shape")
        labels.append(str(item["name"]))
    return tuple(labels)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--issue", required=True, type=int)
    scaffold_parser = subparsers.add_parser("scaffold")
    scaffold_parser.add_argument("--issue", required=True, type=int)
    for subparser in (validate_parser, scaffold_parser):
        subparser.add_argument("--repo", default="QPlus-Capital/trading-system")
    args = parser.parse_args(argv)
    try:
        payload = _issue_payload(args.issue, args.repo)
        labels = _payload_labels(payload)
        risk_class = risk_class_from_labels(labels)
        if args.command == "validate":
            body = payload.get("body")
            if not isinstance(body, str):
                raise ValueError("issue body is missing")
            result = validate_issue_body(body, risk_class)
            if not result.ok:
                print("Issue body: NOT VALID")
                for issue in result.issues:
                    print(f"  - {issue}")
                return 1
            print(f"Issue body: valid for {risk_class}.")
            return 0
        created = scaffold_task(args.issue, labels=labels)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Issue tooling failed closed: {exc}", file=sys.stderr)
        return 2
    if created:
        print(f"Created {len(created)} artifact file(s) under .ai/tasks/{args.issue}/.")
    else:
        print(f"{risk_class} requires no task artifact files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
