"""Shared run-book for the staged framework CLI.

A *research run* is one directory under ``reports/research/`` that flows through the four
stages; each stage reads the previous one's artifact from it and writes its own. This module
holds the run directory + the terminal UX (a stage banner, and the exact NEXT command to run,
with the run directory already filled in, so the operator never has to guess what to type).

Deliberately strategy-agnostic: it moves files and prints text, nothing else.
"""

from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import REPO_ROOT

# Render umlauts correctly on UTF-8 terminals (the Windows 11 default) instead of a cp1252 crash.
with contextlib.suppress(Exception):  # pragma: no cover - stream may not support reconfigure
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

_REPO_ROOT = REPO_ROOT
RESEARCH_ROOT = _REPO_ROOT / "reports" / "research"
TOTAL_STAGES = 4


@dataclass(frozen=True)
class RunDir:
    """One framework run's directory: where each stage reads and writes its artifacts."""

    path: Path

    @classmethod
    def create(cls) -> RunDir:
        p = RESEARCH_ROOT / f"run_{datetime.now():%Y%m%d_%H%M}"
        p.mkdir(parents=True, exist_ok=True)
        return cls(p)

    @classmethod
    def open(cls, path: str | Path) -> RunDir:
        p = Path(path)
        if not p.is_dir():
            raise SystemExit(f"run directory not found: {p}")
        return cls(p)

    def file(self, name: str) -> Path:
        return self.path / name

    def require(self, name: str, produced_by: str) -> Path:
        """The artifact ``name``, or a friendly error pointing at the stage that makes it."""
        f = self.file(name)
        if not f.exists():
            raise SystemExit(
                f"missing '{name}' in {self.path}\n  -> run the '{produced_by}' stage first."
            )
        return f

    def save_json(self, name: str, obj: dict[str, Any]) -> Path:
        f = self.file(name)
        f.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        return f

    def load_json(self, name: str) -> dict[str, Any]:
        return dict(json.loads(self.file(name).read_text(encoding="utf-8")))


def banner(step: int, title: str, run: RunDir) -> None:
    """Print the stage header (which stage, its question, which run directory)."""
    line = "=" * 72
    print(f"\n{line}\n  STUFE {step}/{TOTAL_STAGES} - {title}\n  Lauf: {run.path}\n{line}")


def cmd(module: str, *args: str) -> str:
    """The exact shell command that starts stage ``module`` with ``args``."""
    tail = (" " + " ".join(args)) if args else ""
    return f"uv run python -m research.stages.{module}{tail}"


def next_step(command: str, prompt: str) -> None:
    """Print the exact next command to run (with the run dir already filled in)."""
    line = "-" * 72
    print(f"\n{line}\n  NAECHSTER SCHRITT - {prompt}:\n\n    {command}\n{line}")


def finished(prompt: str = "Framework-Lauf komplett - Portfolio steht.") -> None:
    print(f"\n{'-' * 72}\n  [OK] {prompt}\n{'-' * 72}")
