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
    main,
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
        status: str | None = "Ready to Implement",
        labels: set[str] | None = None,
        fail_on: str | None = None,
        sticky_remove: bool = False,
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
        self.sticky_remove = sticky_remove
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
        if self.sticky_remove:
            return
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
    with pytest.raises(BoardError, match="arm requirements not met: observed status='Specifying'"):
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
    assert PUBLIC_COMMANDS == ("status", "add", "move", "arm", "start", "withdraw")
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


@pytest.mark.parametrize("target", ("Specifying", "Implementing", "Blocked"))
def test_move_out_of_ready_removes_approved_before_status_change(target: str) -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})

    state = _service(gateway).move(110, target)

    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == ["remove approved", f"move the card to {target}"]
    assert state.status == target
    assert "approved" not in state.labels


def test_start_refuses_after_demoting_an_approved_card() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})
    service = _service(gateway)

    service.move(110, "Specifying")
    service.move(110, "Ready to Implement")

    with pytest.raises(BoardError, match="observed approved=absent"):
        service.start(110)
    assert gateway.state.status == "Ready to Implement"
    assert "approved" not in gateway.state.labels


def test_withdraw_removes_approved_without_moving_card() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})

    state = _service(gateway).withdraw(110)

    assert state.status == "Ready to Implement"
    assert "approved" not in state.labels
    assert ("remove approved", "approved") in gateway.calls
    assert not any(call[0].startswith("move the card") for call in gateway.calls)


def test_withdrawn_ready_card_can_run_full_arm_sequence() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})
    service = _service(gateway)
    service.withdraw(110)
    gateway.calls.clear()

    state = service.arm(110, body=_VALID_BODY, risk_class="R3")

    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == [
        "write the final issue body",
        "add risk:R3",
        "move the card to Ready to Implement",
        "add approved",
    ]
    assert "approved" in state.labels


@pytest.mark.parametrize("operation", ("move", "start", "withdraw"))
def test_every_permit_removal_is_verified_by_rereading_state(operation: str) -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"}, sticky_remove=True)
    service = _service(gateway)

    with pytest.raises(BoardError, match="observed approved=present"):
        if operation == "move":
            service.move(110, "Specifying")
        elif operation == "start":
            service.start(110)
        else:
            service.withdraw(110)


def test_move_refuses_before_status_change_when_permit_removal_does_not_stick() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"}, sticky_remove=True)

    with pytest.raises(BoardError, match="observed approved=present"):
        _service(gateway).move(110, "Specifying")

    assert gateway.state.status == "Ready to Implement"
    assert not any(call[0].startswith("move the card") for call in gateway.calls)


def test_start_refusal_names_observed_backlog_status() -> None:
    gateway = FakeGateway(status="Backlog", labels={"risk:R3"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert "observed status='Backlog'" in str(raised.value)


def test_start_refusal_names_only_missing_permit_when_ready() -> None:
    gateway = FakeGateway(labels={"risk:R3"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert str(raised.value) == "Start requirements not met: observed approved=absent"


def test_start_refusal_names_both_observed_risk_labels() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R1", "risk:R3"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert str(raised.value) == (
        "Start requirements not met: observed risk labels=['risk:R1', 'risk:R3']"
    )


def test_start_refusal_reports_every_observed_failure() -> None:
    gateway = FakeGateway(status="Backlog", labels={"risk:R1", "risk:R3"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert str(raised.value) == (
        "Start requirements not met: observed status='Backlog'; "
        "observed approved=absent; observed risk labels=['risk:R1', 'risk:R3']"
    )

    arm_gateway = FakeGateway(
        status="Specifying",
        labels={"approved", "risk:R1", "risk:R3"},
    )
    with pytest.raises(BoardError) as arm_raised:
        _service(arm_gateway).arm(110, body=_VALID_BODY, risk_class="R3")
    assert str(arm_raised.value) == (
        "arm requirements not met: observed status='Specifying'; "
        "observed approved=present; observed conflicting risk labels=['risk:R1']"
    )

    approval_gateway = FakeGateway(status="Blocked", labels=set())
    with pytest.raises(BoardError) as approval_raised:
        _service(approval_gateway)._write_approved(110, "R3")
    assert str(approval_raised.value) == (
        "approved requirements not met: observed status='Blocked'; observed risk labels=[]"
    )


@pytest.mark.parametrize(
    ("operation", "status", "expected"),
    (
        ("arm", "Specifying", "arm requirements not met: observed status='Specifying'"),
        (
            "approve",
            "Blocked",
            "approved requirements not met: observed status='Blocked'",
        ),
    ),
)
def test_arm_and_approval_write_refusals_name_observed_status(
    operation: str,
    status: str,
    expected: str,
) -> None:
    gateway = FakeGateway(status=status)
    service = _service(gateway)

    with pytest.raises(BoardError) as raised:
        if operation == "arm":
            service.arm(110, body=_VALID_BODY, risk_class="R3")
        else:
            service._write_approved(110, "R3")

    assert str(raised.value) == expected


@pytest.mark.parametrize("operation", ("start", "arm", "approve", "withdraw"))
def test_refusals_report_a_card_absent_from_project(operation: str) -> None:
    gateway = FakeGateway(status=None)
    service = _service(gateway)

    with pytest.raises(BoardError) as raised:
        if operation == "start":
            service.start(110)
        elif operation == "arm":
            service.arm(110, body=_VALID_BODY, risk_class="R3")
        elif operation == "approve":
            service._write_approved(110, "R3")
        else:
            service.withdraw(110)

    assert "observed project status=absent" in str(raised.value)
    assert "wrong status" not in str(raised.value)


def test_refusal_messages_contain_only_observed_state_values() -> None:
    gateway = FakeGateway(status="Specifying", labels={"risk:R0", "risk:R2"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert str(raised.value) == (
        "Start requirements not met: observed status='Specifying'; "
        "observed approved=absent; observed risk labels=['risk:R0', 'risk:R2']"
    )


def test_no_board_operation_path_reaches_armed_ready_without_arm() -> None:
    contract = load_contract()
    transitions = [
        transition
        for transition in contract.transitions
        if transition.source != "-" and transition.target != "Done"
    ]

    for transition in transitions:
        gateway = FakeGateway(
            status=transition.source,
            labels={"approved", "risk:R3"},
        )
        state = _service(gateway, contract).move(110, transition.target)
        if state.status == "Ready to Implement":
            assert "approved" not in state.labels, transition

    armed = FakeGateway(labels={"risk:R3"})
    armed_state = _service(armed, contract).arm(110, body=_VALID_BODY, risk_class="R3")
    assert armed_state.status == "Ready to Implement"
    assert "approved" in armed_state.labels


def test_only_arm_can_add_approved() -> None:
    gateways = {
        command: FakeGateway(status="Ready to Implement", labels={"approved", "risk:R3"})
        for command in PUBLIC_COMMANDS
        if command != "arm"
    }

    _service(gateways["status"]).status(110)
    _service(gateways["add"]).add(110)
    _service(gateways["move"]).move(110, "Specifying")
    _service(gateways["start"]).start(110)
    _service(gateways["withdraw"]).withdraw(110)

    assert all(("add approved", "approved") not in gateway.calls for gateway in gateways.values())


def test_refusal_messages_do_not_expose_sensitive_values() -> None:
    gateway = FakeGateway(status="Specifying", labels={"risk:R3"})
    gateway.state = replace(
        gateway.state,
        url=(
            "https://github.com/QPlus-Capital/trading-system/issues/110"
            "?credential=synthetic-private-value"
        ),
        body="account 123456789 token synthetic-private-value",
    )

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    message = str(raised.value)
    assert "observed status='Specifying'" in message
    assert "synthetic-private-value" not in message
    assert "123456789" not in message
    assert "github.com" not in message


def test_withdraw_cli_dispatches_to_board_service(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[int] = []

    class StubService:
        def __init__(self, gateway: object) -> None:
            del gateway

        def withdraw(self, issue: int) -> IssueState:
            calls.append(issue)
            return IssueState(
                number=issue,
                url="https://example.invalid/issue",
                body="",
                labels=frozenset({"risk:R3"}),
                status="Ready to Implement",
            )

    monkeypatch.setattr("scripts.quality.board.GhBoardGateway", lambda **kwargs: object())
    monkeypatch.setattr("scripts.quality.board.BoardService", StubService)

    assert main(["withdraw", "110"]) == 0
    assert calls == [110]
    assert capsys.readouterr().out == "#110: status=Ready to Implement labels=risk:R3\n"
