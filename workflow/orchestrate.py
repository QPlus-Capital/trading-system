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
    uv run python -m workflow.orchestrate run 101 --max-rounds 5 --dry-run
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from workflow import board, gates
from workflow.classify import REPO_ROOT, changed_paths, load_model, needs_full_review
from workflow.mutation import MutationTarget, load_policy, select_affected_targets

#: The reviewer writes this into its summary comment. Counting a structured marker keeps the loop's
#: exit condition out of the reviewer's prose; the sha names the commit the verdict certifies —
#: without it, a round in which no new review landed silently reused the previous round's verdict —
#: and the evidence field says what the verdict rests on: `executed` when the reviewer ran the
#: commands it relied on, `static` when it could not. Rounds two to four on #102 ran with every
#: command refused, declared it openly in prose, and were still counted as clean; a marker without
#: the field is therefore no verdict at all.
VERDICT = re.compile(
    r"<!--\s*workflow-verdict\s+sha:\s*(?P<sha>[0-9a-fA-F]{7,40})\s+"
    r"blocking:\s*(?P<blocking>\d+)\s+advisory:\s*(?P<advisory>\d+)\s+"
    r"evidence:\s*(?P<evidence>executed|static)\s*-->"
)
#: The reviewer wraps every decision that belongs to the operator in this pair, so the cycle can
#: forward the decision itself — on #102 two well-formed decisions sat only in the pull-request
#: review, and the operator, reading the ticket chat, never saw either.
DECISION = re.compile(
    r"<!--\s*workflow-decision\s*-->\s*(?P<text>.*?)\s*<!--\s*/workflow-decision\s*-->",
    re.DOTALL,
)


def _contract_max_rounds() -> int:
    """The fix-round cap, read from the contract instead of duplicated here.

    ``workflow.toml`` names itself the single machine-readable source of "the review loop's
    blocking severities and cap" — yet this module carried its own literal ``2``. One number,
    one place; the two would have drifted the day the operator changed the cap.
    """

    spec = tomllib.loads(board.CONTRACT_PATH.read_text(encoding="utf-8"))
    return int(spec["review"]["loop"]["max_fix_rounds"])


_MAX_ROUNDS = _contract_max_rounds()

#: Below this many changed lines, a repeat round proves itself with the focused tests for the
#: touched modules instead of a full-suite rerun — round 5 of #196 spent sixty-seven minutes
#: re-proving a three-line diff whose full suite the gates had just run on the identical tree.
#: An instruction detail, not contract policy, so it lives here and not in ``workflow.toml``.
_SMALL_FIX_LINES = 50

#: How long the cycle waits before failing closed, in seconds. Checks: the push-triggered CI
#: (quality is ~3 minutes plus queueing). Mutation: one dispatched scoped run, well under the
#: job's own 45-minute cap on the full set.
_CHECKS_TIMEOUT = 25 * 60
_MUTATION_TIMEOUT = 60 * 60
_POLL_SECONDS = 30
_HEARTBEAT_STALE_SECONDS = 90.0


class OrchestrationError(RuntimeError):
    """A step that must stop rather than guess."""


@dataclass(frozen=True)
class Verdict:
    """What the last review concluded, and on what footing."""

    blocking: int
    advisory: int
    evidence: str = "executed"

    @property
    def clean(self) -> bool:
        return self.blocking == 0

    @property
    def proven(self) -> bool:
        """Whether the reviewer executed the commands its conclusions rest on."""

        return self.evidence == "executed"


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


def _say(text: str) -> None:
    """Narrate to stdout without dying with the launcher.

    The builder starts the cycle from a shell tool whose own timeout can expire while the
    mutation measurement is still being awaited; the abandoned pipe then rejects writes. The
    cycle's narration is a courtesy, never evidence — the events and the board are — so a failed
    print is dropped rather than allowed to kill the round that was otherwise proceeding.
    """

    with contextlib.suppress(OSError):
        print(text, flush=True)


def _run(
    args: Sequence[str],
    *,
    capture: bool = True,
    cwd: Path = REPO_ROOT,
) -> str:
    # `gh` and `git` emit UTF-8 on every platform; bare text=True decodes with the platform
    # codec instead. On Windows that is cp1252, the reader thread died on the first typographic
    # quote inside a review body, and subprocess.run returned *empty text with returncode 0* —
    # the cycle then read a posted, well-formed verdict as "no verdict at all" (#186). Explicit
    # UTF-8 with visible replacement characters: mojibake shows, a dead reader never does.
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise OrchestrationError(f"`{args[0]} {args[1] if len(args) > 1 else ''}` failed")
    return (completed.stdout or "").strip()


def _process_alive(pid: int) -> bool:
    """Whether ``pid`` names a live process, without signalling it.

    ``os.kill(pid, 0)`` is the POSIX idiom; on Windows it would *terminate* the process, so the
    liveness probe goes through ``OpenProcess`` there instead.
    """

    if pid <= 0:
        return False
    if sys.platform == "win32":
        query_limited_information = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(query_limited_information, False, pid)
        if not handle:
            return False
        # OpenProcess also succeeds on an exited process whose handles are still held (any
        # waited-but-unreleased child), so the exit code decides: STILL_ACTIVE means running.
        still_active = 259
        exit_code = ctypes.c_ulong()
        queried = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel32.CloseHandle(handle)
        return bool(queried) and exit_code.value == still_active
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lock_path(issue: int) -> Path:
    """One lock per issue, in the git directory every worktree of this repository shares."""

    common = _run(["git", "rev-parse", "--git-common-dir"])
    base = Path(common)
    if not base.is_absolute():
        base = (REPO_ROOT / common).resolve()
    return base / f"qplus-cycle-{issue}.lock"


@contextlib.contextmanager
def _cycle_lock(issue: int) -> Iterator[None]:
    """One ticket, one cycle. A second concurrent cycle refuses, naming the first.

    On #102 a fix session started its own cycle while the cycle that spawned it was still
    waiting for it: three cycles reviewed one branch, the round cap restarted from one each
    time, and one head was measured twice. The lock lives in the shared git directory so every
    worktree sees the same one; a lock whose process is dead is stale and replaced, so a
    crashed cycle never blocks the next by leaving a file behind.
    """

    path = _lock_path(issue)

    def acquire() -> bool:
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
        except FileExistsError:
            return False
        return True

    if not acquire():
        try:
            recorded = int(path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            recorded = 0
        if recorded and _process_alive(recorded):
            raise OrchestrationError(
                f"a cycle for #{issue} is already running (pid {recorded}); a second one would "
                f"race it — if that process is truly gone, remove {path}"
            )
        with contextlib.suppress(OSError):
            path.unlink()
        if not acquire():
            raise OrchestrationError(f"another cycle for #{issue} started first; this one stops")
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


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

    body = _certified_review_body(pull_request, head)
    if body is None:
        return None
    match = VERDICT.search(body)
    assert match is not None  # _certified_review_body only returns a body carrying the marker
    return Verdict(int(match["blocking"]), int(match["advisory"]), match["evidence"])


def _certified_review_body(pull_request: int, head: str) -> str | None:
    """The newest review or comment whose verdict marker names ``head``, or None."""

    raw = _run(["gh", "pr", "view", str(pull_request), "--json", "reviews,comments"])
    payload = json.loads(raw or "{}")
    reviews = [str(entry.get("body", "")) for entry in payload.get("reviews", [])]
    comments = [str(entry.get("body", "")) for entry in payload.get("comments", [])]
    for body in [*reversed(reviews), *reversed(comments)]:
        match = VERDICT.search(body)
        if match and head.lower().startswith(match["sha"].lower()):
            return body
    return None


def review_decisions(pull_request: int, head: str) -> tuple[str, ...]:
    """The operator decisions the certified review wrapped, in review order.

    The reviewer's prose is never parsed for meaning; only explicitly wrapped blocks count, the
    same principle as the verdict marker. Without this, two well-formed decisions on #102 lived
    only in the pull-request review and the operator never saw either.
    """

    body = _certified_review_body(pull_request, head)
    if body is None:
        return ()
    return tuple(match["text"].strip() for match in DECISION.finditer(body))


def events_path(issue: int) -> Path:
    """One event log per issue, in the git directory every worktree of this repository shares."""

    common = _run(["git", "rev-parse", "--git-common-dir"])
    base = Path(common)
    if not base.is_absolute():
        base = (REPO_ROOT / common).resolve()
    return base / f"qplus-events-{issue}.jsonl"


def liveness_path(issue: int) -> Path:
    """The cycle's replaceable liveness record beside its append-only event log."""
    return events_path(issue).with_name(f"qplus-cycle-{issue}.json")


class _CycleHeartbeat:
    """Refresh cycle liveness independently of whichever subprocess the main thread awaits."""

    def __init__(self, issue: int, round_number: int, phase: str, interval: float = 30.0) -> None:
        self.round_number, self.phase, self.interval = round_number, phase, interval
        self.path = liveness_path(issue)
        self._stop, self._lock = threading.Event(), threading.Lock()
        self._error: OSError | None = None
        self._thread = threading.Thread(target=self._beat, daemon=True)

    def _write_locked(self) -> None:
        payload = {
            "updated_at": time.time(),
            "pid": os.getpid(),
            "round": self.round_number,
            "phase": self.phase,
        }
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        for attempt in range(3):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.01)

    def _beat(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                with self._lock:
                    self._write_locked()
                    self._error = None
            except OSError as error:
                self._error = error
                _say(f"WARNING: the cycle heartbeat could not be written: {error}")

    def update(self, *, round_number: int | None = None, phase: str) -> None:
        """Publish a meaningful phase change immediately; periodic beats preserve that state."""
        try:
            with self._lock:
                if round_number is not None:
                    self.round_number = round_number
                self.phase = phase
                self._write_locked()
                self._error = None
        except OSError as error:
            self._error = error
            _say(f"WARNING: the cycle heartbeat could not be written: {error}")

    def __enter__(self) -> _CycleHeartbeat:
        self.update(round_number=self.round_number, phase=self.phase)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, _exc: object, _traceback: object) -> None:
        self._stop.set()
        self._thread.join()
        if exc_type is None:
            with contextlib.suppress(OSError):
                self.path.unlink()


def report(
    issue: int,
    kind: str,
    facts: Mapping[str, object],
    *,
    dry_run: bool = False,
) -> None:
    """Append one structured progress event to the ticket's event log.

    The cycle *records*; the ticket's chat *narrates*. The first design pushed each event into
    the chat's session by spawning a headless process on it — and the operator saw nothing,
    because an already-open window does not reload what another process appends, and the spawned
    narrator knew only the event's five fields, never the artifacts behind them. Now the events
    accumulate here, the chat watches the ticket (``workflow.watch``) and reads this log *plus*
    the real artifacts — review text, run logs, the card — so the narration is written by the
    session the operator is actually looking at. A bare status line proved worse than nothing
    on #177: three of them, hours apart, contradicted one another because none said which commit
    or round it described; every event therefore still carries its round, head, and counts.
    """

    payload = json.dumps(
        {"zeit": _now_iso(), "issue": issue, "ereignis": kind, **dict(facts)},
        ensure_ascii=False,
    )
    _say(f"\n>>> #{issue} [{kind}] {payload}")
    if dry_run:
        return
    with events_path(issue).open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _rounds_recorded(issue: int) -> int:
    """How many rounds this ticket has already consumed, read from its event log.

    The counter survives the cycle process on purpose: without it, every restart began again at
    "round 1 of 2", so granting one more round after the cap actually granted two — the cap was
    reset instead of extended, which is the opposite of what a cap is for.
    """

    log = events_path(issue)
    if not log.is_file():
        return 0
    highest = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("ereignis") == "runde":
            highest = max(highest, int(event.get("runde", 0)))
    return highest


def _forward_decisions(
    issue: int,
    pull_request: int,
    head: str,
    *,
    after_review: str | None = None,
    dry_run: bool = False,
) -> None:
    """Deliver the certified review's operator decisions as the closing event and a comment.

    Round 5 showed why this must run at *every* exit, not only the ready one: at the round cap
    the reviewer's fully formed A/B/C block existed only in the pull request — precisely the stop
    where the operator has to decide. The issue comment is the durable half; the next review
    round reads it, so an answered decision is never re-opened as new.
    """

    decisions = () if dry_run else review_decisions(pull_request, head)
    if not decisions:
        return
    forwarded = "\n\n".join(decisions)
    if after_review:
        forwarded += f"\n\n---\n\nSeit dem Review hat der Zyklus festgestellt:\n\n{after_review}"
    report(
        issue,
        "entscheidung",
        {
            "quelle": "das Review legt diese Entscheidungen dem Operator vor",
            "blockiert_den_merge": "nein",
            "entscheidung": forwarded,
        },
        dry_run=dry_run,
    )
    comment = f"The review left these decisions to the operator:\n\n{forwarded}"
    try:
        _run(["gh", "issue", "comment", str(issue), "--body", comment])
    except OrchestrationError:
        _say(f"the decision comment did not reach issue #{issue}; the event carries it")


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
    "Bash(gh api:*)",
    "Bash(uv run:*)",
)


def review(
    issue: int,
    worktree: Path,
    head: str,
    *,
    lane: str = "lean",
    fix_base: str | None = None,
    fix_lines: int = 0,
    dry_run: bool = False,
) -> int:
    """Start the reviewer as a separate process, with nothing but the issue number and the lane.

    A fresh process is what makes the review independent: it cannot inherit what the builder meant,
    only what the branch contains.

    The process starts in the **main checkout**, so the reviewer's own contracts — the skill and
    the agent definitions under ``.claude/`` — load from there and stay outside the branch's reach.
    The branch under review is supplied as a worktree path opened via ``--add-dir``: source, tests
    and behaviour are inspected *there*, never in the launching checkout, whose files are the
    pre-change versions. The tool allowlist is what lets the review finish headless; everything
    outside it still requires an approval that headless mode cannot grant, which fails closed.

    The **lane is computed by the cycle and stated as an instruction**, not left to the reviewer's
    judgement: two lean rounds in a row engaged the full agent panel anyway and died waiting for
    it. On a repeat round ``fix_base`` names the head the previous round reviewed, and the task
    states the fix diff explicitly — the contract scopes the round to that diff, and re-walking
    the whole change was the single largest time sink the loop had. Returns the reviewer's exit
    status, so the caller can tell a session that ended cleanly but posted nothing from one that
    crashed.
    """

    if lane == "lean":
        lane_instruction = (
            "The effective lane is LEAN: review directly, one pass, and do not invoke any "
            "subagents. "
        )
    else:
        lane_instruction = (
            "The effective lane is the FULL program: engage exactly the agents the contract "
            "selects for the risk class and touched paths — and only SYNCHRONOUSLY: start an "
            "agent and wait for its report in the same turn, never in the background. Your "
            "headless session ends the moment you yield control with agents still running, and "
            "nothing can ever wake you again — three reviews of one ticket died exactly that "
            "way, their verified findings stranded in transcripts. If a delegation cannot "
            "complete, review that area yourself and name the gap. "
        )
    scope_instruction = ""
    if fix_base is not None:
        scope_instruction = (
            f"This is a repeat round. The fix diff is {fix_base[:12]}..{head[:12]} "
            f"({fix_lines} changed line(s)); review that diff and the modules it touches, "
            "nothing more — the contract forbids re-walking what earlier rounds already "
            "established. The full deterministic gate suite ran green on this exact tree "
            "moments before you started. "
        )
        if fix_lines < _SMALL_FIX_LINES:
            scope_instruction += (
                "The fix is small: do not rerun the whole test suite as evidence — run the "
                "tests for the touched modules and the specific counterexamples your findings "
                f"need (`uv run --directory {worktree} python -m workflow.impact --base "
                f"{fix_base[:12]}` names the focused selection). "
            )
    prompt = (
        f"/review-change {issue}\n"
        f"Review the open pull request for this issue. {lane_instruction}{scope_instruction}"
        "Posting the review is your LAST action and is never skipped: a session that ends with "
        "the review unposted has delivered nothing, whatever it verified — post with what you "
        "have rather than end holding evidence. "
        f"The branch under review is checked out "
        f"read-only at {worktree} — read source and tests there, never in this checkout, and "
        f"edit nothing. Run commands against it without `cd`: `uv run --directory {worktree} "
        f"pytest ...` and `git -C {worktree} ...` match your allowlist, a compound command "
        "starting with `cd` does not. Wrap every decision that belongs to the operator in "
        "<!-- workflow-decision --> and <!-- /workflow-decision --> so the cycle can forward it. "
        "Post the review on the pull request with `gh pr review`. End its summary with "
        f"<!-- workflow-verdict sha:{head[:12]} blocking:N advisory:M evidence:executed --> "
        "where the sha names the commit you reviewed, N counts Blocker and Defect findings, M "
        "counts Suspected defect and Note findings, and evidence is `executed` only if you ran "
        "the tests or commands your conclusions rest on — if every command was refused, write "
        "evidence:static and say so in the summary."
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
        return 0
    # The reviewer owns its pipes: with inherited stdio, a launcher whose tool timeout closed the
    # cycle's stdout kills the spawn at its first write — observed on the round-three hand-back.
    # A failed review needs no handling here; the missing verdict is caught where it is read.
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        _say(f"the reviewer exited with {completed.returncode}: {(completed.stderr or '')[-400:]}")
    return completed.returncode


def hand_back(issue: int, reason: str, *, dry_run: bool = False) -> bool:
    """Return blocking evidence to the builder. Claude never edits the branch it reviewed.

    The reason names what is red — review findings, a red gate, red CI, or a red mutation run —
    and the instruction tail is the same contract every time. ``codex exec`` defaults to a sandbox
    that can neither push nor reach the network, so a fix round would silently end at the commit.
    The builder needs the same rights it had in its own session: the operator sanctioned exactly
    this local automation, and the safety hook still blocks live trading, secrets, and direct
    pushes to ``main`` underneath it.

    Returns whether the fix session ran at all. The spawn owns its pipes and its exit status is
    checked, because round three's hand-back died at startup on the launcher's closed stdout and
    the loop then blamed the builder for "pushing nothing" it had never been asked to push. What
    the session achieved is not judged here — the next round measures that; only a spawn that
    did not run is distinguished, so the cycle can stop with the true reason.
    """

    prompt = (
        f"{reason} Fix every blocking point on #{issue} — with a regression test that fails "
        "before the fix where it is in code — push once, and move the card back to Reviewing. "
        "Do not start the review cycle afterwards: the cycle that sent this hand-back is still "
        "running and resumes on your push — a second cycle would race it."
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
        return True
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        _say(
            f"the fix session for #{issue} exited with {completed.returncode}: "
            f"{(completed.stderr or '')[-400:]}"
        )
        return False
    return True


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
        encoding="utf-8",
        errors="replace",
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
            encoding="utf-8",
            errors="replace",
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
    """(still pending, failed, name) for one check run."""

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
    """Wait until no check is still running on **this commit**, then return the red ones.

    No verdict while anything runs: a review posted beside a pending check can be contradicted
    minutes later — the operator watched exactly that contradiction arrive as three conflicting
    status messages on one ticket. The checks are read from the commit's own check runs, never
    from the pull request's rollup: in the window right after a push the rollup still lists the
    *previous* head's completed checks while the new run has not attached yet, and the
    branch-moved guard cannot catch it because the head already matches — round 6 burned a full
    round blocking on the predecessor's red checks that way. An empty list keeps waiting and
    times out rather than passing: no checks is not the same as green checks.
    """

    deadline = time.monotonic() + _CHECKS_TIMEOUT
    while time.monotonic() < deadline:
        raw = _run(["gh", "pr", "view", str(pull_request), "--json", "headRefOid"])
        remote = str(json.loads(raw or "{}").get("headRefOid") or "")
        if remote and remote != head:
            raise OrchestrationError(
                f"the branch moved while the cycle ran: certifying {head[:12]}, found {remote[:12]}"
            )
        runs_raw = _run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100",
                "--jq",
                "{check_runs: [.check_runs[] | {name, status, conclusion}]}",
            ]
        )
        check_runs = json.loads(runs_raw or "{}").get("check_runs") or []
        states = [_check_state(entry) for entry in check_runs]
        if check_runs and not any(pending for pending, _, _ in states):
            return sorted({name for pending, is_failed, name in states if is_failed})
        time.sleep(_POLL_SECONDS)
    raise OrchestrationError("CI did not settle in time; no verdict is issued while checks run")


def _review_scope(
    tree: Path, *, fix_base: str | None = None, risk_class: str = ""
) -> tuple[str, str | None, int]:
    """The effective review scope for the branch in ``tree``: lane, measured base, changed lines.

    The orchestrator computes the lane and states it in the reviewer's task, because leaving the
    call to the reviewer killed two rounds in a row: a lean R2 ticket was reviewed with the full
    agent panel, and the headless session died waiting for agents the lane forbade — twenty
    minutes of verification each time, posted nowhere.

    A first look measures the whole branch against ``origin/main``. A repeat round measures the
    **fix diff** — ``fix_base`` is the head the previous round reviewed — because the contract
    scopes a repeat round to "the fix diff and the modules it touches, nothing more", while the
    branch measurement only ever grows: on #196 a three-line fix was reviewed at full strength
    for sixty-seven minutes because the branch as a whole had crossed the size bound rounds
    earlier and could never come back. The narrow measurement is forfeited in exactly the two
    cases the contract names for a complete fresh review: the fix reaches files outside the
    branch's own diff, or the change is R3 on the live path.

    Returns ``(lane, base, changed_lines)`` where ``base`` is ``None`` when the whole branch was
    measured, so the caller can tell the reviewer which diff its round is scoped to.
    """

    branch_paths = changed_paths("origin/main", root=tree)
    paths, base = branch_paths, "origin/main"
    if fix_base is not None:
        fix_paths = changed_paths(fix_base, root=tree)
        touches_live = risk_class == "R3" and any(path.startswith("live/") for path in branch_paths)
        if not (set(fix_paths) - set(branch_paths)) and not touches_live:
            paths, base = fix_paths, fix_base
    shortstat = _run(
        ["git", "diff", "--shortstat", f"{base}...HEAD"],
        cwd=tree,
    )
    changed_lines = sum(int(n) for n in re.findall(r"(\d+) (?:insertion|deletion)", shortstat))
    lane = "full" if needs_full_review(paths, changed_lines) else "lean"
    return lane, (base if base != "origin/main" else None), changed_lines


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


def cycle(
    issue: int,
    *,
    max_rounds: int = _MAX_ROUNDS,
    dry_run: bool = False,
    resume: bool = False,
    heartbeat: _CycleHeartbeat | None = None,
) -> int:
    """One issue, from a pushed branch to a verdict the operator can act on.

    The round is strictly ordered — gates, settled CI, review, then one mutation measurement on
    the certified head — and nothing later starts while anything earlier still runs. "Ready to
    merge" therefore means: every piece of evidence exists, is green, and describes this commit.

    ``resume`` is the operator's "one more round" after the cap blocked the ticket: the round
    counter continues from the event log — two consumed rounds resume as round 3 **of 3**, never
    as a fresh 1 of 2 — and the run begins by handing the last certified red evidence back to
    the builder, exactly the hand-back the cap suppressed. One extra round per decision; if it
    is not clean either, the card blocks again and the operator decides again.
    """

    card = board.read_card(issue)
    allowed = {"Implementing", "Reviewing"} | ({"Blocked"} if resume else set())
    if card.status not in allowed:
        raise OrchestrationError(
            f"issue #{issue} is in {card.status!r}; the cycle starts once the branch is pushed"
        )
    branch = branch_for(issue)
    pull_request = 0 if dry_run else pull_request_for(issue)
    if not dry_run:
        _ensure_pull_request_title(issue, pull_request)
    stale_head: str | None = None

    def _phase(phase: str, round_number: int | None = None) -> None:
        if heartbeat is not None:
            heartbeat.update(round_number=round_number, phase=phase)

    # Rounds are ticket-lifetime, numbered continuously from the event log: a restart with a
    # fresh budget must not renumber history — round 6's narration said "round 1 of 2" while the
    # log already carried two rounds. A plain run brings a budget of ``max_rounds`` new rounds;
    # ``--resume`` grants exactly one.
    consumed = 0 if dry_run else _rounds_recorded(issue)
    first_round = consumed + 1
    last_round = consumed + (1 if resume else max_rounds)
    if resume and not dry_run and card.status == "Blocked":
        board.move(issue, "Reviewing", actor="orchestrator")

    def _returned(reason: str) -> bool:
        """Hand the round back, or stop with the true reason when the fix session never ran.

        Without this distinction the next round finds the head unmoved and reports "the builder
        pushed nothing" — which round three showed the operator about a builder that was never
        started. A hand-back that did not run is the cycle's failure, not the builder's.
        """

        _phase("builder")
        if hand_back(issue, reason, dry_run=dry_run):
            return True
        if not dry_run:
            board.move(issue, "Blocked", actor="orchestrator")
        report(
            issue,
            "blockiert",
            {
                "grund": "die Rückgabe an den Builder ist nicht gestartet",
                "entscheidung": (
                    "Der Fix-Auftrag hat den Builder nie erreicht — der codex-Prozess ist beim "
                    "Start gescheitert, der Stand ist unverändert. Optionen: `codex exec` von "
                    "Hand prüfen und den Zyklus danach neu starten, oder die offenen Punkte im "
                    "Codex-Chat des Tickets selbst beauftragen. Ohne Aktion bleibt die Karte "
                    "auf Blocked."
                ),
                "kommando": f"uv run python -m workflow.orchestrate run {issue}",
            },
            dry_run=dry_run,
        )
        return False

    if resume and not dry_run:
        # The cap suppressed the very hand-back that would have kept the loop moving; granting
        # one more round starts by delivering it. The last certified verdict decides what was
        # red: blocking findings, or — a clean verdict at the cap — the mutation measurement.
        blocked_head = _pushed_head(branch)
        blocked_verdict = latest_verdict(pull_request, blocked_head)
        report(
            issue,
            "fortsetzung",
            {
                "runde": first_round,
                "max_runden": last_round,
                "grund": "der Operator hat genau eine weitere Runde gewährt",
                "head": blocked_head[:12],
            },
            dry_run=dry_run,
        )
        if blocked_verdict is not None:
            if blocked_verdict.blocking:
                reason = (
                    f"The review of #{issue} reported {blocked_verdict.blocking} blocking "
                    "finding(s) on its pull request. Read that review with "
                    "`gh pr view --json reviews`."
                )
            else:
                reason = (
                    f"The last dispatched mutation measurement on the reviewed head of "
                    f"#{issue} was red; read its mutation-result artifact and tighten or fix "
                    "from measured results only."
                )
            if not _returned(reason):
                return 1
            stale_head = blocked_head

    cap_reason: str | None = None
    post_review_evidence: str | None = None
    for round_number in range(first_round, last_round + 1):
        post_review_evidence = None
        head = "dry-run" if dry_run else _pushed_head(branch)
        if stale_head is not None and head == stale_head:
            if not dry_run:
                board.move(issue, "Blocked", actor="orchestrator")
            report(
                issue,
                "blockiert",
                {
                    "grund": "der Builder hat nach der Rückgabe nichts gepusht",
                    "head": head[:12],
                    "entscheidung": (
                        "Der Zyklus stoppt, statt denselben Stand erneut zu messen. Optionen: "
                        "im Codex-Chat nachsehen, warum kein Push kam, und den Zyklus danach "
                        "neu starten — oder das Ticket zurück in die Spezifikation geben. Ohne "
                        "Aktion bleibt die Karte auf Blocked."
                    ),
                },
                dry_run=dry_run,
            )
            _forward_decisions(issue, pull_request, head, dry_run=dry_run)
            return 1
        report(
            issue,
            "runde",
            {"runde": round_number, "max_runden": last_round, "head": head[:12]},
            dry_run=dry_run,
        )
        _phase("gates", round_number)
        mutation_targets: list[MutationTarget] = []
        red_checks: list[str] = []
        reviewer_exit = 0
        with _branch_worktree(branch) as tree:
            risk, results = gates.run(
                changed_paths("origin/main", root=tree), card.risk_class, root=tree
            )
            _say(gates.render(risk, results))
            failed = [result for result in results if result.exit_status not in (0, None)]
            if not failed:
                mutation_targets, selection_reason = _reachable_mutation_targets(tree)
                _phase("ci")
                red_checks = [] if dry_run else _await_settled_checks(pull_request, head)
                if not red_checks:
                    if not dry_run:
                        board.move(issue, "Reviewing", actor="orchestrator")
                    # A round that follows a hand-back is scoped to the fix diff: ``stale_head``
                    # is exactly the head the previous round reviewed and handed back.
                    lane, fix_base, fix_lines = (
                        ("lean", None, 0)
                        if dry_run
                        else _review_scope(
                            tree, fix_base=stale_head, risk_class=card.risk_class or ""
                        )
                    )
                    report(
                        issue,
                        "review",
                        {
                            "runde": round_number,
                            "gates": "grün",
                            "ci": "grün",
                            "spur": lane,
                            "head": head[:12],
                        },
                        dry_run=dry_run,
                    )
                    _phase("review")
                    reviewer_exit = review(
                        issue,
                        tree,
                        head,
                        lane=lane,
                        fix_base=fix_base,
                        fix_lines=fix_lines,
                        dry_run=dry_run,
                    )

        if failed:
            if round_number == last_round:
                cap_reason = f"Gates rot: {', '.join(result.name for result in failed)}"
                break
            reason = (
                f"The gates failed on {len(failed)} command(s) for #{issue}; reproduce with "
                "`just gates` in the ticket worktree."
            )
            report(
                issue,
                "rückgabe",
                {"runde": round_number, "grund": f"Gates rot: {len(failed)} Kommandos"},
                dry_run=dry_run,
            )
            if not _returned(reason):
                return 1
            stale_head = head
            continue
        if red_checks:
            if round_number == last_round:
                cap_reason = f"CI rot: {', '.join(red_checks)}"
                break
            report(
                issue,
                "rückgabe",
                {"runde": round_number, "grund": f"CI rot: {', '.join(red_checks)}"},
                dry_run=dry_run,
            )
            if not _returned(
                f"CI is red on {', '.join(red_checks)} for the pushed head of #{issue}."
            ):
                return 1
            stale_head = head
            continue

        verdict = None if dry_run else latest_verdict(pull_request, head)
        if verdict is None:
            if reviewer_exit == 0:
                diagnosis = (
                    "Der Reviewer endete ohne Fehler, hinterließ aber kein Review am Pull "
                    "Request — typisch: er wartete beim Sitzungsende noch auf etwas, etwa "
                    "gestartete Subagenten."
                )
            else:
                diagnosis = f"Der Reviewer brach mit Exit-Code {reviewer_exit} ab."
            report(
                issue,
                "kein-urteil",
                {
                    "runde": round_number,
                    "head": head[:12],
                    "reviewer_exit": reviewer_exit,
                    "grund": diagnosis,
                    "entscheidung": (
                        f"{diagnosis} Ohne Urteil wird nichts als mergefähig gemeldet. "
                        "Optionen: den Zyklus erneut starten oder das Review auf dem Pull "
                        "Request selbst ansehen. Ohne Aktion bleibt die Karte auf Reviewing."
                    ),
                    "kommando": f"uv run python -m workflow.orchestrate run {issue}",
                },
                dry_run=dry_run,
            )
            return 1
        report(
            issue,
            "urteil",
            {
                "runde": round_number,
                "blockierend": verdict.blocking,
                "beratend": verdict.advisory,
                "beleg": verdict.evidence,
                "head": head[:12],
            },
            dry_run=dry_run,
        )
        if verdict.clean and not verdict.proven:
            # A clean verdict that executed nothing certifies nothing: rounds two to four on
            # #102 reviewed with every command refused and were still counted as clean. The
            # blocking direction stays valid — findings worth fixing are worth fixing on any
            # footing — but "ready to merge" demands executed evidence or the operator's word.
            report(
                issue,
                "statisches-urteil",
                {
                    "runde": round_number,
                    "head": head[:12],
                    "entscheidung": (
                        "Das Review ist sauber, konnte aber nichts ausführen — sein Urteil ist "
                        "reine Statik-Analyse und wird nicht als mergefähig gemeldet. Optionen: "
                        "den Zyklus erneut starten, damit ein Review mit ausgeführten Tests "
                        "entsteht, oder das statische Urteil selbst akzeptieren und auf dem "
                        "Pull Request mergen. Ohne Aktion bleibt die Karte auf Reviewing."
                    ),
                    "kommando": f"uv run python -m workflow.orchestrate run {issue}",
                },
                dry_run=dry_run,
            )
            _forward_decisions(issue, pull_request, head, dry_run=dry_run)
            return 1
        if verdict.clean:
            if mutation_targets:
                report(
                    issue,
                    "mutation",
                    {
                        "phase": "eine Messung auf dem zertifizierten Stand läuft",
                        "ziele": len(mutation_targets),
                        "dauer": "etwa 5 bis 25 Minuten",
                    },
                    dry_run=dry_run,
                )
                _phase("mutation")
                conclusion, reference = _mutation_evidence(branch, head, dry_run=dry_run)
                post_review_evidence = f"Mutationsmessung: {conclusion} ({reference})"
                if conclusion != "success":
                    if round_number == last_round:
                        cap_reason = f"Mutationsmessung rot ({reference})"
                        break
                    if not dry_run:
                        board.move(issue, "Implementing", actor="orchestrator")
                    report(
                        issue,
                        "rückgabe",
                        {"runde": round_number, "grund": f"Mutationsmessung rot ({reference})"},
                        dry_run=dry_run,
                    )
                    if not _returned(
                        f"The dispatched mutation measurement ({reference}) is red on the "
                        f"reviewed head of #{issue}; read its mutation-result artifact and "
                        "tighten or fix from measured results only."
                    ):
                        return 1
                    stale_head = head
                    continue
                mutation_status = f"gemessen und grün ({reference})"
                if not dry_run:
                    # The pull request carries its own mutation evidence: the checks list says
                    # "mutation — skipped" by design (pushes measure nothing), and round 5
                    # showed that the one green run proving the change lived in a dispatch
                    # nothing on the pull request pointed to.
                    evidence = (
                        f"Mutation measured green on `{head[:12]}`: {reference}, "
                        f"{selection_reason} The push CI skips this job by design; this "
                        "dispatched run is the measurement."
                    )
                    try:
                        _run(["gh", "pr", "comment", str(pull_request), "--body", evidence])
                    except OrchestrationError:
                        _say("the mutation evidence comment did not reach the pull request")
            else:
                mutation_status = "nicht nötig, kein Ziel erreichbar"
                post_review_evidence = f"Mutationsmessung: {mutation_status}"
            report(
                issue,
                "fertig",
                {
                    "status": "sauber und bereit zum Mergen",
                    "runde": round_number,
                    "beratend": verdict.advisory,
                    "mutation": mutation_status,
                    "head": head[:12],
                    "kommando": f"Squash-Merge auf GitHub, danach: just finish {issue}",
                },
                dry_run=dry_run,
            )
            # The operator's decisions close the run — after "fertig", never buried under it.
            _forward_decisions(
                issue,
                pull_request,
                head,
                after_review=post_review_evidence,
                dry_run=dry_run,
            )
            return 0

        if round_number == last_round:
            cap_reason = f"{verdict.blocking} blockierende Befunde aus dem Review"
            break
        if not dry_run:
            board.move(issue, "Implementing", actor="orchestrator")
        report(
            issue,
            "rückgabe",
            {
                "runde": round_number,
                "grund": f"{verdict.blocking} blockierende Befunde aus dem Review",
            },
            dry_run=dry_run,
        )
        if not _returned(
            f"The review of #{issue} reported {verdict.blocking} blocking finding(s) on its "
            "pull request. Read that review with `gh pr view --json reviews`."
        ):
            return 1
        stale_head = head

    if not dry_run:
        board.move(issue, "Blocked", actor="orchestrator")
    report(
        issue,
        "blockiert",
        {
            "grund": f"{cap_reason}; Deckel nach {last_round} Fix-Runden erreicht",
            "entscheidung": (
                "Die Schleife hat ihren Deckel erreicht; was offen ist, steht im letzten Review "
                "auf dem Pull Request und wird als Entscheidungs-Ereignis mitgeliefert. "
                "Optionen: genau eine weitere Runde gewähren (Kommando unten — der Zähler "
                "läuft weiter, nie wieder bei eins los), die Spezifikation ergänzen und neu "
                "freigeben, oder das Ticket zurückstellen. Ohne Aktion bleibt die Karte auf "
                "Blocked."
            ),
            "kommando": f"uv run python -m workflow.orchestrate run {issue} --resume",
        },
        dry_run=dry_run,
    )
    _forward_decisions(
        issue,
        pull_request,
        head,
        after_review=post_review_evidence,
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
    run_cmd.add_argument(
        "--resume",
        action="store_true",
        help="grant exactly one more round after the cap blocked the ticket",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        try:
            return cycle(args.issue, max_rounds=args.max_rounds, dry_run=True, resume=args.resume)
        except KeyboardInterrupt:
            _say("STOPPED: interrupted")
            return 130
        except Exception as error:
            _say(f"STOPPED: {error}")
            return 1

    try:
        with _cycle_lock(args.issue):
            heartbeat = _CycleHeartbeat(
                args.issue,
                round_number=_rounds_recorded(args.issue) + 1,
                phase="start",
            )
            with heartbeat:
                try:
                    return cycle(
                        args.issue,
                        max_rounds=args.max_rounds,
                        dry_run=False,
                        resume=args.resume,
                        heartbeat=heartbeat,
                    )
                except KeyboardInterrupt:
                    report(args.issue, "gestoppt", {"grund": "durch Interrupt beendet"})
                    _say("STOPPED: interrupted")
                    return 130
                except (OrchestrationError, board.BoardError) as error:
                    report(args.issue, "gestoppt", {"grund": str(error)})
                    _say(f"STOPPED: {error}")
                    return 1
                except Exception as error:
                    reason = f"unerwarteter Fehler ({type(error).__name__}): {error}"
                    report(args.issue, "gestoppt", {"grund": reason})
                    _say(f"STOPPED: {reason}")
                    return 1
    except KeyboardInterrupt:
        _say("STOPPED: interrupted")
        return 130
    except Exception as error:
        _say(f"STOPPED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
