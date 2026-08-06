"""The board tool refuses whatever the contract does not permit, and verifies what it writes.

Every test drives a fake GraphQL layer: the board is the single source of truth for real work in
flight, so the suite must never move a real card.
"""

from __future__ import annotations

from typing import Any

import pytest
from workflow import board
from workflow.board import BoardError, Card, Contract, load_contract

_OPTIONS = {
    "Backlog": "opt-backlog",
    "Specifying": "opt-specifying",
    "Ready to Implement": "opt-ready",
    "Implementing": "opt-implementing",
    "Reviewing": "opt-reviewing",
    "Blocked": "opt-blocked",
    "Done": "opt-done",
}


def _card_payload(
    status: str, *, labels: tuple[str, ...] = ("risk:R2",), items: int = 1
) -> dict[str, Any]:
    node = {
        "id": "item-1",
        "project": {"id": "project-1", "number": 1, "title": "board"},
        "fieldValueByName": {
            "name": status,
            "field": {
                "id": "field-1",
                "options": [{"id": oid, "name": name} for name, oid in _OPTIONS.items()],
            },
        },
    }
    return {
        "repository": {
            "issue": {
                "number": 101,
                "title": "a change",
                "state": "OPEN",
                "labels": {"nodes": [{"name": name} for name in labels]},
                "projectItems": {"nodes": [node] * items},
            }
        }
    }


@pytest.fixture
def fake_graphql(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record every request and answer reads from a mutable status."""

    calls: list[dict[str, Any]] = []
    state = {"status": "Specifying"}

    def run(query: str, **variables: object) -> dict[str, Any]:
        calls.append({"query": query, **variables})
        if "mutation" in query:
            for name, option in _OPTIONS.items():
                if option == variables.get("option"):
                    state["status"] = name
            return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}
        return _card_payload(state["status"])

    monkeypatch.setattr(board, "_graphql", run)
    return calls


def test_reading_a_card_costs_exactly_one_request(fake_graphql: list[dict[str, Any]]) -> None:
    """The predecessor listed the whole project to find one card and exhausted the GraphQL budget.
    One card must cost one request, keyed by issue number."""

    card = board.read_card(101)

    assert len(fake_graphql) == 1
    assert fake_graphql[0]["number"] == 101
    assert card.status == "Specifying"
    assert card.risk_class == "R2"


def test_a_permitted_transition_is_written_and_read_back(
    fake_graphql: list[dict[str, Any]],
) -> None:
    confirmed = board.move(101, "Ready to Implement", actor="claude")

    assert confirmed.status == "Ready to Implement"
    kinds = ["mutation" in call["query"] for call in fake_graphql]
    assert kinds == [False, True, False], "read, write, then verify"
    initial, write, verification = fake_graphql
    assert write["project"] == "project-1"
    assert write["item"] == "item-1"
    assert write["field"] == "field-1"
    assert write["option"] == "opt-ready"
    assert initial["number"] == verification["number"] == 101


def test_a_transition_the_contract_omits_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    with pytest.raises(BoardError, match="does not permit"):
        board.move(101, "Reviewing", actor="codex")
    assert all("mutation" not in call["query"] for call in fake_graphql), "nothing was written"


def test_an_automation_owned_status_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    """`Backlog` and `Done` follow the issue's own lifecycle. An agent setting them would make the
    board disagree with whether the issue is open."""

    for status in ("Backlog", "Done"):
        with pytest.raises(BoardError, match="project automation"):
            board.move(101, status, actor="claude")
    assert fake_graphql == []


def test_an_unknown_status_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    with pytest.raises(BoardError, match="not a status"):
        board.move(101, "Erledigt", actor="claude")
    assert fake_graphql == []


def test_moving_to_the_current_status_writes_nothing(fake_graphql: list[dict[str, Any]]) -> None:
    card = board.move(101, "Specifying", actor="claude")

    assert card.status == "Specifying"
    assert all("mutation" not in call["query"] for call in fake_graphql)


def test_a_write_that_did_not_take_effect_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A silent no-op would leave the board claiming a state the work is not in."""

    def run(query: str, **variables: object) -> dict[str, Any]:
        if "mutation" in query:
            return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}
        return _card_payload("Specifying")  # never changes

    monkeypatch.setattr(board, "_graphql", run)

    with pytest.raises(BoardError, match="did not take effect"):
        board.move(101, "Ready to Implement", actor="claude")


def test_the_wrong_actor_is_refused_by_name(fake_graphql: list[dict[str, Any]]) -> None:
    """Regression: a specify session pulled a card backwards out of a build that owned it. The
    contract assigns every transition to an actor; the board now enforces the assignment."""

    with pytest.raises(BoardError, match="'codex' does not move this card"):
        board.move(101, "Ready to Implement", actor="codex")
    assert all("mutation" not in call["query"] for call in fake_graphql), "nothing was written"


def test_an_unknown_actor_is_refused_before_anything_is_read(
    fake_graphql: list[dict[str, Any]],
) -> None:
    with pytest.raises(BoardError, match="not an actor"):
        board.move(101, "Ready to Implement", actor="operator")
    assert fake_graphql == []


def test_an_any_transition_accepts_every_contract_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Implementing -> Blocked` carries `actor = "any"`: whoever hits the wall may say so."""

    for actor in sorted(board.ACTORS):
        state = {"status": "Implementing"}

        def run(
            query: str, _state: dict[str, str] = state, **variables: object
        ) -> dict[str, Any]:
            if "mutation" in query:
                _state["status"] = "Blocked"
            return _card_payload(_state["status"])

        monkeypatch.setattr(board, "_graphql", run)
        assert board.move(101, "Blocked", actor=actor).status == "Blocked"


@pytest.mark.parametrize(
    ("source", "actor"),
    [
        ("Ready to Implement", "claude"),
        ("Implementing", "codex"),
        ("Blocked", "claude"),
    ],
)
def test_every_backward_move_to_specifying_requires_a_reason(
    monkeypatch: pytest.MonkeyPatch, source: str, actor: str
) -> None:
    """Regression: the first real hand-back walked the card backwards and left no trace anywhere
    but a closed chat window."""

    monkeypatch.setattr(board, "_graphql", lambda *a, **k: _card_payload(source))

    with pytest.raises(BoardError, match="requires a reason"):
        board.move(101, "Specifying", actor=actor)
    with pytest.raises(BoardError, match="requires a reason"):
        board.move(101, "Specifying", actor=actor, reason="   ")


def test_starting_specification_from_backlog_needs_no_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"status": "Backlog"}

    def run(query: str, **variables: object) -> dict[str, Any]:
        if "mutation" in query:
            state["status"] = "Specifying"
        return _card_payload(state["status"])

    monkeypatch.setattr(board, "_graphql", run)

    assert board.move(101, "Specifying", actor="claude").status == "Specifying"


def test_the_hand_back_reason_lands_on_the_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"status": "Implementing"}
    comments: list[list[str]] = []

    def run(query: str, **variables: object) -> dict[str, Any]:
        if "mutation" in query:
            state["status"] = "Specifying"
        return _card_payload(state["status"])

    class _Done:
        returncode = 0

    def record_comment(args: list[str], **kwargs: object) -> _Done:
        comments.append(list(args))
        return _Done()

    monkeypatch.setattr(board, "_graphql", run)
    monkeypatch.setattr("workflow.board.subprocess.run", record_comment)

    card = board.move(101, "Specifying", actor="codex", reason="AC-03 is unbuildable as written")

    assert card.status == "Specifying"
    (comment,) = comments
    assert comment[:4] == ["gh", "issue", "comment", "101"]
    assert any("AC-03 is unbuildable as written" in part for part in comment)
    assert any("Implementing -> Specifying by codex" in part for part in comment)


def test_a_reason_that_cannot_be_posted_is_an_error_not_a_shrug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"status": "Implementing"}

    def run(query: str, **variables: object) -> dict[str, Any]:
        if "mutation" in query:
            state["status"] = "Specifying"
        return _card_payload(state["status"])

    class _Failed:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr(board, "_graphql", run)
    monkeypatch.setattr("workflow.board.subprocess.run", lambda args, **kwargs: _Failed())

    with pytest.raises(BoardError, match="did not reach issue"):
        board.move(101, "Specifying", actor="codex", reason="a real gap")


def test_a_card_on_two_boards_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two cards mean two answers to 'where does this stand'. Refuse rather than pick one."""

    monkeypatch.setattr(board, "_graphql", lambda *a, **k: _card_payload("Specifying", items=2))

    with pytest.raises(BoardError, match="exactly one"):
        board.read_card(101)


def test_a_missing_issue_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(board, "_graphql", lambda *a, **k: {"repository": {"issue": None}})

    with pytest.raises(BoardError, match="does not exist"):
        board.read_card(404)


def test_the_contract_is_the_only_source_of_permitted_transitions() -> None:
    """The tool reads the real contract, so a transition added to prose without the TOML does not
    silently become executable."""

    contract = load_contract()

    assert contract.permits("Specifying", "Ready to Implement")
    assert contract.permits("Reviewing", "Implementing")
    assert not contract.permits("Backlog", "Implementing")
    assert not contract.permits("Done", "Specifying")
    assert contract.automated == frozenset({"Backlog", "Done"})


def test_blocked_is_never_a_one_way_door() -> None:
    """Round three stalled here: a mechanically blocked card had only `Blocked -> Specifying`,
    so continuing an unchanged, correctly specified build required a re-specification nobody
    wanted. The operator's 'continue' decision must have its own transition, owned by the
    builder — and the specification path must survive beside it."""

    contract = load_contract()

    assert contract.permits("Blocked", "Implementing")
    assert contract.owner("Blocked", "Implementing") == "codex"
    assert contract.permits("Blocked", "Specifying")
    assert contract.owner("Blocked", "Specifying") == "claude"


def test_the_risk_label_is_read_from_the_card() -> None:
    card = Card(
        issue=1,
        title="t",
        open_state=True,
        status="Specifying",
        labels=("risk:R3",),
        item_id="i",
        project_id="p",
        field_id="f",
        options=_OPTIONS,
    )
    assert card.risk_class == "R3"

    unlabelled = Card(1, "t", True, "Backlog", (), "i", "p", "f", _OPTIONS)
    assert unlabelled.risk_class is None


def test_every_contract_status_has_at_least_one_way_in_or_is_automated() -> None:
    """A status nothing can reach is a dead column that will drift out of the process."""

    contract: Contract = load_contract()
    reachable = {target for _, target in contract.transitions} | contract.automated
    unreachable = set(contract.statuses) - reachable
    assert not unreachable, f"no transition reaches {sorted(unreachable)}"


def test_the_cli_rejoins_a_status_the_shell_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """`just` joins its variadic arguments into the recipe line unquoted, so under cmd.exe
    `"Ready to Implement"` arrived as three words and `--reason "the gap"` lost its quoting —
    the documented hand-back command was unusable on the platform the loop runs on."""

    recorded: dict[str, Any] = {}

    def fake_move(issue: int, target: str, **kwargs: Any) -> Card:
        recorded["target"] = target
        recorded.update(kwargs)
        return Card(issue, "t", True, target, ("risk:R2",), "i", "p", "f", _OPTIONS)

    monkeypatch.setattr(board, "move", fake_move)

    assert board.main(["move", "7", "Ready", "to", "Implement", "--actor", "claude"]) == 0
    assert recorded["target"] == "Ready to Implement"

    assert board.main(["move", "7", "ready-to-implement", "--actor", "claude"]) == 0
    assert recorded["target"] == "Ready to Implement", "case and hyphens resolve to the contract"

    assert (
        board.main(
            ["move", "7", "Specifying", "--actor", "codex", "--reason", "the", "spec", "gap"]
        )
        == 0
    )
    assert recorded["reason"] == "the spec gap", "an unquoted multi-word reason survives"

    assert board.main(["move", "7", "Bogus", "Status", "--actor", "claude"]) == 0
    assert recorded["target"] == "Bogus Status", "an unknown status reaches move() untouched"
