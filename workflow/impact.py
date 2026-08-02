"""Conservative static test-impact analysis for a repository change set.

The report is a focused-test recommendation, never a completeness claim. Static Python imports,
``from`` imports, transitive importers, inheritance names, and a small TOML critical-dependency
map provide evidence; dynamic imports and configured uncertain edges are surfaced separately.
The full test suite remains mandatory before PR readiness.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from workflow.classify import REPO_ROOT, changed_paths, classify_paths, load_model, normalize

CRITICAL_MAP_PATH = REPO_ROOT / "workflow" / "policy" / "critical-dependencies.toml"
DEFAULT_OUTPUT = REPO_ROOT / "workflow" / "impact" / "test-map.json"
_SOURCE_ROOTS = ("core", "research", "live", "monitoring", "scripts", "tests")


@dataclass(frozen=True)
class CriticalEdge:
    source: str
    tests: tuple[str, ...]
    possibly_affected: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ModuleFacts:
    path: str
    module: str
    imports: frozenset[str]
    defined_classes: frozenset[str]
    base_names: frozenset[str]
    dynamic_targets: frozenset[str]
    has_unknown_dynamic_import: bool


@dataclass(frozen=True)
class ImpactReport:
    changed_paths: tuple[str, ...]
    changed_production_files: tuple[str, ...]
    direct_tests: tuple[str, ...]
    transitive_tests: tuple[str, ...]
    critical_escalations: tuple[str, ...]
    unknown_dynamic_edges: tuple[str, ...]
    possibly_affected_tests: tuple[str, ...]
    risk_class: str
    required_gates: tuple[str, ...]
    recommended_pytest_command: str
    completeness_note: str
    full_suite_mandatory: bool = True
    schema_version: int = 1


def _module_name(path: str) -> str:
    module = path.removesuffix(".py").replace("/", ".")
    return module.removesuffix(".__init__")


def _relative_module(current: str, level: int, target: str | None) -> str:
    package = current.split(".")[:-1]
    keep = max(0, len(package) - max(0, level - 1))
    base = package[:keep]
    if target:
        base.extend(target.split("."))
    return ".".join(base)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return _call_name(node).split(".")[-1]


def _facts(path: Path, root: Path, known: frozenset[str]) -> ModuleFacts | None:
    rel = path.relative_to(root).as_posix()
    module = _module_name(rel)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    imports: set[str] = set()
    classes: set[str] = set()
    bases: set[str] = set()
    dynamic_targets: set[str] = set()
    unknown_dynamic = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            parent = (
                _relative_module(module, node.level, node.module)
                if node.level
                else (node.module or "")
            )
            if parent:
                imports.add(parent)
            for alias in node.names:
                candidate = f"{parent}.{alias.name}" if parent else alias.name
                if candidate in known:
                    imports.add(candidate)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
            bases.update(name for base in node.bases if (name := _base_name(base)))
        elif isinstance(node, ast.Call) and _call_name(node.func) in {
            "importlib.import_module",
            "__import__",
        }:
            if (
                node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                dynamic_targets.add(node.args[0].value)
            else:
                unknown_dynamic = True
    return ModuleFacts(
        rel,
        module,
        frozenset(imports),
        frozenset(classes),
        frozenset(bases),
        frozenset(dynamic_targets),
        unknown_dynamic,
    )


def _python_files(root: Path) -> list[Path]:
    if root.resolve() != REPO_ROOT.resolve():
        return sorted(root.rglob("*.py"))
    files: list[Path] = []
    for name in _SOURCE_ROOTS:
        base = root / name
        if base.is_dir():
            files.extend(base.rglob("*.py"))
    return sorted(set(files))


def _load_critical(path: Path | None) -> tuple[CriticalEdge, ...]:
    if path is None or not path.is_file():
        return ()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return tuple(
        CriticalEdge(
            normalize(str(edge["source"])),
            tuple(normalize(str(value)) for value in edge.get("tests", [])),
            tuple(normalize(str(value)) for value in edge.get("possibly_affected", [])),
            str(edge["reason"]),
        )
        for edge in data.get("edges", [])
    )


def _imports_any(imports: Iterable[str], modules: set[str]) -> bool:
    return any(
        imported == module or imported.startswith(f"{module}.")
        for imported in imports
        for module in modules
    )


def changed_tests_exercise_targets(
    paths: Sequence[str],
    target_paths: Sequence[str],
    *,
    root: Path = REPO_ROOT,
    critical_map: Path | None = CRITICAL_MAP_PATH,
) -> bool:
    """Return whether changed tests directly or transitively exercise any target.

    An unreadable test, an unknown dynamic test import, or an unknown dynamic production edge
    fails closed because static analysis cannot prove that the target is untouched.
    """
    normalized_paths = {normalize(path) for path in paths}
    changed_tests = tuple(
        sorted(
            path for path in normalized_paths if path.startswith("tests/") and path.endswith(".py")
        )
    )
    targets = tuple(sorted({normalize(path) for path in target_paths}))
    if not changed_tests or not targets:
        return False

    python_files = _python_files(root)
    known = frozenset(_module_name(path.relative_to(root).as_posix()) for path in python_files)
    target_modules = {_module_name(path) for path in targets}
    for path in changed_tests:
        facts = _facts(root / path, root, known)
        if facts is None or facts.has_unknown_dynamic_import:
            return True
        if _imports_any(facts.imports | facts.dynamic_targets, target_modules):
            return True

    report = analyze_impact(targets, root=root, critical_map=critical_map)
    if report.unknown_dynamic_edges:
        return True
    return bool(set(changed_tests) & set(report.transitive_tests))


def analyze_impact(
    paths: Sequence[str],
    *,
    root: Path = REPO_ROOT,
    critical_map: Path | None = CRITICAL_MAP_PATH,
) -> ImpactReport:
    """Return a conservative test-impact report for explicit repository-relative paths."""
    changed = tuple(sorted({normalize(path) for path in paths}))
    python_files = _python_files(root)
    known = frozenset(_module_name(path.relative_to(root).as_posix()) for path in python_files)
    all_facts = tuple(
        facts for path in python_files if (facts := _facts(path, root, known)) is not None
    )
    by_module = {facts.module: facts for facts in all_facts}
    changed_python = {path for path in changed if path.endswith(".py")}
    changed_modules = {_module_name(path) for path in changed_python}
    changed_production = tuple(
        sorted(path for path in changed if not path.startswith("tests/") and path.endswith(".py"))
    )
    changed_classes = {
        name
        for module in changed_modules
        for name in (by_module[module].defined_classes if module in by_module else ())
    }

    direct: set[str] = {
        path for path in changed if path.startswith("tests/") and path.endswith(".py")
    }
    test_facts = [facts for facts in all_facts if facts.path.startswith("tests/")]
    production_facts = [facts for facts in all_facts if not facts.path.startswith("tests/")]
    for facts in test_facts:
        if _imports_any(facts.imports, changed_modules) or facts.base_names & changed_classes:
            direct.add(facts.path)

    affected_modules = set(changed_modules)
    changed_flag = True
    while changed_flag:
        changed_flag = False
        for facts in production_facts:
            if facts.module in affected_modules:
                continue
            if _imports_any(facts.imports, affected_modules):
                affected_modules.add(facts.module)
                changed_flag = True
    transitive = {
        facts.path
        for facts in test_facts
        if facts.path not in direct and _imports_any(facts.imports, affected_modules)
    }

    unknown_dynamic: set[str] = set()
    dynamic_modules: set[str] = set()
    for facts in production_facts:
        if facts.dynamic_targets & changed_modules or (
            facts.has_unknown_dynamic_import and changed_modules
        ):
            unknown_dynamic.add(facts.path)
            dynamic_modules.add(facts.module)
    possibly = {facts.path for facts in test_facts if _imports_any(facts.imports, dynamic_modules)}

    escalations: list[str] = []
    for edge in _load_critical(critical_map):
        if edge.source not in changed:
            continue
        direct.update(edge.tests)
        possibly.update(edge.possibly_affected)
        escalations.append(f"{edge.source}: {edge.reason}")

    possibly.difference_update(direct)
    possibly.difference_update(transitive)
    focused = sorted(direct | transitive | possibly)
    command = "uv run pytest -q" + (" " + " ".join(focused) if focused else "")
    classification = classify_paths(changed, load_model())
    note = (
        "Static and configured impact analysis is not complete; dynamic runtime relationships may "
        "remain. The full pytest suite remains mandatory before PR readiness."
    )
    return ImpactReport(
        changed,
        changed_production,
        tuple(sorted(direct)),
        tuple(sorted(transitive)),
        tuple(escalations),
        tuple(sorted(unknown_dynamic)),
        tuple(sorted(possibly)),
        classification.risk_class,
        load_model().required_gates(classification.risk_class),
        command,
        note,
    )


def write_test_map(report: ImpactReport, output: Path = DEFAULT_OUTPUT) -> None:
    """Write the stable machine-readable impact artifact."""
    output.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = asdict(report)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_check_command(report: ImpactReport, *, root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Build the changed-Python-only formatter command used by ``check-fast``."""

    python_paths = tuple(
        path for path in report.changed_paths if path.endswith(".py") and (root / path).is_file()
    )
    if not python_paths:
        return ()
    return ("uv", "run", "ruff", "format", "--check", *python_paths)


def _print_group(title: str, values: Sequence[str]) -> None:
    print(f"\n{title}:")
    if values:
        for value in values:
            print(f"  - {value}")
    else:
        print("  - none discovered")


def print_report(report: ImpactReport) -> None:
    """Print the human-readable impact report required by ``just impact``."""
    print(f"Risk class: {report.risk_class}")
    _print_group("Changed production files", report.changed_production_files)
    _print_group("Directly related tests", report.direct_tests)
    _print_group("Transitively relevant tests", report.transitive_tests)
    _print_group("Critical-path escalation", report.critical_escalations)
    _print_group("Unknown/dynamic edges", report.unknown_dynamic_edges)
    _print_group("Possibly affected tests", report.possibly_affected_tests)
    print(f"\nRecommended focused command:\n  {report.recommended_pytest_command}")
    print(f"\nNOTE: {report.completeness_note}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend tests affected by changed files.")
    parser.add_argument("paths", nargs="*", help="explicit changed paths")
    parser.add_argument("--base", default="origin/main", help="git base ref when paths are omitted")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-format", action="store_true")
    parser.add_argument("--run-focused", action="store_true")
    args = parser.parse_args(argv)
    paths = list(args.paths) or changed_paths(args.base)
    report = analyze_impact(paths)
    write_test_map(report, args.output)
    print_report(report)
    if args.check_format:
        command = format_check_command(report)
        if command:
            completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
            if completed.returncode != 0:
                return completed.returncode
        else:
            print("\nNo changed Python files require a format check.")
    if args.run_focused:
        focused = [
            *report.direct_tests,
            *report.transitive_tests,
            *report.possibly_affected_tests,
        ]
        if focused:
            completed = subprocess.run(
                ["uv", "run", "pytest", "-q", *sorted(set(focused))], cwd=REPO_ROOT, check=False
            )
            return completed.returncode
        print("\nNo focused tests were discovered; the full suite is still mandatory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
