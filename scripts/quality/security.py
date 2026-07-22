"""Fail-closed secret scanning backed by detect-secrets and a TOML policy.

The command scans Git-tracked files by default. Findings expose only the path, line number, and
detector type; a credential value or file content is never rendered.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from detect_secrets.core.scan import scan_file
from detect_secrets.settings import default_settings

from scripts.quality.classify import REPO_ROOT

POLICY_PATH = REPO_ROOT / ".ai" / "quality" / "security.toml"


@dataclass(frozen=True)
class SecurityPolicy:
    """Repository-owned scanner scope and static-analysis configuration."""

    exclude_globs: tuple[str, ...]
    static_roots: tuple[str, ...]
    static_ruff_ignores: tuple[str, ...]


@dataclass(frozen=True)
class SecretFinding:
    """A deliberately redacted detect-secrets finding."""

    path: str
    line_number: int
    detector: str


@dataclass(frozen=True)
class SecretScanResult:
    """Secret scan outcome with safe rendering for logs and hooks."""

    findings: tuple[SecretFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def render(self) -> str:
        if self.ok:
            return "Secret scan passed: no findings."
        lines = [f"Secret scan blocked: {len(self.findings)} finding(s)."]
        lines.extend(
            f"- {finding.path}:{finding.line_number} ({finding.detector})"
            for finding in self.findings
        )
        return "\n".join(lines)


def load_security_policy(path: Path = POLICY_PATH) -> SecurityPolicy:
    """Load and validate the repository security policy."""

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("security policy version must be 1")
    roots = tuple(str(value) for value in data.get("static_roots", ()))
    ignores = tuple(str(value) for value in data.get("static_ruff_ignores", ()))
    if not roots:
        raise ValueError("security policy requires static_roots")
    return SecurityPolicy(
        tuple(str(value) for value in data.get("exclude_globs", ())),
        roots,
        ignores,
    )


def _display_path(path: Path, *, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _excluded(path: Path, policy: SecurityPolicy, *, root: Path) -> bool:
    display = _display_path(path, root=root)
    return any(fnmatch.fnmatchcase(display, pattern) for pattern in policy.exclude_globs)


def tracked_paths(*, root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Return every Git-tracked file, failing rather than silently scanning an empty scope."""

    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    paths = tuple(root / raw.decode("utf-8") for raw in completed.stdout.split(b"\0") if raw)
    if not paths:
        raise RuntimeError("secret scan found no Git-tracked files")
    return paths


def scan_secret_paths(
    paths: Sequence[Path],
    policy: SecurityPolicy,
    *,
    root: Path = REPO_ROOT,
) -> SecretScanResult:
    """Scan text paths with all default detect-secrets plugins and redact every result."""

    findings: list[SecretFinding] = []
    with default_settings():
        for path in paths:
            if not path.is_file() or _excluded(path, policy, root=root):
                continue
            for secret in scan_file(str(path)):
                findings.append(
                    SecretFinding(
                        _display_path(path, root=root),
                        secret.line_number,
                        secret.type,
                    )
                )
    return SecretScanResult(tuple(findings))


def main(argv: Sequence[str] | None = None) -> int:
    """Scan explicit paths or every tracked file; return non-zero on any finding or scan error."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        policy = load_security_policy()
        paths = tuple(args.paths) or tracked_paths()
        result = scan_secret_paths(paths, policy)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Secret scan failed closed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(result.render())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
