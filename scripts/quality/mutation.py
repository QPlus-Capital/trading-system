"""Focused mutation testing with a committed, fail-closed TOML baseline.

The changed-file fast scope delegates both range discovery and risk classification to
``scripts.quality.classify``. Mutmut is only the execution engine; this module owns the narrow
target policy, machine-readable result, and survivor ratchet.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.quality.classify import (
    MODEL_PATH,
    Model,
    changed_paths,
    classify_path,
    load_model,
    normalize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / ".ai" / "quality" / "mutation.toml"
BASELINE_PATH = REPO_ROOT / ".ai" / "quality" / "mutation-baseline.toml"
RESULT_ROOT = REPO_ROOT / ".ai" / "mutation"
_RESULT_LINE = re.compile(r"^\s*(?P<name>\S+):\s+(?P<status>[a-z ]+)\s*$")
_STATUS_FIELDS = {
    "killed": "killed",
    "survived": "survived",
    "no tests": "no_tests",
    "skipped": "skipped",
    "suspicious": "suspicious",
    "timeout": "timeout",
    "not checked": "not_checked",
    "check was interrupted by user": "interrupted",
    "segfault": "segfault",
    "caught by type check": "caught_by_type_check",
}


@dataclass(frozen=True)
class MutationTarget:
    """One explicitly bounded production mutation target."""

    id: str
    path: str
    mutant_patterns: tuple[str, ...]


@dataclass(frozen=True)
class MutationPolicy:
    """Pinned tool and critical target set from the authoritative TOML policy."""

    version: int
    tool: str
    tool_version: str
    targets: tuple[MutationTarget, ...]


@dataclass(frozen=True)
class MutationSummary:
    """Counts whose sum is the complete selected mutation set."""

    total: int
    killed: int
    survived: int
    no_tests: int
    skipped: int
    suspicious: int
    timeout: int
    not_checked: int
    interrupted: int
    segfault: int
    caught_by_type_check: int

    @property
    def score(self) -> float:
        """Killed fraction of mutants that produced a semantic test outcome."""
        denominator = self.killed + self.survived
        return self.killed / denominator if denominator else 0.0


@dataclass(frozen=True)
class MutationReport:
    """Mutation outcomes for one named scope."""

    scope: str
    targets: tuple[str, ...]
    mutants: Mapping[str, str]

    @property
    def summary(self) -> MutationSummary:
        """Count every supported status, retaining unknowns as a hard error in validation."""
        counts = Counter(_STATUS_FIELDS.get(status, "unknown") for status in self.mutants.values())
        return MutationSummary(
            total=len(self.mutants),
            **{field: counts[field] for field in _STATUS_FIELDS.values()},
        )


@dataclass(frozen=True)
class Survivor:
    """A reviewed surviving mutant and the reason it is accepted."""

    name: str
    classification: str
    reason: str


@dataclass(frozen=True)
class MutationBaseline:
    """Committed critical-scope ratchet."""

    version: int
    tool: str
    tool_version: str
    change_explanation: str
    targets: tuple[str, ...]
    summary: MutationSummary
    survivors: tuple[Survivor, ...]


def load_policy(path: Path = POLICY_PATH) -> MutationPolicy:
    """Load and validate the mutation target policy with stdlib TOML."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    targets = tuple(
        MutationTarget(
            str(item["id"]),
            normalize(str(item["path"])),
            tuple(str(pattern) for pattern in item["mutant_patterns"]),
        )
        for item in data["targets"]
    )
    if int(data["version"]) != 1 or not targets:
        raise ValueError("mutation policy version must be 1 and define targets")
    if len({target.id for target in targets}) != len(targets):
        raise ValueError("mutation target IDs must be unique")
    if len({target.path for target in targets}) != len(targets):
        raise ValueError("mutation target paths must be unique")
    for target in targets:
        if not (REPO_ROOT / target.path).is_file():
            raise ValueError(f"mutation target does not exist: {target.path}")
        if not target.mutant_patterns:
            raise ValueError(f"mutation target needs at least one function pattern: {target.id}")
    return MutationPolicy(
        1,
        str(data["tool"]["name"]),
        str(data["tool"]["version"]),
        targets,
    )


def _as_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer, got {value!r}")
    return value


def _summary(data: Mapping[str, object]) -> MutationSummary:
    return MutationSummary(
        total=_as_int(data["total"], "total"),
        killed=_as_int(data["killed"], "killed"),
        survived=_as_int(data["survived"], "survived"),
        no_tests=_as_int(data["no_tests"], "no_tests"),
        skipped=_as_int(data["skipped"], "skipped"),
        suspicious=_as_int(data["suspicious"], "suspicious"),
        timeout=_as_int(data["timeout"], "timeout"),
        not_checked=_as_int(data["not_checked"], "not_checked"),
        interrupted=_as_int(data["interrupted"], "interrupted"),
        segfault=_as_int(data["segfault"], "segfault"),
        caught_by_type_check=_as_int(data["caught_by_type_check"], "caught_by_type_check"),
    )


def load_baseline(path: Path = BASELINE_PATH) -> MutationBaseline:
    """Load the committed critical result and its reviewed survivor explanations."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        survivors = tuple(
            Survivor(
                str(name),
                str(group["classification"]),
                str(group["reason"]),
            )
            for group in data.get("survivor_groups", [])
            for name in group["names"]
        )
    except KeyError as exc:
        raise ValueError("every baseline survivor needs a classification") from exc
    baseline = MutationBaseline(
        version=int(data["version"]),
        tool=str(data["tool"]),
        tool_version=str(data["tool_version"]),
        change_explanation=str(data["change_explanation"]),
        targets=tuple(str(value) for value in data["targets"]),
        summary=_summary(data["summary"]),
        survivors=survivors,
    )
    if baseline.version != 1 or not baseline.change_explanation.strip():
        raise ValueError("mutation baseline needs version 1 and a non-empty change explanation")
    accounted = sum(getattr(baseline.summary, field) for field in _STATUS_FIELDS.values())
    if accounted != baseline.summary.total:
        raise ValueError(
            f"mutation baseline counts sum to {accounted}, not total {baseline.summary.total}"
        )
    if baseline.summary.survived != len(survivors):
        raise ValueError("every baseline survivor needs exactly one named explanation")
    if len({item.name for item in survivors}) != len(survivors):
        raise ValueError("baseline survivor names must be unique")
    if any(not item.reason.strip() for item in survivors):
        raise ValueError("every baseline survivor needs a non-empty explanation")
    classifications = {"equivalent", "irrelevant", "meaningful"}
    if any(item.classification not in classifications for item in survivors):
        raise ValueError("survivor classification must be equivalent, irrelevant, or meaningful")
    return baseline


def ensure_supported_platform(system: str | None = None) -> None:
    """Fail closed where Mutmut cannot fork; native Windows is explicitly unsupported."""
    current = platform.system() if system is None else system
    if current != "Linux":
        raise RuntimeError(
            f"Mutmut 3.5.0 requires fork and cannot run on {current}; run the dedicated Linux CI "
            "job (native Windows remains covered by just check)."
        )


def select_fast_targets(
    paths: Sequence[str], policy: MutationPolicy, risk_model: Model
) -> list[MutationTarget]:
    """Select changed configured targets only after the production classifier confirms R3."""
    changed = {normalize(path) for path in paths}
    return [
        target
        for target in policy.targets
        if target.path in changed and classify_path(target.path, risk_model).risk_class == "R3"
    ]


def parse_mutmut_results(text: str) -> dict[str, str]:
    """Parse Mutmut's stable ``name: status`` result listing."""
    results: dict[str, str] = {}
    for line in text.splitlines():
        match = _RESULT_LINE.fullmatch(line)
        if match is None:
            continue
        status = match.group("status")
        if status not in _STATUS_FIELDS:
            raise ValueError(f"unknown Mutmut status {status!r}")
        results[match.group("name")] = status
    if not results:
        raise ValueError("Mutmut produced no parseable mutation results")
    return results


def _health_issues(report: MutationReport) -> list[str]:
    summary = report.summary
    issues: list[str] = []
    for field in (
        "no_tests",
        "skipped",
        "suspicious",
        "timeout",
        "not_checked",
        "interrupted",
        "segfault",
        "caught_by_type_check",
    ):
        value = getattr(summary, field)
        if value:
            issues.append(f"{value} selected mutants ended as {field.replace('_', ' ')}")
    return issues


def check_baseline(report: MutationReport, baseline: MutationBaseline) -> list[str]:
    """Return every critical baseline regression; an empty list is the only pass."""
    issues = _health_issues(report)
    if report.scope != "critical":
        issues.append(f"baseline applies to critical scope, not {report.scope!r}")
    if report.targets != baseline.targets:
        issues.append(
            f"critical targets changed: expected {baseline.targets!r}, observed {report.targets!r}"
        )
    if report.summary.total != baseline.summary.total:
        issues.append(
            f"mutation total changed: expected {baseline.summary.total}, "
            f"observed {report.summary.total}; update the baseline with an explanation"
        )
    allowed = {item.name for item in baseline.survivors}
    observed = {name for name, status in report.mutants.items() if status == "survived"}
    unexpected = sorted(observed - allowed)
    missing = sorted(allowed - observed)
    if unexpected:
        issues.append(f"unexplained surviving mutants: {unexpected}")
    if missing:
        issues.append(
            f"baseline survivor(s) are now killed and the ratchet must be tightened: {missing}"
        )
    if report.summary.score + 1e-12 < baseline.summary.score:
        issues.append(
            f"mutation score regressed: {report.summary.score:.4f} < {baseline.summary.score:.4f}"
        )
    return issues


def _check_fast(report: MutationReport, baseline: MutationBaseline) -> list[str]:
    issues = _health_issues(report)
    allowed = {item.name for item in baseline.survivors}
    unexpected = sorted(
        name
        for name, status in report.mutants.items()
        if status == "survived" and name not in allowed
    )
    if unexpected:
        issues.append(f"unexplained surviving mutants: {unexpected}")
    return issues


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_report(report: MutationReport, path: Path) -> None:
    """Write the current result as deterministic TOML for CI artifact retention."""
    summary = report.summary
    lines = [
        "version = 1",
        f"scope = {_quote(report.scope)}",
        "targets = [" + ", ".join(_quote(value) for value in report.targets) + "]",
        "",
        "[summary]",
    ]
    for field in MutationSummary.__dataclass_fields__:
        lines.append(f"{field} = {getattr(summary, field)}")
    lines.extend(("", "[mutants]"))
    for name, status in sorted(report.mutants.items()):
        lines.append(f"{_quote(name)} = {_quote(status)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_mutmut_config(policy: MutationPolicy) -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    configured = {normalize(str(path)) for path in data["tool"]["mutmut"]["paths_to_mutate"]}
    expected = {target.path for target in policy.targets}
    if configured != expected:
        raise RuntimeError(
            f"[tool.mutmut].paths_to_mutate drifted from mutation.toml: "
            f"expected {sorted(expected)}, observed {sorted(configured)}"
        )


def mutation_executable(tool: str, python: str, system: str) -> str:
    """Resolve the console script beside the overlay Python, never ``python -m mutmut``.

    Mutmut's trampolines import ``mutmut.__main__``. Launching that module as ``__main__`` creates
    a second module identity when the trampoline imports it, rerunning multiprocessing setup and
    failing on Linux before any mutant executes.
    """
    name = f"{tool}.exe" if system == "Windows" else tool
    candidate = Path(python).with_name(name)
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(name)
    if found is None:
        raise RuntimeError(f"cannot find the {tool!r} console script beside {python!r} or on PATH")
    return found


def all_results_command(command: Sequence[str]) -> list[str]:
    """The Mutmut 3.5 CLI requires an explicit boolean value for ``--all``."""
    return [*command, "results", "--all", "true"]


def _tool_command(policy: MutationPolicy) -> list[str]:
    installed = importlib.metadata.version(policy.tool)
    if installed != policy.tool_version:
        raise RuntimeError(
            f"mutation policy requires {policy.tool} {policy.tool_version}, found {installed}"
        )
    return [mutation_executable(policy.tool, sys.executable, platform.system())]


def run(scope: str, base: str, output: Path | None = None) -> int:
    """Run a fresh focused mutation scope, write TOML evidence, and enforce the ratchet."""
    ensure_supported_platform()
    policy = load_policy()
    _validate_mutmut_config(policy)
    if scope == "fast":
        targets = select_fast_targets(changed_paths(base), policy, load_model(MODEL_PATH))
    elif scope == "critical":
        targets = list(policy.targets)
    else:
        raise ValueError(f"unknown mutation scope {scope!r}")
    if not targets:
        print("No configured critical module changed; mutation-fast has no target.")
        return 0

    work = (REPO_ROOT / "mutants").resolve()
    if work.parent != REPO_ROOT.resolve():
        raise RuntimeError(f"refusing to clean mutation work directory outside the repo: {work}")
    if work.exists():
        shutil.rmtree(work)

    command = _tool_command(policy)
    patterns = [pattern for target in targets for pattern in target.mutant_patterns]
    subprocess.run([*command, "run", *patterns], cwd=REPO_ROOT, check=True)
    listed = subprocess.run(
        all_results_command(command),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    all_results = parse_mutmut_results(listed.stdout)
    selected = {
        name: status
        for name, status in all_results.items()
        if any(
            fnmatch.fnmatchcase(name, pattern)
            for target in targets
            for pattern in target.mutant_patterns
        )
    }
    report = MutationReport(scope, tuple(target.id for target in targets), selected)
    result_path = output or RESULT_ROOT / f"{scope}.toml"
    write_report(report, result_path)
    baseline = load_baseline()
    issues = (
        check_baseline(report, baseline) if scope == "critical" else _check_fast(report, baseline)
    )
    print(
        f"Mutation {scope}: {report.summary.killed}/{report.summary.total} killed, "
        f"{report.summary.survived} survived; report {result_path}"
    )
    if issues:
        print("Mutation gate FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print("Mutation gate passed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run focused, baseline-ratcheted mutation tests.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--scope", choices=("fast", "critical"), required=True)
    run_parser.add_argument("--base", default="origin/main")
    run_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    return run(args.scope, args.base, args.output)


if __name__ == "__main__":
    sys.exit(main())
