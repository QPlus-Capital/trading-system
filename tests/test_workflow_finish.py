"""A merged ticket is removed only after every destructive precondition is proven."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from workflow import board, finish

ISSUE = 152
BRANCH = "codex/152-finish-command"


@dataclass(frozen=True)
class TicketRepository:
    repository: Path
    worktree: Path
    remote: Path
    branch_tip: str


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def _card(*, open_state: bool = False, status: str = "Done") -> board.Card:
    return board.Card(
        issue=ISSUE,
        title="Finish a merged ticket",
        open_state=open_state,
        status=status,
        labels=("risk:R3",),
        item_id="item",
        project_id="project",
        field_id="field",
        options={status: "option"},
    )


@pytest.fixture
def ticket_repository(tmp_path: Path) -> TicketRepository:
    remote = tmp_path / "origin.git"
    repository = tmp_path / "repository"
    worktree = tmp_path / "ticket-worktree"

    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    _git(tmp_path, "init", "--initial-branch=main", str(repository))
    _git(repository, "config", "user.email", "tests@example.invalid")
    _git(repository, "config", "user.name", "Workflow tests")
    (repository / "README.md").write_text("main\n", encoding="utf-8")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "-m", "initial")
    _git(repository, "remote", "add", "origin", str(remote))
    _git(repository, "push", "-u", "origin", "main")

    _git(repository, "worktree", "add", "-b", BRANCH, str(worktree), "main")
    _git(worktree, "config", "user.email", "tests@example.invalid")
    _git(worktree, "config", "user.name", "Workflow tests")
    (worktree / "ticket.txt").write_text("ticket\n", encoding="utf-8")
    _git(worktree, "add", "ticket.txt")
    _git(worktree, "commit", "-m", "ticket")
    branch_tip = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "push", "-u", "origin", BRANCH)

    _git(repository, "merge", "--squash", BRANCH)
    _git(repository, "commit", "-m", "squash ticket")
    _git(repository, "push", "origin", "main")
    _git(repository, "fetch", "origin")
    return TicketRepository(repository, worktree, remote, branch_tip)


def _prepare(
    monkeypatch: pytest.MonkeyPatch,
    ticket: TicketRepository,
    *,
    card: board.Card | None = None,
    pull_requests: tuple[finish.MergedPullRequest, ...] | None = None,
) -> None:
    monkeypatch.setattr(board, "read_card", lambda issue: card or _card())
    requests = pull_requests
    if requests is None:
        requests = (finish.MergedPullRequest(BRANCH, ticket.branch_tip),)
    monkeypatch.setattr(
        finish,
        "_read_merged_pull_requests",
        lambda issue, repo_root: requests,
    )


def _local_ref(repository: Path, branch: str = BRANCH) -> str | None:
    value = _git(repository, "show-ref", "--verify", "--hash", f"refs/heads/{branch}", check=False)
    return value or None


def _tracking_ref(repository: Path, branch: str = BRANCH) -> str | None:
    value = _git(
        repository,
        "show-ref",
        "--verify",
        "--hash",
        f"refs/remotes/origin/{branch}",
        check=False,
    )
    return value or None


def _remote_ref(ticket: TicketRepository, branch: str = BRANCH) -> str | None:
    value = _git(
        ticket.repository,
        "ls-remote",
        "--heads",
        "origin",
        f"refs/heads/{branch}",
    )
    return value.split()[0] if value else None


def _artifact_snapshot(ticket: TicketRepository) -> tuple[bool, str | None, str | None, str | None]:
    return (
        ticket.worktree.exists(),
        _local_ref(ticket.repository),
        _remote_ref(ticket),
        _tracking_ref(ticket.repository),
    )


def _finish(ticket: TicketRepository) -> finish.FinishResult:
    return finish.finish_ticket(
        ISSUE,
        repo_root=ticket.repository,
        invocation_dir=ticket.repository,
    )


def _record_commands(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    real_execute = finish._execute

    def record(args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(str(part) for part in args))
        return real_execute(args, cwd=cwd)

    monkeypatch.setattr(finish, "_execute", record)
    return commands


def test_finishing_a_merged_ticket_removes_worktree_branch_and_both_remote_traces(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)

    result = _finish(ticket_repository)

    assert result.removed == ("worktree", "local branch", "remote branch", "remote-tracking ref")
    assert _artifact_snapshot(ticket_repository) == (False, None, None, None)


def test_an_open_issue_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository, card=_card(open_state=True))
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="issue #152 is OPEN"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


@pytest.mark.parametrize(
    "status",
    ["Backlog", "Specifying", "Ready to Implement", "Implementing", "Reviewing", "Blocked"],
)
def test_a_card_that_is_not_done_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    status: str,
) -> None:
    _prepare(monkeypatch, ticket_repository, card=_card(status=status))
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match=rf"card is {status!r}"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


@pytest.mark.parametrize("untracked", [False, True], ids=["modified", "untracked"])
def test_uncommitted_or_untracked_work_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    untracked: bool,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    path = ticket_repository.worktree / ("new.txt" if untracked else "ticket.txt")
    path.write_text("not committed\n", encoding="utf-8")
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="modified or untracked"):
        _finish(ticket_repository)

    assert path.exists()
    assert _artifact_snapshot(ticket_repository) == before


def test_a_branch_tip_github_never_saw_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    (ticket_repository.worktree / "unpublished.txt").write_text("lost\n", encoding="utf-8")
    _git(ticket_repository.worktree, "add", "unpublished.txt")
    _git(ticket_repository.worktree, "commit", "-m", "unpublished")
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="tip .* is not preserved"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


def test_the_repositorys_own_checkout_is_never_removed(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    _git(ticket_repository.repository, "worktree", "remove", str(ticket_repository.worktree))
    _git(ticket_repository.repository, "switch", BRANCH)
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="repository's own checkout"):
        _finish(ticket_repository)

    assert ticket_repository.repository.exists()
    assert _artifact_snapshot(ticket_repository) == before


def test_running_from_inside_the_target_worktree_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="running inside"):
        finish.finish_ticket(
            ISSUE,
            repo_root=ticket_repository.repository,
            invocation_dir=ticket_repository.worktree,
        )

    assert _artifact_snapshot(ticket_repository) == before


@pytest.mark.parametrize("branch_count", [0, 2])
def test_ambiguous_branch_ownership_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    branch_count: int,
) -> None:
    if branch_count == 0:
        _git(ticket_repository.repository, "worktree", "remove", str(ticket_repository.worktree))
        _git(ticket_repository.repository, "branch", "-D", BRANCH)
        _git(ticket_repository.repository, "push", "origin", "--delete", BRANCH)
        pull_requests: tuple[finish.MergedPullRequest, ...] = ()
    else:
        _git(ticket_repository.repository, "branch", "codex/152-other", "main")
        pull_requests = (finish.MergedPullRequest(BRANCH, ticket_repository.branch_tip),)
    _prepare(monkeypatch, ticket_repository, pull_requests=pull_requests)
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match=rf"found {branch_count}"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


def test_only_this_tickets_remote_tracking_reference_is_pruned(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    other = "codex/999-other"
    _git(ticket_repository.repository, "branch", other, "main")
    _git(ticket_repository.repository, "push", "-u", "origin", other)
    other_tracking = _tracking_ref(ticket_repository.repository, other)
    _prepare(monkeypatch, ticket_repository)

    _finish(ticket_repository)

    assert _tracking_ref(ticket_repository.repository, other) == other_tracking
    assert _remote_ref(ticket_repository, other) is not None


def test_a_second_run_reports_nothing_left_to_finish(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    _finish(ticket_repository)

    result = _finish(ticket_repository)

    assert result.nothing_to_finish
    assert result.removed == ()


def test_an_interrupted_run_finishes_the_remaining_remote_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    _git(ticket_repository.repository, "worktree", "remove", str(ticket_repository.worktree))
    _git(ticket_repository.repository, "branch", "-D", BRANCH)

    result = _finish(ticket_repository)

    assert result.removed == ("remote branch", "remote-tracking ref")
    assert _artifact_snapshot(ticket_repository) == (False, None, None, None)


def test_a_worktree_directory_already_deleted_by_hand_still_finishes(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    shutil.rmtree(ticket_repository.worktree)

    result = _finish(ticket_repository)

    assert result.removed == ("worktree", "local branch", "remote branch", "remote-tracking ref")
    assert _artifact_snapshot(ticket_repository) == (False, None, None, None)


def test_a_failure_after_the_first_removal_is_reported_as_partial(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(monkeypatch, ticket_repository)
    real_run = finish._run
    real_finish = finish.finish_ticket

    def deny_push(args: Sequence[str], *, cwd: Path) -> str:
        if list(args[:2]) == ["git", "push"]:
            raise finish.FinishError("`git push` failed: remote rejected")
        return real_run(args, cwd=cwd)

    monkeypatch.setattr(finish, "_run", deny_push)
    monkeypatch.setattr(
        finish,
        "finish_ticket",
        lambda issue: real_finish(
            issue,
            repo_root=ticket_repository.repository,
            invocation_dir=ticket_repository.repository,
        ),
    )

    assert finish.main([str(ISSUE)]) == 1
    output = capsys.readouterr().out
    assert output.startswith("PARTIAL: removed worktree, local branch;")
    assert "re-run to finish" in output


@pytest.mark.parametrize("preserved_by", ["main", "pull-request"])
def test_the_branch_is_deleted_only_when_its_tip_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    preserved_by: str,
) -> None:
    if preserved_by == "main":
        _git(ticket_repository.repository, "reset", "--hard", BRANCH)
        _git(ticket_repository.repository, "push", "--force", "origin", "main")
        requests: tuple[finish.MergedPullRequest, ...] = ()
    else:
        requests = (finish.MergedPullRequest(BRANCH, ticket_repository.branch_tip),)
    _prepare(monkeypatch, ticket_repository, pull_requests=requests)

    _finish(ticket_repository)

    assert _local_ref(ticket_repository.repository) is None


def test_main_and_the_main_checkout_are_never_removable(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(
        monkeypatch,
        ticket_repository,
        pull_requests=(finish.MergedPullRequest("main", ticket_repository.branch_tip),),
    )
    monkeypatch.setattr(finish, "_current_issue_branch_names", lambda *args: {"main"})
    before = _git(ticket_repository.repository, "rev-parse", "main")

    with pytest.raises(finish.FinishError, match="main"):
        _finish(ticket_repository)

    assert _git(ticket_repository.repository, "rev-parse", "main") == before
    assert ticket_repository.repository.exists()


def test_a_refusal_removes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository, pull_requests=())
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="not preserved"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


@pytest.mark.parametrize("refused", [False, True], ids=["success", "refusal"])
def test_finish_never_touches_live_trading(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    refused: bool,
) -> None:
    _prepare(
        monkeypatch,
        ticket_repository,
        card=_card(open_state=refused),
    )
    commands = _record_commands(monkeypatch)

    if refused:
        with pytest.raises(finish.FinishError):
            _finish(ticket_repository)
    else:
        _finish(ticket_repository)

    forbidden = {"live", "live.run", "live-stop", "live-start", "runner"}
    assert not any(
        part.lower() in forbidden
        or part.lower().startswith("live-")
        or part.lower().startswith("runner-")
        for command in commands
        for part in command
    )


@pytest.mark.parametrize("refused", [False, True], ids=["success", "refusal"])
def test_finish_never_writes_the_board_or_merges(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    refused: bool,
) -> None:
    _prepare(
        monkeypatch,
        ticket_repository,
        card=_card(open_state=refused),
    )
    commands = _record_commands(monkeypatch)

    def unexpected_board_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("finish must never write the board")

    monkeypatch.setattr(board, "move", unexpected_board_write)
    if refused:
        with pytest.raises(finish.FinishError):
            _finish(ticket_repository)
    else:
        _finish(ticket_repository)

    lowered = [tuple(part.lower() for part in command) for command in commands]
    assert not any(command[:2] == ("gh", "issue") for command in lowered)
    assert not any(
        command[:3]
        in {
            ("gh", "pr", "merge"),
            ("gh", "pr", "review"),
            ("gh", "pr", "ready"),
        }
        for command in lowered
    )
    assert not any("workflow.board move" in " ".join(command) for command in lowered)
