"""Drive one issue from a pushed branch to a merge-ready pull request, without the operator.

Codex pushes and opens the pull request. From there this connects the two agents:

    gates -> review (fresh Claude process) -> blocking findings? -> back to Codex -> review again

It decides nothing. The risk class decides the gates, the contract decides the transitions, and the
reviewer decides the findings. What this owns is sequencing, the round cap, and telling the operator
once -- when the change is ready to merge, or when it needs a decision only they can make.

**The verdict is read, not interpreted.** The reviewer ends its summary with a machine-readable
marker; this counts blocking findings from that marker. Parsing prose for words like "looks good"
would make the loop's exit condition a matter of phrasing.

**Only the operator merges.** Nothing here merges, approves, or marks anything ready.

CLI::

    uv run python -m workflow.orchestrate run 101
    uv run python -m workflow.orchestrate run 101 --max-rounds 2 --dry-run
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from workflow import board, gates
from workflow.classify import REPO_ROOT, changed_paths

#: The reviewer writes this into its summary comment. Counting a structured marker keeps the loop's
#: exit condition out of the reviewer's prose.
VERDICT = re.compile(
    r"<!--\s*workflow-verdict\s+blocking:\s*(?P<blocking>\d+)\s+advisory:\s*(?P<advisory>\d+)\s*-->"
)
SESSION_MARKER = re.compile(r"<!--\s*claude-session:\s*(?P<session>[A-Za-z0-9_-]+)\s*-->")

_MAX_ROUNDS = 2


class OrchestrationError(RuntimeError):
    """A step that must stop rather than guess."""


@dataclass(frozen=True)
class Verdict:
    """What the last review concluded."""

    blocking: int
    advisory: int

    @property
    def clean(self) -> bool:
        return self.blocking == 0


def _executable(name: str) -> str:
    """Resolve an agent CLI to a concrete path, or stop.

    On Windows, ``codex`` resolves through a ``.cmd`` shim that ``CreateProcess`` cannot start by
    bare name — the spawn raised ``FileNotFoundError`` and the fix round silently never began.
    ``shutil.which`` honours PATHEXT and finds it; a missing CLI is an explicit refusal rather than
    a traceback.
    """

    path = shutil.which(name)
    if path is None:
        raise OrchestrationError(f"the {name!r} CLI is not on PATH; the cycle cannot run headless")
    return path


def _run(
    args: Sequence[str],
    *,
    capture: bool = True,
    cwd: Path = REPO_ROOT,
) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OrchestrationError(f"`{args[0]} {args[1] if len(args) > 1 else ''}` failed")
    return (completed.stdout or "").strip()


def issue_branch_matches(issue: int, branch: str) -> bool:
    """Whether ``branch`` is an agent branch owned by ``issue`` under the contract."""

    return re.fullmatch(rf"(?:codex|claude)/{issue}-[\w.-]+", branch) is not None


def branches_for(issue: int, *, repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """All local branches carrying ``issue``, using the one ownership definition."""

    listing = _run(
        ["git", "branch", "--list", "--format=%(refname:short)"],
        cwd=repo_root,
    )
    return tuple(
        line.strip() for line in listing.splitlines() if issue_branch_matches(issue, line.strip())
    )


def branch_for(issue: int, *, repo_root: Path = REPO_ROOT) -> str:
    """The one branch that carries this issue number, or an error.

    Ownership follows the branch, not the card: the card cannot say who wrote the code.
    """

    matches = branches_for(issue, repo_root=repo_root)
    if len(matches) != 1:
        raise OrchestrationError(
            f"expected exactly one branch for issue #{issue}, found {len(matches)}"
        )
    return matches[0].strip()


def pull_request_for(issue: int) -> int:
    """The pull request the issue's branch owns. Its number never reaches operator-facing text."""

    raw = _run(
        ["gh", "pr", "list", "--head", branch_for(issue), "--state", "open", "--json", "number"]
    )
    entries = json.loads(raw or "[]")
    if len(entries) != 1:
        raise OrchestrationError(
            f"expected exactly one open pull request for issue #{issue}, found {len(entries)}"
        )
    return int(entries[0]["number"])


def latest_verdict(pull_request: int) -> Verdict | None:
    """The most recent structured verdict on the pull request, or None if no review has landed.

    A pull-request review lands in ``reviews``, not ``comments`` — the first version of this
    function read only ``comments`` and could therefore never see a verdict, so the loop's one
    exit condition was unreadable. Both lists are scanned newest-first, reviews before comments,
    because the reviewer submits a real review and a comment is only ever a fallback.
    """

    raw = _run(["gh", "pr", "view", str(pull_request), "--json", "reviews,comments"])
    payload = json.loads(raw or "{}")
    reviews = [str(entry.get("body", "")) for entry in payload.get("reviews", [])]
    comments = [str(entry.get("body", "")) for entry in payload.get("comments", [])]
    for body in [*reversed(reviews), *reversed(comments)]:
        match = VERDICT.search(body)
        if match:
            return Verdict(int(match["blocking"]), int(match["advisory"]))
    return None


def session_for(issue: int) -> str | None:
    """The Claude session that specified this issue, recorded on it in phase 0."""

    raw = _run(["gh", "issue", "view", str(issue), "--json", "body,comments"])
    payload = json.loads(raw or "{}")
    haystack = str(payload.get("body", "")) + "\n".join(
        str(comment.get("body", "")) for comment in payload.get("comments", [])
    )
    match = SESSION_MARKER.search(haystack)
    return match["session"] if match else None


def notify(issue: int, message: str, *, dry_run: bool = False) -> None:
    """Reach the operator in the ticket's own chat, and on the desktop as the reliable signal.

    The operator never has to decide anything inside GitHub; the chat carries the detail.
    """

    print(f"\n>>> #{issue}: {message}")
    if dry_run:
        return
    session = session_for(issue)
    if session:
        subprocess.run(
            [_executable("claude"), "-p", "--resume", session, f"Status zu #{issue}: {message}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


#: What the headless reviewer may do without anyone there to approve: read the ticket and the pull
#: request, post the one review, and inspect the branch. The first real run showed why this list
#: must exist — the reviewer did its work, then could not post it, and the loop ended with "no
#: verdict" because `gh` sat waiting for an approval nobody was present to give.
_REVIEWER_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "Bash(gh issue view:*)",
    "Bash(gh pr view:*)",
    "Bash(gh pr diff:*)",
    "Bash(gh pr list:*)",
    "Bash(gh pr review:*)",
    "Bash(git show:*)",
    "Bash(git log:*)",
    "Bash(git diff:*)",
    "Bash(git grep:*)",
    "Bash(git branch:*)",
    "Bash(uv run pytest:*)",
    "Bash(uv run python:*)",
)


def review(issue: int, worktree: Path, *, dry_run: bool = False) -> None:
    """Start the reviewer as a separate process, with nothing but the issue number.

    A fresh process is what makes the review independent: it cannot inherit what the builder meant,
    only what the branch contains.

    The process starts in the **main checkout**, so the reviewer's own contracts — the skill and
    the agent definitions under ``.claude/`` — load from there and stay outside the branch's reach.
    The branch under review is supplied as a worktree path opened via ``--add-dir``: source, tests
    and behaviour are inspected *there*, never in the launching checkout, whose files are the
    pre-change versions. The tool allowlist is what lets the review finish headless; everything
    outside it still requires an approval that headless mode cannot grant, which fails closed.
    """

    prompt = (
        f"/review-change {issue}\n"
        f"Review the open pull request for this issue. The branch under review is checked out "
        f"read-only at {worktree} — read source and tests and run commands there, never in this "
        "checkout, and edit nothing. Post the review on the pull request with `gh pr review`. End "
        "its summary with <!-- workflow-verdict blocking:N advisory:M --> where N counts Blocker "
        "and Defect findings and M counts Suspected defect and Note findings."
    )
    command = [
        _executable("claude"),
        "-p",
        "--add-dir",
        str(worktree),
        "--allowedTools",
        *_REVIEWER_TOOLS,
        prompt,
    ]
    if dry_run:
        print(f"[dry-run] {' '.join(command[:6])} ... {prompt[:60]!r}")
        return
    subprocess.run(command, cwd=REPO_ROOT, check=False)


def hand_back(issue: int, verdict: Verdict, *, dry_run: bool = False) -> None:
    """Return blocking findings to the builder. Claude never edits the branch it reviewed.

    ``codex exec`` defaults to a sandbox that can neither push nor reach the network, so a fix
    round would silently end at the commit. The builder needs the same rights it had in its own
    session: the operator sanctioned exactly this local automation, and the safety hook still
    blocks live trading, secrets, and direct pushes to ``main`` underneath it.
    """

    prompt = (
        f"The review of #{issue} reported {verdict.blocking} blocking finding(s) on its pull "
        "request. Read that review with `gh pr view --json reviews`, fix every blocking finding "
        "— with a regression test that fails before the fix where the finding is in code — push "
        "once, and move the card back to Reviewing."
    )
    command = [
        _executable("codex"),
        "exec",
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        prompt,
    ]
    if dry_run:
        print(f"[dry-run] codex exec --sandbox danger-full-access {prompt[:60]!r}")
        return
    subprocess.run(command, cwd=REPO_ROOT, check=False)


@contextlib.contextmanager
def _branch_worktree(branch: str) -> Iterator[Path]:
    """A throwaway worktree at the branch tip, so the gates measure the change under review.

    The first version of this module ran the gates in whatever checkout the orchestrator was
    started from — on `main`, `changed_paths` returned nothing and seven green gates were recorded
    as the change's evidence while measuring the wrong tree. The gate *definitions* (the contract,
    the risk model) are still read from the main checkout, so a branch cannot weaken its own gates;
    only the measurement happens on the branch.
    """

    target = Path(tempfile.mkdtemp(prefix=f"qplus-gates-{branch.replace('/', '-')}-"))
    added = subprocess.run(
        ["git", "worktree", "add", "--detach", str(target), branch],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        raise OrchestrationError(
            f"could not create a worktree for {branch!r}; refusing to gate the wrong tree"
        )
    try:
        yield target
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def cycle(issue: int, *, max_rounds: int = _MAX_ROUNDS, dry_run: bool = False) -> int:
    """One issue, from a pushed branch to a verdict the operator can act on."""

    card = board.read_card(issue)
    if card.status not in {"Implementing", "Reviewing"}:
        raise OrchestrationError(
            f"issue #{issue} is in {card.status!r}; the cycle starts once the branch is pushed"
        )
    branch = branch_for(issue)

    for round_number in range(1, max_rounds + 1):
        with _branch_worktree(branch) as tree:
            risk, results = gates.run(
                changed_paths("origin/main", root=tree), card.risk_class, root=tree
            )
            print(gates.render(risk, results))
            failed = [result for result in results if result.exit_status not in (0, None)]
            if failed:
                hand_back(issue, Verdict(len(failed), 0), dry_run=dry_run)
                continue

            if not dry_run:
                board.move(issue, "Reviewing")
            review(issue, tree, dry_run=dry_run)

        verdict = None if dry_run else latest_verdict(pull_request_for(issue))
        if verdict is None:
            notify(
                issue,
                "das Review hat kein Urteil hinterlassen; bitte anschauen",
                dry_run=dry_run,
            )
            return 1
        if verdict.clean:
            note = ""
            if verdict.advisory:
                note = f" ({verdict.advisory} nicht-blockierende Punkte zum Lesen)"
            notify(issue, f"sauber und bereit zum Mergen{note}", dry_run=dry_run)
            return 0

        if round_number == max_rounds:
            break
        if not dry_run:
            board.move(issue, "Implementing")
        hand_back(issue, verdict, dry_run=dry_run)

    if not dry_run:
        board.move(issue, "Blocked")
    notify(
        issue,
        f"nach {max_rounds} Fix-Runden nicht sauber; braucht deine Entscheidung",
        dry_run=dry_run,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive one issue's review cycle.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="run the review cycle for one issue")
    run_cmd.add_argument("issue", type=int)
    run_cmd.add_argument("--max-rounds", type=int, default=_MAX_ROUNDS)
    run_cmd.add_argument("--dry-run", action="store_true", help="print the steps, change nothing")
    args = parser.parse_args(argv)

    try:
        return cycle(args.issue, max_rounds=args.max_rounds, dry_run=args.dry_run)
    except (OrchestrationError, board.BoardError) as error:
        print(f"STOPPED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
