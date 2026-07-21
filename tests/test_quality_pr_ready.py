"""PR readiness composes classification, task validation, traceability, and evidence freshness."""

from __future__ import annotations

import subprocess
from pathlib import Path

import scripts.quality.pr_ready as pr_ready
from scripts.quality.pr_ready import assess_readiness, evidence_is_current

from tests.test_quality_validate_task import _SPEC, _task


def test_missing_evidence_fails_pr_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "evidence.md").unlink()
    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        head_sha="abc123",
    )
    assert not result.ready
    assert any("evidence.md" in check.detail for check in result.checks if not check.ok)


def test_stale_evidence_fails_pr_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        head_sha="new456",
    )
    assert not result.ready
    assert any("stale" in check.detail.lower() for check in result.checks if not check.ok)


def test_a_clean_r1_task_passes(tmp_path: Path) -> None:
    task = _task(tmp_path)
    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        head_sha="abc123",
    )
    assert result.ready
    assert result.risk_class == "R1"


def test_an_r3_change_reports_the_cumulative_r3_gates(tmp_path: Path) -> None:
    task = _task(
        tmp_path,
        spec=_SPEC.replace("R1 — local tooling.", "R3 — quality gates govern result integrity."),
    )
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py", "justfile"],
        head_sha="abc123",
    )
    assert result.ready
    assert result.risk_class == "R3"
    assert "no-autonomous-merge" in result.required_gates
    assert "check" in result.required_gates


def test_declared_risk_may_not_understate_the_classifier(tmp_path: Path) -> None:
    task = _task(tmp_path)
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    assert not result.ready
    assert any("declared risk" in check.detail.lower() for check in result.checks if not check.ok)


def test_cli_exit_code_tracks_clean_and_missing_evidence(
    tmp_path: Path, monkeypatch: object
) -> None:
    task_parent = tmp_path / ".ai" / "tasks"
    task_parent.mkdir(parents=True)
    task = _task(task_parent)
    monkeypatch.setattr(pr_ready, "REPO_ROOT", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        pr_ready, "changed_paths", lambda _base: ["scripts/tool.py"]
    )
    monkeypatch.setattr(pr_ready, "_head_sha", lambda _root: "abc123")  # type: ignore[attr-defined]

    assert pr_ready.main([task.name]) == 0
    (task / "evidence.md").unlink()
    assert pr_ready.main([task.name]) == 1


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _commit(root: Path, message: str) -> str:
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
    return _git(root, "rev-parse", "HEAD")


def test_evidence_only_commit_may_follow_the_tested_head(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    evidence = tmp_path / "evidence.md"
    evidence.write_text("# Evidence\n\nHEAD: pending\n", encoding="utf-8")
    covered = _commit(tmp_path, "code")

    evidence.write_text(f"# Evidence\n\nHEAD: {covered}\n", encoding="utf-8")
    final = _commit(tmp_path, "evidence")
    assert evidence_is_current(evidence, final, root=tmp_path)[0]

    (tmp_path / "code.py").write_text("value = 1\n", encoding="utf-8")
    later = _commit(tmp_path, "later code")
    current, detail = evidence_is_current(evidence, later, root=tmp_path)
    assert not current
    assert "code.py" in detail
