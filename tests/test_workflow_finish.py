"""A merged ticket is removed only after every destructive precondition is proven."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from workflow import board, finish

ISSUE = 152
BRANCH = "codex/152-finish-command"
_REAL_SUBPROCESS_RUN = subprocess.run
REGENERABLE_IGNORED_STATE = (
    ".venv/",
    "__pycache__/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".vscode/",
    "mutants/",
    "workflow/impact/test-map.json",
)


@dataclass(frozen=True)
class TicketRepository:
    repository: Path
    worktree: Path
    remote: Path
    branch_tip: str


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    completed = _REAL_SUBPROCESS_RUN(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def _set_ref(git_dir: Path, ref: str, oid: str, *, delete: bool = False) -> None:
    args = ("-d", ref, oid) if delete else (ref, oid)
    _git(git_dir.parent, f"--git-dir={git_dir}", "update-ref", *args)


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
def ticket_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TicketRepository:
    remote = tmp_path / "origin.git"
    repository = tmp_path / "repository"
    worktree = tmp_path / "ticket-worktree"

    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    _git(tmp_path, "init", "--initial-branch=main", str(repository))
    _git(repository, "config", "user.email", "tests@example.invalid")
    _git(repository, "config", "user.name", "Workflow tests")
    (repository / "README.md").write_text("main\n", encoding="utf-8")
    (repository / ".gitignore").write_text(
        ".env\n"
        "data/\n"
        "catalog/\n"
        "results/\n"
        "reports/\n"
        "workflow/mutation-results/\n"
        ".venv/\n"
        "__pycache__/\n"
        ".mypy_cache/\n"
        ".pytest_cache/\n"
        ".ruff_cache/\n"
        ".vscode/\n"
        "mutants/\n"
        "workflow/impact/test-map.json\n",
        encoding="utf-8",
    )
    _git(repository, "add", "README.md", ".gitignore")
    _git(repository, "commit", "-m", "initial")
    _git(repository, "config", "remote.origin.url", str(remote))
    _git(
        repository,
        "config",
        "remote.origin.fetch",
        "+refs/heads/*:refs/remotes/origin/*",
    )
    (remote / "objects" / "info" / "alternates").write_bytes(
        ((repository / ".git" / "objects").resolve().as_posix() + "\n").encode("utf-8")
    )
    main_tip = _git(repository, "rev-parse", "HEAD")
    _set_ref(remote, "refs/heads/main", main_tip)
    _set_ref(repository / ".git", "refs/remotes/origin/main", main_tip)

    _git(repository, "worktree", "add", "-b", BRANCH, str(worktree), "main")
    _git(worktree, "config", "user.email", "tests@example.invalid")
    _git(worktree, "config", "user.name", "Workflow tests")
    (worktree / "ticket.txt").write_text("ticket\n", encoding="utf-8")
    _git(worktree, "add", "ticket.txt")
    _git(worktree, "commit", "-m", "ticket")
    branch_tip = _git(worktree, "rev-parse", "HEAD")
    _set_ref(remote, f"refs/heads/{BRANCH}", branch_tip)
    _set_ref(repository / ".git", f"refs/remotes/origin/{BRANCH}", branch_tip)

    _git(repository, "merge", "--squash", BRANCH)
    _git(repository, "commit", "-m", "squash ticket")
    merged_tip = _git(repository, "rev-parse", "HEAD")
    _set_ref(remote, "refs/heads/main", merged_tip)
    _set_ref(repository / ".git", "refs/remotes/origin/main", merged_tip)
    ticket = TicketRepository(repository, worktree, remote, branch_tip)
    _record_commands(monkeypatch, ticket)
    return ticket


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
        ticket.remote.parent,
        f"--git-dir={ticket.remote}",
        "show-ref",
        "--verify",
        "--hash",
        f"refs/heads/{branch}",
        check=False,
    )
    return value or None


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


def _card_payload() -> dict[str, object]:
    return {
        "data": {
            "repository": {
                "issue": {
                    "number": ISSUE,
                    "title": "Finish a merged ticket",
                    "state": "CLOSED",
                    "labels": {"nodes": [{"name": "risk:R3"}]},
                    "projectItems": {
                        "nodes": [
                            {
                                "id": "item",
                                "project": {"id": "project", "number": 1, "title": "Workflow"},
                                "fieldValueByName": {
                                    "name": "Done",
                                    "field": {
                                        "id": "field",
                                        "options": [{"id": "done", "name": "Done"}],
                                    },
                                },
                            }
                        ]
                    },
                }
            }
        }
    }


def _pull_request_payload(ticket: TicketRepository) -> dict[str, object]:
    return {
        "data": {
            "repository": {
                "issue": {
                    "closedByPullRequestsReferences": {
                        "nodes": [
                            {
                                "state": "MERGED",
                                "headRefName": BRANCH,
                                "headRefOid": ticket.branch_tip,
                                "headRepository": {"nameWithOwner": "QPlus-Capital/trading-system"},
                            }
                        ]
                    }
                }
            }
        }
    }


def _board_read_command() -> tuple[str, ...]:
    return (
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={board._CARD_QUERY}",
        "-f",
        f"owner={board._OWNER}",
        "-f",
        f"repo={board._REPO}",
        "-F",
        f"number={ISSUE}",
    )


def _pull_request_read_command() -> tuple[str, ...]:
    return (
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={finish._CLOSING_PULL_REQUESTS}",
        "-f",
        f"owner={board._OWNER}",
        "-f",
        f"repo={board._REPO}",
        "-F",
        f"number={ISSUE}",
    )


def _allowed_finish_command(command: tuple[str, ...], ticket: TicketRepository) -> bool:
    exact = {
        ("git", "branch", "--list", "--format=%(refname:short)"),
        ("git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"),
        ("git", "fetch", "origin", "main"),
        ("git", "worktree", "list", "--porcelain"),
        ("git", "status", "--porcelain", "--untracked-files=all"),
        ("git", "worktree", "remove", str(ticket.worktree.resolve())),
        ("git", "branch", "-D", "--", BRANCH),
        ("git", "ls-remote", "--heads", "origin"),
        ("git", "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}"),
        ("git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"),
        ("git", "rev-parse", "--verify", "--quiet", f"refs/heads/{BRANCH}"),
        (
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/remotes/origin/{BRANCH}",
        ),
        (
            "git",
            "merge-base",
            "--is-ancestor",
            ticket.branch_tip,
            "refs/remotes/origin/main",
        ),
        (
            "git",
            "push",
            f"--force-with-lease=refs/heads/{BRANCH}:{ticket.branch_tip}",
            "origin",
            f":refs/heads/{BRANCH}",
        ),
        (
            "git",
            "update-ref",
            "-d",
            f"refs/remotes/origin/{BRANCH}",
            ticket.branch_tip,
        ),
        _board_read_command(),
        _pull_request_read_command(),
    }
    local_ancestry_check = command[:3] == ("git", "merge-base", "--is-ancestor")
    return command in exact or (local_ancestry_check and len(command) == 5)


def _record_commands(
    monkeypatch: pytest.MonkeyPatch,
    ticket: TicketRepository,
) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []

    def record(
        args: Sequence[str],
        *positional: Any,
        **keywords: Any,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(str(part) for part in args)
        commands.append(command)
        if command == _board_read_command():
            return subprocess.CompletedProcess(
                list(args), 0, stdout=json.dumps(_card_payload()), stderr=""
            )
        if command == _pull_request_read_command():
            return subprocess.CompletedProcess(
                list(args), 0, stdout=json.dumps(_pull_request_payload(ticket)), stderr=""
            )
        if not _allowed_finish_command(command, ticket):
            return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")
        if command == ("git", "fetch", "origin", "main"):
            main_tip = _git(
                ticket.remote.parent,
                f"--git-dir={ticket.remote}",
                "show-ref",
                "--verify",
                "--hash",
                "refs/heads/main",
            )
            _set_ref(ticket.repository / ".git", "refs/remotes/origin/main", main_tip)
            return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")
        if command[:2] == ("git", "ls-remote"):
            if len(command) == 5:
                branch = command[4].removeprefix("refs/heads/")
                tip = _remote_ref(ticket, branch)
                stdout = f"{tip}\trefs/heads/{branch}\n" if tip is not None else ""
            else:
                stdout = _git(
                    ticket.remote.parent,
                    f"--git-dir={ticket.remote}",
                    "for-each-ref",
                    "--format=%(objectname)%09%(refname)",
                    "refs/heads",
                )
                if stdout:
                    stdout += "\n"
            return subprocess.CompletedProcess(list(args), 0, stdout=stdout, stderr="")
        if command[:2] == ("git", "push"):
            expected = command[2].rsplit(":", maxsplit=1)[-1]
            if _remote_ref(ticket) != expected:
                return subprocess.CompletedProcess(list(args), 1, stdout="", stderr="stale info")
            _set_ref(ticket.remote, f"refs/heads/{BRANCH}", expected, delete=True)
            return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")
        return _REAL_SUBPROCESS_RUN(args, *positional, **keywords)

    monkeypatch.setattr(subprocess, "run", record)
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
    commands = _record_commands(monkeypatch, ticket_repository)

    with pytest.raises(
        finish.FinishError,
        match=r"^the target worktree contains modified or untracked files$",
    ):
        _finish(ticket_repository)

    assert path.exists()
    assert _artifact_snapshot(ticket_repository) == before
    assert not any(command[:3] == ("git", "worktree", "remove") for command in commands)


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
    invocation_dir = ticket_repository.worktree / "nested" / "directory"
    invocation_dir.mkdir(parents=True)

    with pytest.raises(finish.FinishError, match="running inside"):
        finish.finish_ticket(
            ISSUE,
            repo_root=ticket_repository.repository,
            invocation_dir=invocation_dir,
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
        _set_ref(
            ticket_repository.remote,
            f"refs/heads/{BRANCH}",
            ticket_repository.branch_tip,
            delete=True,
        )
        _set_ref(
            ticket_repository.repository / ".git",
            f"refs/remotes/origin/{BRANCH}",
            ticket_repository.branch_tip,
            delete=True,
        )
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
    other_tip = _git(ticket_repository.repository, "rev-parse", other)
    _set_ref(ticket_repository.remote, f"refs/heads/{other}", other_tip)
    _set_ref(ticket_repository.repository / ".git", f"refs/remotes/origin/{other}", other_tip)
    other_tracking = _tracking_ref(ticket_repository.repository, other)
    _set_ref(ticket_repository.remote, f"refs/heads/{other}", other_tip, delete=True)
    _set_ref(
        ticket_repository.remote,
        f"refs/heads/{BRANCH}",
        ticket_repository.branch_tip,
        delete=True,
    )
    _prepare(monkeypatch, ticket_repository)
    commands = _record_commands(monkeypatch, ticket_repository)

    _finish(ticket_repository)

    assert _tracking_ref(ticket_repository.repository, other) == other_tracking
    assert _remote_ref(ticket_repository, other) is None
    assert (
        "git",
        "update-ref",
        "-d",
        f"refs/remotes/origin/{BRANCH}",
        ticket_repository.branch_tip,
    ) in commands
    assert not any("--prune" in command for command in commands)


def test_a_second_run_reports_nothing_left_to_finish(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    _finish(ticket_repository)

    result = _finish(ticket_repository)

    assert result.nothing_to_finish
    assert result.removed == ()


def test_protected_local_state_in_the_worktree_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    tmp_path: Path,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    contract = tmp_path / "controlled-workflow.toml"
    protected_path = ".venv/controlled-state.json"
    contract.write_text(
        f'[finish]\nprotected_worktree_paths = ["{protected_path}"]\n',
        encoding="utf-8",
    )
    read_protected_paths = finish.load_protected_paths
    monkeypatch.setattr(
        finish,
        "load_protected_paths",
        lambda: read_protected_paths(contract),
    )
    protected = ticket_repository.worktree / protected_path
    protected.parent.mkdir(parents=True)
    protected.write_text("irreplaceable\n", encoding="utf-8")
    before = _artifact_snapshot(ticket_repository)
    commands = _record_commands(monkeypatch, ticket_repository)

    with pytest.raises(finish.FinishError, match=re.escape(protected_path)):
        _finish(ticket_repository)

    assert protected.exists()
    assert _artifact_snapshot(ticket_repository) == before
    assert not any(command[:3] == ("git", "worktree", "remove") for command in commands)


def test_an_empty_protected_directory_does_not_block_the_teardown(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    """Running the suite inside the worktree leaves an empty ``catalog/`` behind — both real
    finishes so far (#152, #172) were refused over it. An empty directory holds no local state,
    so refusing over one would block every routine teardown."""
    _prepare(monkeypatch, ticket_repository)
    (ticket_repository.worktree / "catalog").mkdir()

    _finish(ticket_repository)

    assert not ticket_repository.worktree.exists()


def test_an_empty_protected_directory_does_not_mask_later_protected_state(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    """The allowance is per entry: an empty `catalog/` must not end the scan before a later
    protected path with real content is seen."""
    _prepare(monkeypatch, ticket_repository)
    (ticket_repository.worktree / "catalog").mkdir()
    results = ticket_repository.worktree / "results"
    results.mkdir()
    (results / "run.json").write_text("real\n", encoding="utf-8")

    with pytest.raises(finish.FinishError, match="results"):
        _finish(ticket_repository)

    assert (results / "run.json").exists()


def test_a_protected_directory_with_content_still_refuses(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    catalog = ticket_repository.worktree / "catalog"
    catalog.mkdir()
    (catalog / "frame.parquet").write_bytes(b"data")
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="catalog"):
        _finish(ticket_repository)

    assert (catalog / "frame.parquet").exists()
    assert _artifact_snapshot(ticket_repository) == before


def test_regenerable_ignored_state_is_removed_with_the_worktree(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _prepare(monkeypatch, ticket_repository)
    for state_path in REGENERABLE_IGNORED_STATE:
        path = ticket_repository.worktree / state_path
        if state_path.endswith("/"):
            path.mkdir(parents=True)
            (path / "regenerable.bin").write_bytes(b"cache")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated\n", encoding="utf-8")

    _finish(ticket_repository)

    assert not ticket_repository.worktree.exists()


@pytest.mark.parametrize(
    "contract_body",
    [
        "[finish]\n",
        "[finish]\nprotected_worktree_paths = []\n",
        '[finish]\nprotected_worktree_paths = "data/"\n',
        "[finish]\nprotected_worktree_paths = [1]\n",
        '[finish]\nprotected_worktree_paths = ["/data/"]\n',
        '[finish]\nprotected_worktree_paths = ["C:/data/"]\n',
        '[finish]\nprotected_worktree_paths = ["../data/"]\n',
        "[finish]\nprotected_worktree_paths = ['..\\\\data\\\\']\n",
    ],
    ids=(
        "missing",
        "empty",
        "not-a-list",
        "non-string",
        "posix-absolute",
        "windows-absolute",
        "posix-parent",
        "windows-parent",
    ),
)
def test_an_unusable_protected_list_is_refused(
    tmp_path: Path,
    contract_body: str,
) -> None:
    contract = tmp_path / "unusable-workflow.toml"
    contract.write_text(contract_body, encoding="utf-8")

    with pytest.raises(finish.FinishError, match="protected worktree path"):
        finish.load_protected_paths(contract)


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


def test_a_failure_after_the_first_removal_is_not_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(monkeypatch, ticket_repository)
    real_apply = finish._apply
    real_finish = finish.finish_ticket
    advanced_oid = _git(ticket_repository.repository, "rev-parse", "origin/main")

    def advance_remote_then_apply(
        plan: finish.FinishPlan,
        repo_root: Path,
    ) -> finish.FinishResult:
        _set_ref(ticket_repository.remote, f"refs/heads/{BRANCH}", advanced_oid)
        return real_apply(plan, repo_root)

    monkeypatch.setattr(finish, "_apply", advance_remote_then_apply)
    monkeypatch.setattr(
        finish,
        "finish_ticket",
        lambda issue: real_finish(
            issue,
            repo_root=ticket_repository.repository,
            invocation_dir=ticket_repository.repository,
        ),
    )

    assert finish.main([str(ISSUE)]) == 2
    output = capsys.readouterr().out
    assert output.startswith("PARTIAL: removed worktree, local branch;")
    assert "stale info" in output
    assert "re-run to finish" in output
    assert _remote_ref(ticket_repository) == advanced_oid

    def refuse(issue: int) -> finish.FinishResult:
        raise finish.FinishError("precondition failed")

    monkeypatch.setattr(finish, "finish_ticket", refuse)
    assert finish.main([str(ISSUE)]) == 1
    assert capsys.readouterr().out == "REFUSED: precondition failed\n"


@pytest.mark.parametrize("legacy", ["codex/issue-152-finish-command", "codex/152finish-command"])
@pytest.mark.parametrize("arrival", ["local", "pull-request"])
def test_a_legacy_branch_name_is_never_removed(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    legacy: str,
    arrival: str,
) -> None:
    if arrival == "local":
        _git(ticket_repository.worktree, "branch", "-m", legacy)
        pull_requests = (finish.MergedPullRequest(BRANCH, ticket_repository.branch_tip),)
    else:
        _set_ref(
            ticket_repository.remote,
            f"refs/heads/{legacy}",
            ticket_repository.branch_tip,
        )
        pull_requests = (finish.MergedPullRequest(legacy, ticket_repository.branch_tip),)
    _prepare(monkeypatch, ticket_repository, pull_requests=pull_requests)
    before = _artifact_snapshot(ticket_repository)
    legacy_oid = _local_ref(ticket_repository.repository, legacy)
    legacy_remote_oid = _remote_ref(ticket_repository, legacy)

    with pytest.raises(finish.FinishError, match="outside the contract pattern"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before
    assert _local_ref(ticket_repository.repository, legacy) == legacy_oid
    assert _remote_ref(ticket_repository, legacy) == legacy_remote_oid


def test_a_legacy_name_only_in_the_pull_request_record_does_not_refuse(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    legacy = "codex/111-152-review-path"
    _git(ticket_repository.repository, "worktree", "remove", str(ticket_repository.worktree))
    _git(ticket_repository.repository, "branch", "-D", BRANCH)
    _set_ref(
        ticket_repository.remote,
        f"refs/heads/{BRANCH}",
        ticket_repository.branch_tip,
        delete=True,
    )
    _set_ref(
        ticket_repository.repository / ".git",
        f"refs/remotes/origin/{BRANCH}",
        ticket_repository.branch_tip,
        delete=True,
    )
    _prepare(
        monkeypatch,
        ticket_repository,
        pull_requests=(finish.MergedPullRequest(legacy, ticket_repository.branch_tip),),
    )

    result = _finish(ticket_repository)

    assert result.nothing_to_finish
    assert result.removed == ()


@pytest.mark.parametrize("preserved_by", ["main", "pull-request"])
def test_the_branch_is_deleted_only_when_its_tip_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    preserved_by: str,
) -> None:
    if preserved_by == "main":
        _git(ticket_repository.repository, "reset", "--hard", BRANCH)
        main_tip = _git(ticket_repository.repository, "rev-parse", "main")
        _set_ref(ticket_repository.remote, "refs/heads/main", main_tip)
        _set_ref(ticket_repository.repository / ".git", "refs/remotes/origin/main", main_tip)
        requests: tuple[finish.MergedPullRequest, ...] = ()
    else:
        requests = (finish.MergedPullRequest(BRANCH, ticket_repository.branch_tip),)
    _prepare(monkeypatch, ticket_repository, pull_requests=requests)

    _finish(ticket_repository)

    assert _local_ref(ticket_repository.repository) is None


def test_a_tip_ahead_of_main_without_a_pull_request_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    _git(ticket_repository.worktree, "reset", "--hard", "origin/main")
    (ticket_repository.worktree / "ahead.txt").write_text("ahead\n", encoding="utf-8")
    _git(ticket_repository.worktree, "add", "ahead.txt")
    _git(ticket_repository.worktree, "commit", "-m", "ahead of main")
    ahead_tip = _git(ticket_repository.worktree, "rev-parse", BRANCH)
    _set_ref(ticket_repository.remote, f"refs/heads/{BRANCH}", ahead_tip)
    _set_ref(
        ticket_repository.repository / ".git",
        f"refs/remotes/origin/{BRANCH}",
        ahead_tip,
    )
    _prepare(monkeypatch, ticket_repository, pull_requests=())
    before = _artifact_snapshot(ticket_repository)

    with pytest.raises(finish.FinishError, match="not preserved"):
        _finish(ticket_repository)

    assert _artifact_snapshot(ticket_repository) == before


def test_the_merged_pull_request_record_is_read_from_github(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    monkeypatch.setattr(board, "read_card", lambda issue: _card())
    real_execute = finish._execute
    github_calls: list[tuple[str, ...]] = []
    payload = _pull_request_payload(ticket_repository)

    def execute(args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        if tuple(args[:3]) == ("gh", "api", "graphql"):
            github_calls.append(tuple(args))
            return subprocess.CompletedProcess(list(args), 0, json.dumps(payload), "")
        return real_execute(args, cwd=cwd)

    monkeypatch.setattr(finish, "_execute", execute)

    _finish(ticket_repository)

    assert len(github_calls) == 1
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
    monkeypatch.setattr(finish, "_branch_names", lambda *args: {"main"})
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
    if refused:
        (ticket_repository.worktree / "untracked.txt").write_text("refuse\n", encoding="utf-8")
    commands = _record_commands(monkeypatch, ticket_repository)

    if refused:
        with pytest.raises(finish.FinishError):
            _finish(ticket_repository)
    else:
        _finish(ticket_repository)

    assert commands
    assert all(_allowed_finish_command(command, ticket_repository) for command in commands)


@pytest.mark.parametrize("refused", [False, True], ids=["success", "refusal"])
def test_finish_never_writes_the_board_or_merges(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
    refused: bool,
) -> None:
    if refused:
        (ticket_repository.worktree / "untracked.txt").write_text("refuse\n", encoding="utf-8")
    commands = _record_commands(monkeypatch, ticket_repository)

    def unexpected_board_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("finish must never write the board")

    monkeypatch.setattr(board, "move", unexpected_board_write)
    if refused:
        with pytest.raises(finish.FinishError):
            _finish(ticket_repository)
    else:
        _finish(ticket_repository)

    assert commands
    assert all(_allowed_finish_command(command, ticket_repository) for command in commands)


def test_issue_numbers_match_on_digit_boundaries_not_substrings() -> None:
    """Regression (D-2): a substring test read `codex/152-...` as carrying issues 15, 52, 2 and 1,
    so finishing any of those refused while the 152 branch was live."""

    assert finish._carries_issue_number(152, BRANCH)
    for foreign_issue in (15, 52, 2, 1):
        assert not finish._carries_issue_number(foreign_issue, BRANCH), (
            f"issue {foreign_issue} must not claim {BRANCH!r}"
        )
    assert finish._carries_issue_number(95, "codex/issue-95-explicit-swap-direction")


def test_a_backslash_rooted_protected_entry_is_rejected(tmp_path: Path) -> None:
    """Regression (D-1): a backslash-rooted entry is not absolute on POSIX and not absolute on
    Windows either -- but it is *rooted* on Windows, so joinpath landed outside the worktree and
    the protection silently checked the wrong place."""

    for value in ("\\data", "C:data", "data\\sub"):
        contract = tmp_path / "contract.toml"
        contract.write_text(
            f"[finish]\nprotected_worktree_paths = [{value!r}]\n".replace("\\", "\\\\"),
            encoding="utf-8",
        )
        with pytest.raises(finish.FinishError, match="not repository-relative"):
            finish.load_protected_paths(contract)


def test_protected_state_lookup_fails_closed_outside_the_worktree(tmp_path: Path) -> None:
    """Even if a rooted entry slipped past validation, the point of use refuses rather than
    checking a path outside the worktree and concluding the state is absent.

    `/data` escapes on every platform; the backslash variant escapes only on Windows, which is
    exactly why validation rejects backslashes outright rather than trusting platform semantics.
    """

    worktree = tmp_path / "wt"
    worktree.mkdir()
    with pytest.raises(finish.FinishError, match="escapes the worktree"):
        finish._protected_local_state(worktree, ("/data",))


def test_the_repositorys_own_protected_list_binds(tmp_path: Path) -> None:
    """Regression (D-3): the suite bound only synthetic contract files, so dropping `.env` from
    the repository's real list deleted credentials with every test green."""

    values = set(finish.load_protected_paths())
    assert {".env", "data/", "catalog/", "results/", "reports/"} <= values, (
        "the contract's own protected list lost a load-bearing entry"
    )


def test_a_merged_pull_request_of_another_issue_never_resolves_to_a_branch(
    monkeypatch: pytest.MonkeyPatch,
    ticket_repository: TicketRepository,
) -> None:
    """Regression (D-4): without the ownership filter, a merged pull request whose head branch
    belongs to a *different* issue was adopted as this issue's branch and deleted."""

    _prepare(monkeypatch, ticket_repository)
    _finish(ticket_repository)  # tear down 152's own artifacts first

    foreign = "codex/95-other-work"
    _git(ticket_repository.repository, "branch", foreign, "origin/main")
    _prepare(
        monkeypatch,
        ticket_repository,
        pull_requests=(finish.MergedPullRequest(foreign, ticket_repository.branch_tip),),
    )

    result = _finish(ticket_repository)

    assert result.nothing_to_finish, "a foreign-issue record is not this issue's work"
    assert _local_ref(ticket_repository.repository, foreign) is not None, (
        "the foreign issue's live branch must survive"
    )
