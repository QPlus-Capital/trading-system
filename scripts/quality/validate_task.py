"""Validate concise engineering-task artifacts and requirement-to-test traceability.

The task schema is machine-readable TOML under ``.ai/quality``. The validator deliberately parses
only stable, auditable Markdown structures: level-two section headings, ``AC-*`` / ``INV-*`` IDs,
traceability-table rows, and review finding rows. It never stores or requests model transcripts.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.quality.classify import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / ".ai" / "quality" / "task-artifacts.toml"
TASK_ROOT = REPO_ROOT / ".ai" / "tasks"
_AC = re.compile(r"\bAC-\d+\b", re.IGNORECASE)
_INV = re.compile(r"\bINV-\d+\b", re.IGNORECASE)
_SECTION = re.compile(
    r"^##\s+(?P<heading>.+?)\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_CRITICAL = {"P0", "P1", "P2"}
_SEVERITIES = {"P0", "P1", "P2", "P3"}
_RISK = re.compile(r"\bR([0-3])\b")
_NO_FINDINGS = re.compile(
    r"^\s*no findings;\s*(?P<count>\d+)\s+counterexamples attempted\.?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class TaskSchema:
    required_files: tuple[str, ...]
    sections: dict[str, tuple[str, ...]]
    resolved_review_statuses: frozenset[str]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    task_dir: Path
    issues: tuple[ValidationIssue, ...]
    acceptance_ids: tuple[str, ...] = ()
    invariant_ids: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class EvidenceRecord:
    """One command result associated with a machine-readable gate identifier."""

    gate: str
    command: str
    exit_status: int
    result: str


def load_schema(path: Path = SCHEMA_PATH) -> TaskSchema:
    """Load and minimally validate the task-artifact TOML schema."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    required = tuple(str(name) for name in data["required_files"])
    sections = {
        str(name): tuple(str(section) for section in values)
        for name, values in data.get("sections", {}).items()
    }
    statuses = frozenset(str(value).strip().lower() for value in data["resolved_review_statuses"])
    if not required or not statuses:
        raise ValueError("task schema requires files and resolved review statuses")
    return TaskSchema(required, sections, statuses)


def _normal_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _sections(text: str) -> dict[str, str]:
    return {
        _normal_heading(match.group("heading")): match.group("body").strip()
        for match in _SECTION.finditer(text)
    }


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _traceability_rows(text: str) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for cells in _table_rows(text):
        requirement_cell = cells[0] if cells else ""
        ids = [
            match.upper()
            for match in (*_AC.findall(requirement_cell), *_INV.findall(requirement_cell))
        ]
        for requirement_id in ids:
            mapped[requirement_id] = cells
    return mapped


def _plain_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def evidence_records(text: str) -> tuple[EvidenceRecord, ...]:
    """Parse gate evidence from the four-column schema or its legacy three-column form."""

    rows = _table_rows(_sections(text).get("commands", ""))
    if not rows:
        return ()
    header = [_normal_heading(cell) for cell in rows[0]]
    modern = header[:4] == ["gate", "command", "exit status", "result"]
    legacy = header[:3] == ["command", "exit status", "result"]
    if not modern and not legacy:
        return ()

    records: list[EvidenceRecord] = []
    for cells in rows[1:]:
        if modern and len(cells) >= 4:
            gate, command, status, result = cells[:4]
        elif legacy and len(cells) >= 3:
            command, status, result = cells[:3]
            gate = command
        else:
            continue
        if re.fullmatch(r"-?\d+", status) is None:
            continue
        normalized_gate = _plain_cell(gate).casefold()
        normalized_command = _plain_cell(command)
        if not normalized_gate or not normalized_command or not result.strip():
            continue
        records.append(
            EvidenceRecord(
                normalized_gate,
                normalized_command,
                int(status),
                result.strip(),
            )
        )
    return tuple(records)


def _declared_risk(spec: str) -> str | None:
    match = _RISK.search(_sections(spec).get("risk class", ""))
    return f"R{match.group(1)}" if match is not None else None


def _review_ran(text: str) -> bool:
    findings = _sections(text).get("findings", "")
    has_finding = any(
        len(cells) >= 5
        and cells[1].upper() in _SEVERITIES
        and all(cell.strip() for cell in cells[:5])
        for cells in _table_rows(findings)
    )
    no_findings = _NO_FINDINGS.search(findings)
    return has_finding or (no_findings is not None and int(no_findings.group("count")) >= 1)


def _critical_review_issues(text: str, resolved: frozenset[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for cells in _table_rows(text):
        severities = {cell.upper() for cell in cells} & _CRITICAL
        if not severities:
            continue
        status = cells[-1].strip().casefold()
        for severity in sorted(severities):
            if status not in resolved:
                issues.append(
                    ValidationIssue(
                        "unresolved-review",
                        f"review.md has unresolved {severity} finding (status {cells[-1]!r})",
                    )
                )
    return issues


def validate_task_dir(task_dir: Path, schema_path: Path = SCHEMA_PATH) -> ValidationResult:
    """Validate one task directory; return every finding rather than stopping at the first."""
    schema = load_schema(schema_path)
    issues: list[ValidationIssue] = []
    content: dict[str, str] = {}
    for name in schema.required_files:
        path = task_dir / name
        if not path.is_file():
            issues.append(ValidationIssue("missing-file", f"missing required task file: {name}"))
            continue
        content[name] = path.read_text(encoding="utf-8")

    for name, required in schema.sections.items():
        if name not in content:
            continue
        sections = _sections(content[name])
        for section in required:
            body = sections.get(_normal_heading(section))
            if body is None:
                issues.append(
                    ValidationIssue(
                        "missing-section", f"{name} is missing required section: {section}"
                    )
                )
            elif not body:
                issues.append(
                    ValidationIssue("empty-section", f"{name} has an empty section: {section}")
                )

    spec = content.get("spec.md", "")
    acceptance = tuple(dict.fromkeys(match.upper() for match in _AC.findall(spec)))
    invariants = tuple(dict.fromkeys(match.upper() for match in _INV.findall(spec)))
    if spec and not acceptance:
        issues.append(ValidationIssue("missing-ac", "spec.md must define at least one AC-* ID"))
    if spec and not invariants:
        issues.append(ValidationIssue("missing-inv", "spec.md must define at least one INV-* ID"))

    test_plan = content.get("test-plan.md", "")
    mapped = _traceability_rows(test_plan)
    for requirement_id in (*acceptance, *invariants):
        row = mapped.get(requirement_id)
        if row is None:
            issues.append(
                ValidationIssue(
                    "unmapped-requirement",
                    f"{requirement_id} has no mapped test in test-plan.md",
                )
            )
        elif len(row) < 4 or not all(cell.strip() for cell in row[1:4]):
            issues.append(
                ValidationIssue(
                    "incomplete-trace",
                    f"{requirement_id} needs a test plus before-fix and after-fix results",
                )
            )

    review = content.get("review.md")
    if review is not None:
        issues.extend(_critical_review_issues(review, schema.resolved_review_statuses))
        if _declared_risk(spec) == "R3" and not _review_ran(review):
            issues.append(
                ValidationIssue(
                    "missing-adversarial-review",
                    "R3 review.md must record a finding row or 'No findings; N counterexamples "
                    "attempted' with N >= 1",
                )
            )

    evidence = content.get("evidence.md")
    if evidence is not None and not evidence_records(evidence):
        issues.append(
            ValidationIssue(
                "missing-command-evidence",
                "evidence.md must record gate, command, numeric exit status, and result",
            )
        )

    return ValidationResult(task_dir, tuple(issues), acceptance, invariants)


def validate_task(task_id: str, task_root: Path = TASK_ROOT) -> ValidationResult:
    """Validate ``.ai/tasks/<task_id>``."""
    return validate_task_dir(task_root / task_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an engineering task artifact set.")
    parser.add_argument("task_id", help="directory name under .ai/tasks")
    args = parser.parse_args(argv)
    result = validate_task(args.task_id)
    if result.ok:
        print(
            f"Task {args.task_id}: valid "
            f"({len(result.acceptance_ids)} AC, {len(result.invariant_ids)} INV)."
        )
        return 0
    print(f"Task {args.task_id}: NOT VALID")
    for issue in result.issues:
        print(f"  - [{issue.code}] {issue.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
