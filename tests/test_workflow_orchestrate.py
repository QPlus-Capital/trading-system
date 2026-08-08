"""The orchestrator sequences the two agents; it must never decide or merge.

Everything here drives fakes. The real cycle starts agent processes and moves a real card, so the
suite proves the decisions without performing any of them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from workflow import board as board_module
from workflow import gates as gates_module
from workflow import orchestrate
from workflow.gates import GateResult
from workflow.orchestrate import VERDICT, OrchestrationError, Verdict


def _green() -> tuple[str, list[GateResult]]:
    return "R2", [GateResult("check", "just check", 0, 1.0, "green")]


def _red() -> tuple[str, list[GateResult]]:
    return "R2", [GateResult("check", "just check", 1, 1.0, "FAILED (exit 1)")]


def _read_liveness_record(path: Path, *, newer_than: float | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + 1.0
    last_error: PermissionError | None = None
    while time.monotonic() < deadline:
        try:
            payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except PermissionError as error:
            last_error = error
        else:
            if newer_than is None or payload["updated_at"] > newer_than:
                return payload
        time.sleep(0.01)

    message = "the heartbeat record did not become readable and newer within one second"
    if last_error is not None:
        raise AssertionError(message) from last_error
    raise AssertionError(message)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A fake cycle: recorded calls, a scripted verdict sequence, and no real process anywhere."""

    log: dict[str, Any] = {
        "reviews": 0,
        "handbacks": [],
        "moves": [],
        "notices": [],
        "sequence": [],
        "mutation_runs": 0,
        "runs": [],
    }
    verdicts: list[Verdict] = []
    state: dict[str, Any] = {
        "status": "Implementing",
        "risk": "R2",
        "verdicts": verdicts,
        "gates": _green,
        "red_checks": [],
        "mutation_targets": [],
        "mutation_conclusion": "success",
        "hand_back_starts": True,
        "decisions": [],
        "rounds_recorded": 0,
    }

    class FakeCard:
        status = property(lambda self: state["status"])
        risk_class = property(lambda self: state["risk"])

    @contextmanager
    def fake_worktree(branch: str) -> Iterator[Path]:
        log.setdefault("worktrees", []).append(branch)
        yield Path("fake-worktree")

    monkeypatch.setattr(board_module, "read_card", lambda issue: FakeCard())
    monkeypatch.setattr(
        board_module, "move", lambda issue, target, **kwargs: log["moves"].append(target)
    )
    monkeypatch.setattr(gates_module, "run", lambda paths, risk, root=None: state["gates"]())
    monkeypatch.setattr(orchestrate, "changed_paths", lambda base, root=None: ["core/paths.py"])
    monkeypatch.setattr(orchestrate, "pull_request_for", lambda issue: 999)
    monkeypatch.setattr(orchestrate, "branch_for", lambda issue: f"codex/{issue}-fake")
    monkeypatch.setattr(orchestrate, "_branch_worktree", fake_worktree)
    monkeypatch.setattr(orchestrate, "_ensure_pull_request_title", lambda issue, pr: None)
    # The fake head advances after every hand-back, as a builder that actually pushed would
    # advance it; the no-push test overrides this with a constant.
    monkeypatch.setattr(orchestrate, "_pushed_head", lambda branch: f"head-{len(log['handbacks'])}")

    def settled_checks(pull_request: int, head: str) -> list[str]:
        log["sequence"].append("checks")
        return list(state["red_checks"])

    def reachable_targets(tree: Path) -> tuple[list[Any], str]:
        return list(state["mutation_targets"]), "fake selection"

    def mutation_evidence(branch: str, head: str, *, dry_run: bool = False) -> tuple[str, str]:
        log["mutation_runs"] += 1
        log["sequence"].append("mutation")
        return str(state["mutation_conclusion"]), "run 4242"

    monkeypatch.setattr(orchestrate, "_await_settled_checks", settled_checks)
    monkeypatch.setattr(orchestrate, "_reachable_mutation_targets", reachable_targets)
    monkeypatch.setattr(orchestrate, "_mutation_evidence", mutation_evidence)
    monkeypatch.setattr(
        orchestrate,
        "_review_scope",
        lambda tree, fix_base=None, risk_class="": (str(state.get("lane", "lean")), fix_base, 3),
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
        log["reviews"] += 1
        log["sequence"].append("review")
        log.setdefault("review_trees", []).append(worktree)
        log.setdefault("lanes", []).append(lane)
        log.setdefault("scope_bases", []).append(fix_base)
        return int(state.get("reviewer_exit", 0))

    def hand_back(issue: int, reason: str, *, dry_run: bool = False) -> bool:
        log["handbacks"].append(reason)
        return bool(state["hand_back_starts"])

    def report(
        issue: int,
        kind: str,
        facts: Mapping[str, object],
        *,
        dry_run: bool = False,
    ) -> None:
        log["notices"].append((kind, dict(facts)))

    def verdict(pull_request: int, head: str) -> Verdict | None:
        pending: list[Verdict] = state["verdicts"]
        return pending.pop(0) if pending else None

    def run_recorder(args: Sequence[str], **kwargs: Any) -> str:
        log["runs"].append(list(args))
        return ""

    monkeypatch.setattr(orchestrate, "review", review)
    monkeypatch.setattr(orchestrate, "hand_back", hand_back)
    monkeypatch.setattr(orchestrate, "report", report)
    monkeypatch.setattr(orchestrate, "latest_verdict", verdict)
    monkeypatch.setattr(orchestrate, "_run", run_recorder)
    monkeypatch.setattr(
        orchestrate, "_rounds_recorded", lambda issue: int(state["rounds_recorded"])
    )
    monkeypatch.setattr(
        orchestrate, "review_decisions", lambda pull_request, head: tuple(state["decisions"])
    )

    log["state"] = state
    return log


def test_a_clean_review_ends_in_exactly_one_final_event(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]

    assert orchestrate.cycle(101) == 0
    assert harness["reviews"] == 1
    assert harness["handbacks"] == []
    kinds = [kind for kind, _ in harness["notices"]]
    assert kinds.count("fertig") == 1 and kinds[-1] == "fertig", (
        "the final event closes the stream; nothing follows it"
    )
    _, facts = harness["notices"][-1]
    assert facts["status"] == "sauber und bereit zum Mergen"
    assert "kommando" in facts, "the operator is told exactly what to run"


def test_advisory_findings_do_not_trigger_a_fix_round(harness: dict[str, Any]) -> None:
    """Only Blocker and Defect block. Letting the other two drive rounds made the loop spin."""
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=4)]

    assert orchestrate.cycle(101) == 0
    assert harness["handbacks"] == []
    _, facts = harness["notices"][-1]
    assert facts["beratend"] == 4


def test_a_blocking_finding_returns_the_change_to_the_builder(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = [
        Verdict(blocking=2, advisory=0),
        Verdict(blocking=0, advisory=0),
    ]

    assert orchestrate.cycle(101) == 0
    assert len(harness["handbacks"]) == 1
    assert "2 blocking finding" in harness["handbacks"][0]
    assert harness["reviews"] == 2, "the fix is reviewed again"
    assert "Implementing" in harness["moves"], "the card follows the work"


def test_the_round_cap_blocks_rather_than_looping(harness: dict[str, Any]) -> None:
    """Without a cap, a reviewer that keeps finding things and a builder that keeps fixing them
    never hand back to the operator."""
    harness["state"]["verdicts"] = [Verdict(blocking=1, advisory=0)] * 6

    assert orchestrate.cycle(101, max_rounds=2) == 1
    assert harness["reviews"] == 2
    assert harness["moves"][-1] == "Blocked"
    kind, facts = harness["notices"][-1]
    assert kind == "blockiert"
    assert "entscheidung" in facts, "a decision event names options, never a bare status"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("gates", "Gates rot: check"),
        ("ci", "CI rot: quality"),
        ("mutation", "Mutationsmessung rot (run 4242)"),
        ("review", "2 blockierende Befunde"),
    ],
)
def test_the_capped_exit_names_what_was_red(
    harness: dict[str, Any], failure: str, expected: str
) -> None:
    if failure == "gates":
        harness["state"]["gates"] = _red
    elif failure == "ci":
        harness["state"]["red_checks"] = ["quality"]
    elif failure == "mutation":
        harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]
        harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]
        harness["state"]["mutation_conclusion"] = "failure"
    else:
        harness["state"]["verdicts"] = [Verdict(blocking=2, advisory=0)]

    assert orchestrate.cycle(101, max_rounds=1) == 1
    kind, facts = harness["notices"][-1]
    assert kind == "blockiert"
    assert expected in str(facts["grund"])


def test_a_failing_gate_never_reaches_the_reviewer(harness: dict[str, Any]) -> None:
    """Reviewing a change whose own tests fail wastes the reviewer and the operator's attention."""
    harness["state"]["gates"] = _red

    assert orchestrate.cycle(101, max_rounds=2) == 1
    assert harness["reviews"] == 0
    assert harness["handbacks"], "the builder is told instead"
    assert harness["moves"][-1] == "Blocked", (
        "at the cap the operator is told, not the builder again"
    )


def test_red_ci_hands_back_before_any_review_starts(harness: dict[str, Any]) -> None:
    """A verdict issued beside red or running checks is exactly the ambiguity #177 produced:
    three contradicting status messages on one ticket."""
    harness["state"]["red_checks"] = ["quality"]

    assert orchestrate.cycle(101, max_rounds=2) == 1
    assert harness["reviews"] == 0
    assert any("CI is red on quality" in reason for reason in harness["handbacks"])


def test_a_clean_verdict_without_reachable_targets_skips_the_mutation_run(
    harness: dict[str, Any],
) -> None:
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]

    assert orchestrate.cycle(101) == 0
    assert harness["mutation_runs"] == 0
    _, facts = harness["notices"][-1]
    assert str(facts["mutation"]).startswith("nicht nötig")


def test_a_clean_verdict_with_reachable_targets_waits_for_the_measurement(
    harness: dict[str, Any],
) -> None:
    """Ready-to-merge must mean the mutation evidence exists and is green on this head — not
    that a run is still pending somewhere, and not that a push may trigger one later."""
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]
    harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]

    assert orchestrate.cycle(101) == 0
    assert harness["mutation_runs"] == 1
    _, facts = harness["notices"][-1]
    assert str(facts["mutation"]).startswith("gemessen und grün")
    assert harness["sequence"] == ["checks", "review", "mutation"], (
        "evidence is strictly ordered; nothing later starts while anything earlier runs"
    )


def test_a_red_mutation_measurement_is_a_blocking_finding(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = [
        Verdict(blocking=0, advisory=0),
        Verdict(blocking=0, advisory=0),
    ]
    harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]
    harness["state"]["mutation_conclusion"] = "failure"

    assert orchestrate.cycle(101, max_rounds=2) == 1
    assert any("mutation measurement" in reason for reason in harness["handbacks"])
    assert harness["moves"][-1] == "Blocked", (
        "a second red measurement exhausts the rounds and needs the operator"
    )


def test_a_review_without_a_verdict_stops_instead_of_guessing(harness: dict[str, Any]) -> None:
    """No marker means the review did not complete. Treating that as clean would merge unreviewed
    work."""
    harness["state"]["verdicts"] = []

    assert orchestrate.cycle(101) == 1
    kind, facts = harness["notices"][-1]
    assert kind == "kein-urteil"
    assert "entscheidung" in facts


def test_the_cycle_refuses_a_card_that_has_not_started(harness: dict[str, Any]) -> None:
    harness["state"]["status"] = "Ready to Implement"

    with pytest.raises(OrchestrationError, match="the cycle starts"):
        orchestrate.cycle(101)


def test_the_verdict_marker_is_parsed_not_interpreted() -> None:
    body = (
        "## Review\n\nTwo defects and a note.\n\n"
        "<!-- workflow-verdict sha:a3c889f00123 blocking: 2 advisory: 1 evidence:executed -->\n"
    )
    match = VERDICT.search(body)
    assert match and match["blocking"] == "2" and match["advisory"] == "1"
    assert match["sha"] == "a3c889f00123"  # pragma: allowlist secret
    assert match["evidence"] == "executed"

    static = VERDICT.search(
        "<!-- workflow-verdict sha:a3c889f00123 blocking: 0 advisory: 3 evidence:static -->"
    )
    assert static is not None and static["evidence"] == "static"

    for prose in (
        "looks good to me",
        "LGTM",
        "no blocking findings",
        # The pre-#177 marker without a sha: it cannot say which commit it certifies, so it no
        # longer counts as a verdict at all.
        "<!-- workflow-verdict blocking: 0 advisory: 0 -->",
        # The pre-#102-recovery marker without evidence: it cannot say what its conclusions
        # rest on — rounds two to four of #102 were command-refused static reviews that still
        # counted as clean under this format.
        "<!-- workflow-verdict sha:a3c889f00123 blocking: 0 advisory: 0 -->",
        "<!-- workflow-verdict sha:a3c889f00123 blocking: 0 advisory: 0 evidence:guessed -->",
    ):
        assert VERDICT.search(prose) is None, "prose must never stand in for the marker"


@pytest.mark.parametrize(
    ("branch", "owned"),
    [
        ("codex/152-finish-command", True),
        ("claude/152-finish-command", True),
        ("codex/issue-152-finish-command", False),
        ("codex/1523-finish-command", False),
        ("codex/15-finish-command", False),
        ("feature/152-finish-command", False),
        ("codex/152", False),
        ("codex/152-", False),
        ("Codex/152-finish-command", False),
        ("codex/152-finish/command", False),
    ],
)
def test_issue_branch_ownership_is_exactly_the_contract_pattern(
    branch: str,
    owned: bool,
) -> None:
    assert orchestrate.issue_branch_matches(152, branch) is owned


def test_the_review_prompt_is_not_swallowed_by_the_tool_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: --allowedTools is variadic, and a prompt placed after it was parsed as one more
    tool name — the reviewer started with no task and the CLI exited with 'Input must be
    provided'. The prompt must sit directly after -p."""

    captured: list[list[str]] = []
    spawn_kwargs: dict[str, Any] = {}

    def fake_run(argv: Sequence[str], **kwargs: Any) -> SimpleNamespace:
        captured.append(list(argv))
        spawn_kwargs.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("workflow.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    head = "feedc0ffee0123456789"  # pragma: allowlist secret
    orchestrate.review(172, Path("some-worktree"), head)

    (argv,) = captured
    assert argv[1] == "-p"
    assert argv[2].startswith("/review-change 172"), "the prompt must follow -p immediately"
    assert "sha:feedc0ffee01" in argv[2], "the reviewer is told which commit its verdict names"
    assert argv.index("--allowedTools") > argv.index(argv[2])
    assert argv[-1] != argv[2], "the prompt must not be the trailing variadic argument"
    assert spawn_kwargs["capture_output"] is True, (
        "the reviewer owns its pipes; inherited stdio dies with the launcher's tool timeout"
    )
    assert "evidence:executed" in argv[2] and "evidence:static" in argv[2], (
        "the reviewer must be told to declare what its verdict rests on"
    )
    assert "workflow-decision" in argv[2], "operator decisions must be wrapped for forwarding"
    assert "LEAN" in argv[2] and "do not invoke any subagents" in argv[2], (
        "the default lane instruction is lean and forbids the agent panel"
    )
    assert "LAST action" in argv[2], (
        "posting the review must be the session's final act; three reviews ended holding "
        "their evidence"
    )


def test_the_full_lane_demands_synchronous_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A headless session dies the moment it yields with background agents running; the full
    program must say so in the task itself, because the skill alone did not save three rounds."""

    captured: list[list[str]] = []

    def fake_run(argv: Sequence[str], **kwargs: Any) -> SimpleNamespace:
        captured.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("workflow.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    head = "feedc0ffee0123456789"  # pragma: allowlist secret
    orchestrate.review(190, Path("some-worktree"), head, lane="full")

    (argv,) = captured
    assert "SYNCHRONOUSLY" in argv[2] and "wait for its report in the same turn" in argv[2]
    assert "review that area yourself" in argv[2], (
        "a delegation that cannot complete falls back to the reviewer, never to silence"
    )
    assert "LAST action" in argv[2]
    assert "--directory" in argv[2] and "cd" in argv[2], (
        "the reviewer is taught the worktree-safe invocations its allowlist matches"
    )
    assert "Bash(gh api:*)" in argv, "inline review comments need gh api"
    assert "Bash(uv run:*)" in argv, "test execution must not depend on one exact spelling"


def test_a_hand_back_that_never_started_stops_with_the_true_reason(
    harness: dict[str, Any],
) -> None:
    """Round three of the E2E validation: the codex spawn died on the launcher's closed stdout,
    and the next round blamed the builder for pushing nothing — about a builder that was never
    started. A hand-back that did not run is the cycle's own failure and stops under its name."""

    harness["state"]["verdicts"] = [Verdict(blocking=1, advisory=0)]
    harness["state"]["hand_back_starts"] = False

    assert orchestrate.cycle(101) == 1
    assert harness["reviews"] == 1, "no further round runs on a hand-back that never started"
    assert harness["moves"][-1] == "Blocked"
    kind, facts = harness["notices"][-1]
    assert kind == "blockiert"
    assert "nicht gestartet" in str(facts["grund"])
    assert "entscheidung" in facts and "kommando" in facts
    assert not any("gepusht" in str(f.get("grund", "")) for _, f in harness["notices"]), (
        "the builder is never blamed for a fix round it was not given"
    )


def test_a_dead_hand_back_spawn_is_reported_not_believed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, Any] = {}

    def fake_run(argv: Sequence[str], **kwargs: Any) -> SimpleNamespace:
        recorded["argv"] = list(argv)
        recorded.update(kwargs)
        return SimpleNamespace(returncode=1, stdout="", stderr="stdout is closed")

    monkeypatch.setattr("workflow.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    assert orchestrate.hand_back(102, "CI is red.") is False
    assert recorded["capture_output"] is True, (
        "the fix session owns its pipes; inherited stdio dies with the launcher"
    )

    monkeypatch.setattr(
        "workflow.orchestrate.subprocess.run",
        lambda argv, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert orchestrate.hand_back(102, "CI is red.") is True


def test_resume_grants_exactly_one_more_round_and_the_counter_continues(
    harness: dict[str, Any],
) -> None:
    """Round 5: after the cap, every restart began again at round 1 of 2 — granting one more
    round actually granted two, and the cap was reset instead of extended. The counter now
    survives in the event log, and the resumed run starts with the hand-back the cap withheld."""

    harness["state"]["status"] = "Blocked"
    harness["state"]["rounds_recorded"] = 2
    harness["state"]["verdicts"] = [
        Verdict(blocking=1, advisory=0),  # the capped verdict, read for the pre-hand-back
        Verdict(blocking=0, advisory=0),  # the extra round's clean verdict
    ]

    assert orchestrate.cycle(101, resume=True) == 0
    assert "Reviewing" in harness["moves"], "the orchestrator returns the card itself"
    assert len(harness["handbacks"]) == 1, "the suppressed hand-back is delivered first"
    kinds = [kind for kind, _ in harness["notices"]]
    assert kinds[0] == "fortsetzung"
    runde = next(facts for kind, facts in harness["notices"] if kind == "runde")
    assert runde["runde"] == 3 and runde["max_runden"] == 3, (
        "two consumed rounds resume as round 3 of 3, never as a fresh 1 of 2"
    )
    assert kinds[-1] == "fertig"


def test_a_red_resume_round_blocks_again_and_names_the_next_resume(
    harness: dict[str, Any],
) -> None:
    harness["state"]["status"] = "Blocked"
    harness["state"]["rounds_recorded"] = 2
    harness["state"]["verdicts"] = [
        Verdict(blocking=1, advisory=0),
        Verdict(blocking=1, advisory=0),
    ]

    assert orchestrate.cycle(101, resume=True) == 1
    assert harness["moves"][-1] == "Blocked", "one extra round, then the operator decides again"
    kind, facts = harness["notices"][-1]
    assert kind == "blockiert"
    assert "nach 3 Fix-Runden" in str(facts["grund"])
    assert "--resume" in str(facts["kommando"])


def test_a_blocked_card_needs_the_resume_flag(harness: dict[str, Any]) -> None:
    harness["state"]["status"] = "Blocked"

    with pytest.raises(OrchestrationError, match="the cycle starts"):
        orchestrate.cycle(101)


def test_decisions_are_forwarded_at_the_cap_not_only_when_ready(
    harness: dict[str, Any],
) -> None:
    """Round 5's cap stop left the reviewer's fully formed decision block only in the pull
    request — precisely the stop where the operator had to decide."""

    harness["state"]["verdicts"] = [Verdict(blocking=1, advisory=0)] * 6
    harness["state"]["decisions"] = ["**Decision — how does this leave Blocked?** A or B."]

    assert orchestrate.cycle(101, max_rounds=2) == 1
    kinds = [kind for kind, _ in harness["notices"]]
    assert kinds[-2] == "blockiert" and kinds[-1] == "entscheidung", (
        "the decision closes the run at the cap exactly as it does on the ready path"
    )
    assert any(call[:3] == ["gh", "issue", "comment"] for call in harness["runs"]), (
        "the durable half lands on the issue"
    )


def test_a_green_measurement_posts_its_evidence_on_the_pull_request(
    harness: dict[str, Any],
) -> None:
    """The checks list says "mutation — skipped" by design; without this comment the one run
    that actually measured the change is linked from nowhere on the pull request."""

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]
    harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]

    assert orchestrate.cycle(101) == 0
    comment = next(call for call in harness["runs"] if call[:3] == ["gh", "pr", "comment"])
    assert any("run 4242" in part for part in comment), "the evidence names its run"


def test_rounds_recorded_reads_the_event_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "qplus-events-101.jsonl"
    monkeypatch.setattr(orchestrate, "events_path", lambda issue: log)

    assert orchestrate._rounds_recorded(101) == 0, "no log means no rounds consumed"
    log.write_text(
        json.dumps({"ereignis": "runde", "runde": 1})
        + "\n"
        + json.dumps({"ereignis": "urteil", "runde": 1})
        + "\n"
        + json.dumps({"ereignis": "runde", "runde": 2})
        + "\n"
        + "not json\n"
        + json.dumps({"ereignis": "runde", "runde": 1})
        + "\n",
        encoding="utf-8",
    )
    assert orchestrate._rounds_recorded(101) == 2, (
        "the highest recorded round wins, and a corrupt line never ends the count"
    )


def test_settled_checks_are_read_from_the_commit_not_the_rollup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round 6 regression: right after a push the pull request's rollup still lists the
    *previous* commit's completed checks, and the branch-moved guard cannot catch it because the
    head already matches — a full round blocked on the predecessor's red checks."""

    head = "c890868caaeff81e53b0adeacde7b9d2cd406000"  # pragma: allowlist secret
    queried: list[str] = []

    def fake_run(args: Sequence[str], **kwargs: Any) -> str:
        if args[:3] == ["gh", "pr", "view"]:
            return json.dumps({"headRefOid": head})
        assert args[:2] == ["gh", "api"]
        queried.append(str(args[2]))
        return json.dumps(
            {
                "check_runs": [
                    {"name": "quality", "status": "completed", "conclusion": "success"},
                    {"name": "mutation", "status": "completed", "conclusion": "skipped"},
                ]
            }
        )

    monkeypatch.setattr(orchestrate, "_run", fake_run)

    assert orchestrate._await_settled_checks(193, head) == []
    assert all(f"commits/{head}/check-runs" in path for path in queried), (
        "the checks must be asked for the commit itself, never for the pull request's rollup"
    )


def test_a_commit_with_no_attached_checks_keeps_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No checks is not the same as green checks — the window right after a push has none."""

    head = "c890868caaeff81e53b0adeacde7b9d2cd406000"  # pragma: allowlist secret

    def fake_run(args: Sequence[str], **kwargs: Any) -> str:
        if args[:3] == ["gh", "pr", "view"]:
            return json.dumps({"headRefOid": head})
        return json.dumps({"check_runs": []})

    monkeypatch.setattr(orchestrate, "_run", fake_run)
    monkeypatch.setattr(orchestrate, "_CHECKS_TIMEOUT", 0.05)
    monkeypatch.setattr(orchestrate, "_POLL_SECONDS", 0.01)

    with pytest.raises(OrchestrationError, match="did not settle"):
        orchestrate._await_settled_checks(193, head)


def test_the_cycle_states_the_lane_it_computed(harness: dict[str, Any]) -> None:
    """Two lean rounds in a row engaged the full agent panel anyway and died waiting for it; the
    lane is the orchestrator's call, stated in the reviewer's task, never the reviewer's own."""

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]
    harness["state"]["lane"] = "full"

    assert orchestrate.cycle(101) == 0
    assert harness["lanes"] == ["full"], "the reviewer receives the lane the cycle computed"
    review_facts = next(facts for kind, facts in harness["notices"] if kind == "review")
    assert review_facts["spur"] == "full", "the operator sees the lane in the event"


def test_the_review_lane_is_computed_from_the_carve_out_and_the_diff_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    big_diff = " 3 files changed, 296 insertions(+), 45 deletions(-)"
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: big_diff)

    monkeypatch.setattr(
        orchestrate, "changed_paths", lambda base, root=None: ["live/risk_control.py"]
    )
    assert orchestrate._review_scope(Path("tree"))[0] == "full", "the carve-out always reviews full"

    monkeypatch.setattr(orchestrate, "changed_paths", lambda base, root=None: ["tests/test_x.py"])
    assert orchestrate._review_scope(Path("tree"))[0] == "full", "296+45 crosses the size bound"

    monkeypatch.setattr(
        orchestrate, "_run", lambda args, **kwargs: " 1 file changed, 9 insertions(+)"
    )
    assert orchestrate._review_scope(Path("tree"))[0] == "lean"


def test_a_repeat_round_measures_the_fix_diff_not_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round 5 of #196 reviewed a three-line fix at full strength for sixty-seven minutes because
    the branch as a whole had crossed the size bound rounds earlier and could never come back."""

    def shortstat(args: Sequence[str], **kwargs: Any) -> str:
        base = str(args[3])
        if base.startswith("prev-head"):
            return " 1 file changed, 3 insertions(+)"
        return " 5 files changed, 400 insertions(+), 20 deletions(-)"

    monkeypatch.setattr(orchestrate, "_run", shortstat)
    monkeypatch.setattr(
        orchestrate,
        "changed_paths",
        lambda base, root=None: (
            ["workflow/orchestrate.py", "tests/test_workflow_orchestrate.py"]
            if base == "origin/main"
            else ["tests/test_workflow_orchestrate.py"]
        ),
    )
    lane, base, lines = orchestrate._review_scope(Path("tree"), fix_base="prev-head")
    assert (lane, base, lines) == ("lean", "prev-head", 3), (
        "a three-line fix inside the branch diff is measured as a three-line fix"
    )

    # A fix reaching outside the branch's own diff forfeits the narrow measurement.
    monkeypatch.setattr(
        orchestrate,
        "changed_paths",
        lambda base, root=None: (
            ["workflow/orchestrate.py"] if base == "origin/main" else ["workflow/elsewhere.py"]
        ),
    )
    lane, base, _ = orchestrate._review_scope(Path("tree"), fix_base="prev-head")
    assert base is None and lane == "full", (
        "a fix outside the original diff is a complete fresh review of the branch"
    )

    # R3 on the live path always re-reviews the whole branch, whatever the fix touched.
    monkeypatch.setattr(orchestrate, "changed_paths", lambda base, root=None: ["live/runner.py"])
    lane, base, _ = orchestrate._review_scope(Path("tree"), fix_base="prev-head", risk_class="R3")
    assert base is None and lane == "full"


def test_a_round_after_a_hand_back_is_scoped_to_the_fix_diff(harness: dict[str, Any]) -> None:
    """The head the previous round reviewed becomes the next round's fix-diff base; the first
    round has none and measures the whole branch."""

    harness["state"]["verdicts"] = [
        Verdict(blocking=1, advisory=0),
        Verdict(blocking=0, advisory=0),
    ]

    assert orchestrate.cycle(101, max_rounds=2) == 0
    assert harness["scope_bases"] == [None, "head-0"], (
        "round one measures the branch; round two measures from the handed-back head"
    )


def test_the_round_cap_is_read_from_the_contract() -> None:
    """The contract names itself the single source of the loop's cap; a literal in the
    orchestrator drifted the day the operator changed the number."""

    import tomllib

    spec = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "workflow" / "workflow.toml").read_text(
            encoding="utf-8"
        )
    )
    assert orchestrate._MAX_ROUNDS == spec["review"]["loop"]["max_fix_rounds"] == 5


def test_a_small_repeat_round_is_scoped_to_focused_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repeat round names its fix diff and, below the small-fix bound, forbids a full-suite
    rerun — the gates ran the identical tree moments earlier."""

    captured: list[list[str]] = []

    def fake_run(argv: Sequence[str], **kwargs: Any) -> SimpleNamespace:
        captured.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("workflow.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    head = "feedc0ffee0123456789"  # pragma: allowlist secret
    orchestrate.review(
        196, Path("some-worktree"), head, lane="lean", fix_base="abc1234def567890", fix_lines=3
    )

    (argv,) = captured
    prompt = argv[2]
    assert "repeat round" in prompt and "abc1234def56" in prompt, (
        "the reviewer is told which diff its round is scoped to"
    )
    assert "do not rerun the whole test suite" in prompt, (
        "a three-line fix is proven by focused tests, not a full-suite rerun"
    )
    assert "workflow.impact" in prompt, "the focused selection is named, not left to guesswork"

    captured.clear()
    orchestrate.review(
        196, Path("some-worktree"), head, lane="lean", fix_base="abc1234def567890", fix_lines=120
    )
    (argv,) = captured
    assert "repeat round" in argv[2] and "do not rerun the whole test suite" not in argv[2], (
        "a larger fix keeps the scope but not the focused-tests restriction"
    )


def test_a_reviewer_that_died_empty_is_named_not_guessed_at(harness: dict[str, Any]) -> None:
    """Rounds 3 and 4 on #190 ended cleanly, posted nothing, and the operator got the same
    generic "kein-urteil" a crash would produce. The exit status tells the two apart."""

    harness["state"]["verdicts"] = []
    harness["state"]["reviewer_exit"] = 0

    assert orchestrate.cycle(101) == 1
    kind, facts = harness["notices"][-1]
    assert kind == "kein-urteil"
    assert facts["reviewer_exit"] == 0
    assert "kein Review am Pull" in str(facts["grund"]), (
        "a clean exit that posted nothing is its own diagnosis, not a generic missing verdict"
    )


def test_a_crashed_reviewer_reports_its_exit_code(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = []
    harness["state"]["reviewer_exit"] = 17

    assert orchestrate.cycle(101) == 1
    _, facts = harness["notices"][-1]
    assert facts["reviewer_exit"] == 17
    assert "Exit-Code 17" in str(facts["grund"])


def test_a_plain_restart_continues_the_numbering(harness: dict[str, Any]) -> None:
    """The narration must agree with the log: after two recorded rounds a plain restart runs
    round 3 with a fresh full budget, never a renumbered "round 1"."""

    harness["state"]["rounds_recorded"] = 2
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]

    assert orchestrate.cycle(101) == 0
    runde = next(facts for kind, facts in harness["notices"] if kind == "runde")
    assert runde["runde"] == 3 and runde["max_runden"] == 2 + orchestrate._MAX_ROUNDS


def test_the_hand_back_prompt_forbids_a_second_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fix session follows the builder contract, whose last step starts the review cycle — so
    on #102 every hand-back spawned a cycle beside the one still waiting for it: three cycles,
    four reviews, one head measured twice, and a round cap that restarted from one each time."""

    captured: list[list[str]] = []

    def fake_run(argv: Sequence[str], **kwargs: Any) -> SimpleNamespace:
        captured.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("workflow.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    assert orchestrate.hand_back(102, "CI is red.") is True
    (argv,) = captured
    assert "Do not start the review cycle" in argv[-1]


def test_a_second_cycle_for_the_same_issue_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "qplus-cycle-101.lock"
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: lock)

    with orchestrate._cycle_lock(101):
        second = orchestrate._cycle_lock(101)
        with pytest.raises(OrchestrationError, match="already running"), second:
            pass  # pragma: no cover - the second acquisition must refuse
        assert lock.exists(), "the refusal must not tear down the running cycle's lock"
    assert not lock.exists(), "the lock leaves with its cycle"


def test_a_stale_lock_from_a_dead_cycle_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crashed cycle must not block the next one forever; a live one must."""

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock = tmp_path / "qplus-cycle-101.lock"
    lock.write_text(str(dead.pid), encoding="utf-8")
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: lock)

    with orchestrate._cycle_lock(101):
        assert lock.read_text(encoding="utf-8").strip() != str(dead.pid), (
            "the stale lock is replaced by the living cycle's"
        )


def test_the_cli_takes_the_lock_before_the_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = tmp_path / "qplus-cycle-101.lock"
    record = tmp_path / "qplus-cycle-101.json"
    active_liveness = json.dumps(
        {"updated_at": 1.0, "pid": os.getpid(), "round": 7, "phase": "review"}
    )
    notices: list[tuple[object, ...]] = []
    lock.write_text(str(os.getpid()), encoding="utf-8")
    record.write_text(active_liveness, encoding="utf-8")
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: lock)
    monkeypatch.setattr(orchestrate, "liveness_path", lambda issue: record)
    monkeypatch.setattr(orchestrate, "_rounds_recorded", lambda issue: 0)
    monkeypatch.setattr(
        orchestrate, "cycle", lambda issue, **kwargs: pytest.fail("the cycle must not start")
    )
    monkeypatch.setattr(
        orchestrate, "report", lambda *args, **kwargs: notices.append((*args, kwargs))
    )

    assert orchestrate.main(["run", "101"]) == 1
    assert "already running" in capsys.readouterr().out
    assert notices == [], "a refused second CLI must not stop the cycle which owns the log"
    assert record.read_text(encoding="utf-8") == active_liveness, (
        "a refused second CLI must not alter the running cycle's liveness record"
    )


def test_a_dry_run_failure_records_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    notices: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        orchestrate,
        "cycle",
        lambda issue, **kwargs: (_ for _ in ()).throw(OrchestrationError("dry refusal")),
    )
    monkeypatch.setattr(
        orchestrate, "report", lambda *args, **kwargs: notices.append((*args, kwargs))
    )

    assert orchestrate.main(["run", "101", "--dry-run"]) == 1
    assert notices == [], "--dry-run prints failures but does not append terminal events"


def test_cycle_heartbeat_continues_while_the_main_thread_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "qplus-cycle-101.json"
    original_read_text = Path.read_text
    collided = False

    def collide_with_first_read(path: Path, *args: Any, **kwargs: Any) -> str:
        nonlocal collided
        if path == record and not collided:
            collided = True
            raise PermissionError("the heartbeat replaced the record while it was being read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(orchestrate, "liveness_path", lambda issue: record)
    monkeypatch.setattr(Path, "read_text", collide_with_first_read)

    with orchestrate._CycleHeartbeat(101, round_number=7, phase="review", interval=0.01):
        first = _read_liveness_record(record)
        time.sleep(0.04)
        second = _read_liveness_record(record, newer_than=first["updated_at"])

    assert collided, "the regression probe must exercise a concurrent read collision"
    assert second["updated_at"] > first["updated_at"]
    assert second["pid"] == os.getpid()
    assert second["round"] == 7 and second["phase"] == "review"
    assert not record.exists(), "an orderly exit removes the liveness record"


def test_a_heartbeat_write_failure_does_not_override_the_cycle_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "qplus-cycle-101.json"
    log = tmp_path / "qplus-events-101.jsonl"
    lock = tmp_path / "qplus-cycle-101.lock"
    heartbeat_type = orchestrate._CycleHeartbeat
    original_write = heartbeat_type._write_locked
    calls = 0
    failed_beat = threading.Event()
    recovered_beat = threading.Event()

    def fail_after_entry(heartbeat: orchestrate._CycleHeartbeat) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            failed_beat.set()
            raise PermissionError("the observer file is briefly busy")
        original_write(heartbeat)
        if calls > 2:
            recovered_beat.set()

    def finish_after_failed_beat(issue: int, **kwargs: object) -> int:
        heartbeat = kwargs["heartbeat"]
        assert isinstance(heartbeat, heartbeat_type)
        assert failed_beat.wait(timeout=1.0), "the periodic beat must encounter the transient error"
        assert recovered_beat.wait(timeout=1.0), (
            "the heartbeat thread must write another beat after a transient error"
        )
        return 0

    monkeypatch.setattr(orchestrate, "liveness_path", lambda issue: record)
    monkeypatch.setattr(orchestrate, "events_path", lambda issue: log)
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: lock)
    monkeypatch.setattr(orchestrate, "_rounds_recorded", lambda issue: 0)
    monkeypatch.setattr(heartbeat_type, "_write_locked", fail_after_entry)
    monkeypatch.setattr(
        orchestrate,
        "_CycleHeartbeat",
        lambda issue, round_number, phase: heartbeat_type(
            issue, round_number, phase, interval=0.001
        ),
    )
    monkeypatch.setattr(orchestrate, "cycle", finish_after_failed_beat)

    assert orchestrate.main(["run", "101"]) == 0
    assert not record.exists()


def test_an_orderly_cli_failure_is_recorded_and_clears_liveness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "qplus-cycle-101.json"
    lock = tmp_path / "qplus-cycle-101.lock"
    notices: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(orchestrate, "liveness_path", lambda issue: record)
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: lock)
    monkeypatch.setattr(orchestrate, "_rounds_recorded", lambda issue: 0)
    monkeypatch.setattr(
        orchestrate,
        "cycle",
        lambda issue, **kwargs: (_ for _ in ()).throw(OrchestrationError("refused safely")),
    )
    monkeypatch.setattr(
        orchestrate,
        "report",
        lambda issue, kind, facts, **kwargs: notices.append((kind, dict(facts))),
    )

    assert orchestrate.main(["run", "101"]) == 1
    assert notices[-1] == ("gestoppt", {"grund": "refused safely"})
    assert not record.exists()


def test_an_unexpected_cli_failure_is_recorded_before_liveness_is_cleared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "qplus-cycle-101.json"
    log = tmp_path / "qplus-events-101.jsonl"
    monkeypatch.setattr(orchestrate, "liveness_path", lambda issue: record)
    monkeypatch.setattr(orchestrate, "events_path", lambda issue: log)
    monkeypatch.setattr(orchestrate, "_lock_path", lambda issue: tmp_path / "cycle.lock")
    monkeypatch.setattr(orchestrate, "_rounds_recorded", lambda issue: 0)
    monkeypatch.setattr(
        orchestrate,
        "cycle",
        lambda issue, **kwargs: (_ for _ in ()).throw(KeyError("unexpected failure")),
    )

    assert orchestrate.main(["run", "101"]) == 1
    terminal = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert terminal["ereignis"] == "gestoppt"
    assert "KeyError" in terminal["grund"] and "unexpected failure" in terminal["grund"]
    assert not record.exists()


def test_a_clean_static_verdict_is_presented_never_certified(harness: dict[str, Any]) -> None:
    """Rounds two to four on #102 reviewed with every command refused, declared it in prose, and
    were still counted as clean. A clean verdict that executed nothing is the operator's call."""

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=3, evidence="static")]
    harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]

    assert orchestrate.cycle(101) == 1
    assert harness["mutation_runs"] == 0, "no measurement is spent on an unproven review"
    kind, facts = harness["notices"][-1]
    assert kind == "statisches-urteil"
    assert "entscheidung" in facts and "kommando" in facts


def test_reviewer_decisions_close_the_run_and_land_on_the_issue(
    harness: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two well-formed operator decisions on #102 lived only in the pull-request review; the
    ticket chat reported "0 blocking, 7 advisory" and the operator never saw either."""

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=2)]
    harness["state"]["decisions"] = ["**Decision — boundary.** A or B; default A."]
    comments: list[list[str]] = []

    def record_run(args: Sequence[str], **kwargs: Any) -> str:
        comments.append(list(args))
        return ""

    monkeypatch.setattr(orchestrate, "_run", record_run)

    assert orchestrate.cycle(101) == 0
    kinds = [kind for kind, _ in harness["notices"]]
    assert kinds[-1] == "entscheidung", "the decision closes the run, never buried under fertig"
    assert kinds[-2] == "fertig"
    _, facts = harness["notices"][-1]
    assert "boundary" in str(facts["entscheidung"])
    (comment,) = [call for call in comments if call[:3] == ["gh", "issue", "comment"]]
    assert comment[2] == "comment", (
        "the decision also lands on the issue, the one channel an open chat cannot swallow"
    )


def test_decision_blocks_are_extracted_from_the_certified_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = (
        "## Review\\n\\nFine.\\n\\n"
        "<!-- workflow-decision -->\\n**Decision 1.** Accept or widen.\\n"
        "<!-- /workflow-decision -->\\n"
        "prose between\\n"
        "<!-- workflow-decision -->**Decision 2.** Merge order.<!-- /workflow-decision -->\\n"
        "<!-- workflow-verdict sha:feedc0ffee01 blocking:0 advisory:2 evidence:executed -->"
    )
    payload = '{"reviews": [{"body": "' + body + '"}], "comments": []}'
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    decisions = orchestrate.review_decisions(158, "feedc0ffee0123456789")

    assert len(decisions) == 2
    assert decisions[0].startswith("**Decision 1.**")
    assert decisions[1] == "**Decision 2.** Merge order."

    assert orchestrate.review_decisions(158, "0000000000") == (), (
        "decisions ride only on the review whose verdict names the head"
    )


def test_forwarded_decisions_include_evidence_produced_after_the_review(
    harness: dict[str, Any],
) -> None:
    decision = "**Decision.** Dispatch the mutation measurement?"
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=1)]
    harness["state"]["decisions"] = [decision]
    harness["state"]["mutation_targets"] = ["workflow-finish-teardown"]

    assert orchestrate.cycle(101) == 0
    _, facts = harness["notices"][-1]
    forwarded = str(facts["entscheidung"])
    assert forwarded.startswith(decision), "the reviewer's text stays intact and first"
    assert "---" in forwarded and "run 4242" in forwarded
    comment = next(call for call in harness["runs"] if call[:3] == ["gh", "issue", "comment"])
    assert decision in comment[-1] and "run 4242" in comment[-1]


def test_a_builder_that_pushed_nothing_stops_the_loop(harness: dict[str, Any]) -> None:
    """Regression from #177: a hand-back after which the head never moved burned a complete
    gate-and-review round on the identical commit. The cycle now stops and asks the operator."""

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orchestrate, "_pushed_head", lambda branch: "same-head-forever")
        harness["state"]["verdicts"] = [Verdict(blocking=2, advisory=0)]

        assert orchestrate.cycle(101) == 1

    assert harness["reviews"] == 1, "the unchanged head is never re-reviewed"
    assert harness["moves"][-1] == "Blocked"
    kind, facts = harness["notices"][-1]
    assert kind == "blockiert"
    assert "nichts gepusht" in str(facts["grund"])


def test_a_missing_title_prefix_is_corrected_from_the_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `[naming]` rule was violated twice in a row while it lived in prose alone."""

    calls: list[list[str]] = []

    def fake_run(args: Sequence[str], **kwargs: object) -> str:
        calls.append(list(args))
        if "view" in args:
            return '{"title": "The pinned dependency trips a deprecation"}'
        return ""

    monkeypatch.setattr(orchestrate, "_run", fake_run)
    orchestrate._ensure_pull_request_title(177, 178)

    edit = next(call for call in calls if "edit" in call)
    assert "#177 - The pinned dependency trips a deprecation" in edit


def test_a_correct_title_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: Sequence[str], **kwargs: object) -> str:
        calls.append(list(args))
        return '{"title": "#177 - Already correct"}'

    monkeypatch.setattr(orchestrate, "_run", fake_run)
    orchestrate._ensure_pull_request_title(177, 178)

    assert not any("edit" in call for call in calls), "no write when the contract already holds"


def test_an_event_is_recorded_never_pushed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cycle records; the ticket's chat pulls. Spawning a narrator on the chat's session was
    tried and failed twice — the open window never showed the message. The payload still carries
    round, head and counts, because three context-free status lines on #177 read as
    contradictions."""

    log = tmp_path / "qplus-events-177.jsonl"
    monkeypatch.setattr(orchestrate, "events_path", lambda issue: log)
    monkeypatch.setattr(
        "workflow.orchestrate.subprocess.run",
        lambda *a, **k: pytest.fail("an event must spawn nothing"),
    )

    head = "a3c889f00123"  # pragma: allowlist secret
    orchestrate.report(177, "urteil", {"runde": 2, "blockierend": 0, "beratend": 3, "head": head})
    orchestrate.report(177, "fertig", {"runde": 2}, dry_run=True)

    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1, "a dry run records nothing"
    event = json.loads(lines[0])
    assert event["ereignis"] == "urteil" and event["runde"] == 2
    assert event["head"] == head and event["issue"] == 177
    assert event["zeit"], "an undated event cannot be ordered against the artifacts"


def test_the_orchestrator_never_merges() -> None:
    """It sequences and reports. Merging is the operator's, and nothing else's."""
    source = Path(orchestrate.__file__).read_text(encoding="utf-8")
    for forbidden in ("pr merge", "--merge", "--squash", "--admin", "pr ready", "--approve"):
        assert forbidden not in source


def test_the_verdict_is_read_from_reviews_not_only_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a pull-request review lands in `reviews`, not `comments`. The first version read
    only `comments`, so the reviewer's verdict was invisible and every cycle ended with "no
    verdict" — verified against the real review of issue #152. The fake below is the shape
    `gh pr view --json reviews,comments` actually returns."""

    payload = (
        '{"reviews": [{"body": "## Review\\n\\nNot ready.\\n\\n'
        '<!-- workflow-verdict sha:a46ae66f1b4c blocking: 3 advisory: 13 evidence:executed -->"}],'
        ' "comments": []}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    verdict = orchestrate.latest_verdict(158, "a46ae66f1b4cbf2df9e235a97acf43916c42b7ca")

    assert verdict is not None
    assert verdict.blocking == 3 and verdict.advisory == 13
    assert verdict.proven


def test_the_newest_review_wins_over_older_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '{"reviews": ['
        '{"body": "<!-- workflow-verdict sha:feedc0ffee01 blocking: 3 advisory: 1 '
        'evidence:executed -->"},'
        '{"body": "<!-- workflow-verdict sha:feedc0ffee01 blocking: 0 advisory: 2 '
        'evidence:executed -->"}'
        '], "comments": [{"body": "unrelated chatter"}]}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    verdict = orchestrate.latest_verdict(158, "feedc0ffee0123456789")

    assert verdict is not None and verdict.clean and verdict.advisory == 2


def test_a_verdict_for_another_commit_is_no_verdict_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression from #177: a round in which the builder pushed nothing produced no new review,
    and the loop reused the previous round's verdict as if it were fresh. It happened to be
    blocking; clean, it would have recommended merging an unreviewed commit."""

    payload = (
        '{"reviews": [{"body": "<!-- workflow-verdict sha:0ddba11c0de5 blocking: 0 '
        'advisory: 0 evidence:executed -->"}], "comments": []}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    unrelated_head = "a46ae66f1b4cbf2df9e235a97acf439"  # pragma: allowlist secret
    assert orchestrate.latest_verdict(158, unrelated_head) is None


def test_the_gates_measure_the_branch_not_the_launching_checkout(
    harness: dict[str, Any],
) -> None:
    """Regression: the first version ran the gates in whatever checkout the orchestrator was
    started from. On `main` that meant an empty diff — and seven green gates recorded as the
    change's evidence while measuring the wrong tree."""

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]

    assert orchestrate.cycle(101) == 0
    assert harness["worktrees"] == ["codex/101-fake"], (
        "the gates must run inside a worktree at the branch tip"
    )
    assert harness["review_trees"] == [Path("fake-worktree")], (
        "the reviewer must be pointed at the same worktree, not at the launching checkout"
    )


def test_a_missing_branch_stops_the_cycle_before_any_gate(harness: dict[str, Any]) -> None:
    """No branch means nothing attributable to gate. Running anyway would measure the wrong tree."""

    def refuse(issue: int) -> str:
        raise OrchestrationError(f"expected exactly one branch for issue #{issue}, found 0")

    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]
    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(orchestrate, "branch_for", refuse)
        with pytest.raises(OrchestrationError, match="exactly one branch"):
            orchestrate.cycle(101)
    assert harness["reviews"] == 0


def test_run_decodes_agent_output_as_utf8_on_any_platform() -> None:
    """gh answers in UTF-8. Decoded with the platform codec, the reader thread died on the
    first typographic quote inside a review body and subprocess.run returned empty text with
    returncode 0 -- the cycle then read a posted, well-formed verdict as "no verdict at all"
    (#186)."""

    script = "import sys; sys.stdout.buffer.write('„Karte“ ist grün — ok'.encode('utf-8'))"
    out = orchestrate._run([sys.executable, "-c", script])
    assert "„" in out and "—" in out, "UTF-8 agent output must survive the decode on every platform"
