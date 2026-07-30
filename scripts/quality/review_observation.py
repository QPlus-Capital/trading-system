"""Observe independent pull-request review from GitHub commit and review data."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, cast

from scripts.quality.classify import REPO_ROOT

ReviewStatus = Literal["verified", "rejected", "unverifiable"]
_TASK_ARTIFACT_PREFIX = ".ai/tasks/"
_NON_BLOCKING_STATES = frozenset({"APPROVED", "COMMENTED"})


@dataclass(frozen=True)
class PullRequestCommit:
    """One pull-request commit with the paths needed to classify its scope."""

    sha: str
    committed_at: datetime
    paths: tuple[str, ...]


@dataclass(frozen=True)
class PullRequestReview:
    """One submitted GitHub review."""

    submitted_at: datetime
    state: str
    url: str | None


@dataclass(frozen=True)
class PullRequestSnapshot:
    """The external facts required by the independent-review decision."""

    commits: tuple[PullRequestCommit, ...]
    reviews: tuple[PullRequestReview, ...]


@dataclass(frozen=True)
class ReviewObservation:
    """A readiness verdict with an explicit unverifiable state for local use."""

    status: ReviewStatus
    detail: str
    url: str | None


class ReviewGateway(Protocol):
    """External GitHub boundary used by the pure review-ordering decision."""

    def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot: ...


class ReviewGatewayError(RuntimeError):
    """GitHub review facts could not be obtained or validated."""


def only_task_artifacts(paths: Sequence[str]) -> bool:
    """Return true only for a non-empty diff wholly below ``.ai/tasks/``."""

    normalized = tuple(path.strip().replace("\\", "/") for path in paths if path.strip())
    return bool(normalized) and all(path.startswith(_TASK_ARTIFACT_PREFIX) for path in normalized)


def task_artifact_only_synchronization(action: str, paths: Sequence[str]) -> bool:
    """Select reduced CI only for an observed task-only PR synchronization diff."""

    return action == "synchronize" and only_task_artifacts(paths)


def observe_independent_review(
    gateway: ReviewGateway,
    head_sha: str,
) -> ReviewObservation:
    """Require a non-blocking review after the last non-task-artifact commit."""

    try:
        snapshot = gateway.snapshot_for_head(head_sha)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return ReviewObservation(
            "unverifiable",
            f"independent review is UNVERIFIABLE: {type(exc).__name__}",
            None,
        )

    relevant = tuple(commit for commit in snapshot.commits if not only_task_artifacts(commit.paths))
    if not relevant:
        return ReviewObservation(
            "rejected",
            "pull request has no non-task-artifact commit to review",
            None,
        )
    last_change = relevant[-1]
    current_reviews = tuple(
        review
        for review in snapshot.reviews
        if review.submitted_at > last_change.committed_at and review.state != "DISMISSED"
    )
    if not current_reviews:
        return ReviewObservation(
            "rejected",
            f"no submitted PR review exists after non-artifact commit {last_change.sha}",
            None,
        )
    latest = max(current_reviews, key=lambda review: review.submitted_at)
    if latest.state not in _NON_BLOCKING_STATES:
        return ReviewObservation(
            "rejected",
            f"latest current PR review has blocking state {latest.state}",
            latest.url,
        )
    return ReviewObservation(
        "verified",
        f"independent PR review verified after non-artifact commit {last_change.sha}",
        latest.url,
    )


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReviewGatewayError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ReviewGatewayError(f"{label} must be a JSON array")
    return cast(list[object], value)


def _text(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ReviewGatewayError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewGatewayError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReviewGatewayError(f"{label} must include a timezone")
    return parsed


class GhReviewGateway:
    """Thin ``gh`` adapter; review policy remains in :func:`observe_independent_review`."""

    def __init__(self, *, root: Path = REPO_ROOT) -> None:
        self.root = root

    def _run_json(self, args: Sequence[str], label: str) -> object:
        completed = subprocess.run(
            ["gh", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            raise ReviewGatewayError(
                completed.stderr.strip() or completed.stdout.strip() or f"{label} failed"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ReviewGatewayError(f"{label} returned invalid JSON") from exc

    def _paginated_array(self, endpoint: str, label: str) -> list[object]:
        pages = _array(
            self._run_json(("api", "--paginate", "--slurp", endpoint), label),
            f"{label} pages",
        )
        flattened: list[object] = []
        for page in pages:
            flattened.extend(_array(page, f"{label} page"))
        return flattened

    def _pull_request(self, head_sha: str) -> tuple[str, int]:
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
        if event_path:
            payload = _object(
                json.loads(Path(event_path).read_text(encoding="utf-8")),
                "GitHub event",
            )
            pull_request = _object(payload.get("pull_request"), "pull_request")
            head = _object(pull_request.get("head"), "pull_request.head")
            if _text(head, "sha") != head_sha:
                raise ReviewGatewayError("GitHub event head does not match the checked-out HEAD")
            number = pull_request.get("number")
            if not isinstance(number, int):
                raise ReviewGatewayError("pull_request.number must be an integer")
            if not repository:
                base = _object(pull_request.get("base"), "pull_request.base")
                repo = _object(base.get("repo"), "pull_request.base.repo")
                repository = _text(repo, "full_name")
            return repository, number

        view = _object(
            self._run_json(
                ("pr", "view", "--json", "number,headRefOid,baseRepository"),
                "gh pr view",
            ),
            "gh pr view",
        )
        if _text(view, "headRefOid") != head_sha:
            raise ReviewGatewayError("GitHub pull-request head does not match local HEAD")
        number = view.get("number")
        if not isinstance(number, int):
            raise ReviewGatewayError("pull request number must be an integer")
        if not repository:
            base_repository = _object(view.get("baseRepository"), "baseRepository")
            repository = _text(base_repository, "nameWithOwner")
        return repository, number

    def snapshot_for_head(self, head_sha: str) -> PullRequestSnapshot:
        repository, number = self._pull_request(head_sha)
        raw_commits = self._paginated_array(
            f"repos/{repository}/pulls/{number}/commits?per_page=100",
            "pull-request commits",
        )
        commits: list[PullRequestCommit] = []
        for item in raw_commits:
            summary = _object(item, "pull-request commit")
            sha = _text(summary, "sha")
            commit_data = _object(summary.get("commit"), "commit")
            committer = _object(commit_data.get("committer"), "commit.committer")
            detail = _object(
                self._run_json(("api", f"repos/{repository}/commits/{sha}"), "commit detail"),
                "commit detail",
            )
            files = _array(detail.get("files"), "commit files")
            commits.append(
                PullRequestCommit(
                    sha,
                    _timestamp(_text(committer, "date"), "commit.committer.date"),
                    tuple(_text(_object(file, "commit file"), "filename") for file in files),
                )
            )

        raw_reviews = self._paginated_array(
            f"repos/{repository}/pulls/{number}/reviews?per_page=100",
            "pull-request reviews",
        )
        reviews: list[PullRequestReview] = []
        for item in raw_reviews:
            review = _object(item, "pull-request review")
            submitted = review.get("submitted_at")
            if not isinstance(submitted, str) or not submitted:
                continue
            url = review.get("html_url")
            reviews.append(
                PullRequestReview(
                    _timestamp(submitted, "review.submitted_at"),
                    _text(review, "state").upper(),
                    url if isinstance(url, str) and url else None,
                )
            )
        return PullRequestSnapshot(tuple(commits), tuple(reviews))
