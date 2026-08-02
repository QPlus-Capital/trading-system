"""Run exactly the gates this branch's risk class requires, and report them as evidence.

The risk class decides which gates are mandatory; this runs them in contract order and prints the
table that goes into the pull request. Nothing here decides policy -- the class comes from the
classifier and the gate list from ``workflow/workflow.toml``, so a gate cannot be added or dropped
by editing this file.

A gate the platform cannot run is reported as ``deferred``, never as passed. The mutation gate needs
``fork``, which Windows does not have; until the development platform moves to macOS (issue #150) it
runs in CI instead. Reporting that as green would be the report saying the numbers held when nothing
measured them.

CLI::

    uv run python -m workflow.gates                 # branch vs origin/main
    uv run python -m workflow.gates --base HEAD~1
    uv run python -m workflow.gates --risk R2       # force a class
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from workflow.classify import (
    CLASSES,
    MODEL_PATH,
    REPO_ROOT,
    changed_paths,
    classify_paths,
    load_model,
)

_PLATFORMS = {"win32": "windows", "darwin": "darwin", "linux": "linux"}


@dataclass(frozen=True)
class GateResult:
    """One gate, the command that ran it, and what it returned."""

    name: str
    command: str
    exit_status: int | None
    seconds: float
    detail: str

    @property
    def deferred(self) -> bool:
        return self.exit_status is None

    @property
    def passed(self) -> bool:
        return self.exit_status == 0


def load_gate_commands(path: Path = MODEL_PATH) -> dict[str, dict[str, object]]:
    return dict(tomllib.loads(path.read_text(encoding="utf-8"))["gates"])


def _runnable_here(spec: dict[str, object]) -> bool:
    allowed = spec.get("local_platforms")
    if not isinstance(allowed, list):
        return True
    return _PLATFORMS.get(sys.platform, sys.platform) in {str(item) for item in allowed}


def run_gate(name: str, spec: dict[str, object], *, root: Path = REPO_ROOT) -> GateResult:
    command = str(spec["command"])
    if not _runnable_here(spec):
        return GateResult(name, command, None, 0.0, f"deferred: not runnable on {sys.platform}")
    started = time.monotonic()
    completed = subprocess.run(command.split(), cwd=root, check=False)
    elapsed = time.monotonic() - started
    detail = "green" if completed.returncode == 0 else f"FAILED (exit {completed.returncode})"
    return GateResult(name, command, completed.returncode, elapsed, detail)


def required_gates(
    paths: Sequence[str], declared: str | None = None
) -> tuple[str, tuple[str, ...]]:
    """The effective risk class and the gates it requires, cumulative through the lower classes."""

    model = load_model()
    risk = classify_paths(paths, model).risk_class
    if declared is not None and CLASSES.index(declared) > CLASSES.index(risk):
        risk = declared
    return risk, model.required_gates(risk)


def run(paths: Sequence[str], declared: str | None = None) -> tuple[str, list[GateResult]]:
    """Run every required gate in contract order, stopping at the first real failure."""

    risk, gates = required_gates(paths, declared)
    commands = load_gate_commands()
    results: list[GateResult] = []
    for name in gates:
        spec = commands.get(name)
        if spec is None:
            results.append(GateResult(name, "(undefined)", 1, 0.0, "no command defined"))
            break
        result = run_gate(name, spec)
        results.append(result)
        if result.exit_status not in (0, None):
            break
    return risk, results


def render(risk: str, results: Sequence[GateResult]) -> str:
    """The gates table, in the shape the pull-request body expects."""

    lines = [
        f"Risk class: {risk}",
        "",
        "| Gate | Command | Exit | Result |",
        "|---|---|---|---|",
    ]
    for result in results:
        status = "-" if result.deferred else str(result.exit_status)
        lines.append(f"| `{result.name}` | `{result.command}` | {status} | {result.detail} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the gates this change's risk class requires.")
    parser.add_argument("--base", default="origin/main", help="base ref for the diff")
    parser.add_argument("--risk", choices=CLASSES, help="raise the class above the classifier")
    args = parser.parse_args(argv)

    paths = changed_paths(args.base)
    if not paths:
        print("No changed paths; nothing to gate.")
        return 0

    risk, results = run(paths, args.risk)
    print()
    print(render(risk, results))

    failed = [result for result in results if result.exit_status not in (0, None)]
    deferred = [result for result in results if result.deferred]
    if failed:
        print(f"\nNOT READY: {failed[0].name} failed.")
        return 1
    if deferred:
        names = ", ".join(result.name for result in deferred)
        print(f"\nGREEN, with {names} deferred to CI.")
        return 0
    print("\nGREEN: every required gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
