"""PR readiness composes classification, task validation, traceability, and evidence freshness."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import scripts.quality.pr_ready as pr_ready
from scripts.quality.classify import load_model
from scripts.quality.pr_ready import assess_readiness, evidence_is_current

from tests.test_quality_validate_task import _task


def _record_gate_evidence(task: Path, risk_class: str) -> None:
    gates = load_model().required_gates(risk_class)
    rows = "\n".join(f"| `{gate}` | `verify {gate}` | 0 | passed |" for gate in gates)
    (task / "evidence.md").write_text(
        "# Evidence\n\n## HEAD\nHEAD: abc123\n\n## Commands\n"
        "| Gate | Command | Exit status | Result |\n"
        "|---|---|---:|---|\n"
        f"{rows}\n\n"
        "## Coverage and mutation\nComplete.\n\n## Deferred checks\nNone.\n",
        encoding="utf-8",
    )


def _record_no_findings_review(task: Path, attempts: int = 3) -> None:
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n"
        f"No findings; {attempts} counterexamples attempted\n\n"
        "## Dispositions\nNo findings to disposition.\n",
        encoding="utf-8",
    )


def test_missing_evidence_fails_pr_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "evidence.md").unlink()
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    assert not result.ready
    assert any("evidence.md" in check.detail for check in result.checks if not check.ok)


def test_stale_evidence_fails_pr_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="new456",
    )
    assert not result.ready
    assert any("stale" in check.detail.lower() for check in result.checks if not check.ok)


def test_a_clean_r1_task_passes(tmp_path: Path) -> None:
    result = assess_readiness(
        None,
        changed=["scripts/tool.py"],
        head_sha="abc123",
    )
    assert result.ready
    assert result.risk_class == "R1"


def test_a_nonzero_required_gate_blocks_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    evidence = task / "evidence.md"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "| `check` | `verify check` | 0 | passed |",
            "| `check` | `verify check` | 0 | passed |\n| `check` | `failed check` | 1 | failed |",
        ),
        encoding="utf-8",
    )
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    assert not result.ready
    assert any(
        "check" in check.detail and "non-zero" in check.detail
        for check in result.checks
        if not check.ok
    )


def test_a_missing_required_gate_blocks_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    evidence = task / "evidence.md"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "| `impacted-tests` | `verify impacted-tests` | 0 | passed |\n", ""
        ),
        encoding="utf-8",
    )
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
    )
    assert not result.ready
    assert any(
        "missing required gates: impacted-tests" in check.detail
        for check in result.checks
        if not check.ok
    )


def test_a_full_clean_r3_gate_run_is_ready(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    _record_no_findings_review(task)
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py", "justfile"],
        head_sha="abc123",
    )
    assert result.ready
    assert result.risk_class == "R3"
    assert set(result.required_gates) == set(load_model().required_gates("R3"))


def test_an_r3_change_reports_the_cumulative_r3_gates(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    _record_no_findings_review(task)
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py", "justfile"],
        head_sha="abc123",
    )
    assert result.ready
    assert result.risk_class == "R3"
    assert "no-autonomous-merge" in result.required_gates
    assert "check" in result.required_gates


def test_a_manual_r3_upgrade_enforces_the_cumulative_r3_gates(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_no_findings_review(task)
    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        head_sha="abc123",
        declared_risk="R3",
    )
    assert not result.ready
    assert result.classification.risk_class == "R1"
    assert result.risk_class == "R3"
    assert "no-autonomous-merge" in result.required_gates
    assert any("missing required gates" in check.detail for check in result.checks if not check.ok)


def test_declared_risk_may_not_understate_the_classifier(tmp_path: Path) -> None:
    task = _task(tmp_path)
    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
        declared_risk="R1",
    )
    assert not result.ready
    assert any("declared risk" in check.detail.lower() for check in result.checks if not check.ok)


def test_cli_exit_code_tracks_clean_and_missing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_parent = tmp_path / ".ai" / "tasks"
    task_parent.mkdir(parents=True)
    task = _task(task_parent)
    _record_gate_evidence(task, "R3")
    monkeypatch.setattr(pr_ready, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        pr_ready,
        "changed_paths",
        lambda _base: ["scripts/quality/pr_ready.py", ".ai/tasks/task/evidence.md"],
    )
    monkeypatch.setattr(pr_ready, "_head_sha", lambda _root: "abc123")

    assert pr_ready.main([task.name]) == 0
    assert capsys.readouterr().out.rstrip().endswith("READY")
    (task / "evidence.md").unlink()
    assert pr_ready.main([task.name]) == 1
    assert capsys.readouterr().out.rstrip().endswith("NOT READY")


def test_cli_reports_not_ready_for_a_failing_required_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_parent = tmp_path / ".ai" / "tasks"
    task_parent.mkdir(parents=True)
    task = _task(task_parent)
    _record_gate_evidence(task, "R3")
    evidence = task / "evidence.md"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "| `check` | `verify check` | 0 | passed |",
            "| `check` | `verify check` | 2 | failed |",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pr_ready, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        pr_ready,
        "changed_paths",
        lambda _base: ["scripts/quality/pr_ready.py", ".ai/tasks/task/evidence.md"],
    )
    monkeypatch.setattr(pr_ready, "_head_sha", lambda _root: "abc123")

    assert pr_ready.main([task.name]) == 1
    output = capsys.readouterr().out
    assert "required gates with non-zero exit: check (2)" in output
    assert output.rstrip().endswith("NOT READY")


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
