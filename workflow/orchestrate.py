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
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from workflow import board, gates
from workflow.classify import REPO_ROOT, changed_paths, load_model
from workflow.mutation import MutationTarget, load_policy, select_affected_targets

#: The reviewer writes this into its summary comment. Counting a structured marker keeps the loop's
#: exit condition out of the reviewer's prose, and the sha names the commit the verdict certifies —
#: without it, a round in which no new review landed silently reused the previous round's verdict.
VERDICT = re.compile(
    r"<!--\s*workflow-verdict\s+sha:\s*(?P<sha>[0-9a-fA-F]{7,40})\s+"
    r"blocking:\s*(?P<blocking>\d+)\s+advisory:\s*(?P<advisory>\d+)\s*-->"
)
SESSION_MARKER = re.compile(r"<!--\s*claude-session:\s*(?P<session>[A-Za-z0-9_-]+)\s*-->")

_MAX_ROUNDS = 2

#: How long the cycle waits before failing closed, in seconds. Checks: the push-triggered CI
#: (quality is ~3 minutes plus queueing). Mutation: one dispatched scoped run, well under the
#: job's own 45-minute cap on the full set.
_CHECKS_TIMEOUT = 25 * 60
_MUTATION_TIMEOUT = 60 * 60
_POLL_SECONDS = 30


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


def latest_verdict(pull_request: int, head: str) -> Verdict | None:
    """The newest structured verdict **for this head**, or None if none certifies it.

    A pull-request review lands in ``reviews``, not ``comments`` — the first version of this
    function read only ``comments`` and could therefore never see a verdict, so the loop's one
    exit condition was unreadable. Both lists are scanned newest-first, reviews before comments,
    because the reviewer submits a real review and a comment is only ever a fallback.

    The sha requirement closes the second gap #177 exposed: a round in which the builder pushed
    nothing produced no new review, and the loop reused the previous round's verdict as if it
    were fresh. It happened to be a blocking verdict; in the other direction it would have been
    a merge recommendation for an unreviewed commit. A verdict for another commit is not stale
    context — it is no verdict at all.
    """

    raw = _run(["gh", "pr", "view", str(pull_request), "--json", "reviews,comments"])
    payload = json.loads(raw or "{}")
    reviews = [str(entry.get("body", "")) for entry in payload.get("reviews", [])]
    comments = [str(entry.get("body", "")) for entry in payload.get("comments", [])]
    for body in [*reversed(reviews), *reversed(comments)]:
        match = VERDICT.search(body)
        if match and head.lower().startswith(match["sha"].lower()):
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
            [
                _executable("claude"),
                "-p",
                "--resume",
                session,
                (
                    f"[Orchestrator] Status zu #{issue}: {message} — nur zur Kenntnis für den "
                    "Operator, keine Aktion nötig. Führe keine Kommandos aus und antworte "
                    "höchstens mit einem kurzen Satz."
                ),
            ],
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
    "Bash(gh run view:*)",
    "Bash(gh run list:*)",
    "Bash(uv run pytest:*)",
    "Bash(uv run python:*)",
)


def review(issue: int, worktree: Path, head: str, *, dry_run: bool = False) -> None:
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
        f"its summary with <!-- workflow-verdict sha:{head[:12]} blocking:N advisory:M --> where "
        "the sha names the commit you reviewed, N counts Blocker and Defect findings, and M "
        "counts Suspected defect and Note findings."
    )
    # The prompt sits directly after -p: --allowedTools is variadic and would otherwise swallow
    # it as one more tool name, leaving the reviewer with an empty task — observed on the first
    # round-two attempt, where the CLI exited with "Input must be provided".
    command = [
        _executable("claude"),
        "-p",
        prompt,
        "--add-dir",
        str(worktree),
        "--allowedTools",
        *_REVIEWER_TOOLS,
    ]
    if dry_run:
        print(f"[dry-run] {' '.join(command[:6])} ... {prompt[:60]!r}")
        return
    subprocess.run(command, cwd=REPO_ROOT, check=False)


def hand_back(issue: int, reason: str, *, dry_run: bool = False) -> None:
    """Return blocking evidence to the builder. Claude never edits the branch it reviewed.

    The reason names what is red — review findings, a red gate, red CI, or a red mutation run —
    and the instruction tail is the same contract every time. ``codex exec`` defaults to a sandbox
    that can neither push nor reach the network, so a fix round would silently end at the commit.
    The builder needs the same rights it had in its own session: the operator sanctioned exactly
    this local automation, and the safety hook still blocks live trading, secrets, and direct
    pushes to ``main`` underneath it.
    """

    prompt = (
        f"{reason} Fix every blocking point on #{issue} — with a regression test that fails "
        "before the fix where it is in code — push once, and move the card back to Reviewing."
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


def _ensure_pull_request_title(issue: int, pull_request: int) -> None:
    """Correct a pull-request title missing its ``#<issue> - `` prefix.

    The contract's ``[naming]`` rule was violated twice in a row while it lived in prose alone;
    the cycle reads the title anyway, so it now enforces the rule instead of hoping.
    """

    raw = _run(["gh", "pr", "view", str(pull_request), "--json", "title"])
    title = str(json.loads(raw or "{}").get("title") or "").strip()
    prefix = f"#{issue} - "
    if title.startswith(prefix):
        return
    stripped = re.sub(rf"^#?{issue}\s*[-–—:]*\s*", "", title).strip() or title
    corrected = f"{prefix}{stripped}"
    _run(["gh", "pr", "edit", str(pull_request), "--title", corrected])
    print(f"corrected the pull-request title to {corrected!r}")


def _pushed_head(branch: str) -> str:
    """The branch tip, proven identical locally and on the remote.

    Everything downstream — CI, the review, the mutation evidence — certifies one commit. If the
    local branch and the remote disagree, part of that evidence would describe a commit nobody
    merges, so the cycle stops instead of certifying an ambiguity.
    """

    local = _run(["git", "rev-parse", branch])
    listed = _run(["git", "ls-remote", "origin", f"refs/heads/{branch}"])
    remote = listed.split()[0] if listed else ""
    if remote != local:
        raise OrchestrationError(
            f"branch {branch!r} is not pushed as it stands: local {local[:12]}, "
            f"remote {remote[:12] or 'absent'}"
        )
    return local


def _check_state(entry: Mapping[str, object]) -> tuple[bool, bool, str]:
    """(still pending, failed, name) for one rollup entry, check runs and contexts alike."""

    name = str(entry.get("name") or entry.get("context") or "check")
    conclusion = str(entry.get("conclusion") or "").upper()
    if conclusion:
        return False, conclusion not in {"SUCCESS", "SKIPPED", "NEUTRAL"}, name
    state = str(entry.get("status") or entry.get("state") or "").upper()
    if state in {"SUCCESS", "SKIPPED", "NEUTRAL"}:
        return False, False, name
    if state in {"FAILURE", "ERROR"}:
        return False, True, name
    return True, False, name


def _await_settled_checks(pull_request: int, head: str) -> list[str]:
    """Wait until no check is still running on the head, then return the red ones.

    No verdict while anything runs: a review posted beside a pending check can be contradicted
    minutes later — the operator watched exactly that contradiction arrive as three conflicting
    status messages on one ticket. An empty rollup keeps waiting and times out rather than
    passing: no checks is not the same as green checks.
    """

    deadline = time.monotonic() + _CHECKS_TIMEOUT
    while time.monotonic() < deadline:
        raw = _run(
            ["gh", "pr", "view", str(pull_request), "--json", "headRefOid,statusCheckRollup"]
        )
        payload = json.loads(raw or "{}")
        remote = str(payload.get("headRefOid") or "")
        if remote and remote != head:
            raise OrchestrationError(
                f"the branch moved while the cycle ran: certifying {head[:12]}, "
                f"found {remote[:12]}"
            )
        rollup = payload.get("statusCheckRollup") or []
        states = [_check_state(entry) for entry in rollup]
        if rollup and not any(pending for pending, _, _ in states):
            return sorted({name for pending, is_failed, name in states if is_failed})
        time.sleep(_POLL_SECONDS)
    raise OrchestrationError("CI did not settle in time; no verdict is issued while checks run")


def _reachable_mutation_targets(tree: Path) -> tuple[list[MutationTarget], str]:
    """The mutation targets the branch diff can reach, measured on the branch worktree."""

    return select_affected_targets(
        changed_paths("origin/main", root=tree), load_policy(), load_model(), root=tree
    )


def _mutation_evidence(branch: str, head: str, *, dry_run: bool = False) -> tuple[str, str]:
    """Dispatch the one scoped mutation measurement for this head and wait for its conclusion.

    Exactly one measurement per certified head: pushes no longer trigger mutation in CI, so the
    evidence is produced here, after the review is clean, on the commit the review certified.
    Nothing is reported ready while it runs.
    """

    if dry_run:
        print(f"[dry-run] gh workflow run ci.yml --ref {branch} -f scope=mutation-affected")
        return "success", "dry-run"
    _run(["gh", "workflow", "run", "ci.yml", "--ref", branch, "-f", "scope=mutation-affected"])
    deadline = time.monotonic() + _MUTATION_TIMEOUT
    while time.monotonic() < deadline:
        raw = _run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "ci.yml",
                "--branch",
                branch,
                "--event",
                "workflow_dispatch",
                "--limit",
                "5",
                "--json",
                "databaseId,headSha,status,conclusion",
            ]
        )
        for entry in json.loads(raw or "[]"):
            if str(entry.get("headSha")) != head:
                continue
            if str(entry.get("status")) == "completed":
                return (
                    str(entry.get("conclusion") or "failure"),
                    f"run {entry.get('databaseId')}",
                )
            break
        time.sleep(_POLL_SECONDS)
    raise OrchestrationError(f"the mutation run for {head[:12]} did not complete in time")


def cycle(issue: int, *, max_rounds: int = _MAX_ROUNDS, dry_run: bool = False) -> int:
    """One issue, from a pushed branch to a verdict the operator can act on.

    The round is strictly ordered — gates, settled CI, review, then one mutation measurement on
    the certified head — and nothing later starts while anything earlier still runs. "Ready to
    merge" therefore means: every piece of evidence exists, is green, and describes this commit.
    """

    card = board.read_card(issue)
    if card.status not in {"Implementing", "Reviewing"}:
        raise OrchestrationError(
            f"issue #{issue} is in {card.status!r}; the cycle starts once the branch is pushed"
        )
    branch = branch_for(issue)
    pull_request = 0 if dry_run else pull_request_for(issue)
    if not dry_run:
        _ensure_pull_request_title(issue, pull_request)
    stale_head: str | None = None

    for round_number in range(1, max_rounds + 1):
        head = "dry-run" if dry_run else _pushed_head(branch)
        if stale_head is not None and head == stale_head:
            if not dry_run:
                board.move(issue, "Blocked", actor="orchestrator")
            notify(
                issue,
                "der Builder hat nach der Rückgabe nichts gepusht; der Zyklus stoppt, statt "
                "denselben Stand erneut zu messen — braucht deine Entscheidung",
                dry_run=dry_run,
            )
            return 1
        mutation_targets: list[MutationTarget] = []
        red_checks: list[str] = []
        with _branch_worktree(branch) as tree:
            risk, results = gates.run(
                changed_paths("origin/main", root=tree), card.risk_class, root=tree
            )
            print(gates.render(risk, results))
            failed = [result for result in results if result.exit_status not in (0, None)]
            if not failed:
                mutation_targets, _ = _reachable_mutation_targets(tree)
                red_checks = [] if dry_run else _await_settled_checks(pull_request, head)
                if not red_checks:
                    if not dry_run:
                        board.move(issue, "Reviewing", actor="orchestrator")
                    review(issue, tree, head, dry_run=dry_run)

        if failed:
            if round_number == max_rounds:
                break
            hand_back(
                issue,
                f"The gates failed on {len(failed)} command(s) for #{issue}; reproduce with "
                "`just gates` in the ticket worktree.",
                dry_run=dry_run,
            )
            stale_head = head
            continue
        if red_checks:
            if round_number == max_rounds:
                break
            hand_back(
                issue,
                f"CI is red on {', '.join(red_checks)} for the pushed head of #{issue}.",
                dry_run=dry_run,
            )
            stale_head = head
            continue

        verdict = None if dry_run else latest_verdict(pull_request, head)
        if verdict is None:
            notify(
                issue,
                "das Review hat kein Urteil hinterlassen; bitte anschauen",
                dry_run=dry_run,
            )
            return 1
        if verdict.clean:
            if mutation_targets:
                conclusion, reference = _mutation_evidence(branch, head, dry_run=dry_run)
                if conclusion != "success":
                    if round_number == max_rounds:
                        break
                    if not dry_run:
                        board.move(issue, "Implementing", actor="orchestrator")
                    hand_back(
                        issue,
                        f"The dispatched mutation measurement ({reference}) is red on the "
                        f"reviewed head of #{issue}; read its mutation-result artifact and "
                        "tighten or fix from measured results only.",
                        dry_run=dry_run,
                    )
                    stale_head = head
                    continue
                mutation_note = " — Mutation gemessen und grün"
            else:
                mutation_note = " — keine Mutation nötig, kein Ziel erreichbar"
            note = ""
            if verdict.advisory:
                note = f" ({verdict.advisory} nicht-blockierende Punkte zum Lesen)"
            notify(issue, f"sauber und bereit zum Mergen{note}{mutation_note}", dry_run=dry_run)
            return 0

        if round_number == max_rounds:
            break
        if not dry_run:
            board.move(issue, "Implementing", actor="orchestrator")
        hand_back(
            issue,
            f"The review of #{issue} reported {verdict.blocking} blocking finding(s) on its "
            "pull request. Read that review with `gh pr view --json reviews`.",
            dry_run=dry_run,
        )
        stale_head = head

    if not dry_run:
        board.move(issue, "Blocked", actor="orchestrator")
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
