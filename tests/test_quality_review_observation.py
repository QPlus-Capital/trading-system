"""Independent-review readiness is observed from GitHub, never self-reported."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.quality.review_observation import (
    GH_PR_VIEW_ARGS,
    GhReviewGateway,
    PullRequestCommit,
    PullRequestReview,
    PullRequestSnapshot,
    ReviewGatewayError,
    ReviewObservation,
    detect_task_artifact_only_synchronization,
    main,
    observe_independent_review,
    only_task_artifacts,
    task_artifact_only_synchronization,
    task_id_from_pr_body,
)


def _at(minute: int) -> datetime:
    return datetime(2026, 7, 30, 12, minute, tzinfo=UTC)


def _commit(sha: str, *paths: str, author: str | None = None) -> PullRequestCommit:
    return PullRequestCommit(sha, paths, author)


def _review(
    minute: int,
    state: str,
    commit_id: str,
    *,
    author: str = "reviewer",
    review_id: int = 1,
) -> PullRequestReview:
    return PullRequestReview(
        submitted_at=_at(minute),
        state=state,
        url=f"https://review/{review_id}",
        commit_id=commit_id,
        author=author,
        review_id=review_id,
    )


class FakeReviewGateway:
    def __init__(self, snapshot: PullRequestSnapshot) -> None:
        self.snapshot = snapshot

    def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
        assert head_sha == "head"
        return self.snapshot


@pytest.mark.parametrize(
    ("reviews", "expected"),
    [
        ((_review(2, "COMMENTED", "code"),), "verified"),
        ((_review(2, "APPROVED", "code"),), "verified"),
        ((_review(2, "CHANGES_REQUESTED", "code"),), "rejected"),
        ((), "rejected"),
    ],
)
def test_review_verdict_comes_from_the_latest_review_after_the_last_code_commit(
    reviews: tuple[PullRequestReview, ...],
    expected: str,
) -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("code", "scripts/quality/pr_ready.py"),
            _commit("artifact", ".ai/tasks/134/review.md"),
        ),
        reviews=reviews,
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == expected
    )


def test_a_code_commit_after_every_review_makes_the_review_stale() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("reviewed", "scripts/quality/pr_ready.py"),
            _commit("latest", "tests/test_quality_pr_ready.py"),
        ),
        reviews=(_review(59, "COMMENTED", "reviewed"),),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "rejected"
    assert "current non-artifact commit" in result.detail


def test_review_on_an_artifact_descendant_of_the_last_code_commit_is_current() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("code", "scripts/quality/pr_ready.py"),
            _commit("records", ".ai/tasks/134/review.md", ".ai/tasks/134/evidence.md"),
        ),
        reviews=(_review(1, "COMMENTED", "records"),),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "verified"
    )


def test_an_artifact_commit_for_another_task_invalidates_the_review() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("code", "scripts/quality/pr_ready.py"),
            _commit("other", ".ai/tasks/107/review.md"),
        ),
        reviews=(_review(3, "COMMENTED", "code"),),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "rejected"
    )


def test_a_comment_cannot_clear_the_same_reviewers_change_request() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("code", "scripts/quality/pr_ready.py"),),
        reviews=(
            _review(2, "CHANGES_REQUESTED", "code", review_id=1),
            _review(3, "COMMENTED", "code", review_id=2),
        ),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "rejected"
    assert "CHANGES_REQUESTED" in result.detail


def test_a_current_review_cannot_clear_an_undismissed_earlier_change_request() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("earlier", "scripts/quality/pr_ready.py"),
            _commit("current", "tests/test_quality_pr_ready.py"),
        ),
        reviews=(
            _review(2, "CHANGES_REQUESTED", "earlier", review_id=1),
            _review(3, "COMMENTED", "current", review_id=2),
        ),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "rejected"
    assert "CHANGES_REQUESTED" in result.detail


def test_the_same_reviewers_later_approval_clears_their_change_request() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("earlier", "scripts/quality/pr_ready.py"),
            _commit("current", "tests/test_quality_pr_ready.py"),
        ),
        reviews=(
            _review(2, "CHANGES_REQUESTED", "earlier", review_id=1),
            _review(3, "APPROVED", "current", review_id=2),
        ),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "verified"
    )


def test_a_change_request_orphaned_by_a_rebase_still_blocks() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("rebased", "scripts/quality/pr_ready.py"),),
        reviews=(
            _review(2, "CHANGES_REQUESTED", "pre-rebase-sha", review_id=1),
            _review(3, "COMMENTED", "rebased", review_id=2),
        ),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "rejected"
    assert "CHANGES_REQUESTED" in result.detail


def test_a_dismissed_change_request_orphaned_by_a_rebase_no_longer_blocks() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("rebased", "scripts/quality/pr_ready.py"),),
        reviews=(
            _review(2, "DISMISSED", "pre-rebase-sha", review_id=1),
            _review(3, "COMMENTED", "rebased", review_id=2),
        ),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "verified"
    )


def test_an_explicitly_dismissed_change_request_no_longer_blocks_a_current_review() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("earlier", "scripts/quality/pr_ready.py"),
            _commit("current", "tests/test_quality_pr_ready.py"),
        ),
        reviews=(
            _review(2, "DISMISSED", "earlier", review_id=1),
            _review(3, "COMMENTED", "current", review_id=2),
        ),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "verified"
    )


def test_equal_timestamp_review_states_are_order_independent_and_blocking_wins() -> None:
    blocking = _review(2, "CHANGES_REQUESTED", "code", review_id=1)
    other = _review(2, "COMMENTED", "code", review_id=2)
    for reviews in ((blocking, other), (other, blocking)):
        snapshot = PullRequestSnapshot(
            commits=(_commit("code", "scripts/quality/pr_ready.py"),),
            reviews=reviews,
        )
        assert (
            observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
            == "rejected"
        )


def test_equal_timestamp_latest_decisive_review_id_wins_independently_of_api_order() -> None:
    blocking = _review(2, "CHANGES_REQUESTED", "code", review_id=1)
    approval = _review(2, "APPROVED", "code", review_id=2)
    for reviews in ((blocking, approval), (approval, blocking)):
        snapshot = PullRequestSnapshot(
            commits=(_commit("code", "scripts/quality/pr_ready.py"),),
            reviews=reviews,
        )
        assert (
            observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
            == "verified"
        )


def test_same_account_comment_is_observed_but_independence_is_not_verified() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("code", "scripts/quality/pr_ready.py", author="shared-account"),),
        reviews=(
            _review(
                2,
                "COMMENTED",
                "code",
                author="shared-account",
                review_id=1,
            ),
        ),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "verified"
    assert "independence is not verified" in result.detail
    assert "shared-account" in result.detail


def test_a_dismissed_approval_cannot_verify_the_pull_request() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("code", "scripts/quality/pr_ready.py"),),
        reviews=(_review(2, "DISMISSED", "code"),),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "rejected"
    )


def test_a_pull_request_with_only_task_artifact_commits_cannot_self_certify() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            _commit("review", ".ai/tasks/134/review.md"),
            _commit("evidence", ".ai/tasks/134/evidence.md"),
        ),
        reviews=(_review(2, "APPROVED", "evidence"),),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134")

    assert result.status == "rejected"
    assert "no non-task-artifact commit" in result.detail


def test_one_reviewers_current_change_request_blocks_another_reviewers_comment() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("code", "scripts/quality/pr_ready.py"),),
        reviews=(
            _review(2, "CHANGES_REQUESTED", "code", author="reviewer-a", review_id=1),
            _review(3, "COMMENTED", "code", author="reviewer-b", review_id=2),
        ),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "rejected"
    )


def test_a_review_bound_to_an_unknown_commit_cannot_verify_the_pull_request() -> None:
    snapshot = PullRequestSnapshot(
        commits=(_commit("code", "scripts/quality/pr_ready.py"),),
        reviews=(_review(2, "APPROVED", "not-in-this-pr"),),
    )

    assert (
        observe_independent_review(FakeReviewGateway(snapshot), "head", task_id="134").status
        == "rejected"
    )


def test_gateway_failure_is_explicitly_unverifiable_and_keeps_the_cause() -> None:
    class OfflineGateway:
        def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
            raise RuntimeError("rate limit exhausted")

    assert observe_independent_review(OfflineGateway(), "head", task_id="134") == ReviewObservation(
        "unverifiable",
        "independent review is UNVERIFIABLE: RuntimeError: rate limit exhausted",
        None,
    )


def test_value_error_at_the_gateway_is_reported_without_a_traceback() -> None:
    class InvalidGateway:
        def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
            raise ValueError("malformed event timestamp")

    result = observe_independent_review(InvalidGateway(), "head", task_id="134")

    assert result.status == "unverifiable"
    assert "malformed event timestamp" in result.detail


@pytest.mark.parametrize(
    ("paths", "task_id", "expected"),
    [
        ((".ai/tasks/134/evidence.md",), "134", True),
        ((".ai/tasks/134/review.md", ".ai/tasks/134/evidence.md"), "134", True),
        ((".ai/tasks/_templates/review.md",), "134", False),
        ((".ai/tasks/107/review.md",), "134", False),
        ((".ai/tasks/README.md",), "134", False),
        ((".ai/tasks/134/unknown.md",), "134", False),
        (("monitoring/dashboard.py",), "134", False),
        (("tests/test_quality_pr_ready.py", ".ai/tasks/134/evidence.md"), "134", False),
        ((), "134", False),
    ],
)
def test_task_artifact_only_scope_is_derived_from_the_diff(
    paths: tuple[str, ...],
    task_id: str,
    expected: bool,
) -> None:
    assert only_task_artifacts(paths, task_id=task_id) is expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", None),
        (
            "`.ai/tasks/134/`\n`.ai/tasks/135/`",
            None,
        ),
        ("`.ai/tasks/_templates/`", None),
        ("Task artifact: `.ai/tasks/134/`", "134"),
    ],
)
def test_task_id_from_pr_body_requires_one_non_template_task(
    body: str,
    expected: str | None,
) -> None:
    assert task_id_from_pr_body(body) == expected


def test_templates_are_never_artifact_only_even_for_a_template_task_id() -> None:
    assert not only_task_artifacts(
        [".ai/tasks/_templates/review.md"],
        task_id="_templates",
    )


@pytest.mark.parametrize(
    ("action", "paths", "task_id", "expected"),
    [
        ("synchronize", (".ai/tasks/134/review.md",), "134", True),
        ("synchronize", (".ai/tasks/107/review.md",), "134", False),
        ("synchronize", ("core/strategy.py",), "134", False),
        ("synchronize", ("tests/test_strategy.py",), "134", False),
        ("opened", (".ai/tasks/134/review.md",), "134", False),
        ("ready_for_review", (".ai/tasks/134/evidence.md",), "134", False),
    ],
)
def test_reduced_ci_requires_a_task_only_synchronize_event(
    action: str,
    paths: tuple[str, ...],
    task_id: str,
    expected: bool,
) -> None:
    assert task_artifact_only_synchronization(action, paths, task_id=task_id) is expected


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit_file(root: Path, path: str, content: str) -> str:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(root, "add", path)
    _git(root, "commit", "-m", content)
    return _git(root, "rev-parse", "HEAD")


def test_ci_scope_detector_uses_the_real_no_rename_git_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    base = _commit_file(tmp_path, ".ai/tasks/134/review.md", "first")
    _commit_file(tmp_path, ".ai/tasks/134/review.md", "second")

    assert detect_task_artifact_only_synchronization("synchronize", base, "134", root=tmp_path)

    attack = tmp_path / "attack"
    attack.mkdir()
    _git(attack, "init")
    _git(attack, "config", "user.name", "Test")
    _git(attack, "config", "user.email", "test@example.com")
    attack_base = _commit_file(attack, "live/risk_control.py", "preserved production content")
    (attack / ".ai" / "tasks" / "134").mkdir(parents=True)
    _git(attack, "mv", "live/risk_control.py", ".ai/tasks/134/review.md")
    _git(attack, "commit", "-m", "rename production into task artifacts")

    assert not detect_task_artifact_only_synchronization(
        "synchronize",
        attack_base,
        "134",
        root=attack,
    )


def test_ci_scope_detector_fails_closed_to_the_full_set_for_an_unreachable_base(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _commit_file(tmp_path, ".ai/tasks/134/review.md", "first")

    assert not detect_task_artifact_only_synchronization(
        "synchronize", "0" * 40, "134", root=tmp_path
    )


def test_ci_scope_detector_treats_an_empty_diff_as_full_scope(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    head = _commit_file(tmp_path, ".ai/tasks/134/review.md", "first")

    assert not detect_task_artifact_only_synchronization(
        "synchronize",
        head,
        "134",
        root=tmp_path,
    )


def test_the_requested_gh_pr_view_fields_exist_in_the_installed_cli() -> None:
    if shutil.which("gh") is None:
        pytest.skip("gh is unavailable")
    probe = subprocess.run(
        ["gh", "pr", "view", "--json", "__probe__"],
        capture_output=True,
        text=True,
        check=False,
    )
    available = {
        line.strip()
        for line in f"{probe.stdout}\n{probe.stderr}".splitlines()
        if line.startswith("  ")
    }

    assert set(GH_PR_VIEW_ARGS[3].split(",")) <= available


def test_gateway_parses_all_pages_and_preserves_rename_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "pull_request": {
                    "number": 143,
                    "head": {"sha": "head"},
                    "base": {"repo": {"full_name": "QPlus-Capital/trading-system"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    commands: list[str] = []

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        commands.append(command)
        if "/commits?per_page=100" in command:
            payload: object = [
                [{"sha": "code", "author": {"login": "builder"}}],
                [{"sha": "head", "author": {"login": "builder"}}],
            ]
        elif "/commits/code?per_page=100" in command:
            payload = [
                {
                    "files": [
                        {
                            "filename": ".ai/tasks/134/risk_control.py",
                            "previous_filename": "live/risk_control.py",
                        }
                    ]
                }
            ]
        elif "/commits/head?per_page=100" in command:
            payload = [{"files": [{"filename": ".ai/tasks/134/review.md"}]}]
        elif "/reviews?per_page=100" in command:
            payload = [
                [
                    {
                        "id": 1,
                        "submitted_at": None,
                        "state": "PENDING",
                        "commit_id": "head",
                        "user": {"login": "pending"},
                    },
                    {
                        "id": 2,
                        "submitted_at": "2026-07-30T12:03:00Z",
                        "state": "DISMISSED",
                        "commit_id": "head",
                        "user": {"login": "dismissed"},
                    },
                ],
                [
                    {
                        "id": 3,
                        "submitted_at": "2026-07-30T12:04:00Z",
                        "state": "COMMENTED",
                        "commit_id": "head",
                        "html_url": "https://review/3",
                        "user": {"login": "reviewer"},
                    }
                ],
            ]
        else:
            raise AssertionError(f"unexpected gh command: {command}")
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr(
        "scripts.quality.review_observation.subprocess.run",
        fake_run,
    )

    snapshot = GhReviewGateway(root=tmp_path).snapshot_for_head("head")

    assert snapshot.commits == (
        _commit(
            "code",
            ".ai/tasks/134/risk_control.py",
            "live/risk_control.py",
            author="builder",
        ),
        _commit("head", ".ai/tasks/134/review.md", author="builder"),
    )
    assert snapshot.reviews == (
        PullRequestReview(_at(3), "DISMISSED", None, "head", "dismissed", 2),
        _review(4, "COMMENTED", "head", author="reviewer", review_id=3),
    )
    paginated = [command for command in commands if "?per_page=100" in command]
    assert len(paginated) == 4
    assert all("--paginate" in command and "--slurp" in command for command in paginated)


def test_gateway_refuses_a_head_mismatch_before_querying_reviews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "pull_request": {
                    "number": 143,
                    "head": {"sha": "different"},
                    "base": {"repo": {"full_name": "QPlus-Capital/trading-system"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))

    with pytest.raises(ReviewGatewayError, match="head"):
        GhReviewGateway(root=tmp_path).snapshot_for_head("head")


def test_local_gateway_refuses_a_pull_request_head_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert args == ["gh", *GH_PR_VIEW_ARGS]
        payload = {
            "number": 143,
            "headRefOid": "different",
            "url": "https://github.com/QPlus-Capital/trading-system/pull/143",
        }
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    with pytest.raises(ReviewGatewayError, match="head"):
        GhReviewGateway(root=tmp_path).snapshot_for_head("head")


def test_local_gateway_derives_the_base_repository_from_the_pr_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "fork-owner/trading-system")

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert args == ["gh", *GH_PR_VIEW_ARGS]
        payload = {
            "number": 143,
            "headRefOid": "head",
            "url": "https://github.com/QPlus-Capital/trading-system/pull/143",
        }
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    assert GhReviewGateway(root=tmp_path)._pull_request("head") == (
        "QPlus-Capital/trading-system",
        143,
    )


def test_local_gateway_rejects_a_malformed_pull_request_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        payload = {
            "number": 143,
            "headRefOid": "head",
            "url": "not-a-pull-request-url",
        }
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    with pytest.raises(ReviewGatewayError, match="pull-request URL"):
        GhReviewGateway(root=tmp_path)._pull_request("head")


def test_gateway_requires_the_paginated_commit_tail_to_equal_the_checked_out_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        if args == ["gh", *GH_PR_VIEW_ARGS]:
            payload: object = {
                "number": 143,
                "headRefOid": "head",
                "url": "https://github.com/QPlus-Capital/trading-system/pull/143",
            }
        elif "/commits?per_page=100" in command:
            payload = [[{"sha": "truncated-old-head"}]]
        elif "/commits/truncated-old-head?per_page=100" in command:
            payload = [{"files": [{"filename": "core/strategy.py"}]}]
        elif "/reviews?per_page=100" in command:
            payload = [[]]
        else:
            raise AssertionError(f"unexpected gh command: {command}")
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    with pytest.raises(ReviewGatewayError, match="commit tail"):
        GhReviewGateway(root=tmp_path).snapshot_for_head("head")


@pytest.mark.parametrize(
    ("detail", "message"),
    [
        ({"files": None}, "commit files"),
        ({"files": [{"filename": "core/a.py", "previous_filename": ""}]}, "previous_filename"),
    ],
)
def test_gateway_refuses_incomplete_commit_file_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    detail: dict[str, object],
    message: str,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        if args == ["gh", *GH_PR_VIEW_ARGS]:
            payload: object = {
                "number": 143,
                "headRefOid": "head",
                "url": "https://github.com/QPlus-Capital/trading-system/pull/143",
            }
        elif "/commits?per_page=100" in command:
            payload = [[{"sha": "head"}]]
        elif "/commits/head?per_page=100" in command:
            payload = [detail]
        else:
            raise AssertionError(f"unexpected gh command: {command}")
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    with pytest.raises(ReviewGatewayError, match=message):
        GhReviewGateway(root=tmp_path).snapshot_for_head("head")


def test_gateway_refuses_a_naive_review_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        if args == ["gh", *GH_PR_VIEW_ARGS]:
            payload: object = {
                "number": 143,
                "headRefOid": "head",
                "url": "https://github.com/QPlus-Capital/trading-system/pull/143",
            }
        elif "/commits?per_page=100" in command:
            payload = [[{"sha": "head"}]]
        elif "/commits/head?per_page=100" in command:
            payload = [{"files": [{"filename": "core/a.py"}]}]
        elif "/reviews?per_page=100" in command:
            payload = [
                [
                    {
                        "id": 1,
                        "submitted_at": "2026-07-30T12:00:00",
                        "state": "COMMENTED",
                        "commit_id": "head",
                        "user": {"login": "reviewer"},
                    }
                ]
            ]
        else:
            raise AssertionError(f"unexpected gh command: {command}")
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr("scripts.quality.review_observation.subprocess.run", fake_run)

    with pytest.raises(ReviewGatewayError, match="timezone"):
        GhReviewGateway(root=tmp_path).snapshot_for_head("head")


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "message"),
    [
        (1, "", "authentication failed", "authentication failed"),
        (0, "{not-json", "", "invalid JSON"),
    ],
)
def test_gateway_reports_process_and_json_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    stderr: str,
    message: str,
) -> None:
    monkeypatch.setattr(
        "scripts.quality.review_observation.subprocess.run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, returncode, stdout, stderr),
    )

    with pytest.raises(ReviewGatewayError, match=message):
        GhReviewGateway(root=tmp_path)._run_json(("api", "endpoint"), "probe")


def test_ci_scope_entrypoint_writes_the_computed_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("EVENT_ACTION", "synchronize")
    monkeypatch.setenv("BEFORE_SHA", "base")
    monkeypatch.setenv("PR_BODY", "## Task artifact\n`.ai/tasks/134/`")
    observed: list[tuple[str, str, str]] = []

    def detect(action: str, before: str, task_id: str) -> bool:
        observed.append((action, before, task_id))
        return True

    monkeypatch.setattr(
        "scripts.quality.review_observation.detect_task_artifact_only_synchronization",
        detect,
    )

    assert main(["ci-scope"]) == 0
    assert observed == [("synchronize", "base", "134")]
    assert output.read_text(encoding="utf-8") == "only=true\n"
