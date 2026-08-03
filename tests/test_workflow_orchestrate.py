"""The orchestrator sequences the two agents; it must never decide or merge.

Everything here drives fakes. The real cycle starts agent processes and moves a real card, so the
suite proves the decisions without performing any of them.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from workflow import board as board_module
from workflow import gates as gates_module
from workflow import orchestrate
from workflow.gates import GateResult
from workflow.orchestrate import SESSION_MARKER, VERDICT, OrchestrationError, Verdict


def _green() -> tuple[str, list[GateResult]]:
    return "R2", [GateResult("check", "just check", 0, 1.0, "green")]


def _red() -> tuple[str, list[GateResult]]:
    return "R2", [GateResult("check", "just check", 1, 1.0, "FAILED (exit 1)")]


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A fake cycle: recorded calls, a scripted verdict sequence, and no real process anywhere."""

    log: dict[str, Any] = {"reviews": 0, "handbacks": [], "moves": [], "notices": []}
    verdicts: list[Verdict] = []
    state: dict[str, Any] = {
        "status": "Implementing",
        "risk": "R2",
        "verdicts": verdicts,
        "gates": _green,
    }

    class FakeCard:
        status = property(lambda self: state["status"])
        risk_class = property(lambda self: state["risk"])

    @contextmanager
    def fake_worktree(branch: str) -> Iterator[Path]:
        log.setdefault("worktrees", []).append(branch)
        yield Path("fake-worktree")

    monkeypatch.setattr(board_module, "read_card", lambda issue: FakeCard())
    monkeypatch.setattr(board_module, "move", lambda issue, target: log["moves"].append(target))
    monkeypatch.setattr(gates_module, "run", lambda paths, risk, root=None: state["gates"]())
    monkeypatch.setattr(orchestrate, "changed_paths", lambda base, root=None: ["core/paths.py"])
    monkeypatch.setattr(orchestrate, "pull_request_for", lambda issue: 999)
    monkeypatch.setattr(orchestrate, "branch_for", lambda issue: f"codex/{issue}-fake")
    monkeypatch.setattr(orchestrate, "_branch_worktree", fake_worktree)

    def review(issue: int, worktree: Path, *, dry_run: bool = False) -> None:
        log["reviews"] += 1
        log.setdefault("review_trees", []).append(worktree)

    def hand_back(issue: int, verdict: Verdict, *, dry_run: bool = False) -> None:
        log["handbacks"].append(verdict)

    def notify(issue: int, message: str, *, dry_run: bool = False) -> None:
        log["notices"].append(message)

    def verdict(pull_request: int) -> Verdict | None:
        pending: list[Verdict] = state["verdicts"]
        return pending.pop(0) if pending else None

    monkeypatch.setattr(orchestrate, "review", review)
    monkeypatch.setattr(orchestrate, "hand_back", hand_back)
    monkeypatch.setattr(orchestrate, "notify", notify)
    monkeypatch.setattr(orchestrate, "latest_verdict", verdict)

    log["state"] = state
    return log


def test_a_clean_review_notifies_once_and_stops(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=0)]

    assert orchestrate.cycle(101) == 0
    assert harness["reviews"] == 1
    assert harness["handbacks"] == []
    assert len(harness["notices"]) == 1
    assert "bereit zum Mergen" in harness["notices"][0]


def test_advisory_findings_do_not_trigger_a_fix_round(harness: dict[str, Any]) -> None:
    """Only Blocker and Defect block. Letting the other two drive rounds made the loop spin."""
    harness["state"]["verdicts"] = [Verdict(blocking=0, advisory=4)]

    assert orchestrate.cycle(101) == 0
    assert harness["handbacks"] == []
    assert "4 nicht-blockierende" in harness["notices"][0]


def test_a_blocking_finding_returns_the_change_to_the_builder(harness: dict[str, Any]) -> None:
    harness["state"]["verdicts"] = [
        Verdict(blocking=2, advisory=0),
        Verdict(blocking=0, advisory=0),
    ]

    assert orchestrate.cycle(101) == 0
    assert [v.blocking for v in harness["handbacks"]] == [2]
    assert harness["reviews"] == 2, "the fix is reviewed again"
    assert "Implementing" in harness["moves"], "the card follows the work"


def test_the_round_cap_blocks_rather_than_looping(harness: dict[str, Any]) -> None:
    """Without a cap, a reviewer that keeps finding things and a builder that keeps fixing them
    never hand back to the operator."""
    harness["state"]["verdicts"] = [Verdict(blocking=1, advisory=0)] * 6

    assert orchestrate.cycle(101, max_rounds=2) == 1
    assert harness["reviews"] == 2
    assert harness["moves"][-1] == "Blocked"
    assert "braucht deine Entscheidung" in harness["notices"][-1]


def test_a_failing_gate_never_reaches_the_reviewer(harness: dict[str, Any]) -> None:
    """Reviewing a change whose own tests fail wastes the reviewer and the operator's attention."""
    harness["state"]["gates"] = _red

    assert orchestrate.cycle(101, max_rounds=1) == 1
    assert harness["reviews"] == 0
    assert harness["handbacks"], "the builder is told instead"


def test_a_review_without_a_verdict_stops_instead_of_guessing(harness: dict[str, Any]) -> None:
    """No marker means the review did not complete. Treating that as clean would merge unreviewed
    work."""
    harness["state"]["verdicts"] = []

    assert orchestrate.cycle(101) == 1
    assert "kein Urteil" in harness["notices"][-1]


def test_the_cycle_refuses_a_card_that_has_not_started(harness: dict[str, Any]) -> None:
    harness["state"]["status"] = "Ready to Implement"

    with pytest.raises(OrchestrationError, match="the cycle starts"):
        orchestrate.cycle(101)


def test_the_verdict_marker_is_parsed_not_interpreted() -> None:
    body = (
        "## Review\n\nTwo defects and a note.\n\n"
        "<!-- workflow-verdict blocking: 2 advisory: 1 -->\n"
    )
    match = VERDICT.search(body)
    assert match and match["blocking"] == "2" and match["advisory"] == "1"

    for prose in ("looks good to me", "LGTM", "no blocking findings"):
        assert VERDICT.search(prose) is None, "prose must never stand in for the marker"


def test_the_session_marker_binds_a_ticket_to_its_chat() -> None:
    found = SESSION_MARKER.search("<!-- claude-session: abc-123 -->")
    assert found is not None and found["session"] == "abc-123"
    assert SESSION_MARKER.search("no marker here") is None


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
    monkeypatch.setattr(
        orchestrate.subprocess, "run", lambda argv, **kwargs: captured.append(list(argv))
    )
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)

    orchestrate.review(172, Path("some-worktree"))

    (argv,) = captured
    assert argv[1] == "-p"
    assert argv[2].startswith("/review-change 172"), "the prompt must follow -p immediately"
    assert argv.index("--allowedTools") > argv.index(argv[2])
    assert argv[-1] != argv[2], "the prompt must not be the trailing variadic argument"


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
        '<!-- workflow-verdict blocking: 3 advisory: 13 -->"}], "comments": []}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    verdict = orchestrate.latest_verdict(158)

    assert verdict is not None
    assert verdict.blocking == 3 and verdict.advisory == 13


def test_the_newest_review_wins_over_older_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '{"reviews": ['
        '{"body": "<!-- workflow-verdict blocking: 3 advisory: 1 -->"},'
        '{"body": "<!-- workflow-verdict blocking: 0 advisory: 2 -->"}'
        '], "comments": [{"body": "unrelated chatter"}]}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    verdict = orchestrate.latest_verdict(158)

    assert verdict is not None and verdict.clean and verdict.advisory == 2


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
