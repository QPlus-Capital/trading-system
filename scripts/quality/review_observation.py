"""Observe independent pull-request review from GitHub commit and review data."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, cast

from scripts.quality.classify import REPO_ROOT

ReviewStatus = Literal["verified", "rejected", "unverifiable"]
_TASK_ARTIFACT_NAMES = frozenset({"impact.md", "test-plan.md", "review.md", "evidence.md"})
_TASK_REFERENCE = re.compile(r"\.ai/tasks/(?P<task_id>[A-Za-z0-9._-]+)/")
_NON_BLOCKING_STATES = frozenset({"APPROVED", "COMMENTED"})
_DECISIVE_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED"})


@dataclass(frozen=True)
class PullRequestCommit:
    """One pull-request commit with the paths needed to classify its scope."""

    sha: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class PullRequestReview:
    """One submitted GitHub review bound to GitHub's authoritative commit identity."""

    submitted_at: datetime
    state: str
    url: str | None
    commit_id: str
    author: str
    review_id: int


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


def _normalized_task_artifact(path: str) -> tuple[str, str] | None:
    normalized = path.strip().replace("\\", "/")
    parts = normalized.split("/")
    if (
        len(parts) != 4
        or parts[:2] != [".ai", "tasks"]
        or parts[2] in {"", "_templates"}
        or parts[3] not in _TASK_ARTIFACT_NAMES
    ):
        return None
    return parts[2], parts[3]


def only_task_artifacts(paths: Sequence[str], *, task_id: str) -> bool:
    """Return true only for audit files belonging to the task under review."""

    normalized = tuple(path for path in paths if path.strip())
    if not normalized:
        return False
    return all(
        (artifact := _normalized_task_artifact(path)) is not None and artifact[0] == task_id
        for path in normalized
    )


def task_artifact_only_synchronization(
    action: str,
    paths: Sequence[str],
    *,
    task_id: str,
) -> bool:
    """Select reduced CI only for an observed current-task synchronization diff."""

    return action == "synchronize" and only_task_artifacts(paths, task_id=task_id)


def detect_task_artifact_only_synchronization(
    action: str,
    before_sha: str,
    task_id: str,
    *,
    root: Path = REPO_ROOT,
) -> bool:
    """Read the real no-rename Git delta; any Git failure selects the full CI set."""

    if action != "synchronize" or not before_sha or not task_id:
        return False
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", before_sha, "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    paths = tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())
    return task_artifact_only_synchronization(action, paths, task_id=task_id)


def task_id_from_pr_body(body: str) -> str | None:
    """Return one unambiguous task artifact identifier from a pull-request body."""

    task_ids = tuple(
        dict.fromkeys(match.group("task_id") for match in _TASK_REFERENCE.finditer(body))
    )
    return task_ids[0] if len(task_ids) == 1 and task_ids[0] != "_templates" else None


def _reviewer_states(
    reviews: Sequence[PullRequestReview],
) -> tuple[PullRequestReview, ...]:
    """Reduce submitted reviews to each reviewer's current meaningful state."""

    grouped: dict[str, list[PullRequestReview]] = defaultdict(list)
    for review in reviews:
        if review.state != "DISMISSED":
            grouped[review.author].append(review)

    current: list[PullRequestReview] = []
    for author_reviews in grouped.values():
        selected: PullRequestReview | None = None
        by_time: dict[datetime, list[PullRequestReview]] = defaultdict(list)
        for review in author_reviews:
            by_time[review.submitted_at].append(review)
        for submitted_at in sorted(by_time):
            simultaneous = by_time[submitted_at]
            changes_requested = [
                review for review in simultaneous if review.state == "CHANGES_REQUESTED"
            ]
            approvals = [review for review in simultaneous if review.state == "APPROVED"]
            other_decisive = [
                review
                for review in simultaneous
                if review.state not in _NON_BLOCKING_STATES | {"DISMISSED"}
            ]
            comments = [review for review in simultaneous if review.state == "COMMENTED"]
            if changes_requested:
                selected = max(changes_requested, key=lambda review: review.review_id)
            elif approvals:
                selected = max(approvals, key=lambda review: review.review_id)
            elif other_decisive:
                selected = max(other_decisive, key=lambda review: review.review_id)
            elif comments and (selected is None or selected.state not in _DECISIVE_STATES):
                selected = max(comments, key=lambda review: review.review_id)
        if selected is not None:
            current.append(selected)
    return tuple(current)


def observe_independent_review(
    gateway: ReviewGateway,
    head_sha: str,
    task_id: str,
) -> ReviewObservation:
    """Require a non-blocking review bound to the current non-artifact code state."""

    try:
        snapshot = gateway.snapshot_for_head(head_sha)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return ReviewObservation(
            "unverifiable",
            f"independent review is UNVERIFIABLE: {type(exc).__name__}: {exc}",
            None,
        )

    commit_indexes = {commit.sha: index for index, commit in enumerate(snapshot.commits)}
    relevant_indexes = tuple(
        index
        for index, commit in enumerate(snapshot.commits)
        if not only_task_artifacts(commit.paths, task_id=task_id)
    )
    if not relevant_indexes:
        return ReviewObservation(
            "rejected",
            "pull request has no non-task-artifact commit to review",
            None,
        )
    last_change_index = relevant_indexes[-1]
    last_change = snapshot.commits[last_change_index]
    current_reviews = tuple(
        review
        for review in snapshot.reviews
        if commit_indexes.get(review.commit_id, -1) >= last_change_index
    )
    states = _reviewer_states(current_reviews)
    if not states:
        return ReviewObservation(
            "rejected",
            f"no submitted PR review is bound to current non-artifact commit {last_change.sha}",
            None,
        )
    blocking = tuple(review for review in states if review.state not in _NON_BLOCKING_STATES)
    if blocking:
        latest_blocking = max(
            blocking,
            key=lambda review: (review.submitted_at, review.review_id, review.author),
        )
        return ReviewObservation(
            "rejected",
            f"current PR review has blocking state {latest_blocking.state}",
            latest_blocking.url,
        )
    latest = max(
        states,
        key=lambda review: (review.submitted_at, review.review_id, review.author),
    )
    return ReviewObservation(
        "verified",
        f"independent PR review is bound to current non-artifact commit {last_change.sha}",
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


def _integer(data: Mapping[str, object], name: str) -> int:
    value = data.get(name)
    if type(value) is not int:
        raise ReviewGatewayError(f"{name} must be an integer")
    return value


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewGatewayError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReviewGatewayError(f"{label} must include a timezone")
    return parsed


def _commit_paths(files: Sequence[object]) -> tuple[str, ...]:
    paths: list[str] = []
    for item in files:
        file = _object(item, "commit file")
        paths.append(_text(file, "filename"))
        previous = file.get("previous_filename")
        if previous is not None:
            if not isinstance(previous, str) or not previous:
                raise ReviewGatewayError("previous_filename must be a non-empty string")
            paths.append(previous)
    return tuple(dict.fromkeys(paths))


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

    def _commit_files(self, repository: str, sha: str) -> list[object]:
        pages = _array(
            self._run_json(
                (
                    "api",
                    "--paginate",
                    "--slurp",
                    f"repos/{repository}/commits/{sha}?per_page=100",
                ),
                "commit detail",
            ),
            "commit detail pages",
        )
        files: list[object] = []
        for page in pages:
            detail = _object(page, "commit detail page")
            files.extend(_array(detail.get("files"), "commit files"))
        if not pages:
            raise ReviewGatewayError("commit detail returned no pages")
        return files

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
            number = _integer(pull_request, "number")
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
        number = _integer(view, "number")
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
            commits.append(
                PullRequestCommit(sha, _commit_paths(self._commit_files(repository, sha)))
            )
        if not commits or commits[-1].sha != head_sha:
            raise ReviewGatewayError(
                "paginated pull-request commit tail does not match the checked-out HEAD"
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
            user = _object(review.get("user"), "review.user")
            url = review.get("html_url")
            reviews.append(
                PullRequestReview(
                    _timestamp(submitted, "review.submitted_at"),
                    _text(review, "state").upper(),
                    url if isinstance(url, str) and url else None,
                    _text(review, "commit_id"),
                    _text(user, "login"),
                    _integer(review, "id"),
                )
            )
        return PullRequestSnapshot(tuple(commits), tuple(reviews))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ci-scope",))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Expose the fail-closed synchronization detector to the CI workflow."""

    _parser().parse_args(argv)
    task_id = task_id_from_pr_body(os.environ.get("PR_BODY", ""))
    reduced = task_id is not None and detect_task_artifact_only_synchronization(
        os.environ.get("EVENT_ACTION", ""),
        os.environ.get("BEFORE_SHA", ""),
        task_id,
    )
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is required")
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(f"only={str(reduced).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
