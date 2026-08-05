"""The orchestrator sequences the two agents; it must never decide or merge.

Everything here drives fakes. The real cycle starts agent processes and moves a real card, so the
suite proves the decisions without performing any of them.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
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

    log: dict[str, Any] = {
        "reviews": 0,
        "handbacks": [],
        "moves": [],
        "notices": [],
        "sequence": [],
        "mutation_runs": 0,
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
    monkeypatch.setattr(
        orchestrate, "_pushed_head", lambda branch: f"head-{len(log['handbacks'])}"
    )

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

    def review(issue: int, worktree: Path, head: str, *, dry_run: bool = False) -> None:
        log["reviews"] += 1
        log["sequence"].append("review")
        log.setdefault("review_trees", []).append(worktree)

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

    monkeypatch.setattr(orchestrate, "review", review)
    monkeypatch.setattr(orchestrate, "hand_back", hand_back)
    monkeypatch.setattr(orchestrate, "report", report)
    monkeypatch.setattr(orchestrate, "latest_verdict", verdict)

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
        "<!-- workflow-verdict sha:a3c889f00123 blocking: 2 advisory: 1 -->\n"
    )
    match = VERDICT.search(body)
    assert match and match["blocking"] == "2" and match["advisory"] == "1"
    assert match["sha"] == "a3c889f00123"  # pragma: allowlist secret

    for prose in (
        "looks good to me",
        "LGTM",
        "no blocking findings",
        # The pre-#177 marker without a sha: it cannot say which commit it certifies, so it no
        # longer counts as a verdict at all.
        "<!-- workflow-verdict blocking: 0 advisory: 0 -->",
    ):
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


def test_an_event_carries_its_facts_and_forbids_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ticket session narrates events; it must never be prompted into working. The payload
    carries round, head and counts, because three context-free status lines on #177 read as
    contradictions."""

    captured: list[list[str]] = []
    monkeypatch.setattr(
        "workflow.orchestrate.subprocess.run", lambda argv, **kwargs: captured.append(list(argv))
    )
    monkeypatch.setattr(orchestrate, "_executable", lambda name: name)
    monkeypatch.setattr(orchestrate, "session_for", lambda issue: "session-abc")

    head = "a3c889f00123"  # pragma: allowlist secret
    orchestrate.report(
        177, "urteil", {"runde": 2, "blockierend": 0, "beratend": 3, "head": head}
    )

    (argv,) = captured
    prompt = argv[-1]
    assert '"runde": 2' in prompt and '"head": "a3c889f00123"' in prompt  # pragma: allowlist secret
    assert "Führe keine Kommandos aus" in prompt
    assert "entscheidung" in prompt, "the rendering rule for decision events travels with it"


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
        '<!-- workflow-verdict sha:a46ae66f1b4c blocking: 3 advisory: 13 -->"}], "comments": []}'
    )
    monkeypatch.setattr(orchestrate, "_run", lambda args, **kwargs: payload)

    verdict = orchestrate.latest_verdict(158, "a46ae66f1b4cbf2df9e235a97acf43916c42b7ca")

    assert verdict is not None
    assert verdict.blocking == 3 and verdict.advisory == 13


def test_the_newest_review_wins_over_older_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '{"reviews": ['
        '{"body": "<!-- workflow-verdict sha:feedc0ffee01 blocking: 3 advisory: 1 -->"},'
        '{"body": "<!-- workflow-verdict sha:feedc0ffee01 blocking: 0 advisory: 2 -->"}'
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
        'advisory: 0 -->"}], "comments": []}'
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
