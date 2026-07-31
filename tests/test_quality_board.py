"""Behavioural guards for contract-driven GitHub board operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from scripts.quality.board import (
    PUBLIC_COMMANDS,
    BoardError,
    BoardService,
    GhBoardGateway,
    IssueState,
    main,
)
from scripts.quality.issue_body import validate_issue_body
from scripts.quality.workflow_contract import (
    ApprovalStep,
    Transition,
    WorkflowContract,
    load_contract,
)

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

_ROOT = Path(__file__).resolve().parents[1]
_WriteHook = Callable[[IssueState], IssueState]


class FakeGateway:
    def __init__(
        self,
        *,
        status: str | None = "Ready to Implement",
        labels: set[str] | None = None,
        fail_on: str | None = None,
        sticky_remove: bool = False,
        sticky_status: bool = False,
        sticky_add_labels: set[str] | None = None,
        status_names: set[str] | None = None,
        on_write: dict[str, _WriteHook] | None = None,
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
        self.sticky_status = sticky_status
        self.sticky_add_labels = frozenset(sticky_add_labels or set())
        self.on_write = dict(on_write or {})
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
        if label in self.sticky_add_labels:
            return
        self.state = replace(self.state, labels=self.state.labels | {label})

    def remove_label(self, issue: int, label: str) -> None:
        self._write(f"remove {label}", label)
        if self.sticky_remove:
            return
        self.state = replace(self.state, labels=self.state.labels - {label})

    def set_status(self, issue: int, status: str) -> None:
        self._write(f"move the card to {status}", status)
        if self.sticky_status:
            return
        self.state = replace(self.state, status=status)

    def add_issue(self, issue: int) -> None:
        self._write("add issue", str(issue))

    def _write(self, operation: str, value: str) -> None:
        self.calls.append((operation, value))
        if self.fail_on == operation:
            raise BoardError(f"injected failure: {operation}")
        hook = self.on_write.pop(operation, None)
        if hook is not None:
            self.state = hook(self.state)


class StrictIssueGateway(FakeGateway):
    """Reject every write that loses the selected issue or its body."""

    @staticmethod
    def _assert_issue(issue: int) -> None:
        assert issue == 110

    def update_issue_body(self, issue: int, body: str) -> None:
        self._assert_issue(issue)
        assert isinstance(body, str)
        super().update_issue_body(issue, body)

    def add_label(self, issue: int, label: str) -> None:
        self._assert_issue(issue)
        super().add_label(issue, label)

    def remove_label(self, issue: int, label: str) -> None:
        self._assert_issue(issue)
        super().remove_label(issue, label)

    def set_status(self, issue: int, status: str) -> None:
        self._assert_issue(issue)
        super().set_status(issue, status)

    def add_issue(self, issue: int) -> None:
        self._assert_issue(issue)
        super().add_issue(issue)


def _service(gateway: FakeGateway, contract: WorkflowContract | None = None) -> BoardService:
    return BoardService(gateway, contract=contract or load_contract())


def test_every_board_write_preserves_the_selected_issue_and_body() -> None:
    _service(StrictIssueGateway()).add(110)

    armed = StrictIssueGateway(labels=set())
    _service(armed).arm(110, body=_VALID_BODY, risk_class="R3")

    moved = StrictIssueGateway(labels={"approved", "risk:R3"})
    _service(moved).move(110, "Specifying")

    started = StrictIssueGateway(labels={"approved", "risk:R3"})
    _service(started).start(110)


def test_missing_status_options_report_the_complete_exact_set() -> None:
    names = {item.name for item in load_contract().statuses} - {"Blocked", "Done"}
    gateway = FakeGateway(status_names=names)

    with pytest.raises(BoardError) as raised:
        _service(gateway).status(110)

    assert str(raised.value) == "project is missing contract Status option(s): Blocked, Done"


def test_add_requires_project_membership_readback() -> None:
    gateway = FakeGateway(status=None)

    with pytest.raises(BoardError) as raised:
        _service(gateway).add(110)

    assert str(raised.value) == "issue #110 was not added to the project"


def test_arm_reports_the_complete_issue_body_validation() -> None:
    gateway = FakeGateway()
    expected = "issue body is not approvable: " + "; ".join(validate_issue_body("", "R3").issues)

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body="", risk_class="R3")

    assert str(raised.value) == expected


def test_arm_rejects_an_unimplemented_approval_action_exactly() -> None:
    contract = replace(
        load_contract(),
        approval_steps=(ApprovalStep(1, "unknown action", False),),
    )

    with pytest.raises(BoardError) as raised:
        _service(FakeGateway(labels=set()), contract).arm(
            110,
            body=_VALID_BODY,
            risk_class="R3",
        )

    assert str(raised.value) == ("no board operation implements approval action 'unknown action'")


def test_arm_reports_a_lost_approval_write_exactly() -> None:
    gateway = FakeGateway(labels=set(), sticky_add_labels={"approved"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    assert str(raised.value) == "approval operation completed without the approved label"


def test_permit_removal_failure_is_reported_exactly() -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"}, sticky_remove=True)

    with pytest.raises(BoardError) as raised:
        _service(gateway).withdraw(110)

    assert str(raised.value) == ("permit removal did not take effect: observed approved=present")


def test_move_reports_absent_project_membership_exactly() -> None:
    with pytest.raises(BoardError) as raised:
        _service(FakeGateway(status=None)).move(110, "Specifying")

    assert str(raised.value) == "move refused: observed project status=absent"


def test_withdraw_reports_absent_project_membership_exactly() -> None:
    with pytest.raises(BoardError) as raised:
        _service(FakeGateway(status=None)).withdraw(110)

    assert str(raised.value) == "withdraw refused: observed project status=absent"


def test_done_remains_reserved_for_project_automation_exactly() -> None:
    with pytest.raises(BoardError) as raised:
        _service(FakeGateway(status="Reviewing")).move(110, "Done")

    assert str(raised.value) == "Done is set only by project automation after merge"


def test_move_reports_a_disallowed_contract_edge_exactly() -> None:
    with pytest.raises(BoardError) as raised:
        _service(FakeGateway(status="Backlog")).move(110, "Reviewing")

    assert str(raised.value) == "contract does not allow 'Backlog' -> 'Reviewing'"


def test_move_reports_the_reserved_start_edge_exactly() -> None:
    with pytest.raises(BoardError) as raised:
        _service(FakeGateway()).move(110, "Implementing")

    assert str(raised.value) == (
        "contract edge 'Ready to Implement' -> 'Implementing' is reserved for `start`"
    )


def test_move_reports_the_complete_post_withdrawal_failure_exactly() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        fail_on="move the card to Specifying",
    )

    with pytest.raises(BoardError) as raised:
        _service(gateway).move(110, "Specifying")

    assert str(raised.value) == (
        "status update failed after the permit was already withdrawn: observed approved=absent"
    )


def test_start_requires_the_named_builder_guard_exactly() -> None:
    contract = load_contract()
    without_start = replace(
        contract,
        builder_guards=tuple(guard for guard in contract.builder_guards if guard.name != "Start"),
    )

    with pytest.raises(BoardError) as raised:
        _service(
            FakeGateway(labels={"approved", "risk:R3"}),
            without_start,
        ).start(110)

    assert str(raised.value) == "workflow contract has no Start builder guard"


def test_start_ignores_build_start_triggers_for_other_sources_and_actors() -> None:
    contract = load_contract()
    with_distractor = replace(
        contract,
        transitions=contract.transitions
        + (
            Transition(
                source="Backlog",
                target="Specifying",
                actor="Claude",
                trigger="build starts; synthetic distractor",
            ),
        ),
    )
    gateway = FakeGateway(labels={"approved", "risk:R3"})

    state = _service(gateway, with_distractor).start(110)

    assert state.status == "Implementing"
    assert "approved" not in state.labels


def test_start_requires_exactly_one_codex_build_start_transition() -> None:
    contract = load_contract()
    without_start_transition = replace(
        contract,
        transitions=tuple(
            transition
            for transition in contract.transitions
            if not (
                transition.source == "Ready to Implement"
                and transition.actor == "Codex"
                and transition.trigger.startswith("build starts;")
            )
        ),
    )

    with pytest.raises(BoardError) as raised:
        _service(
            FakeGateway(labels={"approved", "risk:R3"}),
            without_start_transition,
        ).start(110)

    assert str(raised.value) == ("workflow contract must define one Codex build-start transition")


@pytest.mark.parametrize(
    "status",
    tuple(item.name for item in load_contract().statuses if item.name != "Ready to Implement"),
)
def test_arm_refuses_a_card_outside_ready_without_mutation(status: str) -> None:
    gateway = FakeGateway(status=status)
    with pytest.raises(
        BoardError,
        match=rf"arm requirements not met: observed status='{status}'",
    ):
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


def test_start_issues_no_removal_when_permit_vanishes_during_move() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        on_write={
            "move the card to Implementing": lambda state: replace(
                state,
                labels=state.labels - {"approved"},
            ),
        },
    )

    state = _service(gateway).start(110)

    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == ["move the card to Implementing"]
    assert "approved" not in state.labels


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


@pytest.mark.parametrize("target", ("Specifying", "Blocked"))
def test_move_out_of_ready_removes_approved_before_status_change(target: str) -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})

    state = _service(gateway).move(110, target)

    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == ["remove approved", f"move the card to {target}"]
    assert state.status == target
    assert "approved" not in state.labels


def test_move_cannot_reach_implementing_without_the_start_guard() -> None:
    gateway = FakeGateway(labels=set())

    with pytest.raises(BoardError, match="reserved for `start`"):
        _service(gateway).move(110, "Implementing")

    assert gateway.state.status == "Ready to Implement"
    assert gateway.calls == [("status_names", ""), ("issue_state", "110")]


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
    with pytest.raises(BoardError, match="observed approved=absent"):
        _service(gateway).start(110)


def test_withdrawn_ready_card_can_run_full_arm_sequence() -> None:
    observed_statuses: list[str | None] = []

    def observe_noop_status(state: IssueState) -> IssueState:
        observed_statuses.append(state.status)
        return state

    gateway = FakeGateway(labels={"approved", "risk:R3"})
    service = _service(gateway)
    service.withdraw(110)
    gateway.calls.clear()
    gateway.on_write["move the card to Ready to Implement"] = observe_noop_status

    state = service.arm(110, body=_VALID_BODY, risk_class="R3")

    writes = [call[0] for call in gateway.calls if call[0] not in {"status_names", "issue_state"}]
    assert writes == [
        "write the final issue body",
        "add risk:R3",
        "move the card to Ready to Implement",
        "add approved",
    ]
    assert observed_statuses == ["Ready to Implement"]
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


def test_move_refuses_when_the_status_write_does_not_take_effect() -> None:
    gateway = FakeGateway(
        status="Implementing",
        labels={"approved", "risk:R3"},
        sticky_status=True,
    )

    with pytest.raises(BoardError, match="status update did not produce 'Reviewing'"):
        _service(gateway).move(110, "Reviewing")

    assert gateway.state.status == "Implementing"
    assert "approved" not in gateway.state.labels


def test_start_refuses_when_the_status_write_does_not_take_effect() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        sticky_status=True,
    )

    with pytest.raises(BoardError, match="build-start status update did not produce"):
        _service(gateway).start(110)

    assert gateway.state.status == "Ready to Implement"
    assert "approved" in gateway.state.labels


def test_arm_refuses_when_the_approved_write_does_not_take_effect() -> None:
    gateway = FakeGateway(
        labels=set(),
        sticky_add_labels={"approved"},
    )

    with pytest.raises(BoardError, match="completed without the approved label"):
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    assert gateway.state.status == "Ready to Implement"
    assert "risk:R3" in gateway.state.labels
    assert "approved" not in gateway.state.labels


def test_move_refuses_when_status_changes_during_permit_withdrawal() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        on_write={
            "remove approved": lambda state: replace(state, status="Blocked"),
        },
    )

    with pytest.raises(
        BoardError,
        match="status changed while withdrawing the permit: observed status='Blocked'",
    ):
        _service(gateway).move(110, "Specifying")

    assert gateway.state.status == "Blocked"
    assert "approved" not in gateway.state.labels
    assert not any(call[0].startswith("move the card") for call in gateway.calls)


def test_move_refuses_when_a_third_party_readds_permit_after_status_write() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        on_write={
            "move the card to Specifying": lambda state: replace(
                state,
                labels=state.labels | {"approved"},
            ),
        },
    )

    with pytest.raises(
        BoardError,
        match="status update retained a stale permit: observed approved=present",
    ):
        _service(gateway).move(110, "Specifying")

    assert gateway.state.status == "Specifying"
    assert "approved" in gateway.state.labels


def test_withdraw_refuses_when_status_changes_during_permit_removal() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        on_write={
            "remove approved": lambda state: replace(state, status="Blocked"),
        },
    )

    with pytest.raises(
        BoardError,
        match="status changed while withdrawing the permit: observed status='Blocked'",
    ):
        _service(gateway).withdraw(110)

    assert gateway.state.status == "Blocked"
    assert "approved" not in gateway.state.labels


def test_move_failure_after_withdrawal_reports_the_absent_permit() -> None:
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        fail_on="move the card to Specifying",
    )

    with pytest.raises(BoardError, match="permit was already withdrawn") as raised:
        _service(gateway).move(110, "Specifying")

    assert "observed approved=absent" in str(raised.value)
    assert gateway.state.status == "Ready to Implement"
    assert "approved" not in gateway.state.labels


def test_move_without_a_permit_propagates_the_underlying_failure() -> None:
    gateway = FakeGateway(
        labels={"risk:R3"},
        fail_on="move the card to Specifying",
    )

    with pytest.raises(BoardError) as raised:
        _service(gateway).move(110, "Specifying")

    assert str(raised.value) == "injected failure: move the card to Specifying"
    assert gateway.state.status == "Ready to Implement"
    assert "approved" not in gateway.state.labels
    assert not any(call[0].startswith("remove") for call in gateway.calls)


@pytest.mark.parametrize("target", ("Backlog", "Reviewing", "Done"))
def test_a_refused_move_preserves_the_permit(target: str) -> None:
    gateway = FakeGateway(labels={"approved", "risk:R3"})

    with pytest.raises(BoardError):
        _service(gateway).move(110, target)

    assert gateway.state.status == "Ready to Implement"
    assert "approved" in gateway.state.labels
    assert not any(call[0].startswith("remove") for call in gateway.calls)


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


def test_start_refuses_a_card_without_any_risk_label() -> None:
    gateway = FakeGateway(labels={"approved"})

    with pytest.raises(BoardError) as raised:
        _service(gateway).start(110)

    assert str(raised.value) == "Start requirements not met: observed risk labels=[]"
    assert gateway.state.status == "Ready to Implement"
    assert "approved" in gateway.state.labels


def test_start_guard_condition_set_is_unchanged() -> None:
    contract_risk_labels = {"risk:R0", "risk:R1", "risk:R2", "risk:R3"}
    label_universe = (
        "approved",
        *sorted(contract_risk_labels),
        "risk:R4",
    )
    statuses = tuple(status.name for status in load_contract().statuses)

    for status in statuses:
        for mask in range(1 << len(label_universe)):
            labels = {label for index, label in enumerate(label_universe) if mask & (1 << index)}
            risks = labels & contract_risk_labels
            expected_accept = (
                status == "Ready to Implement" and "approved" in labels and len(risks) == 1
            )
            gateway = FakeGateway(status=status, labels=labels)

            if expected_accept:
                assert _service(gateway).start(110).status == "Implementing"
            else:
                with pytest.raises(BoardError, match=r"^Start requirements not met: "):
                    _service(gateway).start(110)


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
    assert "approved" not in approval_gateway.state.labels
    assert ("add approved", "approved") not in approval_gateway.calls


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
    if operation == "approve":
        assert "approved" not in gateway.state.labels
        assert ("add approved", "approved") not in gateway.calls


def test_arm_refuses_when_status_changes_before_the_approval_write() -> None:
    gateway = FakeGateway(
        labels=set(),
        sticky_status=True,
        on_write={
            "move the card to Ready to Implement": lambda state: replace(
                state,
                status="Implementing",
            )
        },
    )

    with pytest.raises(
        BoardError,
        match="approved requirements not met: observed status='Implementing'",
    ):
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    assert gateway.state.status == "Implementing"
    assert ("add approved", "approved") not in gateway.calls


@pytest.mark.parametrize("operation", ("move", "start", "arm", "approve", "withdraw"))
def test_refusals_report_a_card_absent_from_project(operation: str) -> None:
    gateway = FakeGateway(status=None)
    service = _service(gateway)

    with pytest.raises(BoardError) as raised:
        if operation == "move":
            service.move(110, "Specifying")
        elif operation == "start":
            service.start(110)
        elif operation == "arm":
            service.arm(110, body=_VALID_BODY, risk_class="R3")
        elif operation == "approve":
            service._write_approved(110, "R3")
        else:
            service.withdraw(110)

    assert "observed project status=absent" in str(raised.value)
    assert "#110" not in str(raised.value)


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
        if transition.source == "Ready to Implement" and transition.target == "Implementing":
            with pytest.raises(BoardError, match="reserved for `start`"):
                _service(gateway, contract).move(110, transition.target)
            assert "approved" in gateway.state.labels
            continue
        state = _service(gateway, contract).move(110, transition.target)
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


def test_interleaved_state_secrets_are_not_echoed_by_verification_failure() -> None:
    marker = "synthetic-private-value"
    gateway = FakeGateway(
        labels={"approved", "risk:R3"},
        on_write={
            "move the card to Specifying": lambda state: replace(
                state,
                url=f"https://example.invalid/?access_token={marker}",
                body=f"account 123456789 token {marker}",
                labels=state.labels | {"approved"},
            ),
        },
    )

    with pytest.raises(BoardError) as raised:
        _service(gateway).move(110, "Specifying")

    message = str(raised.value)
    assert message == "status update retained a stale permit: observed approved=present"
    assert marker not in message
    assert "123456789" not in message
    assert "example.invalid" not in message


def test_unapprovable_body_is_not_echoed_in_refusal() -> None:
    marker = "synthetic-private-value"
    body = f"not approvable; account 123456789 token {marker}"
    gateway = FakeGateway()

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body=body, risk_class="R3")

    message = str(raised.value)
    assert message.startswith("issue body is not approvable:")
    assert marker not in message
    assert "123456789" not in message
    assert body not in message
    assert not any(call[0] not in {"status_names", "issue_state"} for call in gateway.calls)


def test_raw_gh_stderr_is_not_echoed_in_board_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "synthetic-private-value"
    gateway = GhBoardGateway()
    gateway._scope_checked = True

    class Result:
        returncode = 1
        stdout = ""
        stderr = f"request failed at https://example.invalid/?access_token={marker}"

    monkeypatch.setattr("scripts.quality.board.subprocess.run", lambda *args, **kwargs: Result())

    with pytest.raises(BoardError) as raised:
        gateway._run(("issue", "view", "110"))

    message = str(raised.value)
    assert message == "GitHub board operation failed; inspect the local gh error."
    assert marker not in message
    assert "example.invalid" not in message


@pytest.mark.parametrize(
    ("body", "risk_class", "expected"),
    (
        ("not an issue body", "R3", "issue body is not approvable"),
        (_VALID_BODY, "R9", "unknown risk class: R9"),
    ),
)
def test_arm_refuses_unapprovable_input_before_any_write(
    body: str,
    risk_class: str,
    expected: str,
) -> None:
    gateway = FakeGateway()

    with pytest.raises(BoardError, match=expected):
        _service(gateway).arm(110, body=body, risk_class=risk_class)

    assert not any(call[0] not in {"status_names", "issue_state"} for call in gateway.calls)


@pytest.mark.parametrize("risk_class", ("R0", "R1", "R2", "R3"))
def test_arm_writes_the_requested_risk_label_for_every_class(risk_class: str) -> None:
    body = _VALID_BODY.replace("R3 — approval", f"{risk_class} — approval")
    gateway = FakeGateway(labels=set())

    state = _service(gateway).arm(110, body=body, risk_class=risk_class)

    assert (f"add risk:{risk_class}", f"risk:{risk_class}") in gateway.calls
    assert {
        label for label in state.labels if label in {"risk:R0", "risk:R1", "risk:R2", "risk:R3"}
    } == {f"risk:{risk_class}"}
    assert "approved" in state.labels


def test_arm_ignores_a_non_contract_risk_lookalike() -> None:
    gateway = FakeGateway(labels={"risk:R4"})

    state = _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    assert "approved" in state.labels
    assert {"risk:R3", "risk:R4"} <= state.labels


def test_arm_reports_only_contract_risks_when_risk_write_is_lost() -> None:
    gateway = FakeGateway(
        labels={"risk:R4"},
        sticky_add_labels={"risk:R3"},
    )

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body=_VALID_BODY, risk_class="R3")

    assert str(raised.value) == "approved requirements not met: observed risk labels=[]"
    assert "approved" not in gateway.state.labels


@pytest.mark.parametrize(
    ("requested", "existing"),
    (
        ("R0", "risk:R3"),
        ("R1", "risk:R0"),
        ("R2", "risk:R1"),
        ("R3", "risk:R2"),
    ),
)
def test_arm_refuses_conflicting_risk_for_every_requested_class(
    requested: str,
    existing: str,
) -> None:
    body = _VALID_BODY.replace("R3 — approval", f"{requested} — approval")
    if requested == "R3":
        body = body.replace("Board tooling.", "R3 board tooling.")
    assert body != _VALID_BODY
    gateway = FakeGateway(labels={existing})

    with pytest.raises(BoardError) as raised:
        _service(gateway).arm(110, body=body, risk_class=requested)

    assert str(raised.value) == (
        f"arm requirements not met: observed conflicting risk labels=['{existing}']"
    )
    assert not any(call[0].startswith(("add", "move", "write")) for call in gateway.calls)


def test_workflow_documents_the_complete_public_board_command_surface() -> None:
    text = (_ROOT / "docs" / "engineering" / "workflow.md").read_text(encoding="utf-8")
    section = text.split("### Board command surface", 1)[1].split("## The labels", 1)[0]
    documented = {line.split("`", 2)[1] for line in section.splitlines() if line.startswith("| `")}
    assert documented == set(PUBLIC_COMMANDS)


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


def test_cli_refusal_returns_two_and_keeps_the_stable_prefix(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class StubService:
        def __init__(self, gateway: object) -> None:
            del gateway

        def start(self, issue: int) -> IssueState:
            raise BoardError(f"refused issue {issue}")

    monkeypatch.setattr("scripts.quality.board.GhBoardGateway", lambda **kwargs: object())
    monkeypatch.setattr("scripts.quality.board.BoardService", StubService)

    assert main(["start", "110"]) == 2
    assert capsys.readouterr().err == "Board operation refused: refused issue 110\n"
