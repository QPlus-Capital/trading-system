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
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

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


def _run(args: Sequence[str], *, capture: bool = True) -> str:
    completed = subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        capture_output=capture,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OrchestrationError(f"`{args[0]} {args[1] if len(args) > 1 else ''}` failed")
    return (completed.stdout or "").strip()


def branch_for(issue: int) -> str:
    """The one branch that carries this issue number, or an error.

    Ownership follows the branch, not the card: the card cannot say who wrote the code.
    """

    listing = _run(["git", "branch", "--list", "--format=%(refname:short)"])
    pattern = re.compile(rf"^(?:codex|claude)/{issue}-[\w.-]+$")
    matches = [line for line in listing.splitlines() if pattern.match(line.strip())]
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
    """The most recent structured verdict on the pull request, or None if no review has landed."""

    raw = _run(["gh", "pr", "view", str(pull_request), "--json", "comments"])
    comments = json.loads(raw or "{}").get("comments", [])
    for comment in reversed(comments):
        match = VERDICT.search(str(comment.get("body", "")))
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
            ["claude", "-p", "--resume", session, f"Status for #{issue}: {message}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def review(issue: int, *, dry_run: bool = False) -> None:
    """Start the reviewer as a separate process, with nothing but the issue number.

    A fresh process is what makes the review independent: it cannot inherit what the builder meant,
    only what the branch contains.
    """

    prompt = (
        f"/review-change {issue}\n"
        "Review the open pull request for this issue. End your summary comment with "
        "<!-- workflow-verdict blocking:N advisory:M --> where N counts Blocker and Defect "
        "findings and M counts Suspected defect and Note findings."
    )
    if dry_run:
        print(f"[dry-run] claude -p {prompt!r}")
        return
    subprocess.run(["claude", "-p", prompt], cwd=REPO_ROOT, check=False)


def hand_back(issue: int, verdict: Verdict, *, dry_run: bool = False) -> None:
    """Return blocking findings to the builder. Claude never edits the branch it reviewed."""

    prompt = (
        f"The review of #{issue} reported {verdict.blocking} blocking finding(s) on its pull "
        "request. Fix every one of them with a regression test that fails before the fix, push "
        "once, and move the card back to Reviewing."
    )
    if dry_run:
        print(f"[dry-run] codex exec {prompt!r}")
        return
    subprocess.run(["codex", "exec", prompt], cwd=REPO_ROOT, check=False)


def cycle(issue: int, *, max_rounds: int = _MAX_ROUNDS, dry_run: bool = False) -> int:
    """One issue, from a pushed branch to a verdict the operator can act on."""

    card = board.read_card(issue)
    if card.status not in {"Implementing", "Reviewing"}:
        raise OrchestrationError(
            f"issue #{issue} is in {card.status!r}; the cycle starts once the branch is pushed"
        )

    for round_number in range(1, max_rounds + 1):
        risk, results = gates.run(changed_paths("origin/main"), card.risk_class)
        print(gates.render(risk, results))
        failed = [result for result in results if result.exit_status not in (0, None)]
        if failed:
            hand_back(issue, Verdict(len(failed), 0), dry_run=dry_run)
            continue

        if not dry_run:
            board.move(issue, "Reviewing")
        review(issue, dry_run=dry_run)

        verdict = None if dry_run else latest_verdict(pull_request_for(issue))
        if verdict is None:
            notify(issue, "the review left no verdict; it needs a look", dry_run=dry_run)
            return 1
        if verdict.clean:
            note = ""
            if verdict.advisory:
                note = f" ({verdict.advisory} non-blocking point(s) to read)"
            notify(issue, f"clean and ready to merge{note}", dry_run=dry_run)
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
        f"still not clean after {max_rounds} fix rounds; it needs a decision",
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
