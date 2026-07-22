"""Evaluate whether a pull request satisfies its risk-class workflow gates."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.quality.classify import (
    REPO_ROOT,
    Classification,
    changed_paths,
    classify_paths,
    load_model,
)
from scripts.quality.validate_task import discover_task_id, evidence_records, validate_task_dir

_RISK_RE = re.compile(r"\bR([0-3])\b")
_HEAD_RE = re.compile(r"^HEAD:\s*(\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ReadinessCheck:
    """One readiness assertion and its human-readable result."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ReadinessResult:
    """Complete result of evaluating one task against a change set."""

    ready: bool
    classification: Classification
    risk_class: str
    required_gates: tuple[str, ...]
    declared_risk: str | None
    checks: tuple[ReadinessCheck, ...]


def _declared_risk(spec_path: Path) -> str | None:
    if not spec_path.is_file():
        return None
    headings = spec_path.read_text(encoding="utf-8")
    section = re.search(
        r"^## Risk class\s*$\n(?P<body>.*?)(?=^## |\Z)",
        headings,
        flags=re.MULTILINE | re.DOTALL,
    )
    if section is None:
        return None
    match = _RISK_RE.search(section.group("body"))
    return f"R{match.group(1)}" if match is not None else None


def _recorded_head(evidence_path: Path) -> str | None:
    if not evidence_path.is_file():
        return None
    match = _HEAD_RE.search(evidence_path.read_text(encoding="utf-8"))
    return match.group(1) if match is not None else None


def _git_output(args: Sequence[str], *, root: Path) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def evidence_is_current(
    evidence_path: Path,
    head_sha: str,
    *,
    root: Path = REPO_ROOT,
) -> tuple[bool, str]:
    """Accept evidence for HEAD or an ancestor followed only by its evidence file."""

    recorded = _recorded_head(evidence_path)
    if recorded is None:
        return False, "evidence.md must contain a 'HEAD: <sha>' line"
    if recorded == head_sha:
        return True, f"evidence covers HEAD {head_sha}"

    ancestor = _git_output(["merge-base", "--is-ancestor", recorded, head_sha], root=root)
    if ancestor is None:
        return False, f"stale evidence covers {recorded}, not HEAD {head_sha}"

    changed = _git_output(["diff", "--name-only", f"{recorded}..{head_sha}"], root=root)
    if changed is None:
        return False, f"could not compare evidence SHA {recorded} with HEAD {head_sha}"
    try:
        evidence_relative = evidence_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False, "evidence file is outside the repository"
    later_paths = {line.strip().replace("\\", "/") for line in changed.splitlines() if line.strip()}
    if later_paths == {evidence_relative}:
        return True, f"evidence covers {recorded}; only {evidence_relative} changed afterward"
    return False, (
        f"evidence covers {recorded}, but later changes are not evidence-only: "
        f"{', '.join(sorted(later_paths)) or '(none)'}"
    )


def assess_readiness(
    task_dir: Path,
    changed: Sequence[str],
    head_sha: str,
    *,
    root: Path = REPO_ROOT,
) -> ReadinessResult:
    """Run task, risk, traceability, review, and evidence gates."""

    model = load_model()
    classification = classify_paths(changed, model)
    validation = validate_task_dir(task_dir)
    declared = _declared_risk(task_dir / "spec.md")
    risk_class = classification.risk_class
    if declared is not None and int(declared[1]) > int(risk_class[1]):
        risk_class = declared
    required_gates = model.required_gates(risk_class)

    checks: list[ReadinessCheck] = [
        ReadinessCheck(
            "task-artifacts",
            validation.ok,
            "all task artifacts are valid"
            if validation.ok
            else "; ".join(issue.message for issue in validation.issues),
        )
    ]

    if declared is None:
        checks.append(ReadinessCheck("risk-class", False, "spec.md has no declared risk class"))
    elif int(declared[1]) < int(classification.risk_class[1]):
        checks.append(
            ReadinessCheck(
                "risk-class",
                False,
                f"declared risk {declared} understates classifier result "
                f"{classification.risk_class}",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "risk-class",
                True,
                f"declared risk {declared}; classifier result {classification.risk_class}",
            )
        )

    evidence_path = task_dir / "evidence.md"
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.is_file() else ""
    records = evidence_records(evidence_text)
    missing_gates = [
        gate for gate in required_gates if not any(record.gate == gate for record in records)
    ]
    failed_gates = {
        gate: tuple(record.exit_status for record in records if record.gate == gate)
        for gate in required_gates
        if any(record.gate == gate and record.exit_status != 0 for record in records)
    }
    gate_details: list[str] = []
    if missing_gates:
        gate_details.append(f"missing required gates: {', '.join(missing_gates)}")
    if failed_gates:
        failures = ", ".join(
            f"{gate} ({'/'.join(str(status) for status in statuses)})"
            for gate, statuses in failed_gates.items()
        )
        gate_details.append(f"required gates with non-zero exit: {failures}")
    gates_ok = not gate_details
    checks.append(
        ReadinessCheck(
            "required-gates",
            gates_ok,
            f"all {len(required_gates)} required gates have exit 0"
            if gates_ok
            else "; ".join(gate_details),
        )
    )

    evidence_ok, evidence_detail = evidence_is_current(evidence_path, head_sha, root=root)
    checks.append(ReadinessCheck("evidence-current", evidence_ok, evidence_detail))

    return ReadinessResult(
        ready=all(check.ok for check in checks),
        classification=classification,
        risk_class=risk_class,
        required_gates=required_gates,
        declared_risk=declared,
        checks=tuple(checks),
    )


def _head_sha(root: Path) -> str:
    head = _git_output(["rev-parse", "HEAD"], root=root)
    if head is None:
        raise RuntimeError("could not resolve git HEAD")
    return head


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id", nargs="?", help="task directory name under .ai/tasks")
    parser.add_argument(
        "--base",
        default="origin/main",
        help="git base ref used for changed-path classification (default: origin/main)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run PR readiness checks and return non-zero when any mandatory gate fails."""

    args = _parser().parse_args(argv)
    paths = changed_paths(args.base)
    task_id = args.task_id or discover_task_id(paths)
    if task_id is None:
        print(
            "NOT READY: provide a task ID or change files in exactly one .ai/tasks/<id>/ directory"
        )
        return 1

    result = assess_readiness(REPO_ROOT / ".ai" / "tasks" / task_id, paths, _head_sha(REPO_ROOT))
    print(f"Risk: {result.risk_class}")
    print("Reasons:")
    for reason in result.classification.reasons:
        print(f"  - {reason}")
    print(f"Required gates: {', '.join(result.required_gates) or '(none)'}")
    print("Readiness checks:")
    for check in result.checks:
        marker = "PASS" if check.ok else "FAIL"
        print(f"  [{marker}] {check.name}: {check.detail}")
    print("READY" if result.ready else "NOT READY")
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
