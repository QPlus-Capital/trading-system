"""Behavioural guards for contract-driven GitHub board operations."""

from __future__ import annotations

from dataclasses import replace

import pytest
from scripts.quality.board import (
    PUBLIC_COMMANDS,
    BoardError,
    BoardService,
    GhBoardGateway,
    IssueState,
)
from scripts.quality.workflow_contract import WorkflowContract, load_contract

_VALID_BODY = """## Problem
Problem.

## Goal
Goal.

## Scope
Board tooling.

## Non-goals
No automation.

## Acceptance criteria
- [ ] AC-01 Works.

## Invariants
- [ ] INV-01 Safe.

## Affected modules
scripts/quality/board.py

## Risk class
R3 — approval state governs every build.

## Verification plan
Behavioural tests.

## Open decisions (Jan)
None.
"""


class FakeGateway:
    def __init__(
        self,
        *,
        status: str = "Ready to Implement",
        labels: set[str] | None = None,
        fail_on: str | None = None,
        status_names: set[str] | None = None,
    ) -> None:
        contract_names = {item.name for item in load_contract().statuses}
        self.available_statuses = status_names if status_names is not None else contract_names
        self.state = IssueState(
            number=110,
            url="https://github.com/QPlus-Capital/trading-system/issues/110",
            body=_VALID_BODY,
            labels=frozenset(labels if labels is not None else {"risk:R3"}),
            status=status,
        )
        self.fail_on = fail_on
        self.calls: list[tuple[str, str]] = []

    def status_names(self) -> frozenset[str]:
        self.calls.append(("status_names", ""))
        return frozenset(self.available_statuses)

    def issue_state(self, issue: int) -> IssueState:
        assert issue == 110
        self.calls.append(("issue_state", str(issue)))
        return self.state

    def update_issue_body(self, issue: int, body: str) -> None:
        self._write("write the final issue body", body)
        self.state = replace(self.state, body=body)

    def add_label(self, issue: int, label: str) -> None:
        self._write(f"add {label}", label)
        self.state = replace(self.state, labels=self.state.labels | {label})

    def remove_label(self, issue: int, label: str) -> None:
        self._write(f"remove {label}", label)
        self.state = replace(self.state, labels=self.state.labels - {label})

    def set_status(self, issue: int, status: str) -> None:
        self._write(f"move the card to {status}", status)
        self.state = replace(self.state, status=status)

    def add_issue(self, issue: int) -> None:
        self._write("add issue", str(issue))

    def _write(self, operation: str, value: str) -> None:
        self.calls.append((operation, value))
        if self.fail_on == operation:
            raise BoardError(f"injected failure: {operation}")


def _service(gateway: FakeGateway, contract: WorkflowContract | None = None) -> BoardService:
    return BoardService(gateway, contract=contract or load_contract())


def test_arm_refuses_a_card_outside_ready_without_mutation() -> None:
    gateway = FakeGateway(status="Specifying")
    with pytest.raises(BoardError, match="Ready to Implement"):
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")
    assert [call for call in gateway.calls if call[0] != "status_names"] == [("issue_state", "110")]
    assert "approved" not in gateway.state.labels


def test_arm_derives_contract_order_and_never_approves_after_status_failure() -> None:
    gateway = FakeGateway(fail_on="move the card to Ready to Implement")
    contract = load_contract()
    shuffled = replace(contract, approval_steps=tuple(reversed(contract.approval_steps)))
    with pytest.raises(BoardError, match="injected failure"):
        _service(gateway, shuffled).arm(110, body=_VALID_BODY, risk_class="R3")
    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == [
        "write the final issue body",
        "add risk:R3",
        "move the card to Ready to Implement",
    ]
    assert "approved" not in gateway.state.labels


def test_start_moves_before_removing_permit_and_preserves_it_on_failure() -> None:
    failed = FakeGateway(labels={"approved", "risk:R3"}, fail_on="move the card to Implementing")
    with pytest.raises(BoardError, match="injected failure"):
        _service(failed).start(110)
    assert "approved" in failed.state.labels
    assert ("remove approved", "approved") not in failed.calls

    clean = FakeGateway(labels={"approved", "risk:R3"})
    _service(clean).start(110)
    writes = [call[0] for call in clean.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == ["move the card to Implementing", "remove approved"]
    assert clean.state.status == "Implementing"
    assert "approved" not in clean.state.labels


def test_every_contract_status_must_resolve_to_a_runtime_option() -> None:
    names = {item.name for item in load_contract().statuses} - {"Blocked"}
    gateway = FakeGateway(status_names=names)
    with pytest.raises(BoardError, match="Blocked"):
        _service(gateway).status(110)
    assert [call for call in gateway.calls if call[0] != "status_names"] == []


def test_missing_project_scope_has_one_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = GhBoardGateway()

    class Result:
        returncode = 0
        stdout = "Token scopes: 'repo', 'workflow'"
        stderr = ""

    monkeypatch.setattr("scripts.quality.board.subprocess.run", lambda *args, **kwargs: Result())
    with pytest.raises(
        BoardError,
        match=r"GitHub token needs the `project` scope; run `gh auth refresh -s project`\.",
    ):
        gateway.status_names()


def test_public_command_surface_cannot_done_merge_approve_or_create_pr() -> None:
    assert PUBLIC_COMMANDS == ("status", "add", "move", "arm", "start")
    forbidden = {"done", "merge", "approve", "pr", "pull-request"}
    assert forbidden.isdisjoint(PUBLIC_COMMANDS)

    gateway = FakeGateway(status="Reviewing")
    with pytest.raises(BoardError, match="Done"):
        _service(gateway).move(110, "Done")
    assert not any(call[0].startswith("move the card") for call in gateway.calls)


@pytest.mark.parametrize(
    "operation",
    (
        "write the final issue body",
        "add risk:R3",
        "move the card to Ready to Implement",
        "add approved",
    ),
)
def test_every_arm_write_failure_leaves_approved_absent(operation: str) -> None:
    gateway = FakeGateway(fail_on=operation)
    with pytest.raises(BoardError, match="injected failure"):
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")
    assert "approved" not in gateway.state.labels
