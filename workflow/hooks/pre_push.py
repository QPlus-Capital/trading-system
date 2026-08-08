"""Fail-closed decisions for updates sent to ``main`` by Git's pre-push hook."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from workflow.classify import REPO_ROOT, classify_paths, load_model
from workflow.hooks.decisions import Decision

_MAIN_REF = "refs/heads/main"
_OBJECT_ID = re.compile(r"[0-9a-fA-F]{40,64}")


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def _git(args: Sequence[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _valid_object_id(value: str) -> bool:
    return _OBJECT_ID.fullmatch(value) is not None


def evaluate_update(
    local_sha: str,
    remote_sha: str,
    remote_ref: str,
    *,
    root: Path = REPO_ROOT,
) -> Decision:
    """Allow one ref update unless it violates the direct-``main`` policy."""

    if remote_ref != _MAIN_REF:
        return Decision(True)
    if not _valid_object_id(local_sha) or not _valid_object_id(remote_sha):
        return _deny("Blocked: the push hook could not verify the main ref update.")
    if set(local_sha) == {"0"}:
        return _deny("Blocked: deleting main is prohibited.")
    if set(remote_sha) == {"0"}:
        return _deny("Blocked: the push hook cannot classify creation of main.")

    ancestry = _git(["merge-base", "--is-ancestor", remote_sha, local_sha], root)
    if ancestry.returncode == 1:
        return _deny("Blocked: rewriting main is prohibited.")
    if ancestry.returncode != 0:
        return _deny("Blocked: the push hook could not verify main's ancestry.")

    changed = _git(["diff", "--no-renames", "--name-only", f"{remote_sha}..{local_sha}"], root)
    if changed.returncode != 0:
        return _deny("Blocked: the push hook could not classify the main ref update.")
    paths = [line.strip() for line in changed.stdout.splitlines() if line.strip()]
    if not paths:
        return Decision(True)
    classification = classify_paths(paths, load_model())
    if classification.risk_class != "R0":
        return _deny(
            "Blocked: only an R0 change may be pushed directly to main; "
            f"this update classifies {classification.risk_class}."
        )
    return Decision(True)


def main(*, root: Path = REPO_ROOT) -> int:
    """Read Git's ref-update stream and refuse any update that cannot be verified."""

    try:
        for raw in sys.stdin:
            fields = raw.split()
            if len(fields) != 4:
                raise ValueError("malformed pre-push input")
            _local_ref, local_sha, remote_ref, remote_sha = fields
            decision = evaluate_update(local_sha, remote_sha, remote_ref, root=root)
            if not decision.allowed:
                print(decision.reason, file=sys.stderr)
                return 1
    except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
        print("Blocked: the push hook could not verify the ref updates.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
