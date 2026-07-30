"""PR readiness composes classification, task validation, traceability, and evidence freshness."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import scripts.quality.pr_ready as pr_ready
from scripts.quality.classify import load_model
from scripts.quality.pr_ready import assess_readiness, evidence_is_current
from scripts.quality.review_observation import ReviewObservation
from scripts.quality.validate_task import validate_task_dir

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


def test_review_and_evidence_commits_may_follow_the_tested_head(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    task = tmp_path / ".ai" / "tasks" / "134"
    task.mkdir(parents=True)
    evidence = task / "evidence.md"
    review = task / "review.md"
    evidence.write_text("# Evidence\n\nHEAD: pending\n", encoding="utf-8")
    review.write_text("# Review\n\nPending.\n", encoding="utf-8")
    covered = _commit(tmp_path, "code")

    evidence.write_text(f"# Evidence\n\nHEAD: {covered}\n", encoding="utf-8")
    review.write_text("# Review\n\nCompleted independently.\n", encoding="utf-8")
    final = _commit(tmp_path, "review records")

    assert evidence_is_current(evidence, final, root=tmp_path)[0]


@pytest.mark.parametrize(
    ("observation", "strict", "ready"),
    [
        (ReviewObservation("verified", "review verified", "https://review/1"), True, True),
        (ReviewObservation("rejected", "no current review", None), True, False),
        (ReviewObservation("unverifiable", "review is UNVERIFIABLE", None), False, True),
        (ReviewObservation("unverifiable", "review is UNVERIFIABLE", None), True, False),
    ],
)
def test_readiness_uses_the_observed_review_with_local_advisory_semantics(
    tmp_path: Path,
    observation: ReviewObservation,
    strict: bool,
    ready: bool,
) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    (task / "review.md").write_text(
        "# Anything\n\n## Findings\n\n**No findings; 900 counterexamples attempted**\n\n"
        "## Dispositions\n\nNone.\n",
        encoding="utf-8",
    )

    result = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
        review_observation=observation,
        require_verifiable_review=strict,
    )

    assert result.ready is ready
    assert next(check for check in result.checks if check.name == "independent-review").detail


@pytest.mark.parametrize(
    "observation",
    (
        ReviewObservation("verified", "review verified", "https://review/1"),
        ReviewObservation("rejected", "no current review", None),
        ReviewObservation("unverifiable", "review is UNVERIFIABLE", None),
    ),
)
def test_task_validator_and_pr_readiness_apply_the_same_review_verdict(
    tmp_path: Path,
    observation: ReviewObservation,
) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R3")
    validation = validate_task_dir(
        task,
        review_observation=observation,
        require_verifiable_review=True,
    )
    readiness = assess_readiness(
        task,
        changed=["scripts/quality/pr_ready.py"],
        head_sha="abc123",
        review_observation=observation,
        require_verifiable_review=True,
    )
    review_check = next(check for check in readiness.checks if check.name == "independent-review")

    assert validation.ok is review_check.ok


@pytest.mark.parametrize("risk_class", ("R2", "R3"))
def test_unresolved_review_finding_blocks_readiness_despite_verified_observation(
    tmp_path: Path,
    risk_class: str,
) -> None:
    task_root = tmp_path / ".ai" / "tasks"
    task_root.mkdir(parents=True)
    task = _task(task_root)
    _record_gate_evidence(task, risk_class)
    (task / "review.md").write_text(
        "# Review\n\n## Findings\n\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        "| R-01 | Defect | Broken guard | Pending | unresolved |\n\n"
        "## Dispositions\n\nPending.\n",
        encoding="utf-8",
    )

    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        declared_risk=risk_class,
        head_sha="abc123",
        review_observation=ReviewObservation("verified", "review verified", "https://review/1"),
        require_verifiable_review=True,
    )

    assert not result.ready
    artifact_check = next(check for check in result.checks if check.name == "task-artifacts")
    assert not artifact_check.ok
    assert "unresolved Defect" in artifact_check.detail


def test_r2_requires_the_observed_review_as_well_as_dispositions(tmp_path: Path) -> None:
    task = _task(tmp_path)
    _record_gate_evidence(task, "R2")

    result = assess_readiness(
        task,
        changed=["scripts/tool.py"],
        declared_risk="R2",
        head_sha="abc123",
        review_observation=ReviewObservation("rejected", "no current review", None),
        require_verifiable_review=True,
    )

    assert not result.ready
    review_check = next(check for check in result.checks if check.name == "independent-review")
    assert not review_check.ok
    assert review_check.detail == "no current review"


def test_local_unverifiable_review_is_labelled_advisory_not_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_root = tmp_path / ".ai" / "tasks"
    task_root.mkdir(parents=True)
    task = _task(task_root)
    _record_gate_evidence(task, "R3")
    monkeypatch.setattr(pr_ready, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pr_ready, "changed_paths", lambda base: ["scripts/quality/pr_ready.py"])
    monkeypatch.setattr(pr_ready, "discover_task_id", lambda paths: task.name)
    monkeypatch.setattr(pr_ready, "_head_sha", lambda root: "abc123")
    monkeypatch.setattr(
        pr_ready,
        "observe_independent_review",
        lambda gateway, head_sha, task_id: ReviewObservation(
            "unverifiable", "independent review is UNVERIFIABLE: offline", None
        ),
    )

    assert pr_ready.main([task.name]) == 0
    output = capsys.readouterr().out
    assert "[ADVISORY] independent-review:" in output
    assert "[PASS] independent-review:" not in output
