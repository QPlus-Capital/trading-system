"""Remove every Git artifact left by one completed ticket, after proving it is safe.

The command handles one issue, accepts only the branch ownership rule shared with the orchestrator,
and constructs the complete removal plan before changing any Git state. A partially completed run
is safe to repeat.

CLI::

    uv run python -m workflow.finish 101
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow import board, orchestrate
from workflow.classify import REPO_ROOT

_REPOSITORY = "QPlus-Capital/trading-system"
_OWNER, _NAME = _REPOSITORY.split("/", maxsplit=1)

_CLOSING_PULL_REQUESTS = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    issue(number:$number) {
      closedByPullRequestsReferences(first:10) {
        nodes {
          state
          headRefName
          headRefOid
          headRepository { nameWithOwner }
        }
      }
    }
  }
}
"""


class FinishError(RuntimeError):
    """A teardown step that cannot prove it is safe."""


@dataclass(frozen=True)
class MergedPullRequest:
    """The GitHub preservation record for a ticket branch."""

    head_branch: str
    head_oid: str


@dataclass(frozen=True)
class Worktree:
    """A registered Git worktree and the local branch it holds, when attached."""

    path: Path
    branch: str | None


@dataclass(frozen=True)
class FinishPlan:
    """Every artifact and expected object ID captured before removal begins."""

    branch: str
    worktree: Path | None
    local_oid: str | None
    remote_oid: str | None
    tracking_oid: str | None


@dataclass(frozen=True)
class FinishResult:
    """A concise account of what the command found and removed."""

    removed: tuple[str, ...]
    nothing_to_finish: bool = False


def _execute(args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _run(args: Sequence[str], *, cwd: Path) -> str:
    completed = _execute(args, cwd=cwd)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise FinishError(f"`{' '.join(args[:2])}` failed{suffix}")
    return completed.stdout.strip()


def _read_merged_pull_requests(issue: int, repo_root: Path) -> tuple[MergedPullRequest, ...]:
    """Read the issue's closing pull requests without changing the issue."""

    raw = _run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={_CLOSING_PULL_REQUESTS}",
            "-f",
            f"owner={_OWNER}",
            "-f",
            f"repo={_NAME}",
            "-F",
            f"number={issue}",
        ],
        cwd=repo_root,
    )
    try:
        payload: Any = json.loads(raw)
        if payload.get("errors"):
            raise FinishError("GitHub rejected the closing pull-request query")
        node = payload["data"]["repository"]["issue"]
        entries = node["closedByPullRequestsReferences"]["nodes"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise FinishError("GitHub returned no usable closing pull-request record") from error
    if not isinstance(entries, list):
        raise FinishError("GitHub returned no usable closing pull-request record")

    result: list[MergedPullRequest] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise FinishError("GitHub returned a malformed closing pull-request record")
        repository = entry.get("headRepository") or {}
        if entry.get("state") != "MERGED" or repository.get("nameWithOwner") != _REPOSITORY:
            continue
        branch = str(entry.get("headRefName") or "")
        oid = str(entry.get("headRefOid") or "")
        if branch and oid:
            result.append(MergedPullRequest(branch, oid))
    return tuple(result)


def _ref_oid(repo_root: Path, ref: str) -> str | None:
    completed = _execute(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo_root)
    if completed.returncode == 1:
        return None
    if completed.returncode != 0:
        raise FinishError(f"Git could not inspect {ref!r}")
    return completed.stdout.strip()


def _remote_oid(repo_root: Path, branch: str) -> str | None:
    raw = _run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
        cwd=repo_root,
    )
    if not raw:
        return None
    lines = raw.splitlines()
    if len(lines) != 1:
        raise FinishError(f"the remote returned {len(lines)} tips for {branch!r}")
    return lines[0].split()[0]


def _worktrees(repo_root: Path) -> tuple[Worktree, ...]:
    raw = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    result: list[Worktree] = []
    for block in raw.split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value
        path = fields.get("worktree")
        if not path:
            continue
        branch_ref = fields.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        result.append(Worktree(Path(path).resolve(), branch))
    if not result:
        raise FinishError("Git returned no repository checkout")
    return tuple(result)


def _current_issue_branch_names(issue: int, repo_root: Path) -> set[str]:
    """Use the orchestrator's branch rule; teardown does not define ownership itself."""

    names = set(orchestrate.branches_for(issue, repo_root=repo_root))
    tracking = _run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
        cwd=repo_root,
    )
    remote = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)
    candidates = {
        line.strip().removeprefix("refs/remotes/origin/")
        for line in tracking.splitlines()
        if line.strip()
    }
    candidates.update(
        line.split(maxsplit=1)[1].removeprefix("refs/heads/")
        for line in remote.splitlines()
        if len(line.split(maxsplit=1)) == 2
    )
    names.update(branch for branch in candidates if orchestrate.issue_branch_matches(issue, branch))
    return names


def _is_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _is_ancestor(repo_root: Path, oid: str, descendant: str) -> bool:
    completed = _execute(["git", "merge-base", "--is-ancestor", oid, descendant], cwd=repo_root)
    if completed.returncode not in {0, 1}:
        raise FinishError(f"Git could not prove whether {oid} is preserved by {descendant}")
    return completed.returncode == 0


def _preserved(repo_root: Path, oid: str, pull_request_oid: str | None) -> bool:
    return oid == pull_request_oid or _is_ancestor(repo_root, oid, "refs/remotes/origin/main")


def _plan(issue: int, repo_root: Path, invocation_dir: Path) -> FinishPlan | None:
    card = board.read_card(issue)
    if card.open_state:
        raise FinishError(f"issue #{issue} is OPEN; it must be CLOSED")
    if card.status != "Done":
        raise FinishError(f"issue #{issue} card is {card.status!r}; expected 'Done'")

    pull_requests = _read_merged_pull_requests(issue, repo_root)
    local_branches = _current_issue_branch_names(issue, repo_root)
    if len(local_branches) > 1:
        raise FinishError(
            f"expected exactly one branch carrying issue #{issue}, found {len(local_branches)}"
        )

    if local_branches:
        branch = next(iter(local_branches))
    elif len(pull_requests) == 1:
        branch = pull_requests[0].head_branch
        if not orchestrate.issue_branch_matches(issue, branch):
            raise FinishError(
                f"branch {branch!r} cannot own issue #{issue}; main is never removable"
            )
    else:
        raise FinishError(f"expected exactly one branch carrying issue #{issue}, found 0")

    matching_pull_requests = tuple(pr for pr in pull_requests if pr.head_branch == branch)
    if len(matching_pull_requests) > 1:
        raise FinishError(f"issue #{issue} has more than one merged pull request for {branch!r}")
    if pull_requests and not matching_pull_requests:
        raise FinishError(f"branch {branch!r} does not own issue #{issue}'s merged pull request")
    pull_request_oid = matching_pull_requests[0].head_oid if matching_pull_requests else None

    _run(["git", "fetch", "origin", "main"], cwd=repo_root)
    if _ref_oid(repo_root, "refs/remotes/origin/main") is None:
        raise FinishError("origin/main is unavailable; preservation cannot be proven")

    local_oid = _ref_oid(repo_root, f"refs/heads/{branch}")
    tracking_oid = _ref_oid(repo_root, f"refs/remotes/origin/{branch}")
    remote_oid = _remote_oid(repo_root, branch)
    worktrees = _worktrees(repo_root)
    branch_worktrees = tuple(worktree for worktree in worktrees if worktree.branch == branch)
    if len(branch_worktrees) > 1:
        raise FinishError(f"branch {branch!r} is attached to more than one worktree")
    worktree = branch_worktrees[0].path if branch_worktrees else None

    if local_oid is None and remote_oid is None and tracking_oid is None and worktree is None:
        return None
    if branch == "main":
        raise FinishError("main is never removable")
    if worktree is not None:
        main_checkout = worktrees[0].path
        if worktree == main_checkout:
            raise FinishError("the repository's own checkout is never removed")
        if _is_inside(invocation_dir, worktree):
            raise FinishError("refusing while running inside the target worktree")
        status = _run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=worktree,
        )
        if status:
            raise FinishError("the target worktree contains modified or untracked files")

    oids = (oid for oid in {local_oid, remote_oid, tracking_oid} if oid is not None)
    for oid in oids:
        if not _preserved(repo_root, oid, pull_request_oid):
            raise FinishError(f"branch tip {oid} is not preserved on GitHub")

    return FinishPlan(branch, worktree, local_oid, remote_oid, tracking_oid)


def _apply(plan: FinishPlan, repo_root: Path) -> FinishResult:
    removed: list[str] = []
    if plan.worktree is not None:
        _run(["git", "worktree", "remove", str(plan.worktree)], cwd=repo_root)
        removed.append("worktree")
    if plan.local_oid is not None:
        _run(["git", "branch", "-D", "--", plan.branch], cwd=repo_root)
        removed.append("local branch")
    if plan.remote_oid is not None:
        _run(
            [
                "git",
                "push",
                f"--force-with-lease=refs/heads/{plan.branch}:{plan.remote_oid}",
                "origin",
                f":refs/heads/{plan.branch}",
            ],
            cwd=repo_root,
        )
        removed.append("remote branch")
    if plan.tracking_oid is not None:
        tracking_ref = f"refs/remotes/origin/{plan.branch}"
        current_oid = _ref_oid(repo_root, tracking_ref)
        if current_oid is not None:
            _run(
                ["git", "update-ref", "-d", tracking_ref, plan.tracking_oid],
                cwd=repo_root,
            )
        removed.append("remote-tracking ref")
    return FinishResult(tuple(removed))


def finish_ticket(
    issue: int,
    *,
    repo_root: Path = REPO_ROOT,
    invocation_dir: Path | None = None,
) -> FinishResult:
    """Finish one completed ticket, or refuse before the first removal."""

    root = repo_root.resolve()
    plan = _plan(issue, root, (invocation_dir or Path.cwd()).resolve())
    if plan is None:
        return FinishResult((), nothing_to_finish=True)
    return _apply(plan, root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue", type=int)
    args = parser.parse_args(argv)
    try:
        result = finish_ticket(args.issue)
    except (FinishError, board.BoardError, orchestrate.OrchestrationError) as error:
        print(f"REFUSED: {error}")
        return 1
    if result.nothing_to_finish:
        print(f"#{args.issue}: nothing left to finish")
    else:
        print(f"#{args.issue}: removed {', '.join(result.removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
