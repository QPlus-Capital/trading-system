"""The split finding registry must merge cleanly and preserve every legacy fact."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
from scripts.quality.finding_registry import (
    Finding,
    canonical_content_hash,
    load_findings,
    write_finding,
)

_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = _ROOT / ".ai" / "quality" / "finding-patterns"
_LEGACY = _ROOT / "tests" / "fixtures" / "finding-patterns-v1.toml"


def _finding(name: str) -> Finding:
    return Finding(
        id="",
        source=f"synthetic {name}",
        defect_class=f"{name}-class",
        severity="P2",
        affected=f"{name}.py",
        root_cause=f"{name} root cause",
        why_tests_missed=f"{name} was not exercised",
        regression=f"test_{name}_regression",
        generalized=f"{name} generalized rule",
        workflow_change=f"{name} workflow protection",
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> None:
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test Author",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        message,
    )


def test_independent_finding_files_merge_in_either_order(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    registry = repo / ".ai" / "quality" / "finding-patterns"
    registry.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test Author")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _commit(repo, "base")
    base = _git(repo, "rev-parse", "HEAD")

    for branch, name in (("branch-a", "alpha"), ("branch-b", "beta")):
        _git(repo, "switch", "-c", branch, base)
        write_finding(registry, _finding(name))
        _commit(repo, name)

    for target, first, second in (
        ("order-a-b", "branch-a", "branch-b"),
        ("order-b-a", "branch-b", "branch-a"),
    ):
        _git(repo, "switch", "-c", target, base)
        _git(repo, "merge", "--no-edit", first)
        _git(repo, "merge", "--no-edit", second)
        assert {item.defect_class for item in load_findings(registry)} == {
            "alpha-class",
            "beta-class",
        }


def test_finding_ids_are_derived_and_unclaimable(tmp_path: Path) -> None:
    first = _finding("alpha")
    path = write_finding(tmp_path, first)
    loaded = load_findings(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == f"F-{canonical_content_hash(first).upper()}"
    assert path.stem == canonical_content_hash(first)

    claimed = path.read_text(encoding="utf-8") + '\nid = "F-056"\n'
    path.write_text(claimed, encoding="utf-8")
    with pytest.raises(ValueError, match="derived"):
        load_findings(tmp_path)


def _content(item: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in item.items() if key != "id"}


def test_migration_preserves_all_legacy_ids_and_content() -> None:
    before = tomllib.loads(_LEGACY.read_text(encoding="utf-8"))["finding"]
    after = {finding.id: finding.content for finding in load_findings(_REGISTRY)}
    assert len(before) == 55
    assert set(after) == {str(item["id"]) for item in before}
    assert all(after[str(item["id"])] == _content(item) for item in before)
