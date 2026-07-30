"""Contract-driven, fail-closed GitHub Project board operations."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from scripts.quality.classify import CLASSES, REPO_ROOT
from scripts.quality.issue_body import validate_issue_body
from scripts.quality.workflow_contract import WorkflowContract, load_contract

PUBLIC_COMMANDS = ("status", "add", "move", "arm", "start")
_RISK_LABEL = re.compile(r"^risk:(R[0-3])$")
_PROJECT_SCOPE_ERROR = "GitHub token needs the `project` scope; run `gh auth refresh -s project`."


class BoardError(RuntimeError):
    """A board mutation was refused or could not be verified."""


@dataclass(frozen=True)
class IssueState:
    """The board and label state needed by ordered workflow operations."""

    number: int
    url: str
    body: str
    labels: frozenset[str]
    status: str | None


class BoardGateway(Protocol):
    """External operations used by the pure ordering service."""

    def status_names(self) -> frozenset[str]: ...

    def issue_state(self, issue: int) -> IssueState: ...

    def update_issue_body(self, issue: int, body: str) -> None: ...

    def add_label(self, issue: int, label: str) -> None: ...

    def remove_label(self, issue: int, label: str) -> None: ...

    def set_status(self, issue: int, status: str) -> None: ...

    def add_issue(self, issue: int) -> None: ...


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BoardError(f"{name} must be a JSON object")
    return cast(dict[str, object], value)


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise BoardError(f"{name} must be a JSON array")
    return cast(list[object], value)


def _text(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise BoardError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class _Project:
    project_id: str
    status_field_id: str
    option_ids: Mapping[str, str]


class GhBoardGateway:
    """Thin `gh` adapter; all ordering and policy remains in :class:`BoardService`."""

    def __init__(
        self,
        *,
        repository: str = "QPlus-Capital/trading-system",
        owner: str = "QPlus-Capital",
        project_number: int = 1,
        root: Path = REPO_ROOT,
    ) -> None:
        self.repository = repository
        self.owner = owner
        self.project_number = project_number
        self.root = root
        self._scope_checked = False

    def _ensure_project_scope(self) -> None:
        if self._scope_checked:
            return
        completed = subprocess.run(
            ["gh", "auth", "status", "--hostname", "github.com"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0:
            raise BoardError("GitHub CLI is not authenticated for github.com.")
        scopes = re.search(r"Token scopes:\s*(?P<scopes>.+)", output, re.IGNORECASE)
        if scopes is None or "project" not in {
            item.strip(" '\"") for item in scopes.group("scopes").split(",")
        }:
            raise BoardError(_PROJECT_SCOPE_ERROR)
        self._scope_checked = True

    def _run(self, args: Sequence[str]) -> str:
        self._ensure_project_scope()
        completed = subprocess.run(
            ["gh", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}".casefold()
            if "project" in combined and (
                "scope" in combined or "resource not accessible" in combined or "404" in combined
            ):
                raise BoardError(_PROJECT_SCOPE_ERROR)
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown GitHub error"
            raise BoardError(f"GitHub board operation failed: {detail}")
        return completed.stdout

    def _json(self, args: Sequence[str], name: str) -> dict[str, object]:
        try:
            return _object(json.loads(self._run(args)), name)
        except json.JSONDecodeError as exc:
            raise BoardError(f"{name} returned invalid JSON") from exc

    def _project(self) -> _Project:
        view = self._json(
            (
                "project",
                "view",
                str(self.project_number),
                "--owner",
                self.owner,
                "--format",
                "json",
            ),
            "gh project view",
        )
        fields = self._json(
            (
                "project",
                "field-list",
                str(self.project_number),
                "--owner",
                self.owner,
                "--format",
                "json",
            ),
            "gh project field-list",
        )
        status_fields = [
            _object(item, "project field")
            for item in _array(fields.get("fields"), "project fields")
            if isinstance(item, dict) and item.get("name") == "Status"
        ]
        if len(status_fields) != 1:
            raise BoardError("project must have exactly one Status field")
        status_field = status_fields[0]
        options: dict[str, str] = {}
        for raw in _array(status_field.get("options"), "Status options"):
            option = _object(raw, "Status option")
            name = _text(option, "name")
            if name in options:
                raise BoardError(f"project has duplicate Status option: {name}")
            options[name] = _text(option, "id")
        return _Project(
            project_id=_text(view, "id"),
            status_field_id=_text(status_field, "id"),
            option_ids=options,
        )

    def _items(self) -> tuple[dict[str, object], ...]:
        data = self._json(
            (
                "project",
                "item-list",
                str(self.project_number),
                "--owner",
                self.owner,
                "--limit",
                "1000",
                "--format",
                "json",
            ),
            "gh project item-list",
        )
        return tuple(_object(item, "project item") for item in _array(data.get("items"), "items"))

    def _item(self, issue: int) -> dict[str, object] | None:
        for item in self._items():
            content = item.get("content")
            if not isinstance(content, dict):
                continue
            repository = str(item.get("repository", "")).removeprefix("https://github.com/")
            content_repository = str(content.get("repository", "")).removeprefix(
                "https://github.com/"
            )
            if content.get("number") == issue and self.repository in {
                repository,
                content_repository,
            }:
                return item
        return None

    def status_names(self) -> frozenset[str]:
        return frozenset(self._project().option_ids)

    def issue_state(self, issue: int) -> IssueState:
        data = self._json(
            (
                "issue",
                "view",
                str(issue),
                "--repo",
                self.repository,
                "--json",
                "body,labels,url",
            ),
            "gh issue view",
        )
        labels = frozenset(
            _text(_object(item, "issue label"), "name")
            for item in _array(data.get("labels"), "issue labels")
        )
        item = self._item(issue)
        status: str | None = None
        if item is not None:
            raw_status = item.get("status")
            if raw_status is not None and not isinstance(raw_status, str):
                raise BoardError("project item status must be a string")
            status = raw_status
        return IssueState(
            number=issue,
            url=_text(data, "url"),
            body=str(data.get("body", "")),
            labels=labels,
            status=status,
        )

    def update_issue_body(self, issue: int, body: str) -> None:
        self._run(
            (
                "issue",
                "edit",
                str(issue),
                "--repo",
                self.repository,
                "--body",
                body,
            )
        )

    def add_label(self, issue: int, label: str) -> None:
        self._run(
            (
                "issue",
                "edit",
                str(issue),
                "--repo",
                self.repository,
                "--add-label",
                label,
            )
        )

    def remove_label(self, issue: int, label: str) -> None:
        self._run(
            (
                "issue",
                "edit",
                str(issue),
                "--repo",
                self.repository,
                "--remove-label",
                label,
            )
        )

    def set_status(self, issue: int, status: str) -> None:
        project = self._project()
        option_id = project.option_ids.get(status)
        if option_id is None:
            raise BoardError(f"project has no Status option named {status!r}")
        item = self._item(issue)
        if item is None:
            raise BoardError(f"issue #{issue} is not on project {self.project_number}")
        self._run(
            (
                "project",
                "item-edit",
                "--id",
                _text(item, "id"),
                "--project-id",
                project.project_id,
                "--field-id",
                project.status_field_id,
                "--single-select-option-id",
                option_id,
            )
        )

    def add_issue(self, issue: int) -> None:
        if self._item(issue) is not None:
            return
        state = self.issue_state(issue)
        self._run(
            (
                "project",
                "item-add",
                str(self.project_number),
                "--owner",
                self.owner,
                "--url",
                state.url,
                "--format",
                "json",
            )
        )


class BoardService:
    """Apply the machine contract to ordered GitHub mutations."""

    def __init__(
        self,
        gateway: BoardGateway,
        *,
        contract: WorkflowContract | None = None,
    ) -> None:
        self.gateway = gateway
        self.contract = contract or load_contract()

    def _verify_status_options(self) -> None:
        required = {status.name for status in self.contract.statuses}
        missing = required - set(self.gateway.status_names())
        if missing:
            raise BoardError(
                "project is missing contract Status option(s): " + ", ".join(sorted(missing))
            )

    def status(self, issue: int) -> IssueState:
        self._verify_status_options()
        return self.gateway.issue_state(issue)

    def add(self, issue: int) -> IssueState:
        self._verify_status_options()
        self.gateway.add_issue(issue)
        state = self.gateway.issue_state(issue)
        if state.status is None:
            raise BoardError(f"issue #{issue} was not added to the project")
        return state

    def move(self, issue: int, target: str) -> IssueState:
        self._verify_status_options()
        if target == "Done":
            raise BoardError("Done is set only by project automation after merge")
        state = self.gateway.issue_state(issue)
        if state.status is None:
            raise BoardError(f"issue #{issue} is not on the project")
        allowed = {
            transition.target
            for transition in self.contract.transitions
            if transition.source == state.status and transition.target != "Done"
        }
        if target not in allowed:
            raise BoardError(f"contract does not allow {state.status!r} -> {target!r}")
        self.gateway.set_status(issue, target)
        result = self.gateway.issue_state(issue)
        if result.status != target:
            raise BoardError(f"status update did not produce {target!r}")
        return result

    def arm(self, issue: int, *, body: str, risk_class: str) -> IssueState:
        """Apply the contract approval steps and write `approved` last."""

        self._verify_status_options()
        if risk_class not in CLASSES:
            raise BoardError(f"unknown risk class: {risk_class}")
        initial = self.gateway.issue_state(issue)
        if initial.status != "Ready to Implement":
            raise BoardError("issue must be in Ready to Implement before it can be armed")
        if "approved" in initial.labels:
            raise BoardError("issue is already armed")
        requested_risk = f"risk:{risk_class}"
        existing_risks = {label for label in initial.labels if _RISK_LABEL.fullmatch(label)}
        if existing_risks - {requested_risk}:
            raise BoardError(
                "issue carries a conflicting risk label: "
                + ", ".join(sorted(existing_risks - {requested_risk}))
            )
        validation = validate_issue_body(body, risk_class)
        if not validation.ok:
            raise BoardError("issue body is not approvable: " + "; ".join(validation.issues))

        actions = {
            "write the final issue body": lambda: self.gateway.update_issue_body(issue, body),
            "add risk:Rn": lambda: self.gateway.add_label(issue, requested_risk),
            "move the card to Ready to Implement": lambda: self.gateway.set_status(
                issue, "Ready to Implement"
            ),
            "add approved": lambda: self._write_approved(issue, risk_class),
        }
        for step in sorted(self.contract.approval_steps, key=lambda item: item.order):
            action = actions.get(step.action)
            if action is None:
                raise BoardError(f"no board operation implements approval action {step.action!r}")
            action()
        result = self.gateway.issue_state(issue)
        if "approved" not in result.labels:
            raise BoardError("approval operation completed without the approved label")
        return result

    def _write_approved(self, issue: int, risk_class: str) -> None:
        state = self.gateway.issue_state(issue)
        if state.status != "Ready to Implement":
            raise BoardError("approved refused: card is not in Ready to Implement")
        if f"risk:{risk_class}" not in state.labels:
            raise BoardError(f"approved refused: risk:{risk_class} is absent")
        self.gateway.add_label(issue, "approved")

    def start(self, issue: int) -> IssueState:
        """Consume the Start guard: status first, permit removal second."""

        self._verify_status_options()
        guards = {guard.name: guard for guard in self.contract.builder_guards}
        if "Start" not in guards:
            raise BoardError("workflow contract has no Start builder guard")
        state = self.gateway.issue_state(issue)
        risk_labels = {label for label in state.labels if _RISK_LABEL.fullmatch(label)}
        if (
            state.status != "Ready to Implement"
            or "approved" not in state.labels
            or len(risk_labels) != 1
        ):
            raise BoardError(
                "Start requires Ready to Implement, approved, and exactly one risk:Rn label"
            )
        transitions = [
            item
            for item in self.contract.transitions
            if item.source == state.status
            and item.actor == "Codex"
            and item.trigger.startswith("build starts;")
        ]
        if len(transitions) != 1:
            raise BoardError("workflow contract must define one Codex build-start transition")
        target = transitions[0].target
        self.gateway.set_status(issue, target)
        moved = self.gateway.issue_state(issue)
        if moved.status != target:
            raise BoardError(f"build-start status update did not produce {target!r}")
        self.gateway.remove_label(issue, "approved")
        result = self.gateway.issue_state(issue)
        if "approved" in result.labels:
            raise BoardError("build-start permit removal did not take effect")
        return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="QPlus-Capital/trading-system")
    parser.add_argument("--owner", default="QPlus-Capital")
    parser.add_argument("--project", type=int, default=1)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in PUBLIC_COMMANDS:
        child = subparsers.add_parser(command)
        child.add_argument("issue", type=int)
        if command == "move":
            child.add_argument("status")
        elif command == "arm":
            child.add_argument("--body-file", type=Path, required=True)
            child.add_argument("--risk", choices=CLASSES, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    service = BoardService(
        GhBoardGateway(
            repository=args.repo,
            owner=args.owner,
            project_number=args.project,
        )
    )
    try:
        if args.command == "status":
            state = service.status(args.issue)
        elif args.command == "add":
            state = service.add(args.issue)
        elif args.command == "move":
            state = service.move(args.issue, args.status)
        elif args.command == "arm":
            body = args.body_file.read_text(encoding="utf-8")
            state = service.arm(args.issue, body=body, risk_class=args.risk)
        elif args.command == "start":
            state = service.start(args.issue)
        else:
            raise BoardError(f"unsupported command: {args.command}")
    except (BoardError, OSError, subprocess.SubprocessError) as exc:
        print(f"Board operation refused: {exc}", file=sys.stderr)
        return 2
    print(
        f"#{state.number}: status={state.status or 'not on project'} "
        f"labels={','.join(sorted(state.labels)) or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
