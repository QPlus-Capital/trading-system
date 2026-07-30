"""Independent-review readiness is observed from GitHub, never self-reported."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.quality.review_observation import (
    PullRequestCommit,
    PullRequestReview,
    PullRequestSnapshot,
    ReviewObservation,
    observe_independent_review,
    only_task_artifacts,
    task_artifact_only_synchronization,
)


def _at(minute: int) -> datetime:
    return datetime(2026, 7, 30, 12, minute, tzinfo=UTC)


class FakeReviewGateway:
    def __init__(self, snapshot: PullRequestSnapshot) -> None:
        self.snapshot = snapshot

    def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
        assert head_sha == "head"
        return self.snapshot


@pytest.mark.parametrize(
    ("reviews", "expected"),
    [
        ((PullRequestReview(_at(2), "COMMENTED", "https://review/1"),), "verified"),
        ((PullRequestReview(_at(2), "APPROVED", "https://review/1"),), "verified"),
        ((PullRequestReview(_at(2), "CHANGES_REQUESTED", "https://review/1"),), "rejected"),
        ((), "rejected"),
    ],
)
def test_review_verdict_comes_from_the_latest_review_after_the_last_code_commit(
    reviews: tuple[PullRequestReview, ...],
    expected: str,
) -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            PullRequestCommit("code", _at(1), ("scripts/quality/pr_ready.py",)),
            PullRequestCommit("artifact", _at(3), (".ai/tasks/134/review.md",)),
        ),
        reviews=reviews,
    )

    assert observe_independent_review(FakeReviewGateway(snapshot), "head").status == expected


def test_a_code_commit_after_every_review_makes_the_review_stale() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            PullRequestCommit("first", _at(1), ("scripts/quality/pr_ready.py",)),
            PullRequestCommit("latest", _at(3), ("tests/test_quality_pr_ready.py",)),
        ),
        reviews=(PullRequestReview(_at(2), "COMMENTED", "https://review/1"),),
    )

    result = observe_independent_review(FakeReviewGateway(snapshot), "head")

    assert result.status == "rejected"
    assert "after" in result.detail


def test_review_and_evidence_commits_do_not_invalidate_a_completed_review() -> None:
    snapshot = PullRequestSnapshot(
        commits=(
            PullRequestCommit("code", _at(1), ("scripts/quality/pr_ready.py",)),
            PullRequestCommit(
                "records",
                _at(3),
                (".ai/tasks/134/review.md", ".ai/tasks/134/evidence.md"),
            ),
        ),
        reviews=(PullRequestReview(_at(2), "COMMENTED", "https://review/1"),),
    )

    assert observe_independent_review(FakeReviewGateway(snapshot), "head").status == "verified"


def test_gateway_failure_is_explicitly_unverifiable() -> None:
    class OfflineGateway:
        def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
            raise RuntimeError("offline")

    assert observe_independent_review(OfflineGateway(), "head") == ReviewObservation(
        "unverifiable",
        "independent review is UNVERIFIABLE: RuntimeError",
        None,
    )


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((".ai/tasks/134/evidence.md",), True),
        ((".ai/tasks/134/review.md", ".ai/tasks/134/evidence.md"), True),
        (("monitoring/dashboard.py",), False),
        (("tests/test_quality_pr_ready.py", ".ai/tasks/134/evidence.md"), False),
        ((), False),
    ],
)
def test_task_artifact_only_scope_is_derived_from_the_diff(
    paths: tuple[str, ...],
    expected: bool,
) -> None:
    assert only_task_artifacts(paths) is expected


@pytest.mark.parametrize(
    ("action", "paths", "expected"),
    [
        ("synchronize", (".ai/tasks/134/review.md",), True),
        ("synchronize", ("core/strategy.py",), False),
        ("synchronize", ("tests/test_strategy.py",), False),
        ("opened", (".ai/tasks/134/review.md",), False),
        ("ready_for_review", (".ai/tasks/134/evidence.md",), False),
    ],
)
def test_reduced_ci_requires_a_task_only_synchronize_event(
    action: str,
    paths: tuple[str, ...],
    expected: bool,
) -> None:
    assert task_artifact_only_synchronization(action, paths) is expected
