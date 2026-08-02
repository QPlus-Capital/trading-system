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
    confirmed = board.move(101, "Ready to Implement")

    assert confirmed.status == "Ready to Implement"
    kinds = ["mutation" in call["query"] for call in fake_graphql]
    assert kinds == [False, True, False], "read, write, then verify"


def test_a_transition_the_contract_omits_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    with pytest.raises(BoardError, match="does not permit"):
        board.move(101, "Reviewing")
    assert all("mutation" not in call["query"] for call in fake_graphql), "nothing was written"


def test_an_automation_owned_status_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    """`Backlog` and `Done` follow the issue's own lifecycle. An agent setting them would make the
    board disagree with whether the issue is open."""

    for status in ("Backlog", "Done"):
        with pytest.raises(BoardError, match="project automation"):
            board.move(101, status)
    assert fake_graphql == []


def test_an_unknown_status_is_refused(fake_graphql: list[dict[str, Any]]) -> None:
    with pytest.raises(BoardError, match="not a status"):
        board.move(101, "Erledigt")
    assert fake_graphql == []


def test_moving_to_the_current_status_writes_nothing(fake_graphql: list[dict[str, Any]]) -> None:
    card = board.move(101, "Specifying")

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
        board.move(101, "Ready to Implement")


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
