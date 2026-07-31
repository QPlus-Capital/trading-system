"""Contract-driven, fail-closed GitHub Project board operations."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from scripts.quality.classify import CLASSES, REPO_ROOT
from scripts.quality.issue_body import validate_issue_body
from scripts.quality.workflow_contract import WorkflowContract, load_contract

PUBLIC_COMMANDS = ("status", "add", "move", "arm", "start", "withdraw")
_RISK_LABEL = re.compile(r"^risk:(R[0-3])$")
_PROJECT_SCOPE_ERROR = "GitHub token needs the `project` scope; run `gh auth refresh -s project`."
_ISSUE_SNAPSHOT_QUERY = """
query BoardIssueSnapshot(
  $repositoryOwner: String!
  $repositoryName: String!
  $issue: Int!
  $projectOwner: String!
  $projectNumber: Int!
  $includeProject: Boolean!
) {
  repository(owner: $repositoryOwner, name: $repositoryName) {
    issue(number: $issue) {
      body
      url
      labels(first: 100) {
        pageInfo {
          hasNextPage
        }
        nodes {
          name
        }
      }
      projectItems(first: 20, includeArchived: false) {
        pageInfo {
          hasNextPage
        }
        nodes {
          id
          project {
            id
            number
          }
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
        }
      }
    }
  }
  organization(login: $projectOwner) {
    project: projectV2(number: $projectNumber) @include(if: $includeProject) {
      id
      statusField: field(name: "Status") {
        ... on ProjectV2SingleSelectField {
          id
          options {
            id
            name
          }
        }
      }
    }
  }
}
"""


class BoardError(RuntimeError):
    """A board mutation was refused or could not be verified."""


class BoardRateLimitError(BoardError):
    """GitHub API exhaustion with reset time and confirmed progress."""

    def __init__(
        self,
        reset_at: datetime | None,
        applied_steps: Sequence[str] = (),
        safety_note: str | None = None,
    ) -> None:
        self.reset_at = reset_at
        self.applied_steps = tuple(applied_steps)
        self.safety_note = safety_note
        reset = (
            reset_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if reset_at is not None
            else "unavailable"
        )
        steps = ", ".join(self.applied_steps) or "none"
        note = f"; safety state: {safety_note}" if safety_note is not None else ""
        super().__init__(
            f"GitHub API rate limit exhausted; reset at {reset}; applied steps: {steps}{note}"
        )

    def with_applied_steps(self, applied_steps: Sequence[str]) -> BoardRateLimitError:
        """Return the same exhaustion with earlier confirmed command writes attached."""
        return BoardRateLimitError(
            self.reset_at,
            (*applied_steps, *self.applied_steps),
            self.safety_note,
        )

    def with_safety_note(self, safety_note: str) -> BoardRateLimitError:
        """Return the same exhaustion with an explicit unverified safety state."""
        return BoardRateLimitError(self.reset_at, self.applied_steps, safety_note)


@dataclass(frozen=True)
class IssueState:
    """The board and label state needed by ordered workflow operations."""

    number: int
    url: str
    body: str
    labels: frozenset[str]
    status: str | None
    on_project: bool = True


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
        repository_parts = repository.split("/", 1)
        if len(repository_parts) != 2 or not all(repository_parts):
            raise BoardError("repository must use the owner/name form")
        self._repository_owner, self._repository_name = repository_parts
        self._project_cache: _Project | None = None
        self._item_ids: dict[int, str | None] = {}
        self._issue_urls: dict[int, str] = {}

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

    @staticmethod
    def _rate_limit_reset(output: str) -> datetime | None:
        match = re.search(r"(?im)^x-ratelimit-reset:\s*(\d+)\s*$", output)
        if match is None:
            return None
        try:
            return datetime.fromtimestamp(int(match.group(1)), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _response_body(output: str) -> str:
        normalized = output.replace("\r\n", "\n")
        if not normalized.startswith("HTTP/"):
            return output
        _, separator, body = normalized.partition("\n\n")
        if not separator:
            raise BoardError("GitHub API response omitted its JSON body")
        return body

    @classmethod
    def _graphql_error_types(cls, output: str) -> frozenset[str]:
        try:
            payload = json.loads(cls._response_body(output))
        except (BoardError, json.JSONDecodeError):
            return frozenset()
        if not isinstance(payload, dict):
            return frozenset()
        errors = payload.get("errors")
        if not isinstance(errors, list):
            return frozenset()
        return frozenset(
            str(error.get("type"))
            for error in errors
            if isinstance(error, dict) and isinstance(error.get("type"), str)
        )

    @staticmethod
    def _remaining_is_zero(output: str) -> bool:
        return re.search(r"(?im)^x-ratelimit-remaining:\s*0\s*$", output) is not None

    def _rate_limit_status_reset(self, resource: str) -> datetime | None:
        try:
            completed = subprocess.run(
                ["gh", "api", "rate_limit"],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        resources = payload.get("resources")
        if not isinstance(resources, dict):
            return None
        budget = resources.get(resource)
        if not isinstance(budget, dict):
            return None
        reset = budget.get("reset")
        if type(reset) is not int:
            return None
        try:
            return datetime.fromtimestamp(reset, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _safe_error_detail(stdout: str, stderr: str) -> str | None:
        detail = " ".join(f"{stdout}\n{stderr}".split())
        if not detail:
            return None
        if re.search(
            r"https?://|(?:token|credential|secret)|\b\d{6,10}\b",
            detail,
            re.IGNORECASE,
        ):
            return None
        return detail[:500]

    def _run(self, args: Sequence[str], *, include_headers: bool = False) -> str:
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
            raw = f"{completed.stdout}\n{completed.stderr}"
            combined = raw.casefold()
            error_types = self._graphql_error_types(completed.stdout) | self._graphql_error_types(
                completed.stderr
            )
            structured_graphql = "RATE_LIMITED" in error_types
            structured_header = self._remaining_is_zero(raw)
            english_fallback = "rate limit" in combined
            if structured_graphql or structured_header or english_fallback:
                resource = (
                    "graphql"
                    if structured_graphql or tuple(args[:2]) == ("api", "graphql")
                    else "core"
                )
                reset_at = self._rate_limit_reset(raw)
                if reset_at is None:
                    reset_at = self._rate_limit_status_reset(resource)
                raise BoardRateLimitError(reset_at)
            if "project" in combined and (
                "scope" in combined or "resource not accessible" in combined or "404" in combined
            ):
                raise BoardError(_PROJECT_SCOPE_ERROR)
            detail = self._safe_error_detail(completed.stdout, completed.stderr)
            if detail is None:
                raise BoardError("GitHub board operation failed; inspect the local gh error.")
            raise BoardError(f"GitHub board operation failed: {detail}")
        if include_headers:
            return self._response_body(completed.stdout)
        return completed.stdout

    def _json(
        self,
        args: Sequence[str],
        name: str,
        *,
        include_headers: bool = False,
    ) -> dict[str, object]:
        try:
            return _object(
                json.loads(self._run(args, include_headers=include_headers)),
                name,
            )
        except json.JSONDecodeError as exc:
            raise BoardError(f"{name} returned invalid JSON") from exc

    def _graphql(self, query: str, variables: Mapping[str, str], name: str) -> dict[str, object]:
        args: list[str] = ["api", "graphql", "--include", "-f", f"query={query}"]
        for key, value in variables.items():
            args.extend(("-F", f"{key}={value}"))
        payload = self._json(args, name, include_headers=True)
        return _object(payload.get("data"), f"{name} data")

    def _parse_project(self, data: Mapping[str, object]) -> _Project:
        raw_organization = data.get("organization")
        if not isinstance(raw_organization, dict):
            raise BoardError(
                "--owner must name a GitHub organization; user-owned projects are unsupported"
            )
        organization = cast(dict[str, object], raw_organization)
        project = _object(organization.get("project"), "GitHub project")
        status_field = _object(project.get("statusField"), "project Status field")
        options: dict[str, str] = {}
        for raw in _array(status_field.get("options"), "project Status options"):
            option = _object(raw, "Status option")
            name = _text(option, "name")
            if name in options:
                raise BoardError(f"project has duplicate Status option: {name}")
            options[name] = _text(option, "id")
        return _Project(
            project_id=_text(project, "id"),
            status_field_id=_text(status_field, "id"),
            option_ids=options,
        )

    def _project(self) -> _Project:
        if self._project_cache is None:
            raise BoardError("issue state must load project metadata before board mutation")
        return self._project_cache

    def _issue_snapshot(self, issue: int) -> IssueState:
        include_project = self._project_cache is None
        data = self._graphql(
            _ISSUE_SNAPSHOT_QUERY,
            {
                "repositoryOwner": self._repository_owner,
                "repositoryName": self._repository_name,
                "issue": str(issue),
                "projectOwner": self.owner,
                "projectNumber": str(self.project_number),
                "includeProject": str(include_project).lower(),
            },
            "GitHub issue board snapshot",
        )
        if include_project:
            self._project_cache = self._parse_project(data)
        project = self._project_cache
        if project is None:
            raise BoardError("GitHub issue snapshot omitted project metadata")

        repository = _object(data.get("repository"), "GitHub repository")
        raw_issue = repository.get("issue")
        if raw_issue is None:
            raise BoardError(f"issue #{issue} does not exist in {self.repository}")
        issue_data = _object(raw_issue, "GitHub issue")
        labels_data = _object(issue_data.get("labels"), "issue labels")
        label_page_info = _object(labels_data.get("pageInfo"), "issue label pagination")
        labels_have_next_page = label_page_info.get("hasNextPage")
        if not isinstance(labels_have_next_page, bool):
            raise BoardError("GitHub response omitted issue label pagination state")
        if labels_have_next_page:
            raise BoardError(
                f"issue #{issue} label connection exceeds one bounded query; "
                "permit state is unverifiable"
            )
        labels = frozenset(
            _text(_object(item, "issue label"), "name")
            for item in _array(labels_data.get("nodes"), "issue label nodes")
        )
        project_items = _object(issue_data.get("projectItems"), "issue project items")
        page_info = _object(project_items.get("pageInfo"), "issue project pagination")
        has_next_page = page_info.get("hasNextPage")
        if not isinstance(has_next_page, bool):
            raise BoardError("GitHub response omitted issue project pagination state")
        matching_items: list[dict[str, object]] = []
        for raw_item in _array(project_items.get("nodes"), "issue project item nodes"):
            item = _object(raw_item, "issue project item")
            item_project = _object(item.get("project"), "issue project item project")
            if item_project.get("id") == project.project_id:
                matching_items.append(item)
        if len(matching_items) > 1:
            raise BoardError(
                f"issue #{issue} appears more than once on project {self.project_number}"
            )
        if not matching_items and has_next_page:
            raise BoardError(
                f"issue #{issue} has more project memberships than one bounded query can inspect"
            )

        item_id: str | None = None
        status: str | None = None
        if matching_items:
            item = matching_items[0]
            item_id = _text(item, "id")
            raw_status = item.get("status")
            if raw_status is not None:
                status = _text(_object(raw_status, "project item status"), "name")
        self._item_ids[issue] = item_id
        url = _text(issue_data, "url")
        self._issue_urls[issue] = url
        return IssueState(
            number=issue,
            url=url,
            body=str(issue_data.get("body", "")),
            labels=labels,
            status=status,
            on_project=bool(matching_items),
        )

    def status_names(self) -> frozenset[str]:
        return frozenset(self._project().option_ids)

    def issue_state(self, issue: int) -> IssueState:
        return self._issue_snapshot(issue)

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
        if issue not in self._item_ids:
            self.issue_state(issue)
        item_id = self._item_ids.get(issue)
        if item_id is None:
            raise BoardError(f"issue #{issue} is not on project {self.project_number}")
        self._run(
            (
                "project",
                "item-edit",
                "--id",
                item_id,
                "--project-id",
                project.project_id,
                "--field-id",
                project.status_field_id,
                "--single-select-option-id",
                option_id,
            )
        )

    def add_issue(self, issue: int) -> None:
        if issue not in self._item_ids:
            self.issue_state(issue)
        if self._item_ids.get(issue) is not None:
            return
        url = self._issue_urls.get(issue)
        if url is None:
            raise BoardError(f"issue #{issue} has no verified URL")
        self._run(
            (
                "project",
                "item-add",
                str(self.project_number),
                "--owner",
                self.owner,
                "--url",
                url,
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

    def _state_and_verify(self, issue: int) -> IssueState:
        state = self.gateway.issue_state(issue)
        self._verify_status_options()
        return state

    @staticmethod
    def _apply(
        applied_steps: list[str],
        step: str,
        action: Callable[[], None],
    ) -> None:
        action()
        applied_steps.append(step)

    @staticmethod
    def _progress_error(
        error: BoardRateLimitError,
        applied_steps: Sequence[str],
    ) -> BoardRateLimitError:
        return error.with_applied_steps(applied_steps)

    def status(self, issue: int) -> IssueState:
        try:
            return self._state_and_verify(issue)
        except BoardRateLimitError as exc:
            raise self._progress_error(exc, ()) from exc

    def add(self, issue: int) -> IssueState:
        applied_steps: list[str] = []
        try:
            initial = self._state_and_verify(issue)
            if not initial.on_project:
                self._apply(
                    applied_steps,
                    "add issue to project",
                    lambda: self.gateway.add_issue(issue),
                )
            state = self.gateway.issue_state(issue)
            if not state.on_project:
                raise BoardError(f"issue #{issue} was not added to the project")
            return state
        except BoardRateLimitError as exc:
            raise self._progress_error(exc, applied_steps) from exc

    def move(self, issue: int, target: str) -> IssueState:
        applied_steps: list[str] = []
        try:
            state = self._state_and_verify(issue)
            if target == "Done":
                raise BoardError("Done is set only by project automation after merge")
            if not state.on_project:
                raise BoardError("move refused: " + self._observed_status(state))
            allowed = {
                transition.target
                for transition in self.contract.transitions
                if transition.source == state.status and transition.target != "Done"
            }
            if target not in allowed:
                raise BoardError(f"contract does not allow {state.status!r} -> {target!r}")
            if state.status == "Ready to Implement" and target == "Implementing":
                raise BoardError(
                    "contract edge 'Ready to Implement' -> 'Implementing' is reserved for `start`"
                )
            had_permit = "approved" in state.labels
            withdrawn = state
            if had_permit:
                withdrawn = self._remove_approved_and_verify(issue, state, applied_steps)
            if withdrawn.status != state.status:
                raise BoardError(
                    "status changed while withdrawing the permit: "
                    + self._observed_status(withdrawn)
                )
            step = f"move the card to {target}"
            try:
                self._apply(
                    applied_steps,
                    step,
                    lambda: self.gateway.set_status(issue, target),
                )
            except BoardRateLimitError:
                raise
            except BoardError as exc:
                if had_permit:
                    raise BoardError(
                        "status update failed after the permit was already withdrawn: "
                        "observed approved=absent"
                    ) from exc
                raise
            result = self.gateway.issue_state(issue)
            if result.status != target:
                raise BoardError(f"status update did not produce {target!r}")
            if "approved" in result.labels:
                raise BoardError("status update retained a stale permit: observed approved=present")
            return result
        except BoardRateLimitError as exc:
            raise self._progress_error(exc, applied_steps) from exc

    def withdraw(self, issue: int) -> IssueState:
        """Remove an existing build permit without changing board status."""

        applied_steps: list[str] = []
        try:
            state = self._state_and_verify(issue)
            if not state.on_project:
                raise BoardError("withdraw refused: observed project status=absent")
            result = state
            if "approved" in state.labels:
                result = self._remove_approved_and_verify(issue, state, applied_steps)
            if result.status != state.status:
                raise BoardError(
                    "status changed while withdrawing the permit: " + self._observed_status(result)
                )
            return result
        except BoardRateLimitError as exc:
            raise self._progress_error(exc, applied_steps) from exc

    def arm(self, issue: int, *, body: str, risk_class: str) -> IssueState:
        """Apply the contract approval steps and write `approved` last."""

        applied_steps: list[str] = []
        try:
            if risk_class not in CLASSES:
                raise BoardError(f"unknown risk class: {risk_class}")
            initial = self._state_and_verify(issue)
            failures: list[str] = []
            if initial.status != "Ready to Implement":
                failures.append(self._observed_status(initial))
            if "approved" in initial.labels:
                failures.append("observed approved=present")
            requested_risk = f"risk:{risk_class}"
            existing_risks = {label for label in initial.labels if _RISK_LABEL.fullmatch(label)}
            if existing_risks - {requested_risk}:
                failures.append(
                    "observed conflicting risk labels="
                    + repr(sorted(existing_risks - {requested_risk}))
                )
            if failures:
                raise BoardError("arm requirements not met: " + "; ".join(failures))
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
                    raise BoardError(
                        f"no board operation implements approval action {step.action!r}"
                    )
                self._apply(applied_steps, step.action, action)
            result = self.gateway.issue_state(issue)
            if "approved" not in result.labels:
                raise BoardError("approval operation completed without the approved label")
            return result
        except BoardRateLimitError as exc:
            raise self._progress_error(exc, applied_steps) from exc

    def _write_approved(self, issue: int, risk_class: str) -> None:
        state = self.gateway.issue_state(issue)
        failures: list[str] = []
        if state.status != "Ready to Implement":
            failures.append(self._observed_status(state))
        if f"risk:{risk_class}" not in state.labels:
            risks = sorted(label for label in state.labels if _RISK_LABEL.fullmatch(label))
            failures.append(f"observed risk labels={risks!r}")
        if failures:
            raise BoardError("approved requirements not met: " + "; ".join(failures))
        self.gateway.add_label(issue, "approved")

    @staticmethod
    def _observed_status(state: IssueState) -> str:
        if not state.on_project:
            return "observed project status=absent"
        if state.status is None:
            return "observed project status=unset"
        return f"observed status={state.status!r}"

    def _remove_approved_and_verify(
        self,
        issue: int,
        state: IssueState,
        applied_steps: list[str],
    ) -> IssueState:
        if "approved" not in state.labels:
            return state
        self._apply(
            applied_steps,
            "remove approved",
            lambda: self.gateway.remove_label(issue, "approved"),
        )
        result = self.gateway.issue_state(issue)
        if "approved" in result.labels:
            raise BoardError("permit removal did not take effect: observed approved=present")
        return result

    def start(self, issue: int) -> IssueState:
        """Consume the Start guard: status first, permit removal second."""

        applied_steps: list[str] = []
        permit_guard_passed = False
        try:
            state = self._state_and_verify(issue)
            guards = {guard.name: guard for guard in self.contract.builder_guards}
            if "Start" not in guards:
                raise BoardError("workflow contract has no Start builder guard")
            risk_labels = {label for label in state.labels if _RISK_LABEL.fullmatch(label)}
            failures: list[str] = []
            if state.status != "Ready to Implement":
                failures.append(self._observed_status(state))
            if "approved" not in state.labels:
                failures.append("observed approved=absent")
            if len(risk_labels) != 1:
                failures.append(f"observed risk labels={sorted(risk_labels)!r}")
            if failures:
                raise BoardError("Start requirements not met: " + "; ".join(failures))
            permit_guard_passed = True
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
            move_step = f"move the card to {target}"
            self._apply(
                applied_steps,
                move_step,
                lambda: self.gateway.set_status(issue, target),
            )
            moved = self.gateway.issue_state(issue)
            if moved.status != target:
                raise BoardError(f"build-start status update did not produce {target!r}")
            result = moved
            if "approved" in moved.labels:
                result = self._remove_approved_and_verify(issue, moved, applied_steps)
            return result
        except BoardRateLimitError as exc:
            progress = self._progress_error(exc, applied_steps)
            if permit_guard_passed and "remove approved" not in progress.applied_steps:
                progress = progress.with_safety_note("approved removal is unconfirmed")
            raise progress from exc


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
        elif args.command == "withdraw":
            state = service.withdraw(args.issue)
        else:
            raise BoardError(f"unsupported command: {args.command}")
    except BoardRateLimitError as exc:
        print(f"Board rate limit exhausted: {exc}", file=sys.stderr)
        return 3
    except (BoardError, OSError, subprocess.SubprocessError) as exc:
        print(f"Board operation refused: {exc}", file=sys.stderr)
        return 2
    displayed_status = (
        state.status
        if state.status is not None
        else ("unset" if state.on_project else "not on project")
    )
    print(
        f"#{state.number}: status={displayed_status} labels={','.join(sorted(state.labels)) or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
